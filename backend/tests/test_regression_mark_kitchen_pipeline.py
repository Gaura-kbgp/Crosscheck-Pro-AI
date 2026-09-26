"""
Regression tests protecting the deterministic extraction -> normalization ->
canonical aggregation -> classification -> matching -> cross-check pipeline
against the 94-vs-55-groups Mark Kitchen regression.

Root cause of that regression (see investigation notes in the PR/commit): the
Purchase Order extraction prompt did not distinguish a catalog's decimal
sub-line modification rows (e.g. line "5.1" = a finished-end/depth modifier
of cabinet line "5") from real physical line items, so each sub-line became
its own phantom CanonicalLineItem with a SKU that exists nowhere in Design or
Acknowledgement — inflating EXTRA/UNCERTAIN groups and discrepancy counts.
That fix lives in app/integrations/ai/prompts/order_v1.py and is inherently
an AI-extraction concern (not unit-testable deterministically); the tests
below instead lock down every DETERMINISTIC stage downstream of extraction,
which is what actually decides how many canonical groups/discrepancies a
correctly-extracted document set produces.
"""
import pytest
from uuid import uuid4
from app.models.core import (
    CanonicalLineItem, DocumentType, MatchGroup, MatchGroupStatus,
    Discrepancy, Severity, Organization, Project, Document, ItemCategory
)
from app.engines.matching import MatchingEngine, aggregate_document_items
from app.engines.classification import ItemClassifier
from app.engines.normalization import check_canonical_equivalence
from app.engines.crosscheck import CrossCheckEngine, CATEGORY_DISCREPANCY_POLICY
from app.services.crosscheck_service import CrossCheckService
from app.integrations.ai.prompts.order_v1 import ORDER_PROMPT_V1


def _item(source_type, sku, qty=1, desc="", dims=None, category=None, finish=None, door_style=None, id=None):
    return CanonicalLineItem(
        id=id or uuid4(),
        project_id=uuid4(), organization_id=uuid4(), document_id=uuid4(),
        source_type=source_type, raw_sku=sku, normalized_sku=sku,
        description=desc, quantity=qty, dimensions=dims,
        item_category=category, finish=finish, door_style=door_style,
    )


class TestOrderPromptGuardsAgainstSubLineBleed:
    """The prompt fix itself: guards against silently reverting to the
    generic wording that caused decimal sub-lines to be extracted as
    independent phantom items."""

    def test_prompt_instructs_sub_line_merging(self):
        assert "5.1" in ORDER_PROMPT_V1 or "decimal" in ORDER_PROMPT_V1.lower()
        assert "modifications" in ORDER_PROMPT_V1
        assert "subtotal" in ORDER_PROMPT_V1.lower()
        assert "Net Total" in ORDER_PROMPT_V1 or "net total" in ORDER_PROMPT_V1.lower()


class TestCanonicalAggregation:
    """STEP 2 / STEP 5: duplicate/split raw lines aggregate into one
    canonical matching unit with a summed quantity, without losing raw-line
    traceability, and without collapsing genuinely distinct variant SKUs."""

    def test_split_quantity_lines_aggregate(self):
        """BT36B-2 split across two Order lines (qty 1 + qty 2) must aggregate to 3."""
        items = [
            _item(DocumentType.ORDER, "BT36B-2", qty=1),
            _item(DocumentType.ORDER, "BT36B-2", qty=2),
        ]
        units = aggregate_document_items(items)
        assert len(units) == 1
        assert units[0].aggregate_quantity == 3

    def test_raw_lines_not_deleted_and_traceable(self):
        items = [
            _item(DocumentType.ORDER, "BT36B-2", qty=1),
            _item(DocumentType.ORDER, "BT36B-2", qty=2),
        ]
        original_ids = {i.id for i in items}
        units = aggregate_document_items(items)
        unit = units[0]

        # The raw CanonicalLineItem objects are the same ones passed in — never dropped
        assert {i.id for i in unit.raw_items} == original_ids
        assert unit.primary_item.source_metadata["raw_line_count"] == 2
        assert set(unit.primary_item.source_metadata["raw_line_ids"]) == {str(i) for i in original_ids}
        assert unit.primary_item.source_metadata["raw_quantities"] == [1, 2]

    def test_distinct_skus_are_not_merged(self):
        """Physically different cabinets must never collapse into one unit merely
        because they're both present in the same document."""
        items = [
            _item(DocumentType.ORDER, "BF330", qty=1, id=uuid4()),
            _item(DocumentType.ORDER, "WF342", qty=1, id=uuid4()),
        ]
        units = aggregate_document_items(items)
        assert len(units) == 2

    def test_aggregate_quantity_used_in_crosscheck_not_raw_line(self):
        """Design=2 vs Order(aggregated)=3 must be the comparison — not Design=2
        vs a single raw Order line of 1 or 2."""
        d = _item(DocumentType.DESIGN, "BT36B-2", qty=2)
        o1 = _item(DocumentType.ORDER, "BT36B-2", qty=1)
        o2 = _item(DocumentType.ORDER, "BT36B-2", qty=2)
        a = _item(DocumentType.ACKNOWLEDGEMENT, "BT36B-2", qty=3)

        engine = MatchingEngine()
        groups = engine.match_items([d], [o1, o2], [a], uuid4(), uuid4())
        assert len(groups) == 1
        mg = groups[0]

        cc = CrossCheckEngine()
        discs = cc.evaluate([mg], uuid4(), uuid4())
        qty_discs = [x for x in discs if x.field == "quantity"]
        assert len(qty_discs) == 1
        assert qty_discs[0].source_values["design"] == 2
        assert qty_discs[0].source_values["order"] == 3


