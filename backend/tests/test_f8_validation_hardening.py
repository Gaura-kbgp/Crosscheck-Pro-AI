import pytest
from uuid import uuid4
from app.models.core import (
    ItemCategory,
    CanonicalLineItem,
    DocumentType,
    MatchGroup,
    MatchGroupStatus,
    Severity
)
from app.engines.classification import ItemClassifier
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine
from app.engines.normalization import NOT_SPECIFIED_IN_SOURCE, EXTRACTION_UNCERTAIN


class TestUncertainBehaviorEndToEnd:
    """1. VERIFY UNCERTAIN BEHAVIOR: Genuinely ambiguous cases must produce UNCERTAIN."""

    def setup_method(self):
        self.matcher = MatchingEngine()
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_two_equally_plausible_sku_candidates_become_uncertain(self):
        # Design has 1 instance of generic CAB-X
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="CAB-X",
            normalized_sku="CAB-X",
            quantity=1
        )
        # Order has 2 distinct variant candidates (CAB-X-L and CAB-X-R) without distinguishing dimensions
        o_item1 = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="CAB-X-L",
            normalized_sku="CAB-X-L",
            quantity=1
        )
        o_item2 = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="CAB-X-R",
            normalized_sku="CAB-X-R",
            quantity=1
        )

        mgs = self.matcher.match_items([d_item], [o_item1, o_item2], [], self.proj_id, self.org_id)
        # Must abstain to UNCERTAIN for ambiguous variant candidates, NOT randomly pick one
        uncertain_groups = [m for m in mgs if m.status == MatchGroupStatus.UNCERTAIN]
        assert len(uncertain_groups) >= 2
        for ug in uncertain_groups:
            assert ug.status == MatchGroupStatus.UNCERTAIN

    def test_ambiguous_duplicate_without_dimensions_produces_uncertain(self):
        # Design has two distinct variant items: L and R
        d_item1 = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="FICTIONAL_CAB_36_L",
            normalized_sku="FICTIONAL_CAB_36_L"
        )
        d_item2 = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="FICTIONAL_CAB_36_R",
            normalized_sku="FICTIONAL_CAB_36_R"
        )
        # Order only has generic item
        o_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="FICTIONAL_CAB_36",
            normalized_sku="FICTIONAL_CAB_36"
        )

        mgs = self.matcher.match_items([d_item1, d_item2], [o_item], [], self.proj_id, self.org_id)
        assert all(m.status == MatchGroupStatus.UNCERTAIN for m in mgs)

    def test_similar_descriptions_with_completely_different_skus_do_not_match(self):
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="CAB_ALPHA_100",
            normalized_sku="CAB_ALPHA_100",
            description="Premium Kitchen Base Cabinet Unit"
        )
        o_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="TOTALLY_DIFFERENT_999",
            normalized_sku="TOTALLY_DIFFERENT_999",
            description="Premium Kitchen Base Cabinet Unit"
        )

        mgs = self.matcher.match_items([d_item], [o_item], [], self.proj_id, self.org_id)
        # Because SKUs are completely different, they must NOT falsely match
        assert len(mgs) == 2
        d_group = next(m for m in mgs if m.design_item_id == d_item.id)
        assert d_group.order_item_id is None


class TestExtraVsChangedSemantics:
    """2. VERIFY EXTRA VS CHANGED SEMANTICS: Consistent reporting between summary, status, and discrepancies."""

    def setup_method(self):
        self.matcher = MatchingEngine()
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_generic_extra_item_with_ack_rejection(self):
        # Generic fictional item: absent from Design, present in Order, rejected in Ack
        o_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="EXTRA_VALANCE_99",
            normalized_sku="EXTRA_VALANCE_99",
            quantity=1,
            item_category=ItemCategory.CABINET
        )
        a_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ACKNOWLEDGEMENT,
            raw_sku="EXTRA_VALANCE_99",
            normalized_sku="EXTRA_VALANCE_99",
            quantity=0,
            acknowledgement_status="Rejected",
            item_category=ItemCategory.CABINET
        )

        mgs = self.matcher.match_items([], [o_item], [a_item], self.proj_id, self.org_id)
        assert len(mgs) == 1
        mg = mgs[0]

        # 1. MatchGroup status must be EXTRA (absent from Design)
        assert mg.status == MatchGroupStatus.EXTRA

        # 2. CrossCheck discrepancies evaluation
        discrepancies = self.crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        # Must have:
        # A) Item presence discrepancy for PO addition (Introduced: ORDER)
        # B) Quantity discrepancy for Ack rejection (Introduced: ACKNOWLEDGEMENT)
        presence_d = next((d for d in discrepancies if d.field == "item_presence"), None)
        qty_d = next((d for d in discrepancies if d.field == "quantity"), None)

        assert presence_d is not None
        assert presence_d.introduced_at == DocumentType.ORDER
        assert "Extra line item" in presence_d.explanation

        assert qty_d is not None
        assert qty_d.introduced_at == DocumentType.ACKNOWLEDGEMENT
        assert qty_d.source_values["order"] == 1
        assert qty_d.source_values["acknowledgement"] == 0


