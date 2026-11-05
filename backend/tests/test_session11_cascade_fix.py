"""
Regression tests for Session 11 Fix A (+ determinism fix):
  Cascade failure where one no-finish DESIGN unit causes unrelated units
  with explicit finish evidence to be incorrectly marked UNCERTAIN.

Test plan (9 + 5 determinism tests):
  1. SM96 Display1 SAGEWOOD matches ORDER SAGEWOOD → MATCHED
  2. SM96 Display3 CASHMERE matches ORDER CASHMERE → MATCHED
  3. SM96 Display2 no-finish stays UNCERTAIN
  4. SM96 Display4 no-finish stays UNCERTAIN
  5. SM96 Display6 no-finish stays UNCERTAIN
  6. No-finish ambiguous unit does NOT cause TP96/TUKT/QR96 with finish to become UNCERTAIN
  7. Genuine ambiguity (two DESIGN units same finish, no unique ORDER match) stays UNCERTAIN
  8. No double-consumption of ORDER quantities
  9. Unrelated SKU (B24) is unaffected
 10. Two DESIGN units competing for the same ORDER item → UNCERTAIN (not first-wins MATCHED)
 11. Equal token-richness candidates both contested → both UNCERTAIN
 12. Determinism: repeated runs with the same input produce identical group assignments
 13. Uniquely stronger candidate (higher score) is correctly committed
 14. Genuine ambiguity (tied token overlap) stays UNCERTAIN even with determinism fix
"""
import pytest
from uuid import uuid4
from app.models.core import CanonicalLineItem, DocumentType, ItemCategory, MatchGroupStatus
from app.engines.matching import MatchingEngine


PROJECT_ID = uuid4()
ORG_ID = uuid4()


def _item(source_type, sku, qty=1, finish=None, door_style=None, view_type=None, position=None):
    item = CanonicalLineItem(
        id=uuid4(),
        project_id=PROJECT_ID,
        organization_id=ORG_ID,
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku.upper(),
        quantity=qty,
        finish=finish,
        door_style=door_style,
        item_category=ItemCategory.CABINET,
    )
    if view_type or position:
        item.source_metadata = {"view_type": view_type, "position": position}
    return item


def _run(design_items, order_items, ack_items=None):
    return MatchingEngine().match_items(design_items, order_items, ack_items or [], PROJECT_ID, ORG_ID)


def _status_for(groups, sku):
    return {g.status for g in groups if _sku(g) == sku.upper()}


def _sku(g):
    item = g.design_item or g.order_item or g.ack_item
    return (item.raw_sku or "").upper() if item else ""


# ---------------------------------------------------------------------------
# Tests 1-5: SM96 multi-display scenario (3 with finish, 3 without)
# ---------------------------------------------------------------------------

def _sm96_scenario():
    """
    7 DESIGN SM96 units across displays:
      Display1 SAGEWOOD, Display2 no-finish, Display3 CASHMERE,
      Display4 no-finish, Display5 DEWDROP, Display6 no-finish, Display7 DUNE
    7 ORDER SM96 units (each with the finish that matches a display).
    """
    design = [
        _item("DESIGN", "SM96", finish="SAGEWOOD/PHW", view_type="ELEVATION", position="Display 1: Kitchen"),
        _item("DESIGN", "SM96", finish=None,           view_type="ELEVATION", position="Display 2: Built-In"),
        _item("DESIGN", "SM96", finish="CASHMERE/PHW", view_type="ELEVATION", position="Display 3: Range Kitchen"),
        _item("DESIGN", "SM96", finish=None,           view_type="ELEVATION", position="Display 4: Island"),
        _item("DESIGN", "SM96", finish="DEWDROP",      view_type="ELEVATION", position="Display 5: Oven Kitchen"),
        _item("DESIGN", "SM96", finish=None,           view_type="ELEVATION", position="Display 6: Mudroom"),
        _item("DESIGN", "SM96", finish="DUNE",         view_type="ELEVATION", position="Display 7: Captiv8"),
    ]
    order = [
        _item("ORDER", "SM96", finish="SAGEWOOD/PHW"),
        _item("ORDER", "SM96", finish="CASHMERE MAPLE"),
        _item("ORDER", "SM96", finish="DEWDROP"),
        _item("ORDER", "SM96", finish="DUNE"),
        _item("ORDER", "SM96", finish="ALPINE"),
        _item("ORDER", "SM96", finish="SALT"),
        _item("ORDER", "SM96", finish="LINEN"),
    ]
    return design, order


