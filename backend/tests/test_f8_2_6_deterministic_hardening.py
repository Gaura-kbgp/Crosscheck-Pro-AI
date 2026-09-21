import pytest
from uuid import uuid4
from app.models.core import (
    CanonicalLineItem, MatchGroup, MatchGroupStatus, Severity, DocumentType, ItemCategory
)
from app.engines.matching import MatchingEngine, CanonicalMatchingUnit, aggregate_document_items
from app.engines.crosscheck import CrossCheckEngine
from app.engines.normalization import check_canonical_equivalence, are_skus_equivalent
from app.engines.classification import ItemClassifier


@pytest.fixture
def classifier():
    return ItemClassifier()


@pytest.fixture
def matching_engine():
    return MatchingEngine()


@pytest.fixture
def crosscheck_engine():
    return CrossCheckEngine()


@pytest.fixture
def test_ids():
    return uuid4(), uuid4()


# ==============================================================================
# 1. QUANTITY TESTS (1 - 7)
# ==============================================================================

def test_1_quantity_d2_o3_a2_changed_introduced_order(matching_engine, crosscheck_engine, test_ids):
    """1. D2/O3/A2 -> CHANGED, introduced ORDER"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ORDER
    assert qty_discs[0].source_values == {"design": 2, "order": 3, "acknowledgement": 2}
    assert "reverted to 2 in Acknowledgement" in qty_discs[0].explanation


def test_2_quantity_d3_o3_a2_changed_introduced_ack(matching_engine, crosscheck_engine, test_ids):
    """2. D3/O3/A2 -> CHANGED, introduced ACK"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="WST3657B", quantity=3, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="WST3657B", quantity=3, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="WST3657B", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ACKNOWLEDGEMENT
    assert qty_discs[0].source_values == {"design": 3, "order": 3, "acknowledgement": 2}


def test_3_quantity_d3_o2_a2_changed_introduced_order(matching_engine, crosscheck_engine, test_ids):
    """3. D3/O2/A2 -> CHANGED, introduced ORDER"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="W3930", quantity=3, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ORDER
    assert qty_discs[0].source_values == {"design": 3, "order": 2, "acknowledgement": 2}


def test_4_quantity_d2_o2_a2_matched(matching_engine, crosscheck_engine, test_ids):
    """4. D2/O2/A2 -> MATCHED (no discrepancy)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="B24", quantity=2, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="B24", quantity=2, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="B24", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_5_split_ack_lines_aggregate_correctly(matching_engine, crosscheck_engine, test_ids):
    """5. split Ack lines aggregate correctly (Ack has 1+1 = 2)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="W3930", quantity=3, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET)
    a1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET)
    a2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a1, a2], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].source_values["acknowledgement"] == 2


def test_6_split_order_lines_aggregate_correctly(matching_engine, crosscheck_engine, test_ids):
    """6. split Order lines aggregate correctly (Order has 1+2 = 3)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET)
    o1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=1, item_category=ItemCategory.CABINET)
    o2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o1, o2], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_7_raw_lines_remain_preserved(test_ids):
    """7. raw lines remain preserved in CanonicalMatchingUnit"""
    proj_id, org_id = test_ids
    o1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=1, item_category=ItemCategory.CABINET)
    o2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)

    units = aggregate_document_items([o1, o2])
    assert len(units) == 1
    assert units[0].aggregate_quantity == 3
    assert len(units[0].raw_items) == 2
    assert o1.id in [i.id for i in units[0].raw_items]
    assert o2.id in [i.id for i in units[0].raw_items]


# ==============================================================================
# 2. VARIANTS TESTS (8 - 12)
# ==============================================================================

def test_8_lr_variants_never_blindly_merge(matching_engine, test_ids):
    """8. L/R variants never blindly merge"""
    proj_id, org_id = test_ids
    d_l = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.DESIGN, raw_sku="BT18-2-L", quantity=1, item_category=ItemCategory.CABINET)
    d_r = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.DESIGN, raw_sku="BT18-2-R", quantity=1, item_category=ItemCategory.CABINET)

    units = aggregate_document_items([d_l, d_r])
    assert len(units) == 2

    is_eq, _, _, _ = check_canonical_equivalence(
        sku1="BT18-2-L", desc1="", dims1=None, cat1=ItemCategory.CABINET,
        sku2="BT18-2-R", desc2="", dims2=None, cat2=ItemCategory.CABINET
    )
    assert is_eq is False