class TestGenericApplianceAndArchitecturalClassification:
    """3 & 4. VERIFY APPLIANCE & ARCHITECTURAL CLASSIFICATION on unseen generic examples."""

    def setup_method(self):
        self.classifier = ItemClassifier()
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    @pytest.mark.parametrize("sku,desc", [
        ("AP-36X", "Built-in appliance package"),
        ("ELX-30", "Electric induction cooktop unit"),
        ("REF36", "36 inch French door refrigerator"),
        ("OVN30", "Single wall oven 30 inch"),
        ("DISH-24", "Built-in dishwasher 24"),
    ])
    def test_unseen_generic_appliances(self, sku, desc):
        res = self.classifier.classify(raw_sku=sku, description=desc)
        assert res.category == ItemCategory.APPLIANCE
        assert res.confidence >= 0.85

    @pytest.mark.parametrize("sku,desc", [
        ("WALL-OPENING", "Rough opening in partition wall"),
        ("ROOM-DIM", "Overall room dimension annotation"),
        ("WINDOW-36", "Existing window frame location"),
        ("DOOR-30", "Entry door opening clearance"),
    ])
    def test_unseen_generic_architectural_annotations(self, sku, desc):
        res = self.classifier.classify(raw_sku=sku, description=desc)
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_unseen_appliance_in_design_does_not_create_critical_missing(self):
        d_appl = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="ELX-30",
            normalized_sku="ELX-30",
            item_category=ItemCategory.APPLIANCE,
            quantity=1
        )
        mg = MatchGroup(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            status=MatchGroupStatus.MISSING,
            design_item_id=d_appl.id,
            design_item=d_appl
        )

        discs = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        # Excluded from physical cabinet purchasing presence check -> 0 discrepancies
        assert len(discs) == 0


class TestExtractionFailureVsMissingItem:
    """5. VERIFY EXTRACTION FAILURE VS MISSING ITEM states."""

    def setup_method(self):
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_not_specified_in_source_produces_no_discrepancy(self):
        # When design did not specify finish, but Order specified White -> no contradiction
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="B36",
            finish=None
        )
        o_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="B36",
            finish="White Paint"
        )
        a_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ACKNOWLEDGEMENT,
            raw_sku="B36",
            finish="White Paint"
        )
        mg = MatchGroup(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            status=MatchGroupStatus.MATCHED,
            design_item_id=d_item.id,
            order_item_id=o_item.id,
            ack_item_id=a_item.id,
            design_item=d_item,
            order_item=o_item,
            ack_item=a_item
        )

        discs = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        # Zero finish discrepancies because design did not specify finish
        assert not any(d.field == "finish" for d in discs)


class TestIntroducedAtAttribution:
    """6. VERIFY INTRODUCED AT logic."""

    def setup_method(self):
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_introduced_at_order(self):
        d_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.DESIGN, raw_sku="B36", quantity=1)
        o_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.ORDER, raw_sku="B36", quantity=2)
        a_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="B36", quantity=2)
        mg = MatchGroup(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, status=MatchGroupStatus.MATCHED, design_item_id=d_item.id, order_item_id=o_item.id, ack_item_id=a_item.id, design_item=d_item, order_item=o_item, ack_item=a_item)

        discs = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        qty_d = next(d for d in discs if d.field == "quantity")
        assert qty_d.introduced_at == DocumentType.ORDER

    def test_introduced_at_acknowledgement(self):
        d_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.DESIGN, raw_sku="W2130R", quantity=1)
        o_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.ORDER, raw_sku="W2130R", quantity=1)
        a_item = CanonicalLineItem(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, document_id=uuid4(), source_type=DocumentType.ACKNOWLEDGEMENT, raw_sku="W2142R", substitution_sku="W2130R", quantity=1)
        mg = MatchGroup(id=uuid4(), project_id=self.proj_id, organization_id=self.org_id, status=MatchGroupStatus.CHANGED, design_item_id=d_item.id, order_item_id=o_item.id, ack_item_id=a_item.id, design_item=d_item, order_item=o_item, ack_item=a_item)

        discs = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        sub_d = next(d for d in discs if d.field == "sku")
        assert sub_d.introduced_at == DocumentType.ACKNOWLEDGEMENT
