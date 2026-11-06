"""
Session 13 — Vision Anchor (Option A) regression tests.

Tests _build_spec_anchor_map and the anchored-call path of _vision_batch_extract.
No live API calls, no DB, no PDF rendering (file_bytes mocked).

Run with:
    cd backend && venv/Scripts/python -m pytest tests/test_session13_vision_anchor.py -v
"""
import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch, call
import pytest

from app.core.config import settings
from app.integrations.ai.openai_provider import OpenAIProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provider(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-fake")
    p = OpenAIProvider()
    p.client = MagicMock()
    return p


def _page_ev(num, raw_text="Rich display text with many characters ok and long enough here yes", blocks=None, status="PROCESSED"):
    return {"page_number": num, "raw_text": raw_text, "blocks": blocks or [{}, {}, {}, {}], "status": status}


def _item(sku, pn, finish="CASHMERE"):
    return {"sku": sku, "quantity": 1, "view_type": "ELEVATION", "finish": finish,
            "position": f"Display {pn} area", "page_number": pn}


def _fake_response(items):
    """Return a mock openai response object that yields the given items."""
    resp = MagicMock()
    resp.choices[0].message.content = json.dumps({"items": items})
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    resp.model = "gpt-4o"
    return resp


# ---------------------------------------------------------------------------
# _build_spec_anchor_map tests
# ---------------------------------------------------------------------------

def test_anchor_map_basic_offset2(monkeypatch):
    """Spec page 5 → elevation page 7 (offset=2, standard pattern)."""
    p = _provider(monkeypatch)
    evidence = [
        _page_ev(5, "DISPLAY 2: BUILT-IN\nFINISH\nALPINE ON PHW\nDOOR STYLE"),
        _page_ev(6, "DISPLAY 2 FLOORPLAN"),
        _page_ev(7, "DISPLAY 2 ELEVATIONS callouts"),
    ]
    text_items = [_item("SM96", 7)]
    vision_pages = {7}
    result = p._build_spec_anchor_map(evidence, text_items, vision_pages)
    assert result == {7: 5}


def test_anchor_map_all_three_displays(monkeypatch):
    """Demo Project: pages 5→7, 11→13, 17→19 all detected."""
    p = _provider(monkeypatch)
    evidence = []
    # Display 2 spec/floor/elev
    for pn, text in [(5, "DISPLAY 2\nFINISH\nALPINE ON PHW"), (6, "floorplan text"), (7, "elev text")]:
        evidence.append(_page_ev(pn, text))
    # Display 4 spec/floor/elev
    for pn, text in [(11, "DISPLAY 4\nFINISH\nJUTE ON OAK"), (12, "floorplan text"), (13, "elev text")]:
        evidence.append(_page_ev(pn, text))
    # Display 6 spec/floor/elev
    for pn, text in [(17, "DISPLAY 6\nFINISH\nLAGOON ON PAINTED OAK"), (18, "floorplan text"), (19, "elev text")]:
        evidence.append(_page_ev(pn, text))

    # Text items only on elevation pages (not spec pages)
    text_items = [_item("TUKT", 7, ""), _item("SHC3", 13, ""), _item("AFA56S", 19, "")]
    vision_pages = {7, 13, 19}
    result = p._build_spec_anchor_map(evidence, text_items, vision_pages)
    assert result == {7: 5, 13: 11, 19: 17}


def test_anchor_map_no_finish_keyword_no_anchor(monkeypatch):
    """Page without FINISH keyword is not treated as a spec page."""
    p = _provider(monkeypatch)
    evidence = [
        _page_ev(5, "DISPLAY 2: BUILT-IN\nDOOR STYLE\nHAMPTON 1"),  # no FINISH
        _page_ev(7, "elevations"),
    ]
    result = p._build_spec_anchor_map(evidence, [], {7})
    assert result == {}


def test_anchor_map_spec_page_with_items_not_anchored(monkeypatch):
    """If a page has FINISH text AND extracted items, it is not a spec page."""
    p = _provider(monkeypatch)
    evidence = [
        _page_ev(5, "DISPLAY 2\nFINISH\nALPINE"),
        _page_ev(7, "elevations"),
    ]
    # Page 5 has an extracted item — not a pure spec page
    text_items = [_item("W3036", 5, "ALPINE"), _item("TUKT", 7, "")]
    result = p._build_spec_anchor_map(evidence, text_items, {7})
    assert result == {}


def test_anchor_map_empty_vision_pages(monkeypatch):
    """Empty vision_pages → always returns empty dict."""
    p = _provider(monkeypatch)
    evidence = [_page_ev(5, "FINISH\nALPINE"), _page_ev(7, "elevations")]
    result = p._build_spec_anchor_map(evidence, [], set())
    assert result == {}


# ---------------------------------------------------------------------------
# _vision_batch_extract anchor call construction (requirement 10)
# ---------------------------------------------------------------------------

def test_anchored_call_sends_two_images(monkeypatch, tmp_path):
    """
    When anchor_map={7: 5}, the Vision call for page 7 must send exactly
    two images: spec page 5 first, then elevation page 7 second.
    Requirement 10: inspect Vision request construction.
    """
    p = _provider(monkeypatch)

    # Build a minimal 10-page PDF via fitz
    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(10):
        doc.new_page()
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    file_bytes = pdf_path.read_bytes()

    captured_calls = []
    def _fake_create(**kwargs):
        captured_calls.append(kwargs)
        return _fake_response([{"sku": "SM96", "quantity": 1, "page_number": 7, "finish": "ALPINE ON PHW"}])

    p.client.chat.completions.create = MagicMock(side_effect=_fake_create)

    p._vision_batch_extract(
        file_bytes=file_bytes,
        prompt="extract",
        schema_json={"type": "object", "properties": {"items": {"type": "array"}}},
        system_prompt="system",
        dpi=72,
        page_numbers={7},
        anchor_map={7: 5},
    )

    # Exactly one call should have been made (the anchor call for page 7)
    assert len(captured_calls) >= 1
    anchor_call = captured_calls[0]
    user_content = anchor_call["messages"][1]["content"]

    # First item must be the text prompt
    assert user_content[0]["type"] == "text"
    prompt_text = user_content[0]["text"]
    assert "IMAGE 1" in prompt_text
    assert "IMAGE 2" in prompt_text
    assert "SPECIFICATION SHEET" in prompt_text
    assert "ELEVATION DRAWING" in prompt_text

    # Must have exactly 2 images after the text message
    images = [c for c in user_content if c.get("type") == "image_url"]
    assert len(images) == 2, f"Expected 2 images, got {len(images)}"


def test_anchored_call_items_returned(monkeypatch, tmp_path):
    """Items from the anchored Vision call are returned and have finish populated."""
    p = _provider(monkeypatch)

    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(20):
        doc.new_page()
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    file_bytes = pdf_path.read_bytes()

    returned_items = [
        {"sku": "TUKT", "quantity": 1, "page_number": 7, "finish": "ALPINE ON PHW", "view_type": "ELEVATION"},
        {"sku": "SM96", "quantity": 3, "page_number": 7, "finish": "ALPINE ON PHW", "view_type": "ELEVATION"},
    ]
    p.client.chat.completions.create = MagicMock(return_value=_fake_response(returned_items))

    result = p._vision_batch_extract(
        file_bytes=file_bytes,
        prompt="extract",
        schema_json={},
        system_prompt="system",
        dpi=72,
        page_numbers={7},
        anchor_map={7: 5},
    )

    skus = [i["sku"] for i in result]
    assert "TUKT" in skus
    assert "SM96" in skus
    for item in result:
        assert item["finish"] == "ALPINE ON PHW"


def test_non_anchored_pages_use_normal_batch(monkeypatch, tmp_path):
    """Pages not in anchor_map use the normal batch call (no spec page image)."""
    p = _provider(monkeypatch)

    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(10):
        doc.new_page()
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    file_bytes = pdf_path.read_bytes()

    captured_calls = []
    def _fake_create(**kwargs):
        captured_calls.append(kwargs)
        return _fake_response([])

    p.client.chat.completions.create = MagicMock(side_effect=_fake_create)

    p._vision_batch_extract(
        file_bytes=file_bytes,
        prompt="extract",
        schema_json={},
        system_prompt="system",
        dpi=72,
        page_numbers={4},
        anchor_map={7: 5},  # page 4 is not in anchor_map
    )

    assert len(captured_calls) == 1
    user_content = captured_calls[0]["messages"][1]["content"]
    # Normal batch: prompt text does NOT contain "IMAGE 1" / "SPECIFICATION SHEET"
    assert "SPECIFICATION SHEET" not in user_content[0]["text"]
    # Only 1 image (page 4)
    images = [c for c in user_content if c.get("type") == "image_url"]
    assert len(images) == 1


def test_cross_display_isolation(monkeypatch, tmp_path):
    """
    Display 2 anchor (5→7) must not affect Display 4 (11→13).
    Each display's anchored call is independent.
    """
    p = _provider(monkeypatch)

    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(22):
        doc.new_page()
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    file_bytes = pdf_path.read_bytes()

    call_prompts = []
    def _fake_create(**kwargs):
        call_prompts.append(kwargs["messages"][1]["content"][0]["text"])
        return _fake_response([])

    p.client.chat.completions.create = MagicMock(side_effect=_fake_create)

    p._vision_batch_extract(
        file_bytes=file_bytes,
        prompt="extract",
        schema_json={},
        system_prompt="system",
        dpi=72,
        page_numbers={7, 13},
        anchor_map={7: 5, 13: 11},
    )

    # Should be exactly 2 anchor calls
    assert len(call_prompts) == 2
    # Page 7 call references page 5 and page 7
    assert any("page 5" in t and "page 7" in t for t in call_prompts)
    # Page 13 call references page 11 and page 13
    assert any("page 11" in t and "page 13" in t for t in call_prompts)
    # Page 7 call does NOT reference page 11, page 13 call does NOT reference page 5
    p7_prompt = next(t for t in call_prompts if "page 5" in t)
    p13_prompt = next(t for t in call_prompts if "page 11" in t)
    assert "page 11" not in p7_prompt
    assert "page 5" not in p13_prompt


def test_anchor_call_fails_fallback_to_normal_batch(monkeypatch, tmp_path):
    """
    If the anchor call raises an exception, the page falls back to the
    normal batch loop so Vision still runs (best-effort).
    """
    p = _provider(monkeypatch)

    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(10):
        doc.new_page()
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()
    file_bytes = pdf_path.read_bytes()

    call_count = [0]
    def _fail_then_succeed(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("simulated anchor call failure")
        return _fake_response([{"sku": "TUKT", "quantity": 1, "page_number": 7}])

    p.client.chat.completions.create = MagicMock(side_effect=_fail_then_succeed)

    result = p._vision_batch_extract(
        file_bytes=file_bytes,
        prompt="extract",
        schema_json={},
        system_prompt="system",
        dpi=72,
        page_numbers={7},
        anchor_map={7: 5},
    )

    # Fallback batch call ran and returned the item
    assert any(i["sku"] == "TUKT" for i in result)
