"""
F8.2.7.1 — Unit & Integration Tests for Classification & Discrepancy Exclusion Policy.
Enforces:
1. Classification accuracy for PANEL, ARCHITECTURAL_ANNOTATION, MOLDING, ACCESSORY, COMMERCIAL_CHARGE, FILLER.
2. Discrepancy Exclusion Policy (CATEGORY_DISCREPANCY_POLICY).
3. Non-cabinet items (APPLIANCE, ARCH, COMMERCIAL, MOLDING, ACCESSORY) generate NO physical cabinet discrepancies.
4. FILLER3 and 24UEPF3120 remain genuine discrepancies.
5. UNKNOWN category items generate WARNING severity instead of auto-CRITICAL.
6. 3-way state transition preservation.
"""
from uuid import uuid4
import pytest

from app.engines.classification import ItemClassifier
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine, CATEGORY_DISCREPANCY_POLICY
from app.models.core import (
    CanonicalLineItem, MatchGroup, Discrepancy, MatchGroupStatus,
    DocumentType, ItemCategory, Severity
)


@pytest.fixture
def clf():
    return ItemClassifier()


@pytest.fixture
def matcher():
    return MatchingEngine(fuzzy_threshold=0.7)


@pytest.fixture
def crosscheck():
    return CrossCheckEngine()


# ===========================================================================
# 1. Deterministic Classification Tests (Spec Section 15)
# ===========================================================================
class TestF8271Classification:

    def test_dep1w_classified_as_panel(self, clf):
        res = clf.classify(raw_sku="DEP1W", description="DISHWASHER EP PLY-1 1/2 STILE MAPLE")
        assert res.category == ItemCategory.PANEL

    def test_fap2434_classified_as_panel(self, clf):
        res = clf.classify(raw_sku="FAP2434", description="FRAMED APPLIANCE PNL 18.25-24 HISTORIC MAPLE")
        assert res.category == ItemCategory.PANEL

    def test_dep3m_classified_as_panel(self, clf):
        res = clf.classify(raw_sku="DEP3M", description="DISHWASHER EP PLY- 3 STILE")
        assert res.category == ItemCategory.PANEL

    def test_ledge72_classified_as_architectural(self, clf):
        res = clf.classify(raw_sku="LEDGE72", description="HOOD LEDGE 72 INCH MAPLE")
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_24mwtldx72_classified_as_architectural(self, clf):
        res = clf.classify(raw_sku="24MWTLDX72", description="MANTEL SHELF WITH LEDGE 72 WIDE")
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_ac8hm8_classified_as_molding(self, clf):
        res = clf.classify(raw_sku="AC8HM8", description="HUTCH MLD 8FT MAPLE")
        assert res.category == ItemCategory.MOLDING

    def test_rr_classified_as_accessory(self, clf):
        res = clf.classify(raw_sku="RR", description="TOUCH UP KIT REDWOOD")
        assert res.category == ItemCategory.ACCESSORY

    def test_rkpp_classified_as_accessory(self, clf):
        res = clf.classify(raw_sku="RKPP", description="REPAIR KIT PAINT PEN")
        assert res.category == ItemCategory.ACCESSORY

    def test_rksb_classified_as_accessory(self, clf):
        res = clf.classify(raw_sku="RK-SB", description="TOUCH-UP KIT SPRAY CAN")
        assert res.category == ItemCategory.ACCESSORY

    def test_freight_surcharge_classified_as_commercial(self, clf):
        res = clf.classify(raw_sku="FREIGHTSURCHARGE", description="FREIGHT SURCHARGE FUEL ADJ")
        assert res.category == ItemCategory.COMMERCIAL_CHARGE

    def test_tariff_surcharge_classified_as_commercial(self, clf):
        res = clf.classify(raw_sku="TARIFFSURCHARGE", description="TARIFF SURCHARGE IMPORT TAX")
        assert res.category == ItemCategory.COMMERCIAL_CHARGE

    def test_filler3_classified_as_filler(self, clf):
        res = clf.classify(raw_sku="FILLER3", description="FILLER 3 INCH WIDE")
        assert res.category == ItemCategory.FILLER

    def test_24uepf3120_classified_as_unknown_or_cabinet(self, clf):
        res = clf.classify(raw_sku="24UEPF3120", description="24 UEPF 3120 END FILLER")
        # Should classify as UNKNOWN or PANEL/FILLER, not APPLIANCE
        assert res.category != ItemCategory.APPLIANCE

    def test_negative_generic_word_should_not_misclassify_cabinet(self, clf):
        """A base cabinet description containing 'panel door' should remain CABINET."""
        res = clf.classify(raw_sku="B30", description="Base Cabinet 30 with Raised Panel Door")
        assert res.category == ItemCategory.CABINET


