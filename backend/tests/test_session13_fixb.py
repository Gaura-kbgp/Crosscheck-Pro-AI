"""
Session 13 Fix B — per-display Vision gate regression tests.

All tests are unit tests of _vision_pages_needed. They require no DB, no AI
call, and no live PDF. The 10 planned tests from the Fix B plan are all here,
plus extra coverage required by the approval (multiple distinct finishes per
display, missing/ambiguous position, unnecessary-trigger guard).

Run with:
    cd backend && venv/Scripts/python -m pytest tests/test_session13_fixb.py -v
"""
import pytest
from unittest.mock import MagicMock

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


def _page(num, raw_text="Rich display text with many characters to clear the sparse threshold ok and it is long",
          blocks=None, status="PROCESSED"):
    """Build a page_evidence dict that passes conditions 1–4 by default."""
    return {
        "page_number": num,
        "raw_text": raw_text,
        "blocks": blocks if blocks is not None else [{}, {}, {}, {}],
        "status": status,
    }


def _elev(sku, finish, position, page):
    return {"sku": sku, "quantity": 1, "view_type": "ELEVATION",
            "finish": finish, "position": position, "page_number": page}


def _floor(sku, finish, position, page):
    return {"sku": sku, "quantity": 1, "view_type": "FLOORPLAN",
            "finish": finish, "position": position, "page_number": page}


# ---------------------------------------------------------------------------
# Test 1 — PLANNED: mixed page — one display no-finish, another has finish
# ---------------------------------------------------------------------------