def test_sm96_display1_sagewood_matches():
    """Test 1: SM96 Display1 SAGEWOOD matches ORDER SAGEWOOD → MATCHED."""
    design, order = _sm96_scenario()
    groups = _run(design, order)
    matched = [g for g in groups if g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)
               and g.design_item and g.order_item
               and g.design_item.finish == "SAGEWOOD/PHW"
               and g.order_item.finish == "SAGEWOOD/PHW"]
    assert matched, "SM96 Display1 SAGEWOOD should be MATCHED to ORDER SAGEWOOD"


def test_sm96_display3_cashmere_matches():
    """Test 2: SM96 Display3 CASHMERE matches ORDER CASHMERE → MATCHED."""
    design, order = _sm96_scenario()
    groups = _run(design, order)
    matched = [g for g in groups if g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)
               and g.design_item and g.order_item
               and g.design_item.finish == "CASHMERE/PHW"
               and "CASHMERE" in (g.order_item.finish or "").upper()]
    assert matched, "SM96 Display3 CASHMERE should be MATCHED to ORDER CASHMERE"


def test_sm96_display2_nofinish_uncertain():
    """Test 3: SM96 Display2 no-finish stays UNCERTAIN."""
    design, order = _sm96_scenario()
    groups = _run(design, order)
    uncertain_d = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN
                   and g.design_item and not g.design_item.finish
                   and "DISPLAY 2" in (g.design_item.source_metadata or {}).get("position", "").upper()]
    assert uncertain_d, "SM96 Display2 no-finish should remain UNCERTAIN"


def test_sm96_display4_nofinish_uncertain():
    """Test 4: SM96 Display4 no-finish stays UNCERTAIN."""
    design, order = _sm96_scenario()
    groups = _run(design, order)
    uncertain_d = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN
                   and g.design_item and not g.design_item.finish
                   and "DISPLAY 4" in (g.design_item.source_metadata or {}).get("position", "").upper()]
    assert uncertain_d, "SM96 Display4 no-finish should remain UNCERTAIN"


def test_sm96_display6_nofinish_uncertain():
    """Test 5: SM96 Display6 no-finish stays UNCERTAIN."""
    design, order = _sm96_scenario()
    groups = _run(design, order)
    uncertain_d = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN
                   and g.design_item and not g.design_item.finish
                   and "DISPLAY 6" in (g.design_item.source_metadata or {}).get("position", "").upper()]
    assert uncertain_d, "SM96 Display6 no-finish should remain UNCERTAIN"


# ---------------------------------------------------------------------------
# Test 6: No cross-SKU cascade — TP96/TUKT/QR96 with finish are unaffected
# ---------------------------------------------------------------------------

def test_independent_skus_not_cascaded():
    """
    Test 6: A no-finish ambiguous SM96 unit must not cause TP96/TUKT/QR96
    units (with explicit finish) to become UNCERTAIN.
    """
    design = [
        _item("DESIGN", "SM96",  finish=None,       view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96",  finish=None,       view_type="ELEVATION", position="Display 4"),
        _item("DESIGN", "TP96",  finish="SAGEWOOD", view_type="ELEVATION", position="Display 1"),
        _item("DESIGN", "TUKT",  finish="CASHMERE", view_type="ELEVATION", position="Display 3"),
        _item("DESIGN", "QR96",  finish="DEWDROP",  view_type="ELEVATION", position="Display 5"),
    ]
    order = [
        _item("ORDER", "SM96",  finish="ALPINE"),
        _item("ORDER", "SM96",  finish="SALT"),
        _item("ORDER", "TP96",  finish="SAGEWOOD"),
        _item("ORDER", "TUKT",  finish="CASHMERE"),
        _item("ORDER", "QR96",  finish="DEWDROP"),
    ]
    groups = _run(design, order)
    uncertain = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and _sku(g) in ("TP96", "TUKT", "QR96")]
    assert not uncertain, (
        f"TP96/TUKT/QR96 with explicit finish should NOT be UNCERTAIN; got: "
        f"{[(g.status, _sku(g)) for g in uncertain]}"
    )
    matched_tp96 = [g for g in groups if _sku(g) == "TP96" and g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)]
    assert matched_tp96, "TP96 SAGEWOOD should be MATCHED to ORDER TP96 SAGEWOOD"


