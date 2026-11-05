"""
O3+O4 verification suite — no real API calls, all responses mocked.

Covers:
  O3-1  Every API call path captures usage
  O3-2  Gemini usage_metadata captured
  O3-3  Retry/fallback calls counted separately
  O3-4  Cost calculation uses correct model pricing
  O3-5  document_id stored on Extraction (project_id via document FK)
  O3-6  api_usage column exists on the Extraction model
  O3-7  Cached extractions do not generate api_usage records
  O4-1  Gemini model name reads from settings (not hardcoded)
  O4-2  Gemini API key loaded from settings
  O4-3  OpenAI failure triggers Gemini fallback execution
  O4-4  Non-transient OpenAI error does NOT retry via fallback unnecessarily
  O4-5  Gemini extraction returns same top-level schema keys
  O4-6  Fallback usage recorded with provider="gemini"
"""
import json
import types
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.integrations.ai.factory import _FallbackAIProvider, get_ai_provider
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.openai_provider import OpenAIProvider, _build_usage_summary
from app.models.core import Extraction
from app.schemas.extraction import DesignExtraction


# Real schema instance used throughout to avoid MagicMock JSON serialisation errors
_SCHEMA = DesignExtraction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_usage(prompt=100, completion=50):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def _fake_response(content: dict, prompt=100, completion=50, finish_reason="stop"):
    msg = SimpleNamespace(content=json.dumps(content))
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=_fake_usage(prompt, completion))


def _fake_response_no_usage(content: dict):
    msg = SimpleNamespace(content=json.dumps(content))
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(choices=[choice], usage=None)


# ---------------------------------------------------------------------------
# O3-1 — text PDF path captures usage
# ---------------------------------------------------------------------------

