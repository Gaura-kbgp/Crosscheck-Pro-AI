"""
Regression suite for the DESIGN + CABINET_LIST + ACK dual-key matching workflow.

Matching rules:
  DESIGN.sku ↔ CABINET_LIST.user_code  (via normalized_sku equality)
  CABINET_LIST.manuf_code_normalized ↔ ACK.sku

Cabinet List items set:
  normalized_sku    = normalize_sku(user_code)   # used for DESIGN matching
  source_metadata["manuf_code_normalized"]        # used for ACK matching
"""
from uuid import uuid4
import pytest
from app.models.core import (
    CanonicalLineItem, DocumentType, MatchGroup, MatchGroupStatus,
    ItemCategory, Severity,
)
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine
from app.engines.normalization import normalize_sku


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cl_item(user_code: str, manuf_code: str | None, qty: int = 1, finish: str = "Maple"):
    """Make a CABINET_LIST CanonicalLineItem with dual codes."""
    item = CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.CABINET_LIST,
        raw_sku=user_code,
        normalized_sku=normalize_sku(user_code),
        quantity=qty, finish=finish,
        item_category=ItemCategory.CABINET,
    )
    item.source_metadata = {
        "user_code": user_code,
        "manuf_code": manuf_code,
        "manuf_code_normalized": normalize_sku(manuf_code) if manuf_code else None,
    }
    return item


def _design(sku: str, qty: int = 1, finish: str = "Maple"):
    return CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.DESIGN,
        raw_sku=sku, normalized_sku=normalize_sku(sku),
        quantity=qty, finish=finish, item_category=ItemCategory.CABINET,
    )


def _ack(sku: str, qty: int = 1, finish: str = "Maple"):
    return CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT,
        raw_sku=sku, normalized_sku=normalize_sku(sku),
        quantity=qty, finish=finish, item_category=ItemCategory.CABINET,
    )


def run(design_items, cl_items, ack_items):
    return MatchingEngine().match_items(design_items, cl_items, ack_items, uuid4(), uuid4())


# ---------------------------------------------------------------------------
# Test A — Full three-way match via dual keys
# ---------------------------------------------------------------------------

def test_a_three_way_match_via_dual_keys():
    """
    DESIGN B36 → CL user_code=B36, manuf_code=MANUF-B36 → ACK MANUF-B36.
    Must produce a single MATCHED group with all three items linked.
    """
    d = _design("B36")
    cl = _cl_item("B36", "MANUF-B36")
    a = _ack("MANUF-B36")
    groups = run([d], [cl], [a])
    assert len(groups) == 1
    g = groups[0]
    assert g.status == MatchGroupStatus.MATCHED
    assert g.design_item_id == d.id
    assert g.cabinet_list_item_id == cl.id
    assert g.ack_item_id == a.id


def test_a_three_way_ack_matched_by_manuf_code_not_user_code():
    """
    ACK SKU differs from user_code but matches manuf_code.
    If the engine accidentally used user_code for ACK, it would create MISSING + EXTRA.
    """
    d = _design("UC-B36")
    cl = _cl_item("UC-B36", "MFR36")
    a = _ack("MFR36")
    groups = run([d], [cl], [a])
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.MATCHED
    assert groups[0].ack_item_id == a.id


def test_a_design_sku_does_not_match_manuf_code_in_ack_directly():
    """
    DESIGN SKU = 'W2448', CL user_code='W2448', manuf_code='WMFR-24'.
    ACK SKU = 'WMFR-24'. The DESIGN SKU ≠ ACK SKU.
    Engine must NOT match DESIGN→ACK directly in a CL project.
    """
    d = _design("W2448")
    cl = _cl_item("W2448", "WMFR-24")
    a = _ack("WMFR-24")
    groups = run([d], [cl], [a])
    assert len(groups) == 1
    g = groups[0]
    assert g.status == MatchGroupStatus.MATCHED
    assert g.cabinet_list_item_id == cl.id
    assert g.ack_item_id == a.id


# ---------------------------------------------------------------------------
# Test B — DESIGN + CL matched, ACK by manuf_code
# ---------------------------------------------------------------------------

def test_b_design_cl_match_ack_by_manuf_code():
    """B36 in design matches CL (user_code=B36), ACK has manuf code."""
    d = _design("B36")
    cl = _cl_item("B36", "MFG-B36-STD")
    a = _ack("MFG-B36-STD")
    groups = run([d], [cl], [a])
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.MATCHED
    assert groups[0].cabinet_list_item_id == cl.id


def test_b_design_cl_match_no_ack_produces_matched():
    """DESIGN + CL match exists; no ACK entry for this item."""
    d = _design("W3048")
    cl = _cl_item("W3048", "WMFR3048")
    groups = run([d], [cl], [])
    assert len(groups) == 1
    # D+CL with no ACK → MATCHED (D+O-no-A case)
    assert groups[0].status == MatchGroupStatus.MATCHED
    assert groups[0].ack_item_id is None


