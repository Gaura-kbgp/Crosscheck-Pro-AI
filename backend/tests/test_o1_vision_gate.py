"""
O1 — Vision gate regression tests.

Verifies _vision_pages_needed quality criteria and that _vision_batch_extract
skips the right pages when page_numbers is set.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.core.config import settings
from app.integrations.ai.openai_provider import OpenAIProvider
from app.schemas.extraction import DesignExtraction


def _make_provider(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    p = OpenAIProvider()
    p.client = MagicMock()
    return p


def _page(num, raw_text, blocks=None, status="PROCESSED"):
    return {
        "page_number": num,
        "raw_text": raw_text,
        "blocks": blocks if blocks is not None else [{"block_index": i, "text": f"b{i}"} for i in range(5)],
        "status": status,
        "extraction_method": "pymupdf",
    }


def _item(sku, qty, page):
    return {"sku": sku, "quantity": qty, "page_number": page}


# ---------------------------------------------------------------------------
# _vision_pages_needed: empty page → needs Vision
# ---------------------------------------------------------------------------

def test_empty_page_needs_vision(monkeypatch):
    p = _make_provider(monkeypatch)
    evidence = [_page(1, "", blocks=[], status="EMPTY"), _page(2, "W3015 qty 2 --- cabinet base wall data present here long enough for the threshold check", blocks=[{}, {}, {}, {}])]
    items = [_item("W3015", 2, 2)]
    needed = p._vision_pages_needed(evidence, items)
    assert 1 in needed
    assert 2 not in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: sparse text page (< 3 blocks) → needs Vision
# ---------------------------------------------------------------------------

def test_sparse_blocks_needs_vision(monkeypatch):
    p = _make_provider(monkeypatch)
    # page 1: only 2 blocks → sparse
    evidence = [_page(1, "DISPLAY 1: Kitchen" * 5, blocks=[{}, {}])]
    needed = p._vision_pages_needed(evidence, [])
    assert 1 in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: short text (< 80 chars) → needs Vision
# ---------------------------------------------------------------------------

def test_short_text_needs_vision(monkeypatch):
    p = _make_provider(monkeypatch)
    evidence = [_page(1, "Short text.", blocks=[{}, {}, {}])]
    needed = p._vision_pages_needed(evidence, [])
    assert 1 in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: no items extracted from page → needs Vision
# ---------------------------------------------------------------------------

def test_no_items_on_page_needs_vision(monkeypatch):
    p = _make_provider(monkeypatch)
    # page 1 has rich text but no items extracted from it
    rich_text = "Display 1: Kitchen section shows base and wall cabinets all sizes listed below in full"
    evidence = [_page(1, rich_text, blocks=[{}, {}, {}, {}])]
    items = []  # nothing extracted
    needed = p._vision_pages_needed(evidence, items)
    assert 1 in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: item missing quantity → needs Vision
# ---------------------------------------------------------------------------

def test_missing_quantity_needs_vision(monkeypatch):
    p = _make_provider(monkeypatch)
    rich_text = "Display 1: Kitchen section shows base and wall cabinets all sizes listed below in full"
    evidence = [_page(1, rich_text, blocks=[{}, {}, {}, {}])]
    items = [{"sku": "W3015", "quantity": None, "page_number": 1}]
    needed = p._vision_pages_needed(evidence, items)
    assert 1 in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: well-extracted page → NOT needed
# ---------------------------------------------------------------------------

def test_well_extracted_page_not_needed(monkeypatch):
    p = _make_provider(monkeypatch)
    rich_text = "Display 1: Kitchen section shows base and wall cabinets all sizes listed below in full detail"
    evidence = [_page(1, rich_text, blocks=[{}, {}, {}, {}])]
    items = [_item("W3015", 2, 1), _item("B24BP", 3, 1)]
    needed = p._vision_pages_needed(evidence, items)
    assert 1 not in needed


# ---------------------------------------------------------------------------
# _vision_pages_needed: empty evidence → returns None (Vision all)
# ---------------------------------------------------------------------------

def test_no_evidence_returns_none(monkeypatch):
    p = _make_provider(monkeypatch)
    result = p._vision_pages_needed([], [])
    assert result is None


# ---------------------------------------------------------------------------
# _vision_batch_extract: skips batches entirely when page_numbers excludes them
# ---------------------------------------------------------------------------

def test_vision_batch_skips_excluded_pages(monkeypatch):
    """With page_numbers={2}, only page 2 should be rendered and sent."""
    import fitz as _fitz
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()
    provider.client = MagicMock()

    fake_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"items":[]}'), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    provider.client.chat.completions.create.return_value = fake_resp

    # 3-page PDF: only page 2 needed
    import io
    doc = _fitz.open()
    for _ in range(3):
        doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    items = provider._vision_batch_extract(
        pdf_bytes, "extract", DesignExtraction.model_json_schema(), "system", page_numbers={2}
    )

    # Only 1 API call (1 page → 1 batch), not 3
    assert provider.client.chat.completions.create.call_count == 1
    # The batch content must include exactly 1 image (page 2 only)
    call_args = provider.client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    image_parts = [p for p in user_content if p.get("type") == "image_url"]
    assert len(image_parts) == 1


# ---------------------------------------------------------------------------
# _vision_batch_extract: empty page_numbers set → no API calls
# ---------------------------------------------------------------------------

def test_vision_batch_empty_set_makes_no_calls(monkeypatch):
    import fitz as _fitz
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()
    provider.client = MagicMock()

    doc = _fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    items = provider._vision_batch_extract(
        pdf_bytes, "extract", DesignExtraction.model_json_schema(), "system", page_numbers=set()
    )
    assert items == []
    provider.client.chat.completions.create.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: DESIGN text path uses gate and skips Vision for clean pages
# ---------------------------------------------------------------------------

def test_design_path_skips_vision_when_gate_says_no_pages(monkeypatch):
    """When all pages are well-extracted, Vision pass is skipped entirely."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    provider = OpenAIProvider()
    provider.client = MagicMock()

    # Rich page evidence — all pages will pass the gate (well extracted)
    rich = "Display 1: Kitchen section shows base wall cabinets all sizes fully extracted here yes"
    page_evidence = [_page(1, rich, blocks=[{}, {}, {}, {}])]

    # Text pass returns items with quantities for all pages → gate returns empty set
    items_resp = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps({"items": [{"sku": "W3015", "quantity": 2, "page_number": 1}]})),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
    )
    provider.client.chat.completions.create.return_value = items_resp

    with patch.object(provider, "_get_pdf_page_evidence", return_value=page_evidence):
        result = provider.extract_structured_data(b"fake", "application/pdf", "extract", DesignExtraction, doc_type="DESIGN")

    # Vision should not have been called a second time (only 1 call: text pass)
    assert provider.client.chat.completions.create.call_count == 1
    assert "items" in result