def test_per_display_mixed_page_flags(monkeypatch):
    """
    Page 7: Display 1 items all have finish, Display 2 items all lack finish.
    Old condition-5 would NOT flag (not ALL elevation items are finishless).
    New per-display gate MUST flag because Display 2 is entirely finishless.
    """
    p = _provider(monkeypatch)
    evidence = [_page(7)]
    items = [
        _elev("TP96", "CASHMERE", "Display 1 – Kitchen", 7),
        _elev("QR96", "DEWDROP", "Display 1 – Kitchen", 7),
        _elev("SM96", "", "Display 2 – Pantry", 7),   # no finish
        _elev("TUKT", "", "Display 2 – Pantry", 7),   # no finish
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 7 in needed, "Page 7 must be flagged: Display 2 has all-finishless elevation items"


# ---------------------------------------------------------------------------
# Test 2 — PLANNED: all items missing finish → still flags (backward compat)
# ---------------------------------------------------------------------------

def test_per_display_all_missing_still_flags(monkeypatch):
    """
    Page 19: ALL elevation items on the page are finishless.
    Display 6 (Mudroom) regression guard — old condition-5 fired; must still fire.
    """
    p = _provider(monkeypatch)
    evidence = [_page(19)]
    items = [
        _elev("AFA56S", "", "Display 6 – Mudroom", 19),
        _elev("UC18842L", "", "Display 6 – Mudroom", 19),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 19 in needed, "Page 19 must be flagged: all Display 6 elevation items lack finish"


# ---------------------------------------------------------------------------
# Test 3 — PLANNED: all displays have finish → page NOT flagged
# ---------------------------------------------------------------------------

def test_per_display_all_present_no_flag(monkeypatch):
    """
    Every elevation item on the page has a finish. No Vision needed.
    """
    p = _provider(monkeypatch)
    evidence = [_page(5)]
    items = [
        _elev("TP96", "CASHMERE", "Display 1 – Kitchen", 5),
        _elev("QR96", "SAGEWOOD", "Display 3 – Laundry", 5),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 5 not in needed, "Page 5 must NOT be flagged: every display has finish"


# ---------------------------------------------------------------------------
# Test 4 — PLANNED: partial finish within a display → NOT flagged
# ---------------------------------------------------------------------------

def test_per_display_partial_in_one_display_no_flag(monkeypatch):
    """
    Display with 3 items: 2 have finish, 1 does not.
    Not ALL items in the display are finishless → gate must NOT fire for this display.
    """
    p = _provider(monkeypatch)
    evidence = [_page(8)]
    items = [
        _elev("SM96", "DEWDROP", "Display 2 – Pantry", 8),
        _elev("TP96", "DEWDROP", "Display 2 – Pantry", 8),
        _elev("QR96", "", "Display 2 – Pantry", 8),  # one item missing finish, but not all
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 8 not in needed, "Page 8 must NOT be flagged: Display 2 has at least one item with finish"


# ---------------------------------------------------------------------------
# Test 5 — PLANNED: only FLOORPLAN items → condition 5 must NOT fire
# ---------------------------------------------------------------------------

def test_per_display_no_elevation_items_no_flag(monkeypatch):
    """
    Page has only FLOORPLAN items. The per-display elevation check requires
    elevation_items to be non-empty; with no ELEVATION items, it must not flag.
    """
    p = _provider(monkeypatch)
    evidence = [_page(6)]
    items = [
        _floor("B24", "", "Display 2 – Pantry", 6),
        _floor("B36", "", "Display 2 – Pantry", 6),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 6 not in needed, "Page 6 must NOT be flagged by condition 5: no ELEVATION items"


# ---------------------------------------------------------------------------
# Test 6 — PLANNED: single finishless elevation item → flags
# ---------------------------------------------------------------------------

def test_per_display_single_finishless_item_flags(monkeypatch):
    """
    Display with exactly one elevation item, finish is empty string.
    all(finishless) over a 1-item group is True → page must be flagged.
    """
    p = _provider(monkeypatch)
    evidence = [_page(13)]
    items = [_elev("TUKT", "", "Display 4 – Island", 13)]
    needed = p._vision_pages_needed(evidence, items)
    assert 13 in needed, "Page 13 must be flagged: single finishless elevation item in Display 4"


# ---------------------------------------------------------------------------
# Test 7 — PLANNED: missing/None position → __unknown__ fallback
# ---------------------------------------------------------------------------

def test_per_display_no_position_field_fallback(monkeypatch):
    """
    Items with no position (None or missing key) fall into __unknown__.
    If those items all lack finish, the page must be flagged.
    """
    p = _provider(monkeypatch)
    evidence = [_page(10)]
    items = [
        {"sku": "W3015", "quantity": 1, "view_type": "ELEVATION", "finish": "", "page_number": 10},
        {"sku": "B24", "quantity": 1, "view_type": "ELEVATION", "page_number": 10},  # no 'finish' key
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 10 in needed, "Page 10 must be flagged: __unknown__ display group all finishless"


# ---------------------------------------------------------------------------
# Test 8 — PLANNED: three displays, one has all-finishless items
# ---------------------------------------------------------------------------

def test_per_display_three_displays_one_missing(monkeypatch):
    """
    Display 1 — has finish, Display 2 — all finishless, Display 3 — has finish.
    Gate must fire because Display 2 is entirely finishless.
    """
    p = _provider(monkeypatch)
    evidence = [_page(7)]
    items = [
        _elev("TP96", "CASHMERE", "Display 1 – Kitchen", 7),
        _elev("SM96", "", "Display 2 – Pantry", 7),
        _elev("TUKT", "", "Display 2 – Pantry", 7),
        _elev("QR96", "SAGEWOOD", "Display 3 – Bar", 7),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 7 in needed, "Page 7 must be flagged: Display 2 entirely finishless among three displays"


# ---------------------------------------------------------------------------
# Test 9 — PLANNED: conditions 1–4 still fire independently of condition 5
# ---------------------------------------------------------------------------

def test_vision_gate_conditions_1_to_4_unaffected(monkeypatch):
    """
    Verify the first four conditions still fire even when elevation items all
    have finish (condition 5 would not fire alone).
    """
    p = _provider(monkeypatch)

    # Condition 1: EMPTY page
    evidence_c1 = [_page(1, "", blocks=[], status="EMPTY")]
    items_c1 = [_elev("W3015", "CASHMERE", "Display 1", 1)]
    needed = p._vision_pages_needed(evidence_c1, items_c1)
    assert 1 in needed, "Condition 1 (EMPTY page) must still fire"

    # Condition 2: sparse blocks (< 3)
    evidence_c2 = [_page(2, "Display 1 Kitchen large long text" * 5, blocks=[{}])]
    items_c2 = [_elev("W3015", "CASHMERE", "Display 1", 2)]
    needed = p._vision_pages_needed(evidence_c2, items_c2)
    assert 2 in needed, "Condition 2 (sparse blocks) must still fire"

    # Condition 3: no items extracted from page
    evidence_c3 = [_page(3)]
    needed = p._vision_pages_needed(evidence_c3, [])  # no items → condition 3
    assert 3 in needed, "Condition 3 (no items) must still fire"

    # Condition 4: item missing quantity
    evidence_c4 = [_page(4)]
    items_c4 = [{"sku": "W3015", "quantity": None, "view_type": "ELEVATION",
                 "finish": "CASHMERE", "position": "Display 1", "page_number": 4}]
    needed = p._vision_pages_needed(evidence_c4, items_c4)
    assert 4 in needed, "Condition 4 (missing quantity) must still fire"


# ---------------------------------------------------------------------------
# Test 10 — PLANNED: empty evidence → returns None
# ---------------------------------------------------------------------------

def test_vision_gate_none_on_empty_evidence(monkeypatch):
    """Empty page_evidence → returns None (fall back to Vision on all pages)."""
    p = _provider(monkeypatch)
    result = p._vision_pages_needed([], [])
    assert result is None


# ---------------------------------------------------------------------------
# Test 11 — APPROVAL EXTRA: multiple distinct finishes within one display → NOT flagged
# ---------------------------------------------------------------------------

def test_multiple_distinct_finishes_in_display_no_flag(monkeypatch):
    """
    Display with two items: one CASHMERE, one DEWDROP.
    Both items have finish — different finishes within the same display are fine.
    Gate must NOT fire (the display is not all-finishless).
    """
    p = _provider(monkeypatch)
    evidence = [_page(5)]
    items = [
        _elev("SM96", "CASHMERE", "Display 2 – Pantry", 5),
        _elev("QR96", "DEWDROP", "Display 2 – Pantry", 5),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 5 not in needed, "Page 5 must NOT be flagged: display items have distinct but non-empty finishes"


# ---------------------------------------------------------------------------
# Test 12 — APPROVAL EXTRA: ambiguous position (no display number) → __unknown__
#            treated as one group; if any are finishless, page is flagged
# ---------------------------------------------------------------------------

def test_ambiguous_position_non_numeric_display(monkeypatch):
    """
    Items whose position says 'Island Section' (no digit) cannot be matched
    by the display-digit pattern. They fall into __unknown__. If all lack finish,
    the page should still be flagged.
    """
    p = _provider(monkeypatch)
    evidence = [_page(13)]
    items = [
        _elev("SHC3", "", "Island Section", 13),
        _elev("B24BP", "", "Island Section", 13),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 13 in needed, "Page 13 must be flagged: __unknown__ group all finishless"


# ---------------------------------------------------------------------------
# Test 13 — APPROVAL EXTRA: no unnecessary trigger when unrelated pages pass
# ---------------------------------------------------------------------------

def test_unrelated_pages_not_flagged(monkeypatch):
    """
    Multi-page evidence where only page 7 has a finishless display.
    Pages 1 and 5 (fully extracted, all items with finish) must NOT be flagged.
    """
    p = _provider(monkeypatch)
    evidence = [_page(1), _page(5), _page(7)]
    items = [
        _elev("TP96", "CASHMERE", "Display 1 – Kitchen", 1),
        _elev("QR96", "SAGEWOOD", "Display 3 – Bar", 5),
        _elev("SM96", "", "Display 2 – Pantry", 7),  # only page 7 is finishless
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 7 in needed,  "Page 7 must be flagged"
    assert 1 not in needed, "Page 1 must NOT be flagged"
    assert 5 not in needed, "Page 5 must NOT be flagged"


# ---------------------------------------------------------------------------
# Test 14 — APPROVAL EXTRA: pages 7, 13, 19 structure simulation
#            Exercises the realistic Demo Project display layout
# ---------------------------------------------------------------------------

def test_demo_pages_7_13_19_simulation(monkeypatch):
    """
    Simulate Demo Project page structure as known from the f8.3.7 extraction:
    - Page 7  (Display 2 – Pantry):  ELEVATION items, no finish, Display 1 items WITH finish on same page
    - Page 13 (Display 4 – Island):  ELEVATION items, no finish, Display 3 items WITH finish on same page
    - Page 19 (Display 6 – Mudroom): ELEVATION items, all finishless (no other display)
    - Page 3  (Display 1 – Kitchen): all items have finish → must NOT flag
    All three target pages must be flagged; page 3 must not.
    """
    p = _provider(monkeypatch)
    evidence = [_page(3), _page(7), _page(13), _page(19)]
    items = [
        # Page 3: Display 1, all with finish
        _elev("TP96", "CASHMERE", "Display 1 – Kitchen", 3),
        _elev("QR96", "CASHMERE", "Display 1 – Kitchen", 3),
        # Page 7: Display 1 overflow (has finish) + Display 2 (no finish)
        _elev("SM96", "DEWDROP", "Display 1 – Kitchen", 7),
        _elev("TUKT", "", "Display 2 – Pantry", 7),
        _elev("STR396-CV", "", "Display 2 – Pantry", 7),
        # Page 13: Display 3 (has finish) + Display 4 Island (no finish)
        _elev("UCT96", "SAGEWOOD", "Display 3 – Bar", 13),
        _elev("SHC3", "", "Display 4 – Island", 13),
        _elev("B24BP", "", "Display 4 – Island", 13),
        # Page 19: Display 6 Mudroom, all finishless
        _elev("AFA56S", "", "Display 6 – Mudroom", 19),
        _elev("UC18842L", "", "Display 6 – Mudroom", 19),
    ]
    needed = p._vision_pages_needed(evidence, items)
    assert 7 in needed,  "Page 7 (Display 2 Pantry) must be flagged"
    assert 13 in needed, "Page 13 (Display 4 Island) must be flagged"
    assert 19 in needed, "Page 19 (Display 6 Mudroom) must be flagged"
    assert 3 not in needed, "Page 3 (Display 1 Kitchen, all with finish) must NOT be flagged"
