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
from app.engines.extraction_validator import ExtractionValidator
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine


class TestItemClassification:
    """Tests for generic evidence-based item classification."""

    def setup_method(self):
        self.classifier = ItemClassifier()

    def test_cabinet_classification(self):
        # Base cabinet
        res = self.classifier.classify(raw_sku="B36", description="Base 36 Cabinet 2 Doors")
        assert res.category == ItemCategory.CABINET
        assert res.confidence >= 0.90

        # Wall cabinet
        res = self.classifier.classify(raw_sku="W3630", description="Wall Cabinet 36x30")
        assert res.category == ItemCategory.CABINET

        # Tall / Utility cabinet
        res = self.classifier.classify(raw_sku="U2484", description="Tall Utility Pantry Cabinet")
        assert res.category == ItemCategory.CABINET

        # Generic unseen cabinet
        res = self.classifier.classify(raw_sku="CAB36L", description="Kitchen base cabinet unit")
        assert res.category == ItemCategory.CABINET

    def test_appliance_classification(self):
        # Explicit description
        res = self.classifier.classify(raw_sku="APP-01", description="Built-in Dishwasher 24 inch Stainless")
        assert res.category == ItemCategory.APPLIANCE
        assert res.confidence >= 0.95

        # Drawing CAD placeholder code (unseen)
        res = self.classifier.classify(raw_sku="REF.2D.36", description="")
        assert res.category == ItemCategory.APPLIANCE

        res = self.classifier.classify(raw_sku="DISH-IQ6", description="")
        assert res.category == ItemCategory.APPLIANCE

        res = self.classifier.classify(raw_sku="RANGE1.30", description="")
        assert res.category == ItemCategory.APPLIANCE

        res = self.classifier.classify(raw_sku="MW.HOOD", description="")
        assert res.category == ItemCategory.APPLIANCE

        res = self.classifier.classify(raw_sku="FRIDGE-SPEC-36", description="Refrigerator opening space")
        assert res.category == ItemCategory.APPLIANCE

    def test_architectural_annotation_classification(self):
        res = self.classifier.classify(raw_sku="WALL-OPENING-48", description="Rough wall opening for pass-through")
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

        res = self.classifier.classify(raw_sku="WIN-36", description="Window trim frame opening")
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

        res = self.classifier.classify(raw_sku="ROOM-DIM-120", description="Room dimension ceiling height 9ft")
        assert res.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_filler_classification(self):
        res = self.classifier.classify(raw_sku="FILLER3", description="3 inch decorative overlay filler")
        assert res.category == ItemCategory.FILLER

        res = self.classifier.classify(raw_sku="BF3", description="Base cabinet filler")
        assert res.category == ItemCategory.FILLER

        res = self.classifier.classify(raw_sku="WF330", description="Wall filler 3x30")
        assert res.category == ItemCategory.FILLER

    def test_panel_classification(self):
        res = self.classifier.classify(raw_sku="BEP24", description="Base end panel finished")
        assert res.category == ItemCategory.PANEL

        res = self.classifier.classify(raw_sku="REP36", description="Refrigerator decorative side panel")
        assert res.category == ItemCategory.PANEL

    def test_molding_classification(self):
        res = self.classifier.classify(raw_sku="SCM8", description="Small crown molding 8ft")
        assert res.category == ItemCategory.MOLDING

        res = self.classifier.classify(raw_sku="TK8", description="Toe kick molding strip")
        assert res.category == ItemCategory.MOLDING

        res = self.classifier.classify(raw_sku="VAL36", description="36 inch arched valance trim")
        assert res.category == ItemCategory.MOLDING

    def test_accessory_classification(self):
        res = self.classifier.classify(raw_sku="ROT24", description="Roll-out tray 24 inch")
        assert res.category == ItemCategory.ACCESSORY

        res = self.classifier.classify(raw_sku="TD18", description="Tray divider insert")
        assert res.category == ItemCategory.ACCESSORY

        res = self.classifier.classify(raw_sku="CRB-01", description="Decorative wood corbel bracket")
        assert res.category == ItemCategory.ACCESSORY

    def test_unknown_classification_on_ambiguous_evidence(self):
        res = self.classifier.classify(raw_sku="XYZ-UNKNOWN-99", description="Special unclassified item")
        assert res.category == ItemCategory.UNKNOWN
        assert res.confidence < 0.60