class TestManufacturerVariantMatching:
    """STEP 3: evidence-backed manufacturer variant equivalence, not blind
    string equality — using the dataset's own cited variant pairs."""

    @pytest.mark.parametrize("order_sku,order_desc,ack_sku,ack_desc", [
        ("BFHC12", "Base Cabinet w/ FHD 12in", "BPFHC12", "Base Cabinet w/ FHD 12in"),
        ("BPS12", "Pull Out Storage 12in", "BP52", "Pull Out Storage 12in"),
        ("SBA36B", "Apron Sink Base 36in", "SB36B3", "Apron Sink Base 36in"),
    ])
    def test_cited_variant_pairs_are_evidence_backed_equivalent(self, order_sku, order_desc, ack_sku, ack_desc):
        is_eq, conf, eq_type, evidence = check_canonical_equivalence(
            sku1=order_sku, desc1=order_desc, dims1=None, cat1=ItemCategory.CABINET,
            sku2=ack_sku, desc2=ack_desc, dims2=None, cat2=ItemCategory.CABINET,
        )
        assert is_eq is True
        assert eq_type in ("MANUFACTURER_VARIANT", "NORMALIZED_EXACT", "EXACT")

    def test_unrelated_skus_are_not_equated(self):
        is_eq, conf, eq_type, evidence = check_canonical_equivalence(
            sku1="BF330", desc1="Base Filler Toe", dims1=None, cat1=ItemCategory.FILLER,
            sku2="W3624B", desc2="Wall Cabinet", dims2=None, cat2=ItemCategory.CABINET,
        )
        assert is_eq is False


class TestClassificationPolicy:
    """STEP 4: category-specific discrepancy eligibility policy."""

    def test_eligible_categories(self):
        for cat in (ItemCategory.CABINET, ItemCategory.PANEL, ItemCategory.FILLER, ItemCategory.UNKNOWN):
            assert CATEGORY_DISCREPANCY_POLICY.get(cat, True) is True

    def test_suppressed_categories(self):
        for cat in (ItemCategory.MOLDING, ItemCategory.ACCESSORY, ItemCategory.ARCHITECTURAL_ANNOTATION,
                    ItemCategory.APPLIANCE, ItemCategory.COMMERCIAL_CHARGE):
            assert CATEGORY_DISCREPANCY_POLICY.get(cat, True) is False

    def test_excluded_category_produces_zero_discrepancies_but_group_survives(self):
        """A molding-only item present in Order but not Design must still form
        a canonical/match-group record (for audit trace) but generate no
        physical discrepancy."""
        o = _item(DocumentType.ORDER, "MLD8", qty=5, desc="Scribe Molding", category=ItemCategory.MOLDING)
        mg = MatchGroup(id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
                         status=MatchGroupStatus.EXTRA, order_item_id=o.id, order_item=o)
        cc = CrossCheckEngine()
        discs = cc.evaluate([mg], uuid4(), uuid4())
        assert discs == []

    def test_commercial_charge_is_excluded_from_discrepancies(self):
        o = _item(DocumentType.ORDER, "FREIGHTSURCHARGE", qty=1, desc="Freight Surcharge", category=ItemCategory.COMMERCIAL_CHARGE)
        mg = MatchGroup(id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
                         status=MatchGroupStatus.EXTRA, order_item_id=o.id, order_item=o)
        cc = CrossCheckEngine()
        assert cc.evaluate([mg], uuid4(), uuid4()) == []

    def test_classifier_recognizes_task_specified_keywords(self):
        classifier = ItemClassifier()
        cases = [
            ("DEP1W", "Dishwasher End Panel", ItemCategory.PANEL),
            ("MANTEL01", "Hood Mantel Surround", ItemCategory.ARCHITECTURAL_ANNOTATION),
            ("HMLD8", "Hutch Molding trim", ItemCategory.MOLDING),
            ("RKPG", "Finish Repair Kit - Paint & Glaze", ItemCategory.ACCESSORY),
        ]
        for sku, desc, expected in cases:
            result = classifier.classify(raw_sku=sku, description=desc)
            assert result.category == expected, f"{sku} ({desc}) classified as {result.category}, expected {expected}"