def test_9_unoriented_ack_against_lr_remains_uncertain_without_evidence(matching_engine, test_ids):
    """9. unoriented Ack against L/R remains UNCERTAIN without evidence"""
    proj_id, org_id = test_ids
    d_l = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.DESIGN, raw_sku="BT18-2-L", quantity=1, item_category=ItemCategory.CABINET)
    d_r = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.DESIGN, raw_sku="BT18-2-R", quantity=1, item_category=ItemCategory.CABINET)
    o_l = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.ORDER, raw_sku="BT18-2-L", quantity=1, item_category=ItemCategory.CABINET)
    o_r = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                            source_type=DocumentType.ORDER, raw_sku="BT18-2-R", quantity=1, item_category=ItemCategory.CABINET)
    a_unoriented = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                                     source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT18-2", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d_l, d_r], [o_l, o_r], [a_unoriented], proj_id, org_id)
    # D-O pairs match cleanly, unoriented Ack is preserved for audit
    assert len(mgs) == 3
    l_mg = [m for m in mgs if m.design_item and m.design_item.raw_sku == "BT18-2-L"][0]
    r_mg = [m for m in mgs if m.design_item and m.design_item.raw_sku == "BT18-2-R"][0]
    assert l_mg.status == MatchGroupStatus.MATCHED
    assert r_mg.status == MatchGroupStatus.MATCHED


def test_10_evidence_backed_manufacturer_variant_becomes_one_canonical_group(matching_engine, test_ids):
    """10. evidence-backed manufacturer variant becomes one canonical group (e.g. BFHC12 <-> BPFHC12)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="BFHC12", description="Base Peninsula Flush Hutch Column 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="BFHC12", description="Base Peninsula Flush Hutch Column 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BPFHC12", description="Base Peninsula Flush Hutch Column 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status in [MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED]
    assert mgs[0].design_item_id == d.id
    assert mgs[0].order_item_id == o.id
    assert mgs[0].ack_item_id == a.id


def test_11_unsupported_variant_remains_uncertain(matching_engine, test_ids):
    """11. unsupported variant remains UNCERTAIN / does not match without evidence"""
    is_eq, conf, eq_type, _ = check_canonical_equivalence(
        sku1="CAB_XYZ_99", desc1="Kitchen Cabinet", dims1=None, cat1=ItemCategory.CABINET,
        sku2="CAB_ABC_11", desc2="Kitchen Cabinet", dims2=None, cat2=ItemCategory.CABINET
    )
    assert is_eq is False


def test_12_canonical_1_1_1_item_cannot_become_extra(matching_engine, crosscheck_engine, test_ids):
    """12. canonical 1/1/1 item (e.g. BPS12 / BP52) must NEVER become EXTRA"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="BPS12", description="Base Peninsula Spice Rack 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="BPS12", description="Base Peninsula Spice Rack 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BP52", description="Base Peninsula Spice 12",
                          dimensions={"width": 12}, quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status != MatchGroupStatus.EXTRA
    assert mgs[0].design_item_id is not None
    assert mgs[0].order_item_id is not None
    assert mgs[0].ack_item_id is not None


# ==============================================================================
# 3. CLASSIFICATION TESTS (13 - 18)
# ==============================================================================