# ---------------------------------------------------------------------------
# Test 7: Genuine ambiguity remains UNCERTAIN
# ---------------------------------------------------------------------------

def test_genuine_ambiguity_stays_uncertain():
    """
    Test 7: Two DESIGN SM96 units each with finish "ALPINE CASHMERE" at different
    positions, and two ORDER units with ALPINE and CASHMERE respectively. Neither
    DESIGN unit uniquely resolves to one ORDER unit (_best_config_match ties on
    token overlap 1 vs 1) → all four should stay UNCERTAIN.
    """
    design = [
        # Both have the same bi-token finish → neither uniquely beats the other
        _item("DESIGN", "SM96", finish="ALPINE CASHMERE", view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96", finish="ALPINE CASHMERE", view_type="ELEVATION", position="Display 4"),
    ]
    order = [
        _item("ORDER", "SM96", finish="ALPINE"),
        _item("ORDER", "SM96", finish="CASHMERE"),
    ]
    groups = _run(design, order)
    uncertain = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and _sku(g) == "SM96"]
    assert len(uncertain) >= 2, (
        f"Genuinely ambiguous (tied token overlap) SM96 should stay UNCERTAIN; got {len(uncertain)} uncertain groups"
    )


# ---------------------------------------------------------------------------
# Test 8: No double-consumption of ORDER quantities
# ---------------------------------------------------------------------------

def test_no_double_consumption():
    """
    Test 8: Each ORDER unit can only be matched to at most one DESIGN unit.
    Total ORDER items consumed ≤ total ORDER items in input.
    """
    design, order = _sm96_scenario()
    groups = _run(design, order)
    consumed_order_ids = set()
    for g in groups:
        if g.order_item:
            assert g.order_item.id not in consumed_order_ids, (
                f"ORDER item {g.order_item.id} ({g.order_item.finish}) consumed twice"
            )
            consumed_order_ids.add(g.order_item.id)
    assert len(consumed_order_ids) <= len(order)


# ---------------------------------------------------------------------------
# Test 9: Unrelated projects / SKUs are unaffected
# ---------------------------------------------------------------------------

def test_unrelated_sku_unaffected():
    """
    Test 9: A clean 1-to-1 B24 match in the same project is not disturbed
    by the SM96 cascade-fix code path.
    """
    design = [
        _item("DESIGN", "SM96", finish=None,       view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96", finish=None,       view_type="ELEVATION", position="Display 4"),
        _item("DESIGN", "B24",  finish="SAGEWOOD"),
    ]
    order = [
        _item("ORDER", "SM96", finish="ALPINE"),
        _item("ORDER", "SM96", finish="SALT"),
        _item("ORDER", "B24",  finish="SAGEWOOD"),
    ]
    groups = _run(design, order)
    b24_groups = [g for g in groups if _sku(g) == "B24"]
    assert b24_groups, "B24 group should exist"
    assert all(g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED) for g in b24_groups), (
        f"B24 should be MATCHED/CHANGED, got: {[g.status for g in b24_groups]}"
    )


# ---------------------------------------------------------------------------
# Determinism tests (10-14)
# ---------------------------------------------------------------------------

