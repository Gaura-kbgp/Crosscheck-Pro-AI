"""
F8.3 Phase 2 regression tests: PyMuPDF page/block evidence extraction and
evidence verification against AI-reported page_number/source_text claims.

Synthetic PDFs are built with fitz directly (no network/AI calls needed) so
page numbers, block positions, and text content are exactly known ground
truth to assert against.
"""
import pytest
import fitz

from app.integrations.ai.openai_provider import OpenAIProvider
from app.engines.extraction_validator import ExtractionValidator
from app.models.core import DocumentType


def _make_pdf(pages_text: list) -> bytes:
    """pages_text: list of lists of (x, y, text) triples, one list per page."""
    doc = fitz.open()
    for page_lines in pages_text:
        page = doc.new_page()
        for (x, y, text) in page_lines:
            page.insert_text((x, y), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def provider():
    return OpenAIProvider()


@pytest.fixture
def validator():
    return ExtractionValidator()


class TestPageEvidenceExtraction:
    def test_page_numbers_preserved_in_order(self, provider):
        pdf = _make_pdf([
            [(50, 50, "PAGE ONE CONTENT")],
            [(50, 50, "PAGE TWO CONTENT")],
            [(50, 50, "PAGE THREE CONTENT")],
        ])
        pages = provider._get_pdf_page_evidence(pdf)
        assert [p["page_number"] for p in pages] == [1, 2, 3]
        assert "PAGE ONE CONTENT" in pages[0]["raw_text"]
        assert "PAGE TWO CONTENT" in pages[1]["raw_text"]
        assert "PAGE THREE CONTENT" in pages[2]["raw_text"]

    def test_block_index_and_coordinates_preserved(self, provider):
        pdf = _make_pdf([[(50, 50, "SKU-A ROW"), (50, 150, "SKU-B ROW")]])
        pages = provider._get_pdf_page_evidence(pdf)
        blocks = pages[0]["blocks"]
        assert len(blocks) >= 2
        for b in blocks:
            assert "block_index" in b
            assert all(k in b for k in ("x0", "y0", "x1", "y1", "text"))

    def test_every_page_gets_a_status_none_silently_skipped(self, provider):
        pdf = _make_pdf([[(50, 50, "HAS TEXT")], []])  # page 2 has no text at all
        pages = provider._get_pdf_page_evidence(pdf)
        assert len(pages) == 2
        assert pages[0]["status"] == "PROCESSED"
        assert pages[1]["status"] == "EMPTY"
        # Empty page still has a raw_text key (empty string), never omitted
        assert pages[1]["raw_text"] == ""

    def test_reading_order_top_to_bottom(self, provider):
        """Text inserted lower on the page must read after text inserted higher,
        even if written to the PDF in a different order."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 300), "BOTTOM ROW")
        page.insert_text((50, 50), "TOP ROW")
        pdf = doc.tobytes()
        doc.close()

        pages = OpenAIProvider()._get_pdf_page_evidence(pdf)
        raw_text = pages[0]["raw_text"]
        assert raw_text.index("TOP ROW") < raw_text.index("BOTTOM ROW")

    def test_flattened_text_still_matches_legacy_format(self, provider):
        """_extract_text_from_pdf (used to build the AI prompt) must still
        produce '--- PAGE N ---' markers, unchanged from before Phase 2."""
        pdf = _make_pdf([[(50, 50, "ROW ONE")], [(50, 50, "ROW TWO")]])
        text = provider._extract_text_from_pdf(pdf)
        assert "--- PAGE 1 ---" in text
        assert "--- PAGE 2 ---" in text
        assert "ROW ONE" in text
        assert "ROW TWO" in text


class TestEvidenceValidation:
    def test_matching_source_text_is_verified(self, validator):
        page_evidence = [{"page_number": 1, "status": "PROCESSED", "raw_text": "BT36B-2 Base Cabinet Qty 2", "extraction_method": "pymupdf"}]
        item = {"sku": "BT36B-2", "page_number": 1, "source_text": "BT36B-2 Base Cabinet Qty 2"}
        status, issues = validator.validate_evidence(item, page_evidence)
        assert status == "VERIFIED"
        assert issues == []

    def test_sku_only_match_still_verifies(self, validator):
        """Even if source_text has minor drift, a SKU that literally appears
        on the claimed page is still real, verifiable evidence."""
        page_evidence = [{"page_number": 2, "status": "PROCESSED", "raw_text": "...BFHC12 Filler Panel...", "extraction_method": "pymupdf"}]
        item = {"sku": "BFHC12", "page_number": 2, "source_text": "some slightly different paraphrase"}
        status, issues = validator.validate_evidence(item, page_evidence)
        assert status == "VERIFIED"

    def test_nonexistent_page_flags_invalid_evidence(self, validator):
        page_evidence = [{"page_number": 1, "status": "PROCESSED", "raw_text": "real content", "extraction_method": "pymupdf"}]
        item = {"sku": "X", "page_number": 99, "source_text": "real content"}
        status, issues = validator.validate_evidence(item, page_evidence)
        assert status == "UNCERTAIN"
        assert any(i.issue_type == "INVALID_EVIDENCE" for i in issues)

    def test_no_page_or_source_text_flags_empty_evidence(self, validator):
        status, issues = validator.validate_evidence({"sku": "X"}, [])
        assert status == "UNCERTAIN"
        assert any(i.issue_type == "EMPTY_EVIDENCE" for i in issues)

    def test_hallucinated_source_text_flagged_not_trusted(self, validator):
        """The item claims text that never appeared on that page — this is
        exactly the 'never trust AI-generated evidence' case (§19)."""
        page_evidence = [{"page_number": 1, "status": "PROCESSED", "raw_text": "totally different content here", "extraction_method": "pymupdf"}]
        item = {"sku": "NOTPRESENT", "page_number": 1, "source_text": "this text was never on the page"}
        status, issues = validator.validate_evidence(item, page_evidence)
        assert status == "UNCERTAIN"
        assert any(i.issue_type == "SOURCE_TEXT_MISMATCH" for i in issues)

    def test_scanned_page_never_falsely_verified(self, validator):
        """A vision/scanned page has no deterministic text layer — evidence
        must stay honestly UNCERTAIN, never claim VERIFIED without real text."""
        page_evidence = [{"page_number": 1, "status": "EXTRACTION_UNCERTAIN", "raw_text": None, "extraction_method": "vision"}]
        item = {"sku": "X", "page_number": 1, "source_text": "X appears here"}
        status, issues = validator.validate_evidence(item, page_evidence)
        assert status == "UNCERTAIN"

    def test_item_never_mutated_by_validation(self, validator):
        item = {"sku": "X", "page_number": 1, "source_text": "X here"}
        snapshot = dict(item)
        validator.validate_evidence(item, [{"page_number": 1, "status": "PROCESSED", "raw_text": "X here", "extraction_method": "pymupdf"}])
        assert item == snapshot


class TestPageEvidenceSummary:
    def test_summary_is_bounded_no_raw_text_or_blocks(self, validator):
        page_evidence = [
            {"page_number": 1, "status": "PROCESSED", "raw_text": "a" * 5000, "extraction_method": "pymupdf", "blocks": [{"x0": 1}] * 60},
            {"page_number": 2, "status": "EMPTY", "raw_text": "", "extraction_method": "pymupdf", "blocks": []},
        ]
        summary = validator.summarize_page_evidence(page_evidence)
        assert summary["pages_processed"] == 2
        assert summary["pages_with_text_evidence"] == 1
        assert summary["pages_uncertain"] == 1
        # No raw_text or blocks leaked into the persisted summary
        dumped = str(summary)
        assert "a" * 100 not in dumped


class TestDecimalSubLinesUnaffectedByPhase2:
    """Phase 1's decimal sub-line handling must remain unchanged — evidence
    validation is orthogonal to line-number gap detection."""

    def test_gap_detection_still_works_alongside_evidence_fields(self):
        validator = ExtractionValidator()
        items = [
            {"sku": "A", "line_number": "5", "page_number": 1, "source_text": "5 A"},
            {"sku": "mod", "line_number": "5.1", "page_number": 1, "source_text": "5.1 mod"},
            {"sku": "B", "line_number": "7", "page_number": 1, "source_text": "7 B"},
        ]
        result = validator.validate_document(items, DocumentType.ORDER)
        gap_issues = [i for i in result["issues"] if i["issue_type"] == "LINE_NUMBER_GAP"]
        assert len(gap_issues) == 1
        assert "6" in gap_issues[0]["message"]


class TestTenantIsolationOfEvidence:
    """Evidence lives inside CanonicalLineItem.source_metadata, which is
    already scoped by project_id/organization_id like every other field on
    that row — this asserts the evidence payload itself carries no
    cross-tenant reference (e.g. no document storage URL, no other org's data)."""

    def test_evidence_payload_contains_no_storage_paths_or_urls(self):
        validator = ExtractionValidator()
        page_evidence = [{"page_number": 1, "status": "PROCESSED", "raw_text": "BT36B-2 content", "extraction_method": "pymupdf"}]
        item = {"sku": "BT36B-2", "page_number": 1, "source_text": "BT36B-2 content"}
        status, issues = validator.validate_evidence(item, page_evidence)
        # Evidence status/issues are pure text/enums — no URLs, no storage paths, no IDs from other records
        for i in issues:
            d = i.to_dict()
            assert "http" not in str(d.get("message", ""))
            assert "supabase" not in str(d.get("message", "")).lower()
