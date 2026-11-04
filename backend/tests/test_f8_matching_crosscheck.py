import pytest
from uuid import uuid4
from app.models.core import CanonicalLineItem, DocumentType, MatchGroupStatus, Severity
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine

def make_item(source_type, sku, qty=1, dimensions=None, finish=None, sub_sku=None, door_style=None, notes=None, finish_status=None):
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
        substitution_sku=sub_sku,
        door_style=door_style,
        notes=notes,
        finish_status=finish_status,
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

def test_design_item_from_unrelated_display_is_out_of_scope_not_missing():
    # A Design document can be a multi-display catalog spanning far more
    # than the one order being verified. Order+Ack here are scoped to
    # Monroe/Sagewood; the Design document also contains a trim code from
    # an unrelated Jamestown/Dewdrop display sharing the same SKU token.
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d_in_scope = make_item(DocumentType.DESIGN, "W1848R", 1, finish="Monroe Sagewood", door_style="Monroe")
    o = make_item(DocumentType.ORDER, "W1848R", 1, finish="Monroe Sagewood", door_style="Monroe")
    a = make_item(DocumentType.ACKNOWLEDGEMENT, "W1848R", 1, finish="Monroe Sagewood", door_style="Monroe")

    d_unrelated_display = make_item(DocumentType.DESIGN, "TUKT", 1, finish="Jamestown Dewdrop", door_style="Jamestown")

    groups = matcher.match_items(
        [d_in_scope, d_unrelated_display], [o], [a], proj_id, org_id
    )

    matched_group = next(g for g in groups if g.design_item_id == d_in_scope.id)
    assert matched_group.status == MatchGroupStatus.MATCHED

    unrelated_group = next(g for g in groups if g.design_item_id == d_unrelated_display.id)
    assert unrelated_group.status == MatchGroupStatus.OUT_OF_SCOPE

    # OUT_OF_SCOPE items must never generate a "missing from order" alert.
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    assert not any(disc.match_group_id == unrelated_group.id for disc in discs)

def test_observed_finish_wins_disambiguation_tie_over_inherited():
    # Two order candidates share the same word-overlap score against the
    # design reference (both mention "Dune"), which would otherwise abstain
    # to UNCERTAIN as a tie. An OBSERVED finish (printed on that order row
    # itself) is stronger evidence than one only INHERITED_EXPLICIT from a
    # section header, so it must win the tie rather than leaving both
    # candidates unresolved.
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()

    d = make_item(DocumentType.DESIGN, "TUKT", 1, notes="Doorstyle changed to Dune — not shown")
    o_observed = make_item(DocumentType.ORDER, "TUKT", 1, finish="Winston Captiv8 Dune", finish_status="OBSERVED")
    o_inherited = make_item(DocumentType.ORDER, "TUKT", 1, finish="Winston Captiv8 Dune", finish_status="INHERITED_EXPLICIT")

    groups = matcher.match_items([d], [o_observed, o_inherited], [], proj_id, org_id)

    matched_group = next(g for g in groups if g.design_item_id == d.id)
    assert matched_group.order_item_id == o_observed.id
    assert matched_group.status == MatchGroupStatus.MATCHED

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
