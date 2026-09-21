import pytest
from uuid import uuid4
from app.models.core import CanonicalLineItem, DocumentType, MatchGroupStatus, Severity
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine

def make_item(source_type, sku, qty=1, dimensions=None, finish=None, sub_sku=None):
    return CanonicalLineItem(
        id=uuid4(),
        project_id=uuid4(),
        organization_id=uuid4(),
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku,
        quantity=qty,
        dimensions=dimensions,
        finish=finish,
        substitution_sku=sub_sku
    )

def test_exact_3way_matching():
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d = make_item(DocumentType.DESIGN, "CAB-24-L", 1, {"width": 24, "height": 34.5})
    o = make_item(DocumentType.ORDER, "CAB-24-L", 1, "24 W")
    a = make_item(DocumentType.ACKNOWLEDGEMENT, "CAB-24-L", 1, "24 W")

    groups = matcher.match_items([d], [o], [a], proj_id, org_id)
    assert len(groups) == 1
    mg = groups[0]
    assert mg.status == MatchGroupStatus.MATCHED
    assert mg.design_item_id == d.id
    assert mg.order_item_id == o.id
    assert mg.ack_item_id == a.id

def test_token_equivalent_matching():
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d = make_item(DocumentType.DESIGN, "B36 1TD BUTT", 1)
    o = make_item(DocumentType.ORDER, "B36-1TD-BUTT", 2)
    a = make_item(DocumentType.ACKNOWLEDGEMENT, "B361TDBUTT", 2)

    groups = matcher.match_items([d], [o], [a], proj_id, org_id)
    assert len(groups) == 1
    mg = groups[0]
    assert mg.design_item_id == d.id
    assert mg.order_item_id == o.id
    assert mg.ack_item_id == a.id

    # Test crosscheck discrepancy: Qty changed in Order
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].field == "quantity"
    assert discs[0].introduced_at == DocumentType.ORDER

def test_manufacturer_substitution_matching():
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d = make_item(DocumentType.DESIGN, "W2130R", 1)
    o = make_item(DocumentType.ORDER, "W2130R", 1)
    a = make_item(DocumentType.ACKNOWLEDGEMENT, "W2142R", 1, sub_sku="W2130R")

    groups = matcher.match_items([d], [o], [a], proj_id, org_id)
    assert len(groups) == 1
    mg = groups[0]
    assert mg.design_item_id == d.id
    assert mg.order_item_id == o.id
    assert mg.ack_item_id == a.id

    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    assert any(disc.field == "sku" and disc.introduced_at == DocumentType.ACKNOWLEDGEMENT for disc in discs)

def test_missing_and_extra_detection():
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d = make_item(DocumentType.DESIGN, "SB33 BUTT", 1)
    o_extra = make_item(DocumentType.ORDER, "FILLER-3", 1)

    groups = matcher.match_items([d], [o_extra], [], proj_id, org_id)
    assert len(groups) == 2

    missing_group = next(g for g in groups if g.design_item_id == d.id)
    assert missing_group.status == MatchGroupStatus.MISSING

    extra_group = next(g for g in groups if g.order_item_id == o_extra.id)
    assert extra_group.status == MatchGroupStatus.EXTRA

    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    assert any(disc.field == "item_presence" and disc.introduced_at == DocumentType.ORDER for disc in discs)

def test_safe_introduced_at_with_unspecified_design_dimension():
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    # Design has NO dimension specified
    d = make_item(DocumentType.DESIGN, "RANGE-30", 1, dimensions=None)
    o = make_item(DocumentType.ORDER, "RANGE-30", 1, dimensions="30\" opening")
    a = make_item(DocumentType.ACKNOWLEDGEMENT, "RANGE-30", 1, dimensions="30\" opening")

    groups = matcher.match_items([d], [o], [a], proj_id, org_id)
    assert len(groups) == 1

    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    # Since Design was unspecified and Order = Ack, there should be NO dimension discrepancy
    dim_discs = [disc for disc in discs if disc.field == "dimensions"]
    assert len(dim_discs) == 0