class TestExtractionValidation:
    """Tests for ExtractionValidator evidence checking."""

    def setup_method(self):
        self.validator = ExtractionValidator()

    def test_valid_item_validation(self):
        item = {
            "sku": "B36 1TD",
            "quantity": 1,
            "dimensions": {"width": 36, "height": 34.5, "depth": 24},
            "confidence": 0.95
        }
        is_valid, issues, meta = self.validator.validate_item(item, DocumentType.DESIGN)
        assert is_valid is True
        assert len(issues) == 0

    def test_empty_sku_flagged(self):
        item = {"sku": "", "quantity": 1}
        is_valid, issues, meta = self.validator.validate_item(item, DocumentType.ORDER)
        assert is_valid is False
        assert any(i.field == "sku" for i in issues)

    def test_negative_quantity_flagged(self):
        item = {"sku": "B24", "quantity": -2}
        is_valid, issues, meta = self.validator.validate_item(item, DocumentType.ORDER)
        assert is_valid is False
        assert any(i.field == "quantity" and i.issue_type == "NEGATIVE_QUANTITY" for i in issues)


class TestApplianceAndAnnotationCrossCheckScope:
    """Tests that drawing appliances and annotations do not create false cabinet missing discrepancies."""

    def setup_method(self):
        self.crosscheck = CrossCheckEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_appliance_in_design_excluded_from_critical_missing(self):
        # Appliance present in Design drawing, omitted from cabinet PO
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="REF.2D.36",
            normalized_sku="REF.2D.36",
            item_category=ItemCategory.APPLIANCE,
            quantity=1
        )
        mg = MatchGroup(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            status=MatchGroupStatus.MISSING,
            design_item_id=d_item.id,
            design_item=d_item
        )

        discrepancies = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        # Excluded from cabinet purchasing presence check -> 0 discrepancies
        assert len(discrepancies) == 0

    def test_architectural_annotation_excluded_from_critical_missing(self):
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="WALL-OPENING-48",
            normalized_sku="WALL-OPENING-48",
            item_category=ItemCategory.ARCHITECTURAL_ANNOTATION,
            quantity=1
        )
        mg = MatchGroup(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            status=MatchGroupStatus.MISSING,
            design_item_id=d_item.id,
            design_item=d_item
        )

        discrepancies = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        # Excluded from cabinet purchasing presence check -> 0 discrepancies
        assert len(discrepancies) == 0

    def test_cabinet_in_design_generates_critical_missing(self):
        # Actual cabinet present in Design, missing in PO -> MUST be CRITICAL
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="B36 1TD",
            normalized_sku="B36 1TD",
            item_category=ItemCategory.CABINET,
            quantity=1
        )
        mg = MatchGroup(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            status=MatchGroupStatus.MISSING,
            design_item_id=d_item.id,
            design_item=d_item
        )

        discrepancies = self.crosscheck.evaluate([mg], self.proj_id, self.org_id)
        assert len(discrepancies) == 1
        assert discrepancies[0].severity == Severity.CRITICAL
        assert "missing in Purchase Order" in discrepancies[0].explanation


class TestMatchingSafetyAndAmbiguity:
    """Tests for matching safety, category isolation, and candidate ambiguity."""

    def setup_method(self):
        self.matcher = MatchingEngine()
        self.proj_id = uuid4()
        self.org_id = uuid4()

    def test_conflicting_categories_do_not_match(self):
        # An appliance item and a cabinet item with similar code should NOT match
        d_appl = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="HOOD36",
            normalized_sku="HOOD36",
            description="36 inch range hood appliance",
            item_category=ItemCategory.APPLIANCE
        )
        o_cab = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="HOOD36",
            description="Wood decorative range hood cabinet",
            item_category=ItemCategory.CABINET
        )

        mgs = self.matcher.match_items([d_appl], [o_cab], [], self.proj_id, self.org_id)
        # Because categories conflict (APPLIANCE vs CABINET), they must not be merged into a single match group
        assert len(mgs) == 2
        d_mg = next(m for m in mgs if m.design_item_id == d_appl.id)
        assert d_mg.order_item_id is None

    def test_dimension_conflict_on_token_subset_rejects_match(self):
        # Token subset "B36" vs "B36 1TD" with strongly conflicting depths (e.g. 12" depth vs 24" depth)
        d_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.DESIGN,
            raw_sku="B36",
            normalized_sku="B36",
            dimensions={"width": 36, "height": 34.5, "depth": 12},
            item_category=ItemCategory.CABINET
        )
        o_item = CanonicalLineItem(
            id=uuid4(),
            project_id=self.proj_id,
            organization_id=self.org_id,
            document_id=uuid4(),
            source_type=DocumentType.ORDER,
            raw_sku="B36 1TD BUTT",
            normalized_sku="B36 1TD BUTT",
            dimensions={"width": 36, "height": 34.5, "depth": 24},
            item_category=ItemCategory.CABINET
        )

        mgs = self.matcher.match_items([d_item], [o_item], [], self.proj_id, self.org_id)
        # Dimensions conflict on depth (12 vs 24), so token subset match is rejected
        assert len(mgs) == 2
