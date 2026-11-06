import pytest
from uuid import uuid4
from app.models.core import CanonicalLineItem, DocumentType, MatchGroupStatus, Severity
from app.engines.matching import MatchingEngine, _dedup_view_types
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
    assert mg.cabinet_list_item_id == o.id
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
    assert mg.cabinet_list_item_id == o.id
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
    assert mg.cabinet_list_item_id == o.id
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

    extra_group = next(g for g in groups if g.cabinet_list_item_id == o_extra.id)
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
    assert matched_group.cabinet_list_item_id == o_observed.id
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


# =========================================================================
# Phase 3: view_type deduplication — FLOORPLAN+ELEVATION double-count fix
# =========================================================================

def _vt_item(sku, qty, view_type, position, finish=None):
    return CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.DESIGN,
        raw_sku=sku, normalized_sku=sku, quantity=qty,
        finish=finish,
        source_metadata={"view_type": view_type, "position": position},
    )


def test_elevation_wins_over_floorplan_same_display():
    # B24BP: FLOORPLAN qty=3, ELEVATION qty=2.
    # Dedup keeps ELEVATION (specs). Original qty=2 preserved; resolved_quantity=3 in metadata.
    items = [
        _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island"),
        _vt_item("B24BP", 2, "ELEVATION", "Display 4: Island - Front"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert (result[0].source_metadata or {}).get("view_type") == "ELEVATION"
    assert result[0].quantity == 2  # original ELEVATION qty preserved
    qr = (result[0].source_metadata or {}).get("quantity_resolution", {})
    assert qr["resolved_quantity"] == 3
    assert qr["confidence_status"] == "INFERRED"


def test_different_displays_not_deduplicated():
    # Same SKU in Display 1 and Display 2 → both ELEVATION → keep both (2 items)
    items = [
        _vt_item("W3015BP", 2, "ELEVATION", "Display 1: Kitchen"),
        _vt_item("W3015BP", 1, "ELEVATION", "Display 2: Built-In"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 2


def test_schedule_beats_elevation():
    items = [
        _vt_item("SHC3", 2, "ELEVATION", "Display 4: Island"),
        _vt_item("SHC3", 2, "SCHEDULE", "Display 4: Island"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert (result[0].source_metadata or {}).get("view_type") == "SCHEDULE"


def test_no_view_type_passthrough():
    # Items without view_type (ORDER, ACK) are never filtered
    item = CanonicalLineItem(
        id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
        source_type=DocumentType.ORDER, raw_sku="B24BP", quantity=1,
    )
    result = _dedup_view_types([item])
    assert len(result) == 1


def test_qty_resolution_floorplan_higher():
    # Island: ELEVATION shows 1 front-visible B24BP, FLOORPLAN shows all 3.
    # Original qty=1 preserved; resolved_quantity=3 (INFERRED) stored in metadata.
    items = [
        _vt_item("B24BP", 1, "ELEVATION", "Display 4: Island - Front"),
        _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert result[0].quantity == 1  # original preserved
    qr = (result[0].source_metadata or {}).get("quantity_resolution", {})
    assert qr["resolved_quantity"] == 3
    assert qr["confidence_status"] == "INFERRED"
    assert qr["resolution_method"] == "floorplan_higher_inferred"


def test_qty_resolution_views_agree():
    items = [
        _vt_item("W2442BP", 2, "ELEVATION", "Display 1: Kitchen"),
        _vt_item("W2442BP", 2, "FLOORPLAN", "Display 1: Kitchen"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert result[0].quantity == 2
    qr = (result[0].source_metadata or {}).get("quantity_resolution", {})
    assert qr["resolved_quantity"] == 2
    assert qr["confidence_status"] == "HIGH"


def test_qty_resolution_elevation_higher_needs_review():
    # Unusual: ELEVATION shows more than FLOORPLAN → NEEDS_REVIEW; keep ELEVATION qty
    items = [
        _vt_item("W1218", 3, "ELEVATION", "Display 2: Wall"),
        _vt_item("W1218", 1, "FLOORPLAN", "Display 2: Wall"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert result[0].quantity == 3  # original preserved
    qr = (result[0].source_metadata or {}).get("quantity_resolution", {})
    assert qr["resolved_quantity"] == 3
    assert qr["confidence_status"] == "NEEDS_REVIEW"


def test_canonical_unit_uses_resolved_quantity():
    from app.engines.matching import aggregate_document_items
    items = [
        _vt_item("B24BP", 1, "ELEVATION", "Display 4: Island - Front"),
        _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island"),
    ]
    units = aggregate_document_items(items)
    assert len(units) == 1
    assert units[0].aggregate_quantity == 3  # resolved from FLOORPLAN evidence


def test_elevation_winner_inherits_finish_from_dropped_floorplan():
    # ELEVATION has no finish, FLOORPLAN has finish — winner (ELEVATION) must
    # inherit finish so it reaches the aggregation step with spec data intact.
    items = [
        _vt_item("AFA56S", 1, "ELEVATION", "Display 6 Mudroom", finish=None),
        _vt_item("AFA56S", 1, "FLOORPLAN", "Display 6: Mudroom", finish="LAGOON ON PAINTED OAK"),
    ]
    result = _dedup_view_types(items)
    assert len(result) == 1
    assert result[0].finish == "LAGOON ON PAINTED OAK"
    assert (result[0].source_metadata or {}).get("view_type") == "ELEVATION"


def test_b24bp_elevation_1_floorplan_3_order_3_no_qty_discrepancy():
    # Design has ELEVATION qty=1 and FLOORPLAN qty=3. ORDER has 3.
    # resolved_quantity=3 (INFERRED) → matched, no qty discrepancy.
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()
    d_fp = _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island")
    d_el = _vt_item("B24BP", 1, "ELEVATION", "Display 4: Island - Front")
    o = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id,
        source_type=DocumentType.ORDER, raw_sku="B24BP", normalized_sku="B24BP", quantity=3,
    )
    groups = matcher.match_items([d_fp, d_el], [o], [], proj_id, org_id)
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    qty_discs = [d for d in discs if d.field == "quantity"]
    assert len(qty_discs) == 0, f"Unexpected qty discrepancy: {[(d.design_value, d.order_value) for d in qty_discs]}"


def test_b24bp_elevation_1_floorplan_3_order_2_has_qty_discrepancy():
    # resolved_quantity=3, ORDER=2 → real CHANGED qty discrepancy must be surfaced
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()
    d_fp = _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island")
    d_el = _vt_item("B24BP", 1, "ELEVATION", "Display 4: Island - Front")
    o = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id,
        source_type=DocumentType.ORDER, raw_sku="B24BP", normalized_sku="B24BP", quantity=2,
    )
    groups = matcher.match_items([d_fp, d_el], [o], [], proj_id, org_id)
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    qty_discs = [d for d in discs if d.field == "quantity"]
    assert len(qty_discs) == 1


def test_floorplan_elevation_match_no_false_missing():
    # End-to-end: DESIGN has FLOORPLAN+ELEVATION for same display, ORDER has 1
    # → should match (MATCHED or MATCHED with possible qty discrepancy), NOT MISSING
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()
    d_fp = _vt_item("B24BP", 3, "FLOORPLAN", "Display 4: Island")
    d_el = _vt_item("B24BP", 2, "ELEVATION", "Display 4: Island - Front")
    o = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id,
        source_type=DocumentType.ORDER, raw_sku="B24BP", normalized_sku="B24BP", quantity=2,
    )
    groups = matcher.match_items([d_fp, d_el], [o], [], proj_id, org_id)
    matched = [g for g in groups if g.design_item_id is not None and g.cabinet_list_item_id is not None]
    missing = [g for g in groups if g.status == MatchGroupStatus.MISSING]
    assert len(matched) == 1
    assert len(missing) == 0


def test_needs_review_surfaced_as_discrepancy():
    # ELEVATION (3) > FLOORPLAN (1) → NEEDS_REVIEW must appear as a quantity_resolution discrepancy,
    # not silently MATCHED even when ORDER qty matches ELEVATION.
    proj_id = uuid4()
    org_id = uuid4()
    matcher = MatchingEngine()
    d_fp = _vt_item("W1218", 1, "FLOORPLAN", "Display 2: Wall")
    d_el = _vt_item("W1218", 3, "ELEVATION", "Display 2: Wall - Front")
    o = CanonicalLineItem(
        id=uuid4(), project_id=proj_id, organization_id=org_id,
        source_type=DocumentType.ORDER, raw_sku="W1218", normalized_sku="W1218", quantity=3,
    )
    groups = matcher.match_items([d_fp, d_el], [o], [], proj_id, org_id)
    crosscheck = CrossCheckEngine()
    discs = crosscheck.evaluate(groups, proj_id, org_id)
    nr_discs = [d for d in discs if d.field == "quantity_resolution"]
    assert len(nr_discs) == 1, "NEEDS_REVIEW resolution must surface a discrepancy"
    assert nr_discs[0].source_values["resolution_confidence"] == "NEEDS_REVIEW"
    assert nr_discs[0].source_values["design_raw"] == 3  # ELEVATION qty
    assert nr_discs[0].source_values["order"] == 3
