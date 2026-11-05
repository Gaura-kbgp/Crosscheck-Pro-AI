"""
O2 — gpt-4o-mini for ORDER/ACK text batches.

Verifies:
- When OPENAI_USE_MINI_FOR_TEXT=True and doc_type is ORDER or ACKNOWLEDGEMENT,
  the mini model is used in _extract_text_pages.
- DESIGN always uses the primary model regardless of the flag.
- When the flag is False (default), primary model is always used.
- mini model name flows through to usage records (correct cost calculation).
- Bisect retry inherits the same model override.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.integrations.ai.openai_provider import OpenAIProvider
from app.schemas.extraction import DesignExtraction, OrderExtraction


def _make_provider(monkeypatch, use_mini=True):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o")
    monkeypatch.setattr(settings, "OPENAI_MINI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(settings, "OPENAI_USE_MINI_FOR_TEXT", use_mini)
    return OpenAIProvider()


def _resp(items=None, prompt=50, completion=20, finish="stop"):
    content = json.dumps({"items": items or []})
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content),
            finish_reason=finish,
        )],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def _rich_page(num=1):
    return {
        "page_number": num,
        "raw_text": "Display 1: Kitchen W3015 qty 2 B24BP qty 1 details follow here yes long enough",
        "blocks": [{}, {}, {}, {}],
        "status": "PROCESSED",
        "extraction_method": "pymupdf",
    }


# ---------------------------------------------------------------------------
# ORDER uses mini when flag is on
# ---------------------------------------------------------------------------

def test_order_uses_mini_when_flag_on(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=True)

    calls = []
    def capture_create(**kwargs):
        calls.append(kwargs.get("model"))
        return _resp()

    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = capture_create

    with patch.object(p, "_get_pdf_page_evidence", return_value=[_rich_page()]):
        p.extract_structured_data(b"fake", "application/pdf", "extract", OrderExtraction, doc_type="ORDER")

    assert all(m == "gpt-4o-mini" for m in calls), f"expected mini, got {calls}"


# ---------------------------------------------------------------------------
# ACKNOWLEDGEMENT uses mini when flag is on
# ---------------------------------------------------------------------------

def test_ack_uses_mini_when_flag_on(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=True)

    calls = []
    def capture_create(**kwargs):
        calls.append(kwargs.get("model"))
        return _resp()

    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = capture_create

    with patch.object(p, "_get_pdf_page_evidence", return_value=[_rich_page()]):
        p.extract_structured_data(b"fake", "application/pdf", "extract", DesignExtraction, doc_type="ACKNOWLEDGEMENT")

    assert all(m == "gpt-4o-mini" for m in calls), f"expected mini, got {calls}"


# ---------------------------------------------------------------------------
# DESIGN always uses primary model, even when flag is on
# ---------------------------------------------------------------------------

def test_design_always_uses_primary_model(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=True)

    calls = []
    def capture_create(**kwargs):
        calls.append(kwargs.get("model"))
        return _resp()

    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = capture_create

    with patch.object(p, "_get_pdf_page_evidence", return_value=[_rich_page()]), \
         patch.object(p, "_vision_pages_needed", return_value=set()):
        p.extract_structured_data(b"fake", "application/pdf", "extract", DesignExtraction, doc_type="DESIGN")

    assert all(m == "gpt-4o" for m in calls), f"expected primary, got {calls}"


# ---------------------------------------------------------------------------
# Flag off → primary model for all doc types
# ---------------------------------------------------------------------------

def test_flag_off_uses_primary_for_order(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=False)

    calls = []
    def capture_create(**kwargs):
        calls.append(kwargs.get("model"))
        return _resp()

    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = capture_create

    with patch.object(p, "_get_pdf_page_evidence", return_value=[_rich_page()]):
        p.extract_structured_data(b"fake", "application/pdf", "extract", OrderExtraction, doc_type="ORDER")

    assert all(m == "gpt-4o" for m in calls), f"expected primary, got {calls}"


# ---------------------------------------------------------------------------
# Mini model name flows into usage records (correct cost tracking)
# ---------------------------------------------------------------------------

def test_mini_model_in_usage_record(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=True)
    p.client = MagicMock()
    p.client.chat.completions.create.return_value = _resp(prompt=1_000_000, completion=1_000_000)

    with patch.object(p, "_get_pdf_page_evidence", return_value=[_rich_page()]):
        result = p.extract_structured_data(b"fake", "application/pdf", "extract", OrderExtraction, doc_type="ORDER")

    u = result["_api_usage"]
    assert u["calls"][0]["model"] == "gpt-4o-mini"
    # gpt-4o-mini: $0.75 per 2M tokens; gpt-4o would be $20
    assert u["total_estimated_cost_usd"] < 1.0, "cost must reflect mini pricing, not gpt-4o"


# ---------------------------------------------------------------------------
# Bisect retry inherits the model override
# ---------------------------------------------------------------------------

def test_bisect_retry_inherits_model(monkeypatch):
    p = _make_provider(monkeypatch, use_mini=True)

    call_models = []
    call_count = [0]

    def capture_create(**kwargs):
        call_count[0] += 1
        call_models.append(kwargs.get("model"))
        # First call: truncated → triggers bisect
        if call_count[0] == 1:
            content = '{"items": [{"sku": "W30'  # truncated JSON
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content=content),
                    finish_reason="length",
                )],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
        return _resp()

    p.client = MagicMock()
    p.client.chat.completions.create.side_effect = capture_create

    pages = [_rich_page(1), _rich_page(2)]
    result = p._extract_text_pages(
        pages, 2, "extract", DesignExtraction.model_json_schema(), "system",
        model="gpt-4o-mini",
    )

    assert all(m == "gpt-4o-mini" for m in call_models), \
        f"bisect retries must keep mini model, got {call_models}"
