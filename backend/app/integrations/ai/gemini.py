import json
try:
    from google import genai
except ImportError:
    genai = None
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel
from app.core.config import settings
from app.integrations.ai.base import AIProvider

class GeminiProvider(AIProvider):
    # Gemini 1.5 Flash pricing per 1M tokens (Nov 2025)
    _PRICING = {"input": 0.075, "output": 0.30}

    def __init__(self):
        self.provider_name = "gemini"
        self.client = None
        if settings.GEMINI_API_KEY and genai:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = getattr(settings, "GEMINI_MODEL", None) or "gemini-2.5-flash"

    def extract_structured_data(
        self,
        file_bytes: bytes,
        mime_type: str,
        prompt: str,
        schema: Type[BaseModel],
        doc_type: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not self.client:
            return {}

        schema_json = schema.model_json_schema()
        full_prompt = f"{prompt}\n\nYou MUST return the response strictly matching this JSON schema:\n{json.dumps(schema_json)}"

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                genai.types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                full_prompt
            ],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        try:
            parsed_data = json.loads(response.text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode Gemini JSON response: {e}")

        # Capture usage metadata if the SDK provides it
        um = getattr(response, "usage_metadata", None)
        if um:
            in_tok = getattr(um, "prompt_token_count", 0) or 0
            out_tok = getattr(um, "candidates_token_count", 0) or 0
            cost = (in_tok * self._PRICING["input"] + out_tok * self._PRICING["output"]) / 1_000_000
            parsed_data["_api_usage"] = {
                "provider": "gemini",
                "calls": [{"call_type": "single_shot", "model": self.model_name,
                            "input_tokens": in_tok, "output_tokens": out_tok,
                            "estimated_cost_usd": round(cost, 6)}],
                "total_input_tokens": in_tok,
                "total_output_tokens": out_tok,
                "total_estimated_cost_usd": round(cost, 6),
            }

        return parsed_data