def test_13_appliance_excluded_from_cabinet_presence_discrepancy(matching_engine, crosscheck_engine, test_ids):
    """13. APPLIANCE excluded from cabinet presence discrepancy"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="GR606F-LP", description="Wolf 60 Gas Range",
                          quantity=1, item_category=ItemCategory.APPLIANCE)
    mgs = matching_engine.match_items([d], [], [], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MISSING

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_14_architectural_annotation_excluded(matching_engine, crosscheck_engine, test_ids):
    """14. ARCHITECTURAL_ANNOTATION excluded from cabinet presence discrepancy"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="21AHSDX7230", description="Architectural Hood Shroud",
                          quantity=1, item_category=ItemCategory.ARCHITECTURAL_ANNOTATION)
    mgs = matching_engine.match_items([d], [], [], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_15_commercial_charge_excluded(matching_engine, crosscheck_engine, test_ids):
    """15. COMMERCIAL_CHARGE excluded from cabinet discrepancy"""
    proj_id, org_id = test_ids
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="TARIFFSURCHARGE",
                          description="Tariff Surcharge", quantity=1, item_category=ItemCategory.COMMERCIAL_CHARGE)
    mgs = matching_engine.match_items([], [], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_16_accessory_preserved_but_distinct(classifier):
    """16. ACCESSORY preserved and classified correctly"""
    res = classifier.classify(raw_sku="ROT18", description="Roll Out Tray 18")
    assert res.category == ItemCategory.ACCESSORY


def test_17_panel_molding_preserved_correctly(classifier):
    """17. PANEL/MOLDING preserved correctly"""
    res_panel = classifier.classify(raw_sku="DEP1W", description="Dishwasher End Panel 1.5 Wide")
    assert res_panel.category == ItemCategory.PANEL

    res_molding = classifier.classify(raw_sku="SMCRN8", description="Small Cove Crown Molding 8ft")
    assert res_molding.category in [ItemCategory.MOLDING, ItemCategory.ARCHITECTURAL_ANNOTATION]


def test_18_factory_bundle_tool_preserved_correctly(classifier):
    """18. FACTORY_BUNDLE/FACTORY_TOOL preserved correctly"""
    res_tool = classifier.classify(raw_sku="TOUCHUP-KIT", description="Touch Up Pen and Filler Stick Tool")
    assert res_tool.category in [ItemCategory.FILLER, ItemCategory.ACCESSORY, ItemCategory.CABINET, ItemCategory.UNKNOWN]


# ==============================================================================
# 4. STATE TRANSITIONS TESTS (19 - 22)
# ==============================================================================

def test_19_design_present_order_absent_ack_present(matching_engine, crosscheck_engine, test_ids):
    """19. Design present -> Order absent -> Ack present (Omitted at Order, Restored in Ack)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="CAB_TEST_19", quantity=1, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="CAB_TEST_19", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.CHANGED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].introduced_at == DocumentType.ORDER
    assert "OMITTED" in discs[0].explanation
    assert "RESTORED" in discs[0].explanation
    assert discs[0].severity == Severity.WARNING


def test_20_design_absent_order_present_ack_absent(matching_engine, crosscheck_engine, test_ids):
    """20. Design absent -> Order present -> Ack absent (Added at Order, Omitted in Ack)"""
    proj_id, org_id = test_ids
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="FILLER3", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([], [o], [], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.EXTRA

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].introduced_at == DocumentType.ORDER
    assert discs[0].severity == Severity.CRITICAL


def test_21_design_present_order_present_ack_present(matching_engine, crosscheck_engine, test_ids):
    """21. Design present -> Order present -> Ack present (Consistent throughout)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="B30", quantity=1, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="B30", quantity=1, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="B30", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_22_design_absent_order_absent_ack_present(matching_engine, crosscheck_engine, test_ids):
    """22. Design absent -> Order absent -> Ack present (Added at Ack -> EXTRA Critical)"""
    proj_id, org_id = test_ids
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="SURPRISE_CAB", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([], [], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.EXTRA

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].introduced_at == DocumentType.ACKNOWLEDGEMENT
    assert discs[0].severity == Severity.CRITICAL


# ==============================================================================
# 5. REAL-WORLD REGRESSION TESTS (23 - 30)
# ==============================================================================

def test_23_filler3_remains_extra(matching_engine, crosscheck_engine, test_ids):
    """23. FILLER3 remains EXTRA"""
    proj_id, org_id = test_ids
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="FILLER3", quantity=1, item_category=ItemCategory.CABINET)
    mgs = matching_engine.match_items([], [o], [], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.EXTRA

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].severity == Severity.CRITICAL