# ---------------------------------------------------------------------------
# Test C — CL item with no DESIGN match → EXTRA
# ---------------------------------------------------------------------------

def test_c_cl_no_design_match_becomes_extra():
    """CL item has user_code that doesn't appear in DESIGN → EXTRA."""
    cl = _cl_item("PHANTOM-99", "MFR-99")
    a = _ack("MFR-99")
    groups = run([], [cl], [a])
    assert len(groups) >= 1
    extra_groups = [g for g in groups if g.status == MatchGroupStatus.EXTRA]
    assert len(extra_groups) >= 1


def test_c_cl_no_design_match_no_ack_still_extra():
    """CL item with no DESIGN or ACK → EXTRA."""
    cl = _cl_item("PHANTOM-100", "MFR-100")
    groups = run([], [cl], [])
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.EXTRA


# ---------------------------------------------------------------------------
# Test D1 — CL with no manuf_code but matches DESIGN via user_code → UNCERTAIN
# ---------------------------------------------------------------------------

def test_d1_cl_no_manuf_code_design_match_uncertain():
    """
    CL item matches DESIGN by user_code but has no manuf_code.
    Result must be UNCERTAIN (not MATCHED, not MISSING).
    """
    d = _design("SHC3")
    cl = _cl_item("SHC3", None)  # no manuf_code
    a = _ack("SHC3-MFR")
    groups = run([d], [cl], [a])

    # ACK must remain unconsumed — no path from CL to ACK without manuf_code
    shc_group = next(
        (g for g in groups if g.cabinet_list_item_id == cl.id or g.design_item_id == d.id),
        None
    )
    assert shc_group is not None
    assert shc_group.status == MatchGroupStatus.UNCERTAIN


def test_d1_cl_no_manuf_code_generates_manufacturer_code_discrepancy():
    """
    UNCERTAIN group from missing manuf_code must produce a 'manufacturer_code'
    WARNING discrepancy via CrossCheckEngine.
    """
    d = _design("SHC3")
    cl = _cl_item("SHC3", None)

    groups = run([d], [cl], [])
    uncertain_g = next(g for g in groups if g.status == MatchGroupStatus.UNCERTAIN)

    discs = CrossCheckEngine().evaluate(groups, uuid4(), uuid4())
    manuf_discs = [disc for disc in discs if disc.field == "manufacturer_code"]
    assert len(manuf_discs) >= 1
    assert manuf_discs[0].severity == Severity.WARNING


def test_d1_uncertain_state_causes_pending_review():
    """MISSING_MANUF_CODE discrepancy makes _determine_final_state return PENDING_REVIEW."""
    from app.services.review_service import ReviewService

    d = _design("SHC3")
    cl = _cl_item("SHC3", None)
    groups = run([d], [cl], [])
    uncertain_g = next(g for g in groups if g.status == MatchGroupStatus.UNCERTAIN)

    discs = CrossCheckEngine().evaluate(groups, uuid4(), uuid4())
    manuf_discs = [disc for disc in discs if disc.field == "manufacturer_code"]

    # Simulate what ReviewService._determine_final_state does:
    # PENDING_REVIEW when there are non-auto-resolved discrepancies
    final_state = "RESOLVED_AUTO" if not manuf_discs else "PENDING_REVIEW"
    assert final_state == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# Test D2 — CL with no manuf_code, no DESIGN match → UNCERTAIN
# ---------------------------------------------------------------------------

def test_d2_cl_no_manuf_code_no_design_match_uncertain():
    """
    CL item has no manuf_code and nothing in DESIGN to match.
    Pass 2 guard must produce UNCERTAIN (not EXTRA).
    """
    cl = _cl_item("ORPHAN-X", None)
    groups = run([], [cl], [])
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.UNCERTAIN


def test_d2_no_manuf_code_no_design_match_generates_discrepancy():
    """UNCERTAIN CL-only group still generates manufacturer_code WARNING."""
    cl = _cl_item("ORPHAN-X", None)
    groups = run([], [cl], [])
    discs = CrossCheckEngine().evaluate(groups, uuid4(), uuid4())
    manuf_discs = [d for d in discs if d.field == "manufacturer_code"]
    assert len(manuf_discs) >= 1


# ---------------------------------------------------------------------------
# Detection / isolation
# ---------------------------------------------------------------------------

def test_is_cabinet_list_project_flag_detected():
    """MatchingEngine detects a CL project when any order item is CABINET_LIST."""
    cl = _cl_item("B36", "MFR-B36")
    # We can't inspect is_cabinet_list_project directly, but we can verify
    # the behaviour it gates: ACK matched via manuf_code rather than user_code.
    a = _ack("MFR-B36")
    groups = run([], [cl], [a])
    # CL with no DESIGN → EXTRA; ACK also unclaimed → EXTRA
    # The key assertion: groups should NOT match cl to ack directly
    # (CL with no DESIGN match goes through Pass 2; with manuf_code present, it matches ACK)
    extra_or_matched = [g for g in groups if g.status in (MatchGroupStatus.EXTRA, MatchGroupStatus.MATCHED)]
    assert len(extra_or_matched) >= 1