# ===========================================================================
# 2. Discrepancy Exclusion Policy Tests (Spec Section 16)
# ===========================================================================
class TestDiscrepancyExclusionPolicy:

    def setup_method(self):
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def _create_item(self, doc_type: DocumentType, sku: str, qty: int = 1, category: ItemCategory = ItemCategory.CABINET) -> CanonicalLineItem:
        return CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=doc_type,
            raw_sku=sku,
            normalized_sku=sku,
            quantity=qty,
            item_category=category
        )

    def test_filler3_extra_generates_critical_discrepancy(self, matcher, crosscheck):
        """1. FILLER3 EXTRA -> CRITICAL discrepancy generated."""
        o_item = self._create_item(DocumentType.ORDER, "FILLER3", qty=1, category=ItemCategory.FILLER)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "FILLER3", qty=1, category=ItemCategory.FILLER)

        mgs = matcher.match_items([], [o_item], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].field == "item_presence"
        assert discs[0].severity == Severity.CRITICAL

    def test_freight_surcharge_extra_generates_no_discrepancy(self, matcher, crosscheck):
        """2. FREIGHTSURCHARGE EXTRA -> no physical discrepancy."""
        o_item = self._create_item(DocumentType.ORDER, "FREIGHTSURCHARGE", qty=1, category=ItemCategory.COMMERCIAL_CHARGE)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "FREIGHTSURCHARGE", qty=1, category=ItemCategory.COMMERCIAL_CHARGE)

        mgs = matcher.match_items([], [o_item], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_tariff_surcharge_extra_generates_no_discrepancy(self, matcher, crosscheck):
        """3. TARIFFSURCHARGE EXTRA -> no physical discrepancy."""
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "TARIFFSURCHARGE", qty=1, category=ItemCategory.COMMERCIAL_CHARGE)

        mgs = matcher.match_items([], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_rkpp_ack_only_generates_no_discrepancy(self, matcher, crosscheck):
        """4. RKPP Ack-only -> no physical discrepancy."""
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "RKPP", qty=1, category=ItemCategory.ACCESSORY)

        mgs = matcher.match_items([], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_rr_ack_only_generates_no_discrepancy(self, matcher, crosscheck):
        """5. RR Ack-only -> no physical discrepancy."""
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "RR", qty=1, category=ItemCategory.ACCESSORY)

        mgs = matcher.match_items([], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_rk_sb_ack_only_generates_no_discrepancy(self, matcher, crosscheck):
        """6. RK-SB Ack-only -> no physical discrepancy."""
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "RK-SB", qty=1, category=ItemCategory.ACCESSORY)

        mgs = matcher.match_items([], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_ledge72_architectural_generates_no_discrepancy(self, matcher, crosscheck):
        """7. LEDGE72 Ack/Order-only -> no physical discrepancy if classified ARCHITECTURAL_ANNOTATION."""
        o_item = self._create_item(DocumentType.ORDER, "LEDGE72", qty=1, category=ItemCategory.ARCHITECTURAL_ANNOTATION)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "LEDGE72", qty=1, category=ItemCategory.ARCHITECTURAL_ANNOTATION)

        mgs = matcher.match_items([], [o_item], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_ac8hm8_molding_generates_no_discrepancy(self, matcher, crosscheck):
        """8. AC8HM8 Ack-only -> no physical discrepancy if classified MOLDING."""
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "AC8HM8", qty=1, category=ItemCategory.MOLDING)

        mgs = matcher.match_items([], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 0

    def test_panel_discrepancy_eligibility(self, matcher, crosscheck):
        """9. DEP1W / FAP2434 / DEP3M -> PANEL classification and correct panel discrepancy behavior."""
        d_item = self._create_item(DocumentType.DESIGN, "DEP1W", qty=1, category=ItemCategory.PANEL)

        # Missing in Order & Ack -> PANEL items ARE discrepancy eligible
        mgs = matcher.match_items([d_item], [], [], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].field == "item_presence"
        assert discs[0].severity == Severity.CRITICAL

    def test_24uepf3120_genuine_missing_remains(self, matcher, crosscheck):
        """10. 24UEPF3120 genuine missing -> discrepancy remains."""
        d_item = self._create_item(DocumentType.DESIGN, "24UEPF3120", qty=2, category=ItemCategory.UNKNOWN)

        mgs = matcher.match_items([d_item], [], [], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].field == "item_presence"

    def test_unknown_category_severity_is_warning(self, matcher, crosscheck):
        """11. Unknown category -> remains reviewable at WARNING severity (not auto-CRITICAL)."""
        d_item = self._create_item(DocumentType.DESIGN, "UNKNOWN_SKU_123", qty=1, category=ItemCategory.UNKNOWN)

        mgs = matcher.match_items([d_item], [], [], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].severity == Severity.WARNING


# ===========================================================================
# 3. Three-Way State Transition Tests (Spec Section 14)
# ===========================================================================
class TestThreeWayStateTransitions:

    def setup_method(self):
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def _create_item(self, doc_type: DocumentType, sku: str, qty: int = 1, category: ItemCategory = ItemCategory.CABINET) -> CanonicalLineItem:
        return CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=doc_type,
            raw_sku=sku,
            normalized_sku=sku,
            quantity=qty,
            item_category=category
        )

    def test_state_transition_d_present_o_missing_a_present(self, matcher, crosscheck):
        """D=present, O=missing, A=present -> Design to Order (OMITTED), Order to Ack (RESTORED)."""
        d_item = self._create_item(DocumentType.DESIGN, "B30", qty=1)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "B30", qty=1)

        mgs = matcher.match_items([d_item], [], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        # Deterministic 3-way attribution: Design is the first source where
        # the item exists, so that's where it's introduced.
        assert discs[0].introduced_at == DocumentType.DESIGN
        assert discs[0].severity == Severity.WARNING
        assert "OMITTED" in discs[0].explanation
        assert "RESTORED" in discs[0].explanation

    def test_state_transition_d_present_o_present_a_missing(self, matcher, crosscheck):
        """D=present, O=present, A=missing -> Missing in Ack."""
        d_item = self._create_item(DocumentType.DESIGN, "B30", qty=1)
        o_item = self._create_item(DocumentType.ORDER, "B30", qty=1)

        mgs = matcher.match_items([d_item], [o_item], [], self.proj_id, self.org_id)
        assert len(mgs) == 1
        assert mgs[0].status == MatchGroupStatus.MATCHED

    def test_state_transition_d_missing_o_present_a_present(self, matcher, crosscheck):
        """D=missing, O=present, A=present -> Extra line item added in Order & confirmed in Ack."""
        o_item = self._create_item(DocumentType.ORDER, "W3030", qty=1)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "W3030", qty=1)

        mgs = matcher.match_items([], [o_item], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].introduced_at == DocumentType.ORDER
        assert discs[0].severity == Severity.CRITICAL

    def test_quantity_divergence_design_vs_order(self, matcher, crosscheck):
        """D=2, O=3, A=3 -> Quantity discrepancy introduced at ORDER."""
        d_item = self._create_item(DocumentType.DESIGN, "BT36B-2", qty=2)
        o_item = self._create_item(DocumentType.ORDER, "BT36B-2", qty=3)
        a_item = self._create_item(DocumentType.ACKNOWLEDGEMENT, "BT36B-2", qty=3)

        mgs = matcher.match_items([d_item], [o_item], [a_item], self.proj_id, self.org_id)
        discs = crosscheck.evaluate(mgs, self.proj_id, self.org_id)

        assert len(discs) == 1
        assert discs[0].field == "quantity"
        assert discs[0].introduced_at == DocumentType.ORDER
        assert discs[0].comparison_values["expected"] == 2
        assert discs[0].comparison_values["actual"] == 3
