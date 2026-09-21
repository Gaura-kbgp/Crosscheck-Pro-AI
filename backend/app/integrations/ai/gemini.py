import json
try:
    from google import genai
except ImportError:
    genai = None
from typing import Dict, Any, Type
from pydantic import BaseModel
from app.core.config import settings
from app.integrations.ai.base import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self):
        self.provider_name = "gemini"
        self.client = None
        if settings.GEMINI_API_KEY and genai:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-3.6-flash"
        
    def extract_structured_data(
        self, 
        file_bytes: bytes, 
        mime_type: str, 
        prompt: str, 
        schema: Type[BaseModel]
    ) -> Dict[str, Any]:
        if not self.client:
            # Fallback for testing when no API key
            return {}

        # Build the schema-enhanced prompt
        schema_json = schema.model_json_schema()
        full_prompt = f"{prompt}\n\nYou MUST return the response strictly matching this JSON schema:\n{json.dumps(schema_json)}"
        
        # Upload the file bytes as inline data
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
            return parsed_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode Gemini JSON response: {e}")