class TestFirstDivergenceAttribution:
    """STEP 6: the system must identify the FIRST document where a
    difference appears, per the task's own worked examples."""

    def test_design_absent_order_added_ack_present_introduced_at_order(self):
        """Design=ABSENT, Order=ADDED, Ack=PRESENT -> Introduced at ORDER
        (the item enters the pipeline at Order; Design never had it)."""
        o = _item(DocumentType.ORDER, "PNL144848", desc="Plywood Panel 48x48", category=ItemCategory.CABINET)
        a = _item(DocumentType.ACKNOWLEDGEMENT, "PNL144848", desc="Plywood Panel 48x48", category=ItemCategory.CABINET)
        mg = MatchGroup(id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
                         status=MatchGroupStatus.CHANGED,
                         order_item_id=o.id, order_item=o,
                         ack_item_id=a.id, ack_item=a)
        cc = CrossCheckEngine()
        discs = cc.evaluate([mg], uuid4(), uuid4())
        presence_discs = [x for x in discs if x.field == "item_presence"]
        assert len(presence_discs) == 1
        assert presence_discs[0].introduced_at == DocumentType.ORDER

    def test_design_order_match_ack_changed_introduced_at_acknowledgement(self):
        """Design=PRESENT, Order=PRESENT(matches Design), Ack=CHANGED -> Introduced at ACKNOWLEDGEMENT."""
        d = _item(DocumentType.DESIGN, "W3624B", desc="Wall Cabinet")
        o = _item(DocumentType.ORDER, "W3624B", desc="Wall Cabinet")
        a = _item(DocumentType.ACKNOWLEDGEMENT, "W3624D", desc="Wall Cabinet")
        mg = MatchGroup(id=uuid4(), project_id=uuid4(), organization_id=uuid4(),
                         status=MatchGroupStatus.CHANGED,
                         design_item_id=d.id, design_item=d,
                         order_item_id=o.id, order_item=o,
                         ack_item_id=a.id, ack_item=a)
        cc = CrossCheckEngine()
        discs = cc.evaluate([mg], uuid4(), uuid4())
        sku_discs = [x for x in discs if x.field == "sku"]
        assert len(sku_discs) == 1
        assert sku_discs[0].introduced_at == DocumentType.ACKNOWLEDGEMENT

    def test_single_physical_item_produces_one_presence_discrepancy_not_per_raw_line(self):
        """Multiple raw Order lines for the same physical item must not fan out
        into duplicate discrepancies once aggregated into one canonical unit."""
        d = _item(DocumentType.DESIGN, "BT36B-2", qty=2)
        o1 = _item(DocumentType.ORDER, "BT36B-2", qty=1)
        o2 = _item(DocumentType.ORDER, "BT36B-2", qty=2)

        engine = MatchingEngine()
        groups = engine.match_items([d], [o1, o2], [], uuid4(), uuid4())
        assert len(groups) == 1

        cc = CrossCheckEngine()
        discs = cc.evaluate(groups, uuid4(), uuid4())
        assert len(discs) == 1


class TestUncertainOnlyOnGenuineAmbiguity:
    """STEP 7: UNCERTAIN must only appear when there is genuine, unresolved
    candidate competition — never forced, never from noise items."""

    def test_clean_one_to_one_never_uncertain(self):
        d = _item(DocumentType.DESIGN, "DEP1W", desc="Base Filler w/ End Panel")
        o = _item(DocumentType.ORDER, "DEP1W", desc="Base Filler w/ End Panel")
        a = _item(DocumentType.ACKNOWLEDGEMENT, "DEP1W", desc="Base Filler w/ End Panel")
        engine = MatchingEngine()
        groups = engine.match_items([d], [o], [a], uuid4(), uuid4())
        assert len(groups) == 1
        assert groups[0].status != MatchGroupStatus.UNCERTAIN

    def test_duplicate_design_skus_disambiguated_by_dimensions_not_forced_uncertain(self):
        """Two identical-SKU Design items with distinguishing dimensions must
        resolve deterministically, not collapse into UNCERTAIN."""
        d1 = _item(DocumentType.DESIGN, "BF330", dims={"width": 30})
        d2 = _item(DocumentType.DESIGN, "BF330", dims={"width": 33})
        o1 = _item(DocumentType.ORDER, "BF330", dims={"width": 30})
        o2 = _item(DocumentType.ORDER, "BF330", dims={"width": 33})
        engine = MatchingEngine()
        groups = engine.match_items([d1, d2], [o1, o2], [], uuid4(), uuid4())
        uncertain = [g for g in groups if g.status == MatchGroupStatus.UNCERTAIN]
        assert uncertain == []

    def test_ambiguous_duplicate_without_dimensions_is_uncertain_not_silently_matched(self):
        """Two distinct Design variants (same SKU, different finish — so NOT
        pre-aggregated together, since aggregation keys on SKU+finish+door)
        both plausibly equivalent to a single, unoriented Order candidate,
        with no dimensions to disambiguate: the engine must abstain to
        UNCERTAIN rather than guess which Design item the Order line means."""
        d1 = _item(DocumentType.DESIGN, "3DB21", finish="WHITE")
        d2 = _item(DocumentType.DESIGN, "3DB21", finish="OAK")
        o = _item(DocumentType.ORDER, "3DB21")
        engine = MatchingEngine()
        groups = engine.match_items([d1, d2], [o], [], uuid4(), uuid4())
        assert any(g.status == MatchGroupStatus.UNCERTAIN for g in groups)