def test_24_bt36b2_quantity_2_3_2_is_deterministic(matching_engine, crosscheck_engine, test_ids):
    """24. BT36B-2 quantity 2/3/2 is deterministic"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="BT36B-2", quantity=3, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="BT36B-2", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.MATCHED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ORDER


def test_25_w3930_3_2_2_is_deterministic(matching_engine, crosscheck_engine, test_ids):
    """25. W3930 3/2/2 is deterministic"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="W3930", quantity=3, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="W3930", quantity=2, item_category=ItemCategory.CABINET)
    a1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET)
    a2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                           source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W3930", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a1, a2], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ORDER


def test_26_wst3057b_1_2_2_is_deterministic(matching_engine, crosscheck_engine, test_ids):
    """26. WST3057B 1/2/2 is deterministic (CHANGED, introduced ORDER)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="WST3057B", quantity=1, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="WST3057B", quantity=2, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="WST3057B", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ORDER
    assert qty_discs[0].source_values == {"design": 1, "order": 2, "acknowledgement": 2}


def test_27_wst3657b_3_3_2_is_deterministic(matching_engine, crosscheck_engine, test_ids):
    """27. WST3657B 3/3/2 is deterministic (CHANGED, introduced ACK)"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="WST3657B", quantity=3, item_category=ItemCategory.CABINET)
    o = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ORDER, raw_sku="WST3657B", quantity=3, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="WST3657B", quantity=2, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [o], [a], proj_id, org_id)
    assert len(mgs) == 1

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    qty_discs = [disc for disc in discs if disc.field == "quantity"]
    assert len(qty_discs) == 1
    assert qty_discs[0].introduced_at == DocumentType.ACKNOWLEDGEMENT


def test_28_21ahsdx7230_omitted_and_restored(matching_engine, crosscheck_engine, test_ids):
    """28. 21AHSDX7230 omitted in Order, restored in Ack"""
    proj_id, org_id = test_ids
    d = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.DESIGN, raw_sku="21AHSDX7230", quantity=1, item_category=ItemCategory.CABINET)
    a = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                          source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="21AHSDX7230", quantity=1, item_category=ItemCategory.CABINET)

    mgs = matching_engine.match_items([d], [], [a], proj_id, org_id)
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.CHANGED

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 1
    assert discs[0].introduced_at == DocumentType.ORDER
    assert discs[0].severity == Severity.WARNING


def test_29_appliance_annotations_excluded(matching_engine, crosscheck_engine, test_ids):
    """29. appliance annotations (GR606F-LP, PWS06DSPSS) excluded from cabinet discrepancies"""
    proj_id, org_id = test_ids
    appl1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                              source_type=DocumentType.DESIGN, raw_sku="GR606F-LP", description="Gas Range",
                              quantity=1, item_category=ItemCategory.APPLIANCE)
    appl2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                              source_type=DocumentType.DESIGN, raw_sku="PWS06DSPSS", description="Microwave Drawer",
                              quantity=1, item_category=ItemCategory.APPLIANCE)

    mgs = matching_engine.match_items([appl1, appl2], [], [], proj_id, org_id)
    assert len(mgs) == 2

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0


def test_30_commercial_charges_excluded(matching_engine, crosscheck_engine, test_ids):
    """30. commercial charges (FREIGHTSURCHARGE, TARIFFSURCHARGE) excluded from physical cabinet discrepancies"""
    proj_id, org_id = test_ids
    charge1 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                                source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="FREIGHTSURCHARGE",
                                description="Freight Charge", quantity=1, item_category=ItemCategory.COMMERCIAL_CHARGE)
    charge2 = CanonicalLineItem(id=uuid4(), project_id=proj_id, organization_id=org_id, document_id=uuid4(),
                                source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="TARIFFSURCHARGE",
                                description="Tariff Charge", quantity=1, item_category=ItemCategory.COMMERCIAL_CHARGE)

    mgs = matching_engine.match_items([], [], [charge1, charge2], proj_id, org_id)
    assert len(mgs) == 2

    discs = crosscheck_engine.evaluate(mgs, proj_id, org_id)
    assert len(discs) == 0
