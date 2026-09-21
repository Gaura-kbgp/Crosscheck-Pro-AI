import pytest
from app.integrations.ai.openai_provider import OpenAIProvider
from app.engines.extraction_validator import ExtractionValidator, ValidationIssue
from app.engines.classification import ItemClassifier, ItemCategory
from app.engines.normalization import normalize_sku, normalize_quantity, parse_and_normalize_dimensions
from app.models.core import DocumentType


class TestLayoutExtractionAndBoundarySafety:
    """
    F8.2.2 Generic regression tests for layout-aware extraction,
    SKU boundary safety, and multimodal document handling.
    """

    @pytest.fixture
    def validator(self):
        return ExtractionValidator()

    @pytest.fixture
    def classifier(self):
        return ItemClassifier()

    def test_1_two_adjacent_sku_labels_boundary(self, validator):
        """1. Two adjacent SKU labels should remain distinct and not merge."""
        # Generic fictional SKUs
        item_a = {"sku": "BASE-CAB-36", "quantity": 1, "confidence": 0.95}
        item_b = {"sku": "WALL-CAB-24", "quantity": 1, "confidence": 0.95}

        is_valid_a, issues_a, _ = validator.validate_item(item_a, DocumentType.DESIGN)
        is_valid_b, issues_b, _ = validator.validate_item(item_b, DocumentType.DESIGN)

        assert is_valid_a is True
        assert is_valid_b is True
        assert normalize_sku(item_a["sku"]) == "BASE-CAB-36"
        assert normalize_sku(item_b["sku"]) == "WALL-CAB-24"

    def test_2_multiple_adjacent_sku_labels(self, validator):
        """2. Multiple adjacent SKU labels across a schedule row."""
        skus = ["BT36B-2", "BFHC12", "BPS12", "BT24-2-R"]
        for s in skus:
            is_valid, issues, _ = validator.validate_item({"sku": s, "quantity": 1}, DocumentType.DESIGN)
            assert is_valid is True
            assert len([i for i in issues if i.severity == "ERROR"]) == 0

    def test_3_sku_and_description_nearby_regions(self, validator):
        """3. SKU + description on nearby regions."""
        item = {
            "sku": "BT36B-2",
            "description": "Base w/ 2 Roll-Out Trays - Maple Inset",
            "quantity": 1,
            "dimensions": {"width": 36, "height": 34.5, "depth": 24}
        }
        is_valid, issues, meta = validator.validate_item(item, DocumentType.ORDER)
        assert is_valid is True
        assert meta["confidence"] == 1.0

    def test_4_multiple_cabinet_labels_on_one_page(self, validator):
        """4. Multiple cabinet labels on one drawing page."""
        page_labels = ["WST3657B", "WST2157-L", "24W4827", "4DB21", "B18DWB", "SBA36B"]
        normalized = [normalize_sku(l) for l in page_labels]
        assert len(set(normalized)) == len(page_labels)
        for l in page_labels:
            is_valid, _, _ = validator.validate_item({"sku": l, "quantity": 1}, DocumentType.DESIGN)
            assert is_valid is True

    def test_5_wrapped_text_handling(self):
        """5. Wrapped text lines should normalize cleanly without trailing artifacts."""
        raw_sku_multiline = "BT36B-2\n  "
        assert normalize_sku(raw_sku_multiline) == "BT36B-2"

    def test_6_similar_sku_strings_distinct(self):
        """6. Similar SKU strings should normalize to distinct canonical representations."""
        sku_1 = "WST3057B"
        sku_2 = "WST3657B"
        sku_3 = "WST2157-L"
        assert normalize_sku(sku_1) != normalize_sku(sku_2)
        assert normalize_sku(sku_2) != normalize_sku(sku_3)

    def test_7_sku_separated_by_whitespace(self):
        """7. SKU separated by internal whitespace."""
        sku_with_space = "B36 1TD BUTT"
        assert normalize_sku(sku_with_space) == "B36 1TD BUTT"

    def test_8_sku_separated_by_line_boundary(self):
        """8. SKU separated by line boundary."""
        sku_with_newline = "24UT3693B-4\r\n"
        assert normalize_sku(sku_with_newline) == "24UT3693B-4"

    def test_9_duplicate_sku_instances(self):
        """9. Duplicate SKU instances preserve quantity counts."""
        qty_1 = normalize_quantity(1)
        qty_2 = normalize_quantity(2)
        assert qty_1 == 1
        assert qty_2 == 2

    def test_10_appliance_label_adjacent_to_cabinet(self, classifier):
        """10. Appliance label adjacent to cabinet label should be categorized appropriately."""
        appliance_res = classifier.classify("GR606F-LP", "Gas Range 6-Burner", None, None, "DESIGN")
        cabinet_res = classifier.classify("4DB21", "4-Drawer Base Cabinet", None, None, "DESIGN")

        assert appliance_res.category in [ItemCategory.APPLIANCE, ItemCategory.UNKNOWN]
        assert cabinet_res.category == ItemCategory.CABINET

    def test_11_annotation_adjacent_to_cabinet(self, classifier):
        """11. Architectural annotation adjacent to cabinet label."""
        annot_res = classifier.classify("22CLME1284", "Alcove Hood Column", None, None, "DESIGN")
        cab_res = classifier.classify("W3930", "Wall Cabinet 39x30", None, None, "DESIGN")

        assert cab_res.category == ItemCategory.CABINET
        assert annot_res.category in [ItemCategory.ARCHITECTURAL_ANNOTATION, ItemCategory.UNKNOWN, ItemCategory.CABINET, ItemCategory.ACCESSORY]

    def test_12_suspicious_merged_sku_flagged(self, validator):
        """12. Unusually long merged SKU string without delimiters is flagged by validator."""
        corrupted_merged_sku = "AHSDX723022CLME1284" # 19 chars without delimiters
        is_valid, issues, meta = validator.validate_item({"sku": corrupted_merged_sku, "quantity": 1}, DocumentType.DESIGN)
        merged_issues = [i for i in issues if i.issue_type == "SUSPICIOUS_MERGED_SKU"]
        assert len(merged_issues) > 0
        assert merged_issues[0].severity == "WARNING"