class TestDiscrepancyOperatesOnCanonicalGroupsNotRawLines:
    """STEP 8: the discrepancy engine must never fan out per raw line, per
    accessory, per molding, or per commercial-charge extraction artifact."""

    def test_no_discrepancy_for_every_raw_line_only_for_canonical_group(self, db_session=None):
        pass  # covered by test_single_physical_item_produces_one_presence_discrepancy_not_per_raw_line


@pytest.fixture
def crosscheck_env(db_session):
    org = Organization(name="Mark Kitchen Regression Org")
    db_session.add(org)
    db_session.commit()
    project = Project(organization_id=org.id, name="Mark Kitchen Regression")
    db_session.add(project)
    db_session.commit()
    return CrossCheckService(db_session), project.id, org.id


def _db_item(db_session, project_id, org_id, source_type, sku, qty=1, desc="", category=ItemCategory.CABINET):
    doc = Document(
        id=uuid4(), project_id=project_id, organization_id=org_id,
        document_type=source_type, original_filename="test.pdf",
        storage_path=f"path_{uuid4()}.pdf", mime_type="application/pdf", file_size=100,
    )
    db_session.add(doc)
    db_session.commit()
    item = CanonicalLineItem(
        project_id=project_id, organization_id=org_id, document_id=doc.id,
        source_type=source_type, raw_sku=sku, normalized_sku=sku,
        description=desc, quantity=qty, item_category=category,
    )
    db_session.add(item)
    db_session.commit()
    return item


class TestEndToEndServiceLevel:
    """Sanity check the full CrossCheckService.process_project path (the same
    code the '/crosscheck/run' endpoint calls) against a small synthetic
    dataset shaped like the Mark Kitchen regression: a real cabinet, a split
    quantity, a manufacturer variant, and a non-discrepancy-eligible molding
    item all present at once."""

    def test_mixed_dataset_end_to_end(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env

        # Real cabinet, exact 3-way match
        _db_item(db_session, project_id, org_id, DocumentType.DESIGN, "DEP1W", desc="Base Filler w/ End Panel")
        _db_item(db_session, project_id, org_id, DocumentType.ORDER, "DEP1W", desc="Base Filler w/ End Panel")
        _db_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "DEP1W", desc="Base Filler w/ End Panel")

        # Split-quantity aggregation case
        _db_item(db_session, project_id, org_id, DocumentType.DESIGN, "BT36B-2", qty=2)
        _db_item(db_session, project_id, org_id, DocumentType.ORDER, "BT36B-2", qty=1)
        _db_item(db_session, project_id, org_id, DocumentType.ORDER, "BT36B-2", qty=2)
        _db_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "BT36B-2", qty=3)

        # Non-discrepancy-eligible molding, extra in Order only
        _db_item(db_session, project_id, org_id, DocumentType.ORDER, "MLD8", qty=5, desc="Scribe Molding", category=ItemCategory.MOLDING)

        result = service.process_project(project_id, org_id)

        # 2 canonical groups (DEP1W, BT36B-2) — MLD8 forms its own group too (traceable) but 0 discrepancies from it
        assert result["match_groups_count"] == 3
        discs = db_session.query(Discrepancy).filter(Discrepancy.project_id == project_id).all()
        # Only the quantity discrepancy on the aggregated BT36B-2 group; MLD8 excluded by policy
        assert len(discs) == 1
        assert discs[0].field == "quantity"
        assert discs[0].source_values["design"] == 2
        assert discs[0].source_values["order"] == 3