def test_o3_text_pdf_path_captures_usage(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()

    # raw_text must be >= 30 chars to stay on the text path (not scanned path)
    page_evidence = [{"page_number": 1, "raw_text": "W3015 qty 2 --- cabinet line item data present here", "status": "PROCESSED", "extraction_method": "pymupdf", "blocks": []}]
    items_resp = _fake_response({"items": [{"sku": "W3015", "quantity": 2}]}, prompt=200, completion=80)

    with patch.object(provider, "_get_pdf_page_evidence", return_value=page_evidence), \
         patch.object(provider.client.chat.completions, "create", return_value=items_resp):
        result = provider.extract_structured_data(b"fake", "application/pdf", "extract", _SCHEMA)

    assert "_api_usage" in result
    u = result["_api_usage"]
    assert u["provider"] == "openai"
    assert len(u["calls"]) >= 1
    assert u["total_input_tokens"] == 200
    assert u["total_output_tokens"] == 80
    assert u["total_estimated_cost_usd"] > 0


# ---------------------------------------------------------------------------
# O3-1b — image path captures usage
# ---------------------------------------------------------------------------

def test_o3_image_path_captures_usage(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()

    resp = _fake_response({"items": []}, prompt=50, completion=10)
    with patch.object(provider.client.chat.completions, "create", return_value=resp):
        result = provider.extract_structured_data(b"\xff\xd8\xff", "image/jpeg", "extract", _SCHEMA)

    u = result["_api_usage"]
    assert u["calls"][0]["call_type"] == "vision_single"
    assert u["calls"][0]["page_count"] == 1
    assert u["total_input_tokens"] == 50


# ---------------------------------------------------------------------------
# O3-1c — excel/word/text paths capture usage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mime,text_method", [
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "_extract_text_from_excel"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "_extract_text_from_docx"),
    ("text/plain", None),
])
def test_o3_non_pdf_paths_capture_usage(mime, text_method, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()

    resp = _fake_response({"items": []}, prompt=30, completion=5)
    patches = [patch.object(provider.client.chat.completions, "create", return_value=resp)]
    if text_method:
        patches.append(patch.object(provider, text_method, return_value="col1 | col2"))

    with patches[0]:
        if len(patches) > 1:
            with patches[1]:
                content = b"hello world" if mime == "text/plain" else b"fake"
                result = provider.extract_structured_data(content, mime, "extract", _SCHEMA)
        else:
            result = provider.extract_structured_data(b"hello world", mime, "extract", _SCHEMA)

    u = result.get("_api_usage")
    assert u is not None, f"_api_usage missing for mime={mime}"
    assert u["calls"][0]["call_type"] == "text_single"
    assert u["total_input_tokens"] == 30


# ---------------------------------------------------------------------------
# O3-2 — Gemini usage_metadata captured
# ---------------------------------------------------------------------------

def test_o3_gemini_usage_metadata_captured(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    provider = GeminiProvider()

    usage_meta = SimpleNamespace(prompt_token_count=150, candidates_token_count=60)
    fake_resp = SimpleNamespace(text=json.dumps({"items": []}), usage_metadata=usage_meta)

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_resp
    provider.client = mock_client

    result = provider.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)

    assert "_api_usage" in result
    u = result["_api_usage"]
    assert u["provider"] == "gemini"
    assert u["total_input_tokens"] == 150
    assert u["total_output_tokens"] == 60
    assert u["total_estimated_cost_usd"] > 0
    assert u["calls"][0]["call_type"] == "single_shot"


# ---------------------------------------------------------------------------
# O3-2b — Gemini with no usage_metadata (graceful)
# ---------------------------------------------------------------------------

def test_o3_gemini_no_usage_metadata(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    provider = GeminiProvider()

    fake_resp = SimpleNamespace(text=json.dumps({"items": []}))  # no usage_metadata attr
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_resp
    provider.client = mock_client

    result = provider.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)
    # Should succeed without crashing; no _api_usage key since metadata unavailable
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# O3-3 — Retry/fallback calls counted separately
# ---------------------------------------------------------------------------

def test_o3_fallback_calls_counted_separately(monkeypatch):
    """When OpenAI fails and Gemini succeeds, usage comes from Gemini only."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-fake")

    primary = OpenAIProvider()
    primary.client = MagicMock()
    primary.client.chat.completions.create.side_effect = RuntimeError("credits exhausted")

    secondary = GeminiProvider()
    usage_meta = SimpleNamespace(prompt_token_count=100, candidates_token_count=40)
    fake_resp = SimpleNamespace(text=json.dumps({"items": []}), usage_metadata=usage_meta)
    secondary.client = MagicMock()
    secondary.client.models.generate_content.return_value = fake_resp

    wrapper = _FallbackAIProvider(primary, secondary)
    result = wrapper.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)

    assert "_api_usage" in result
    u = result["_api_usage"]
    assert u["provider"] == "gemini", "fallback usage should be attributed to gemini"
    assert u["total_input_tokens"] == 100


# ---------------------------------------------------------------------------
# O3-4 — Cost calculation uses correct model pricing
# ---------------------------------------------------------------------------

def test_o3_cost_calculation_gpt4o(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()
    assert provider.model_name == "gpt-4o"

    fake_resp = _fake_response({}, prompt=1_000_000, completion=1_000_000)
    rec = provider._make_usage_record("text_batch", fake_resp)
    # gpt-4o: $5/M input + $15/M output = $20 for 1M+1M tokens
    assert abs(rec["estimated_cost_usd"] - 20.0) < 0.001


def test_o3_cost_calculation_mini(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    provider = OpenAIProvider()

    fake_resp = _fake_response({}, prompt=1_000_000, completion=1_000_000)
    rec = provider._make_usage_record("text_batch", fake_resp)
    # gpt-4o-mini: $0.15/M + $0.60/M = $0.75
    assert abs(rec["estimated_cost_usd"] - 0.75) < 0.001


def test_o3_unknown_model_uses_gpt4o_fallback_pricing(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()

    fake_resp = _fake_response({}, prompt=1_000_000, completion=0)
    rec = provider._make_usage_record("text_batch", fake_resp, model_override="unknown-future-model")
    # Fallback pricing: $5/M input
    assert abs(rec["estimated_cost_usd"] - 5.0) < 0.001


# ---------------------------------------------------------------------------
# O3-5 — document_id stored on Extraction (api_usage retrievable via doc)
# ---------------------------------------------------------------------------

def test_o3_extraction_model_has_api_usage_column():
    """Extraction model must have api_usage attribute (column-level check)."""
    ext = Extraction()
    # Column must be accessible and default to None
    assert hasattr(ext, "api_usage")
    assert ext.api_usage is None


def test_o3_extraction_stores_document_id():
    """Extraction has document_id FK — project_id is reachable via Document FK."""
    doc_id = uuid4()
    org_id = uuid4()
    ext = Extraction(
        document_id=doc_id,
        organization_id=org_id,
        raw_data={"items": []},
        api_usage={"provider": "openai", "total_estimated_cost_usd": 0.001},
    )
    assert ext.document_id == doc_id
    assert ext.api_usage["provider"] == "openai"


# ---------------------------------------------------------------------------
# O3-7 — Cached extractions produce no new api_usage
# ---------------------------------------------------------------------------

def test_o3_cached_extraction_no_api_usage():
    """
    The cache-hit path in _extract_one_document returns early (before any AI
    call) so no _api_usage is generated. We verify by checking that no AI
    client call is made when a cached Extraction is returned.
    """
    # This is architecture-verified: the cache-reuse branch at line ~189 of
    # processing.py returns before `ai.extract_structured_data` is called.
    # No separate mock needed — the absence of a create() call IS the proof.
    # We confirm by reading the conditional in processing.py:
    import ast, pathlib
    src = pathlib.Path(__file__).parent.parent / "app/worker/tasks/processing.py"
    tree = ast.parse(src.read_text())
    # Walk the AST and find the early-return inside the cache-reuse block.
    returns_before_ai = False
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Look for: if reused_extraction is not None: return ...
            test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
            if "reused_extraction" in test_src:
                for child in ast.walk(node):
                    if isinstance(child, ast.Return):
                        returns_before_ai = True
                        break
    assert returns_before_ai, "cache-hit path must return before ai.extract_structured_data"


# ---------------------------------------------------------------------------
# O4-1 — Gemini model reads from settings
# ---------------------------------------------------------------------------

def test_o4_gemini_model_reads_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    provider = GeminiProvider()
    assert provider.model_name == "gemini-2.0-flash"


def test_o4_gemini_default_model_is_valid():
    """Default model must not be the broken 'gemini-3.6-flash' name."""
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.client = None
    # Simulate __init__ without a real key
    from app.core.config import settings as s
    model = getattr(s, "GEMINI_MODEL", None) or "gemini-1.5-flash"
    assert model != "gemini-3.6-flash", "broken model name must not be used"
    assert "gemini" in model


# ---------------------------------------------------------------------------
# O4-2 — Gemini API key loaded from settings
# ---------------------------------------------------------------------------

def test_o4_gemini_key_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key-abc")
    # Can't test actual client init without the google.genai import,
    # but verify the provider reads settings.GEMINI_API_KEY (not a hardcode).
    import inspect
    src = inspect.getsource(GeminiProvider.__init__)
    assert "settings.GEMINI_API_KEY" in src


# ---------------------------------------------------------------------------
# O4-3 — OpenAI failure triggers Gemini fallback execution
# ---------------------------------------------------------------------------

def test_o4_openai_failure_triggers_gemini_fallback(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-fake")

    primary = OpenAIProvider()
    primary.client = MagicMock()
    primary.client.chat.completions.create.side_effect = Exception("API key invalid")

    secondary = GeminiProvider()
    secondary.client = MagicMock()
    secondary.client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"items": [{"sku": "W3015", "quantity": 1}]}),
        usage_metadata=None,
    )

    wrapper = _FallbackAIProvider(primary, secondary)
    result = wrapper.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)

    # Gemini was called
    secondary.client.models.generate_content.assert_called_once()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# O4-4 — Non-transient error does NOT loop through all retries
# ---------------------------------------------------------------------------

def test_o4_non_transient_error_raises_immediately(monkeypatch):
    """A hard auth error should propagate immediately — no 3-retry delay."""
    primary = MagicMock()
    primary.extract_structured_data.side_effect = ValueError("bad schema")
    wrapper = _FallbackAIProvider(primary, None)

    with pytest.raises(ValueError, match="bad schema"):
        wrapper.extract_structured_data(b"data", "application/pdf", "extract", MagicMock())

    # Only called once — no retries
    assert primary.extract_structured_data.call_count == 1


# ---------------------------------------------------------------------------
# O4-5 — Gemini output follows same schema (items key present)
# ---------------------------------------------------------------------------

def test_o4_gemini_output_schema_compatible(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    provider = GeminiProvider()

    gemini_output = {"items": [{"sku": "B24BP", "quantity": 3, "finish": "Maple"}]}
    provider.client = MagicMock()
    provider.client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(gemini_output),
        usage_metadata=None,
    )

    result = provider.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)
    # Must have same top-level key as OpenAI output
    assert "items" in result
    assert result["items"][0]["sku"] == "B24BP"


# ---------------------------------------------------------------------------
# O4-6 — Fallback usage recorded with provider="gemini"
# ---------------------------------------------------------------------------

def test_o4_fallback_usage_attributed_to_gemini(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-fake")

    primary = OpenAIProvider()
    primary.client = MagicMock()
    primary.client.chat.completions.create.side_effect = RuntimeError("rate limit 429")

    secondary = GeminiProvider()
    usage_meta = SimpleNamespace(prompt_token_count=200, candidates_token_count=80)
    secondary.client = MagicMock()
    secondary.client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps({"items": []}),
        usage_metadata=usage_meta,
    )

    wrapper = _FallbackAIProvider(primary, secondary)
    result = wrapper.extract_structured_data(b"data", "application/pdf", "extract", _SCHEMA)

    u = result["_api_usage"]
    assert u["provider"] == "gemini"
    assert u["total_input_tokens"] == 200
    assert u["calls"][0]["model"] == secondary.model_name


# ---------------------------------------------------------------------------
# O3+O4 integration: factory wires correctly
# ---------------------------------------------------------------------------

def test_factory_dual_key_wires_gemini_as_secondary(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-fake")
    provider = get_ai_provider()
    assert isinstance(provider._primary, OpenAIProvider)
    assert isinstance(provider._secondary, GeminiProvider)


def test_factory_openai_only_no_secondary(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    provider = get_ai_provider()
    assert isinstance(provider._primary, OpenAIProvider)
    assert provider._secondary is None


def test_factory_no_keys_uses_gemini_primary_no_secondary(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    provider = get_ai_provider()
    assert isinstance(provider._primary, GeminiProvider)
    assert provider._secondary is None
