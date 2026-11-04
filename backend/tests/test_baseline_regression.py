"""
Regression suite tracking the acceptance criteria from the CrossCheckPro
implementation brief's "Baseline" and "Planted changes" test classes
(section 9). These don't need the original PDFs or an AI call — they
construct the same 15-SKU-group baseline directly from the brief's
documented evidence table (source line / SKU / qty / finish) and assert
the matching + crosscheck engines produce the expected decisions.

Baseline evidence (brief §3): a single order, Monroe/Sagewood/PHW,
plywood construction, FX drawer box, scoped to one display. All three
documents (Design, Order, Acknowledgement) agree unless a test below
explicitly plants a change.
"""
from uuid import uuid4
from app.models.core import CanonicalLineItem, DocumentType, MatchGroupStatus, ItemCategory
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine

FINISH = "Monroe Sagewood PHW"

# (sku, qty) pairs for the 15 SKU groups in the brief's baseline evidence map.
BASELINE_SKUS = [
    ("W1848L", 1), ("W1848R", 1), ("EZCW2448R", 1), ("W3048BP", 1),
    ("D2B21", 1), ("B18-TCDL", 1), ("BCC45LH", 1), ("D3B36", 1),
    ("F330", 2), ("TP96", 2), ("STR396-SH", 2), ("F348", 1),
    ("TUKT", 1), ("SM96", 3), ("QR96", 2),
]


def make_item(source_type, sku, qty=1, finish=FINISH):
    # These tests exercise presence/quantity/finish matching, not SKU-to-
    # category classification (QR96/TUKT/etc. would otherwise be
    # auto-classified as trim/molding and excluded from discrepancies by
    # CATEGORY_DISCREPANCY_POLICY — a separate, correct policy that isn't
    # what's under test here), so category is pinned to CABINET explicitly.
    return CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=source_type, raw_sku=sku, normalized_sku=sku,
        quantity=qty, finish=finish, item_category=ItemCategory.CABINET,
    )


def _build_baseline():
    design = [make_item(DocumentType.DESIGN, sku, qty) for sku, qty in BASELINE_SKUS]
    order = [make_item(DocumentType.ORDER, sku, qty) for sku, qty in BASELINE_SKUS]
    ack = [make_item(DocumentType.ACKNOWLEDGEMENT, sku, qty) for sku, qty in BASELINE_SKUS]
    return design, order, ack


def test_baseline_15_groups_no_false_extra_or_missing():
    """
    Brief §2/§9: the baseline has 15 SKU groups that genuinely agree across
    all three documents. The observed failure was 5 MATCHED / 10 EXTRA —
    10 false alerts. None of the 15 groups may resolve to EXTRA or MISSING.
    """
    design, order, ack = _build_baseline()
    matcher = MatchingEngine()
    groups = matcher.match_items(design, order, ack, uuid4(), uuid4())

    assert len(groups) == len(BASELINE_SKUS)
    false_alerts = [g for g in groups if g.status in (MatchGroupStatus.EXTRA, MatchGroupStatus.MISSING)]
    assert false_alerts == [], f"False EXTRA/MISSING alerts: {[g.design_item.raw_sku or g.order_item.raw_sku for g in false_alerts]}"
    assert all(g.status in (MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED) for g in groups)

    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, uuid4(), uuid4())
    assert discs == [], "A fully agreeing baseline must raise zero discrepancies"


def test_planted_quantity_change_detected():
    """Brief §9 planted change: SM96 PO qty 3 -> 4."""
    design, order, ack = _build_baseline()
    for item in order:
        if item.raw_sku == "SM96":
            item.quantity = 4
    for item in ack:
        if item.raw_sku == "SM96":
            item.quantity = 4  # manufacturer confirmed the changed quantity

    matcher = MatchingEngine()
    groups = matcher.match_items(design, order, ack, uuid4(), uuid4())
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, uuid4(), uuid4())

    qty_discs = [d for d in discs if d.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].comparison_values == {"expected": 3, "actual": 4}
    assert qty_discs[0].introduced_at == DocumentType.ORDER

    # Every other SKU group must still be clean — a planted change must
    # never bleed into unrelated groups.
    other_discs = [d for d in discs if d.field != "quantity"]
    assert other_discs == []


def test_planted_finish_change_detected():
    """Brief §9 planted change: D3B36 finish Sagewood -> Cashmere (in the Ack)."""
    design, order, ack = _build_baseline()
    for item in ack:
        if item.raw_sku == "D3B36":
            item.finish = "Cashmere"

    matcher = MatchingEngine()
    groups = matcher.match_items(design, order, ack, uuid4(), uuid4())
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, uuid4(), uuid4())

    finish_discs = [d for d in discs if d.field == "finish"]
    assert len(finish_discs) == 1
    assert finish_discs[0].introduced_at == DocumentType.ACKNOWLEDGEMENT
    assert finish_discs[0].comparison_values["actual"] == "Cashmere"


def test_planted_po_absence_detected():
    """
    Brief §9 planted change: remove QR96 qty 2 from the PO (still present in
    Design and restored/confirmed in the Acknowledgement). This is a
    design-to-order omission, not a plain MISSING/EXTRA — the crosscheck
    engine's 3-way state-transition case must fire.
    """
    design, order, ack = _build_baseline()
    order = [item for item in order if item.raw_sku != "QR96"]

    matcher = MatchingEngine()
    groups = matcher.match_items(design, order, ack, uuid4(), uuid4())
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, uuid4(), uuid4())

    qr96_group = next(g for g in groups if (g.design_item and g.design_item.raw_sku == "QR96"))
    assert qr96_group.order_item_id is None
    assert qr96_group.ack_item_id is not None

    presence_discs = [d for d in discs if d.field == "item_presence" and d.match_group_id == qr96_group.id]
    assert len(presence_discs) == 1
    assert presence_discs[0].source_values == {"design": "PRESENT", "order": "OMITTED", "acknowledgement": "RESTORED"}
