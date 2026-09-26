import pytest
from uuid import uuid4
from app.models.core import CanonicalLineItem, MatchGroup, MatchGroupStatus, Severity, DocumentType, ItemCategory
from app.engines.matching import MatchingEngine, CanonicalMatchingUnit, aggregate_document_items
from app.engines.crosscheck import CrossCheckEngine
from app.engines.normalization import check_canonical_equivalence, are_skus_equivalent


@pytest.fixture
def matching_engine():
    return MatchingEngine()


@pytest.fixture
def crosscheck_engine():
    return CrossCheckEngine()


@pytest.fixture
def test_ids():
    return uuid4(), uuid4()


def test_1_same_sku_split_into_multiple_po_lines(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET
    )
    # Order split across 2 lines: Qty 1 and Qty 2 -> total 3
    o_item1 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=1, item_category=ItemCategory.CABINET
    )
    o_item2 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET
    )
    a_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item1, o_item2], [a_item], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED
    
    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discrepancies = [d for d in discrepancies if d.field == "quantity"]
    assert len(qty_discrepancies) == 0


def test_2_same_sku_split_into_multiple_ack_lines(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET
    )
    o_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET
    )
    # Ack split into 1 + 1 -> total 2
    a_item1 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET
    )
    a_item2 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item], [a_item1, a_item2], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discrepancies = [d for d in discrepancies if d.field == "quantity"]
    assert len(qty_discrepancies) == 0


def test_3_aggregate_quantity_comparison(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    # Design = 3, Order = 2, Ack = 1 + 1 = 2 -> Introduced At ORDER
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="W3930", quantity=3, item_category=ItemCategory.CABINET
    )
    o_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET
    )
    a_item1 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET
    )
    a_item2 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item], [a_item1, a_item2], proj_id, org_id)
    assert len(mgs) == 1
    
    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discrepancies = [d for d in discrepancies if d.field == "quantity"]
    assert len(qty_discrepancies) == 1
    assert qty_discrepancies[0].introduced_at == DocumentType.ORDER
    assert qty_discrepancies[0].source_values == {"design": 3, "order": 2, "acknowledgement": 2}


def test_4_left_right_variants_must_not_blindly_aggregate(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    # Design has separate L and R
    d_item_l = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="BT18-2-L", quantity=1, item_category=ItemCategory.CABINET
    )
    d_item_r = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="BT18-2-R", quantity=1, item_category=ItemCategory.CABINET
    )
    # Ack only has generic BT18-2 without L/R
    a_item1 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT18-2", quantity=1, item_category=ItemCategory.CABINET
    )
    a_item2 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT18-2", quantity=1, item_category=ItemCategory.CABINET
    )

    d_units = aggregate_document_items([d_item_l, d_item_r])
    assert len(d_units) == 2  # NOT merged blindly!


def test_5_manufacturer_variant_mapping():
    # BFHC12 <-> BPFHC12
    is_eq, conf, eq_type, ev = check_canonical_equivalence(
        sku1="BFHC12", desc1="Base Peninsula Flush Hutch Column 12", dims1={"width": 12}, cat1=ItemCategory.CABINET,
        sku2="BPFHC12", desc2="Base Flush Hutch Column 12", dims2={"width": 12}, cat2=ItemCategory.CABINET
    )
    assert is_eq is True
    assert eq_type == "MANUFACTURER_VARIANT"
    assert conf >= 0.90

    # B18DWB <-> B18BWD18
    is_eq, conf, eq_type, ev = check_canonical_equivalence(
        sku1="B18DWB", desc1="Base 18 Waste Basket Double", dims1={"width": 18}, cat1=ItemCategory.CABINET,
        sku2="B18BWD18", desc2="Base Waste Basket Double 18", dims2={"width": 18}, cat2=ItemCategory.CABINET
    )
    assert is_eq is True
    assert eq_type == "MANUFACTURER_VARIANT"

    # SBA36B <-> SB36B3
    is_eq, conf, eq_type, ev = check_canonical_equivalence(
        sku1="SBA36B", desc1="Sink Base Accessible 36 Butt Doors", dims1={"width": 36}, cat1=ItemCategory.CABINET,
        sku2="SB36B3", desc2="Sink Base 36 Butt Doors", dims2={"width": 36}, cat2=ItemCategory.CABINET
    )
    assert is_eq is True
    assert eq_type == "MANUFACTURER_VARIANT"

    # BEPF334 <-> BEFP334
    is_eq, conf, eq_type, ev = check_canonical_equivalence(
        sku1="BEPF334", desc1="Base End Panel Flush", dims1={"width": 0.75, "height": 34.5}, cat1=ItemCategory.PANEL,
        sku2="BEFP334", desc2="Base End Flush Panel", dims2={"width": 0.75, "height": 34.5}, cat2=ItemCategory.PANEL
    )
    assert is_eq is True
    assert eq_type == "MANUFACTURER_VARIANT"