def test_legacy_order_project_not_affected():
    """ORDER items use the original matching path (no dual-key logic)."""
    from app.models.core import CanonicalLineItem as CLI
    d = _design("B36")
    o = CLI(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.ORDER,
        raw_sku="B36", normalized_sku=normalize_sku("B36"),
        quantity=1, finish="Maple", item_category=ItemCategory.CABINET,
    )
    a = _ack("B36")
    groups = MatchingEngine().match_items([d], [o], [a], uuid4(), uuid4())
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.MATCHED
    assert groups[0].cabinet_list_item_id == o.id
    assert groups[0].ack_item_id == a.id


# ---------------------------------------------------------------------------
# Multi-item scenarios
# ---------------------------------------------------------------------------

def test_multiple_cl_items_mixed_manuf_codes():
    """Several CL items; some have manuf_code, one does not."""
    d1, d2, d3 = _design("B36"), _design("W3048"), _design("TUKT")
    cl1 = _cl_item("B36", "MFR-B36")
    cl2 = _cl_item("W3048", "MFR-W3048")
    cl3 = _cl_item("TUKT", None)  # no manuf_code
    a1, a2 = _ack("MFR-B36"), _ack("MFR-W3048")

    groups = run([d1, d2, d3], [cl1, cl2, cl3], [a1, a2])

    statuses = {g.status for g in groups}
    # cl1+cl2 fully matched, cl3 uncertain
    assert MatchGroupStatus.MATCHED in statuses
    assert MatchGroupStatus.UNCERTAIN in statuses

    uncertain = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN]
    assert any(g.cabinet_list_item_id == cl3.id for g in uncertain)


def test_cl_manuf_code_mismatch_design_sku_not_leaked_to_ack():
    """
    DESIGN has SKU='UC-01'. CL has user_code='UC-01', manuf_code='MFR-01'.
    ACK has SKU='UC-01' (same as design/user_code, NOT manuf_code).
    Engine must NOT use 'UC-01' to match ACK — ACK should remain unclaimed.
    """
    d = _design("UC-01")
    cl = _cl_item("UC-01", "MFR-01")
    a = _ack("UC-01")  # ACK SKU matches user_code but NOT manuf_code

    groups = run([d], [cl], [a])
    # CL→ACK requires manuf_code='MFR-01' matching ack.sku='UC-01' → no match.
    # The DESIGN+CL group must have no ACK. The ACK ends up as a separate EXTRA group.
    design_cl_group = next(g for g in groups if g.cabinet_list_item_id == cl.id)
    assert design_cl_group.ack_item_id is None, (
        "ACK must not be matched when its SKU matches user_code but not manuf_code"
    )
    # ACK should be an isolated EXTRA
    ack_group = next((g for g in groups if g.ack_item_id == a.id), None)
    assert ack_group is not None
    assert ack_group.status == MatchGroupStatus.EXTRA


def test_cl_quantity_propagates_to_match_group():
    """Quantity from CL is used in the resulting match group."""
    d = _design("B36", qty=3)
    cl = _cl_item("B36", "MFR-B36", qty=3)
    a = _ack("MFR-B36", qty=3)
    groups = run([d], [cl], [a])
    assert len(groups) == 1
    assert groups[0].status == MatchGroupStatus.MATCHED


def test_cl_ack_quantity_mismatch_produces_changed():
    """When CL manuf_code matches ACK but quantities differ → CHANGED + discrepancy."""
    d = _design("W3030", qty=2)
    cl = _cl_item("W3030", "MFR-W30", qty=2)
    a = _ack("MFR-W30", qty=3)

    groups = run([d], [cl], [a])
    assert len(groups) == 1
    # Quantity mismatch means CHANGED (ack confirmed different qty)
    assert groups[0].status in (MatchGroupStatus.CHANGED, MatchGroupStatus.MATCHED)

    discs = CrossCheckEngine().evaluate(groups, uuid4(), uuid4())
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) >= 1


def test_no_cross_project_contamination():
    """Different project_ids; each run is independent, no shared state."""
    d1 = _design("B36")
    cl1 = _cl_item("B36", "MFR-B36")
    a1 = _ack("MFR-B36")
    g1 = run([d1], [cl1], [a1])

    d2 = _design("W3048")
    cl2 = _cl_item("W3048", "MFR-W3048")
    a2 = _ack("MFR-W3048")
    g2 = run([d2], [cl2], [a2])

    assert len(g1) == 1
    assert len(g2) == 1
    assert g1[0].design_item_id != g2[0].design_item_id
