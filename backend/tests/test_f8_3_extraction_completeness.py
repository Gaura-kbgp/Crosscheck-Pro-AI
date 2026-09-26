"""
F8.3 Phase 1 regression tests: document-level extraction completeness
validation (ExtractionValidator.validate_document) and the "never infer or
fabricate" safety rule now present in all three extraction prompts.
"""
import pytest
from app.engines.extraction_validator import ExtractionValidator
from app.models.core import DocumentType
from app.integrations.ai.prompts.design_v1 import DESIGN_PROMPT_V1
from app.integrations.ai.prompts.order_v1 import ORDER_PROMPT_V1
from app.integrations.ai.prompts.acknowledgement_v1 import ACKNOWLEDGEMENT_PROMPT_V1


@pytest.fixture
def validator():
    return ExtractionValidator()


class TestPromptsCarrySafetyRule:
    """Guards against silently reverting the 'never infer/fabricate' rule
    that governs all AI extraction for this pipeline."""

    @pytest.mark.parametrize("prompt", [DESIGN_PROMPT_V1, ORDER_PROMPT_V1, ACKNOWLEDGEMENT_PROMPT_V1])
    def test_prompt_forbids_inference_and_fabrication(self, prompt):
        lowered = prompt.lower()
        assert "never infer" in lowered or "never" in lowered and "infer" in lowered
        assert "fabricate" in lowered
        assert "confidence" in lowered


class TestEmptyExtractionDetection:
    def test_zero_items_flags_uncertain(self, validator):
        result = validator.validate_document([], DocumentType.ORDER)
        assert result["status"] == "UNCERTAIN"
        assert result["item_count"] == 0
        codes = [i["issue_type"] for i in result["issues"]]
        assert "EMPTY_EXTRACTION" in codes

    def test_nonempty_extraction_does_not_flag_empty(self, validator):
        items = [{"sku": "W3624B", "quantity": 1, "line_number": "1", "confidence": 0.95}]
        result = validator.validate_document(items, DocumentType.ORDER)
        codes = [i["issue_type"] for i in result["issues"]]
        assert "EMPTY_EXTRACTION" not in codes


class TestLineNumberGapDetection:
    def test_clean_sequence_no_gap_flagged(self, validator):
        items = [
            {"sku": "A", "line_number": "1"},
            {"sku": "B", "line_number": "2"},
            {"sku": "C", "line_number": "3"},
        ]
        result = validator.validate_document(items, DocumentType.ORDER)
        codes = [i["issue_type"] for i in result["issues"]]
        assert "LINE_NUMBER_GAP" not in codes
        assert result["status"] == "VALID"

    def test_gap_in_sequence_flagged_not_auto_declared_missing(self, validator):
        """Per spec: a gap is surfaced for review, never silently assumed to
        mean the row is genuinely absent."""
        items = [
            {"sku": "A", "line_number": "1"},
            {"sku": "B", "line_number": "2"},
            {"sku": "D", "line_number": "4"},
            {"sku": "E", "line_number": "5"},
        ]
        result = validator.validate_document(items, DocumentType.ORDER)
        gap_issues = [i for i in result["issues"] if i["issue_type"] == "LINE_NUMBER_GAP"]
        assert len(gap_issues) == 1
        assert "3" in gap_issues[0]["message"]
        # INFO severity (a flag to check), not WARNING (does not itself force UNCERTAIN)
        assert gap_issues[0]["severity"] == "INFO"

    def test_decimal_sub_lines_excluded_from_gap_scan(self, validator):
        """5.1/5.2 belong to parent line 5 and must not be treated as part of
        the top-level sequence, and must not themselves trigger a false gap."""
        items = [
            {"sku": "A", "line_number": "5"},
            {"sku": "mod1", "line_number": "5.1"},
            {"sku": "mod2", "line_number": "5.2"},
            {"sku": "B", "line_number": "6"},
        ]
        result = validator.validate_document(items, DocumentType.ORDER)
        codes = [i["issue_type"] for i in result["issues"]]
        assert "LINE_NUMBER_GAP" not in codes

    def test_single_item_insufficient_for_gap_detection(self, validator):
        items = [{"sku": "A", "line_number": "7"}]
        result = validator.validate_document(items, DocumentType.ORDER)
        codes = [i["issue_type"] for i in result["issues"]]
        assert "LINE_NUMBER_GAP" not in codes


class TestValidateDocumentNeverMutatesInput:
    def test_items_list_unchanged(self, validator):
        items = [{"sku": "A", "line_number": "1", "quantity": 2}]
        snapshot = [dict(i) for i in items]
        validator.validate_document(items, DocumentType.ORDER)
        assert items == snapshot