def test_two_design_units_competing_same_order_both_uncertain():
    """
    Test 10: The else-branch rescue fires (d=Display2 no-finish fails).
    Two rescue candidates (Display4 ALPINE and Display6 ALPINE) BOTH want the same
    ORDER SM96 ALPINE unit. The contested-item guard must mark all three UNCERTAIN.
    """
    design = [
        # d fires else-branch (no finish → fails disambiguation)
        _item("DESIGN", "SM96", finish=None,    view_type="ELEVATION", position="Display 2"),
        # Both these rescue candidates claim the same ORDER ALPINE
        _item("DESIGN", "SM96", finish="ALPINE", view_type="ELEVATION", position="Display 4"),
        _item("DESIGN", "SM96", finish="ALPINE", view_type="ELEVATION", position="Display 6"),
    ]
    order = [
        _item("ORDER", "SM96", finish="ALPINE"),  # only one ORDER ALPINE unit
    ]
    groups = _run(design, order)
    uncertain_d = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and g.design_item]
    uncertain_o = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and g.order_item and not g.design_item]
    matched = [g for g in groups if g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)]
    assert len(uncertain_d) >= 2, (
        f"Both rescue candidates competing for same ORDER should be UNCERTAIN; got {len(uncertain_d)}"
    )
    assert uncertain_o, "Contested ORDER ALPINE unit should be UNCERTAIN"
    assert not matched, f"No MATCHED when both rescue candidates contest same ORDER; got {matched}"


def test_equal_token_richness_contested_both_uncertain():
    """
    Test 11: Else-branch fires. Two rescue candidates with identical token count
    both want the same ORDER item — result must be UNCERTAIN regardless of sort order.
    """
    design = [
        _item("DESIGN", "SM96", finish=None,         view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96", finish="ALPINE SALT", view_type="ELEVATION", position="Display 4"),
        _item("DESIGN", "SM96", finish="ALPINE SALT", view_type="ELEVATION", position="Display 6"),
    ]
    order = [
        _item("ORDER", "SM96", finish="ALPINE SALT"),
    ]
    groups = _run(design, order)
    uncertain_d = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and g.design_item]
    matched = [g for g in groups if g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)]
    assert len(uncertain_d) >= 2, "Both equal-richness contested DESIGN units should be UNCERTAIN"
    assert not matched, "No MATCHED group when both rescue candidates contest same ORDER"


def test_determinism_repeated_runs_identical():
    """
    Test 12: Running match_items twice on the same input produces identical
    group status assignments (same SKUs, same statuses, same order if sorted).
    """
    design, order = _sm96_scenario()
    groups_a = _run(design, order)
    groups_b = _run(design, order)

    def summarise(groups):
        return sorted(
            [(g.status.value,
              g.design_item.finish or "" if g.design_item else "",
              g.order_item.finish or "" if g.order_item else "")
             for g in groups]
        )

    assert summarise(groups_a) == summarise(groups_b), (
        "Two identical runs produced different match group assignments"
    )


def test_uniquely_stronger_candidate_matched():
    """
    Test 13: One DESIGN unit has a unique finish token matching exactly one ORDER unit;
    no other DESIGN unit shares that token → uncontested → should be MATCHED.
    """
    design = [
        _item("DESIGN", "SM96", finish="SAGEWOOD",  view_type="ELEVATION", position="Display 1"),
        _item("DESIGN", "SM96", finish=None,         view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96", finish=None,         view_type="ELEVATION", position="Display 4"),
    ]
    order = [
        _item("ORDER", "SM96", finish="SAGEWOOD PHW"),
        _item("ORDER", "SM96", finish="LINEN"),
    ]
    groups = _run(design, order)
    matched = [g for g in groups if g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED)
               and g.design_item and g.design_item.finish == "SAGEWOOD"]
    assert matched, "DESIGN SAGEWOOD (unique claim) should be MATCHED to ORDER SAGEWOOD PHW"


def test_genuine_tie_stays_uncertain_with_determinism_fix():
    """
    Test 14: Two DESIGN units each have the same two tokens that also appear in
    two ORDER units → tie across the board → all four should stay UNCERTAIN regardless
    of sort order.
    """
    design = [
        _item("DESIGN", "SM96", finish="ALPINE CASHMERE", view_type="ELEVATION", position="Display 2"),
        _item("DESIGN", "SM96", finish="ALPINE CASHMERE", view_type="ELEVATION", position="Display 4"),
    ]
    order = [
        _item("ORDER", "SM96", finish="ALPINE"),
        _item("ORDER", "SM96", finish="CASHMERE"),
    ]
    groups = _run(design, order)
    uncertain = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN and _sku(g) == "SM96"]
    assert len(uncertain) >= 2, f"Tied claims should stay UNCERTAIN; got {len(uncertain)}"