def test_6_unverified_similar_sku_must_remain_uncertain(matching_engine, test_ids):
    proj_id, org_id = test_ids
    # Vague similarity without dimensions or evidence must not match
    is_eq, conf, eq_type, ev = check_canonical_equivalence(
        sku1="CAB_XYZ_99", desc1="Kitchen Cabinet", dims1=None, cat1=ItemCategory.CABINET,
        sku2="CAB_ABC_11", desc2="Kitchen Cabinet", dims2=None, cat2=ItemCategory.CABINET
    )
    assert is_eq is False


def test_7_appliance_must_not_become_cabinet_missing(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    appliance_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="GR606F-LP", description="Wolf 60 Gas Range",
        item_category=ItemCategory.APPLIANCE
    )
    mgs = matching_engine.match_items([appliance_item], [], [], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MISSING

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    # Appliances are excluded from physical cabinet purchasing presence checks (0 discrepancies)
    assert len(discrepancies) == 0


def test_8_commercial_charge_must_not_become_cabinet_extra(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    charge_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="FREIGHTSURCHARGE",
        description="Freight Surcharge", item_category=ItemCategory.COMMERCIAL_CHARGE
    )
    mgs = matching_engine.match_items([], [], [charge_item], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.EXTRA

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    # Commercial charges do not participate in physical cabinet presence checks (0 discrepancies)
    assert len(discrepancies) == 0


def test_9_design_order_omission_ack_restoration(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="TEST_CAB_1", quantity=1, item_category=ItemCategory.CABINET
    )
    a_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="TEST_CAB_1", quantity=1, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [], [a_item], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.CHANGED

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    presence_discrepancies = [d for d in discrepancies if d.field == "item_presence"]
    assert len(presence_discrepancies) == 1
    # Deterministic 3-way attribution: Design is the first source where the
    # item exists, so that's where it's introduced — even though the Order
    # stage is where it was (temporarily) omitted.
    assert presence_discrepancies[0].introduced_at == DocumentType.DESIGN
    assert presence_discrepancies[0].severity == Severity.WARNING
    assert "OMITTED" in presence_discrepancies[0].explanation
    assert "RESTORED" in presence_discrepancies[0].explanation


def test_10_design_order_change_ack_unchanged(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="W3030", quantity=1, item_category=ItemCategory.CABINET
    )
    o_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="W3030", quantity=2, item_category=ItemCategory.CABINET
    )
    a_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3030", quantity=2, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item], [a_item], proj_id, org_id)
    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discrepancies = [d for d in discrepancies if d.field == "quantity"]
    assert len(qty_discrepancies) == 1
    assert qty_discrepancies[0].introduced_at == DocumentType.ORDER


def test_11_design_order_unchanged_ack_substitution(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="B30", quantity=1, item_category=ItemCategory.CABINET
    )
    o_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="B30", quantity=1, item_category=ItemCategory.CABINET
    )
    a_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="B30-UPGRADE", substitution_sku="B30",
        quantity=1, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item], [a_item], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.CHANGED

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    sku_discrepancies = [d for d in discrepancies if d.field == "sku"]
    assert len(sku_discrepancies) == 1
    assert sku_discrepancies[0].introduced_at == DocumentType.ACKNOWLEDGEMENT
    assert sku_discrepancies[0].severity == Severity.WARNING


def test_12_intentional_filler3_extra(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    o_filler = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="FILLER3", quantity=1, item_category=ItemCategory.FILLER
    )
    a_filler = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="FILLER3", quantity=1, item_category=ItemCategory.FILLER
    )

    mgs = matching_engine.match_items([], [o_filler], [a_filler], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.EXTRA

    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discrepancies) == 1
    assert discrepancies[0].introduced_at == DocumentType.ORDER
    assert discrepancies[0].severity == Severity.CRITICAL


def test_13_bt36b_2_aggregate_quantity_discrepancy(matching_engine, crosscheck_engine, test_ids):
    proj_id, org_id = test_ids
    # Design: 2, Order: 1 + 2 = 3, Ack: 3
    d_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.DESIGN, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET
    )
    o_item1 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=1, item_category=ItemCategory.CABINET
    )
    o_item2 = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET
    )
    a_item = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
        source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET
    )

    mgs = matching_engine.match_items([d_item], [o_item1, o_item2], [a_item], proj_id, org_id)
    assert len(mgs) == 1
    
    discrepancies = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discrepancies = [d for d in discrepancies if d.field == "quantity"]
    assert len(qty_discrepancies) == 1
    assert qty_discrepancies[0].introduced_at == DocumentType.ORDER
    assert qty_discrepancies[0].source_values == {"design": 2, "order": 3, "acknowledgement": 3}
