import io
import json
import base64
from typing import Dict, Any, Type, List
from pydantic import BaseModel

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import fitz
except ImportError:
    fitz = None

try:
    import pypdf
except ImportError:
    pypdf = None

from app.core.config import settings
from app.integrations.ai.base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.provider_name = "openai"
        self._init_client()

    def _init_client(self):
        self.client = None
        api_key = (settings.OPENAI_API_KEY or "").strip()
        if api_key and OpenAI:
            self.client = OpenAI(api_key=api_key)
        self.model_name = settings.OPENAI_MODEL or "gpt-4o"

    def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """
        Extracts structured, layout-aware text from PDF bytes using PyMuPDF (fitz)
        preserving spatial boundaries, visual reading order, and block separation.
        Falls back to pypdf if PyMuPDF is unavailable.
        """
        if fitz:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                pages_output = []
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Extract text blocks: (x0, y0, x1, y1, text, block_no, block_type)
                    # block_type == 0 indicates text block
                    blocks = page.get_text("blocks")
                    text_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]
                    
                    # Sort blocks in visual reading order (top-to-bottom quantized, left-to-right)
                    text_blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))
                    
                    page_lines = []
                    for b in text_blocks:
                        cleaned = b[4].strip()
                        if cleaned:
                            page_lines.append(cleaned)
                    
                    page_text = "\n\n".join(page_lines)
                    pages_output.append(f"--- PAGE {page_num + 1} ---\n{page_text}")
                return "\n\n".join(pages_output)
            except Exception as e:
                pass

        if pypdf:
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_text = []
                for idx, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    pages_text.append(f"--- PAGE {idx + 1} ---\n{text}")
                return "\n\n".join(pages_text)
            except Exception as e:
                return f"[PDF Text Extraction Failed: {e}]"

        return ""

    def extract_structured_data(
        self,
        file_bytes: bytes,
        mime_type: str,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Dict[str, Any]:
        if not self.client:
            self._init_client()
        if not self.client:
            raise ValueError(
                "OPENAI_API_KEY is not set in backend/.env. Please paste your OpenAI API key into backend/.env (OPENAI_API_KEY=sk-...) to perform extraction."
            )

        schema_json = schema.model_json_schema()
        system_prompt = (
            "You are an expert AI document analyzer for construction and cabinet manufacturing documents.\n"
            "Your job is to extract detailed, precise structured data from document specifications, purchase orders, and acknowledgements.\n"
            "You MUST respond ONLY with valid JSON strictly adhering to the specified schema."
        )

        if mime_type.startswith("image/"):
            # Direct image input via vision
            base64_img = base64.b64encode(file_bytes).decode("utf-8")
            user_content = [
                {
                    "type": "text",
                    "text": f"{prompt}\n\nYou MUST return the response strictly matching this JSON schema:\n{json.dumps(schema_json)}",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_img}",
                        "detail": "high",
                    },
                }
            ]
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)

        elif mime_type == "application/pdf":
            import re
            # Extract PDF text representation with layout awareness
            pdf_text = self._extract_text_from_pdf(file_bytes)
            actual_text = re.sub(r"--- PAGE \d+ ---", "", pdf_text).strip()

            if len(actual_text) >= 30:
                # Text-based / structured vector PDF
                user_content = [
                    {
                        "type": "text",
                        "text": (
                            f"{prompt}\n\n"
                            f"--- DOCUMENT CONTENT (PDF TEXT WITH SPATIAL LAYOUT) ---\n"
                            f"{pdf_text}\n\n"
                            f"You MUST return the response strictly matching this JSON schema:\n"
                            f"{json.dumps(schema_json)}"
                        ),
                    }
                ]
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                content = response.choices[0].message.content or "{}"
                return json.loads(content)
            else:
                # Scanned / Image PDF (no embedded text) -> Render pages as images and process via Vision
                if not fitz:
                    raise ValueError("PyMuPDF (fitz) is required to process scanned image PDFs.")

                doc_fitz = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(doc_fitz)
                merged_items: List[Dict[str, Any]] = []

                # Process in batches of up to 6 pages per call to ensure high extraction fidelity
                BATCH_SIZE = 6
                for batch_start in range(0, total_pages, BATCH_SIZE):
                    batch_end = min(batch_start + BATCH_SIZE, total_pages)
                    batch_content = [
                        {
                            "type": "text",
                            "text": (
                                f"{prompt}\n\n"
                                f"Analyzing scanned document pages {batch_start + 1} to {batch_end} of {total_pages}.\n"
                                f"You MUST return the response strictly matching this JSON schema:\n"
                                f"{json.dumps(schema_json)}"
                            )
                        }
                    ]
                    for pno in range(batch_start, batch_end):
                        page = doc_fitz[pno]
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("jpeg")
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        batch_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high"
                            }
                        })

                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": batch_content},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.1,
                    )
                    content = response.choices[0].message.content or "{}"
                    try:
                        parsed_batch = json.loads(content)
                        if isinstance(parsed_batch, dict):
                            items = parsed_batch.get("items", [])
                            merged_items.extend(items)
                    except Exception:
                        pass

                return {"items": merged_items}

        else:
            # Plain text, CSV, or other formats
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
            except Exception:
                text_content = str(file_bytes)
            user_content = [
                {
                    "type": "text",
                    "text": (
                        f"{prompt}\n\n"
                        f"--- DOCUMENT CONTENT ---\n"
                        f"{text_content}\n\n"
                        f"You MUST return the response strictly matching this JSON schema:\n"
                        f"{json.dumps(schema_json)}"
                    ),
                }
            ]
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)

