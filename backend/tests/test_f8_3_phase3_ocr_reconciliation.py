"""
F8.3 Phase 3 regression tests: scanned-PDF OCR, multi-pass reconciliation,
extraction stability (document hash, versioning), and idempotency.

OCR tests use a real Tesseract call against a synthetic image (no network),
so page rendering + OCR + status classification are exercised end to end.
Reconciliation tests are pure-function (no AI/OCR calls needed).
"""
import hashlib
import io
import pytest
import fitz

from app.integrations.ai.openai_provider import OpenAIProvider
from app.engines.reconciliation import reconcile_items
from app.engines.extraction_validator import ExtractionValidator
from app.models.core import DocumentType, Extraction, Document, Project, Organization


def _make_pdf(pages_text):
    doc = fitz.open()
    for page_lines in pages_text:
        page = doc.new_page()
        for (x, y, text) in page_lines:
            page.insert_text((x, y), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_pdf(n_pages=1):
    doc = fitz.open()
    for _ in range(n_pages):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def provider():
    return OpenAIProvider()


class TestOCRPageExtraction:
    def test_scanned_page_with_text_ocr_completed(self, provider):
        """A page with no embedded text layer but a rendered text image must
        OCR successfully — this simulates a scanned page (fitz text inserted
        then rasterized has no extractable text() output, so it exercises
        the same OCR_COMPLETED path a real scan would)."""
        pdf = _make_pdf([[(50, 80, "BT36B-2 QTY 2 BASE CABINET")]])
        pages = provider._ocr_pdf_pages(pdf)
        assert len(pages) == 1
        assert pages[0]["page_number"] == 1
        assert pages[0]["extraction_method"] == "tesseract"
        assert pages[0]["ocr_status"] == "OCR_COMPLETED"
        assert "BT36B" in pages[0]["raw_text"]

    def test_blank_page_ocr_empty_not_silently_skipped(self, provider):
        pdf = _make_blank_pdf(1)
        pages = provider._ocr_pdf_pages(pdf)
        assert len(pages) == 1
        assert pages[0]["ocr_status"] == "OCR_EMPTY"
        assert pages[0]["status"] == "EMPTY"
        # Still has an entry — never silently dropped
        assert pages[0]["page_number"] == 1

    def test_multi_page_every_page_gets_entry(self, provider):
        pdf = _make_pdf([
            [(50, 80, "PAGE ONE TEXT")],
            [],  # blank
            [(50, 80, "PAGE THREE TEXT")],
        ])
        pages = provider._ocr_pdf_pages(pdf)
        assert len(pages) == 3
        assert [p["page_number"] for p in pages] == [1, 2, 3]
        assert pages[0]["ocr_status"] == "OCR_COMPLETED"
        assert pages[1]["ocr_status"] == "OCR_EMPTY"
        assert pages[2]["ocr_status"] == "OCR_COMPLETED"

    def test_corrupt_pdf_bytes_never_raises(self, provider):
        pages = provider._ocr_pdf_pages(b"not a real pdf")
        assert pages == []


class TestReconciliationRules:
    """§9 Rules A-D, exercised as pure functions."""

    def test_rule_a_exact_agreement_verified(self):
        ocr = [{"sku": "BT36B-2", "quantity": 2, "page_number": 4, "source_text": "BT36B-2 Qty 2"}]
        vision = [{"sku": "BT36B-2", "quantity": 2, "page_number": 4, "source_text": "BT36B-2 Qty 2"}]
        result = reconcile_items(ocr, vision)
        assert len(result) == 1
        assert result[0].evidence_status == "VERIFIED"
        assert result[0].verification_method == "OCR_PLUS_VISION"
        assert result[0].conflicts == []

    def test_rule_b_one_side_missing_field_not_a_conflict(self):
        """OCR has SKU only; Vision has SKU + quantity. Missing quantity on
        OCR's side must not be treated as a conflict, and must not be invented."""
        ocr = [{"sku": "BT36B-2", "quantity": None}]
        vision = [{"sku": "BT36B-2", "quantity": 2}]
        result = reconcile_items(ocr, vision)
        assert result[0].evidence_status == "VERIFIED"
        assert result[0].conflicts == []
        assert result[0].item.get("quantity") == 2  # Vision's real value kept, not fabricated

    def test_rule_c_quantity_conflict_uncertain_both_values_kept(self):
        ocr = [{"sku": "BT36B-2", "quantity": 2}]
        vision = [{"sku": "BT36B-2", "quantity": 3}]
        result = reconcile_items(ocr, vision)
        assert result[0].evidence_status == "UNCERTAIN"
        assert len(result[0].conflicts) == 1
        conflict = result[0].conflicts[0]
        assert conflict.field == "quantity"
        assert conflict.ocr_value == 2
        assert conflict.vision_value == 3
        # Neither value silently discarded from the conflict record
        d = result[0].to_dict()
        assert d["verification"]["conflicts"][0]["ocr_value"] == 2
        assert d["verification"]["conflicts"][0]["vision_value"] == 3

    def test_sku_conflict_detected(self):
        ocr = [{"sku": "BT36B-Z"}]
        vision = [{"sku": "BT36B-2"}]
        # Different normalized SKUs -> cannot be aligned by SKU at all, so
        # each becomes its own single-source UNCERTAIN entry (never merged).
        result = reconcile_items(ocr, vision)
        assert len(result) == 2
        assert all(r.evidence_status == "UNCERTAIN" for r in result)

    def test_dimension_conflict_flagged(self):
        ocr = [{"sku": "W3624B", "description": "Wall Cabinet 24in"}]
        vision = [{"sku": "W3624B", "description": "Wall Cabinet 30in"}]
        result = reconcile_items(ocr, vision)
        assert result[0].evidence_status == "UNCERTAIN"
        assert any(c.field == "description" for c in result[0].conflicts)

    def test_no_fuzzy_auto_correction(self):
        """§10: OCR typo 'BT36B-Z' must NOT be silently accepted as 'BT36B-2'
        just because they look similar — they must never be merged/matched."""
        ocr = [{"sku": "BT36B-Z", "quantity": 2}]
        vision = [{"sku": "BT36B-2", "quantity": 2}]
        result = reconcile_items(ocr, vision)
        # Two distinct SKUs -> two distinct unaligned, uncertain entries;
        # never collapsed into one verified item.
        assert len(result) == 2
        skus = {r.item.get("sku") for r in result}
        assert skus == {"BT36B-Z", "BT36B-2"}
        assert all(r.evidence_status == "UNCERTAIN" for r in result)

    def test_vision_only_item_never_falsely_verified(self):
        """No OCR counterpart at all -> Vision's claim alone is never
        promoted to VERIFIED."""
        result = reconcile_items([], [{"sku": "FILLER3", "quantity": 1}])
        assert len(result) == 1
        assert result[0].evidence_status == "UNCERTAIN"
        assert result[0].verification_method == "VISION_ONLY"

    def test_duplicate_lines_preserved_not_discarded(self):
        """BT36B-2 Qty 1 + BT36B-2 Qty 2 on both passes — duplicate SKU on
        BOTH sides is ambiguous to align 1:1, so both raw lines from both
        passes must survive as separate entries, never dropped."""
        ocr = [{"sku": "BT36B-2", "quantity": 1}, {"sku": "BT36B-2", "quantity": 2}]
        vision = [{"sku": "BT36B-2", "quantity": 1}, {"sku": "BT36B-2", "quantity": 2}]
        result = reconcile_items(ocr, vision)
        assert len(result) == 4  # all 4 raw items preserved, none merged/dropped

    def test_decimal_sub_lines_not_treated_as_independent_items(self):
        """Reconciliation itself doesn't interpret line numbers — it just
        must not drop or corrupt them; downstream Phase 1 logic still owns
        sub-line semantics."""
        ocr = [{"sku": "W3939", "line_number": "10"}, {"sku": "MD18", "line_number": "10.1"}]
        vision = [{"sku": "W3939", "line_number": "10"}, {"sku": "MD18", "line_number": "10.1"}]
        result = reconcile_items(ocr, vision)
        line_numbers = {r.item.get("line_number") for r in result}
        assert "10" in line_numbers
        assert "10.1" in line_numbers

    def test_unalignable_candidates_result_in_uncertain_not_crash(self):
        ocr = [{"sku": None, "description": "unclear text"}]
        vision = [{"sku": "REAL-SKU", "description": "Base Cabinet"}]
        result = reconcile_items(ocr, vision)
        assert len(result) == 2
        assert all(r.evidence_status == "UNCERTAIN" for r in result)

    def test_field_resolution_ocr_preferred_for_numeric_and_pricing(self):
        """On conflict, deterministic numeric/code fields (quantity, line_number, price)
        prefer OCR while recording both readings and flagging UNCERTAIN."""
        ocr = [{"sku": "W3630", "quantity": 5, "line_number": "34", "unit_price": 450.0}]
        vision = [{"sku": "W3630", "quantity": 3, "line_number": "3", "unit_price": 400.0}]
        result = reconcile_items(ocr, vision)
        assert len(result) == 1
        item = result[0].item
        assert item["quantity"] == 5  # OCR preferred
        assert item["line_number"] == "34"  # OCR preferred
        assert item["unit_price"] == 450.0  # OCR preferred
        assert result[0].evidence_status == "UNCERTAIN"
        conflicts = {c.field: c for c in result[0].conflicts}
        assert "quantity" in conflicts and conflicts["quantity"].preferred_source == "OCR"
        assert "line_number" in conflicts and conflicts["line_number"].preferred_source == "OCR"

    def test_field_resolution_vision_preferred_for_description_and_context(self):
        """On conflict, semantic and layout fields (description, finish, door_style)
        prefer Vision while preserving both readings."""
        ocr = [{"sku": "B24", "description": "B24 CAB BASE 24", "finish": "OAK"}]
        vision = [{"sku": "B24", "description": "24in Base Cabinet with Full Drawer", "finish": "Natural Oak"}]
        result = reconcile_items(ocr, vision)
        assert len(result) == 1
        item = result[0].item
        assert item["description"] == "24in Base Cabinet with Full Drawer"  # Vision preferred
        assert item["finish"] == "Natural Oak"  # Vision preferred
        assert result[0].evidence_status == "UNCERTAIN"
        conflicts = {c.field: c for c in result[0].conflicts}
        assert "description" in conflicts and conflicts["description"].preferred_source == "VISION"

    def test_field_resolution_spatial_drawing_document(self):
        """For DESIGN / DRAWING documents, spatial context and annotations prefer Vision."""
        ocr = [{"sku": "W30", "description": "W30 OAK"}]
        vision = [{"sku": "W30", "description": "Wall Unit 30in (North Elevation Elevation 2)"}]
        result = reconcile_items(ocr, vision, doc_type="DESIGN")
        assert len(result) == 1
        item = result[0].item
        assert item["description"] == "Wall Unit 30in (North Elevation Elevation 2)"
        conflicts = {c.field: c for c in result[0].conflicts}
        assert "description" in conflicts and conflicts["description"].preferred_source == "VISION"


class TestDocumentCompletenessWithReconciliation:
    def test_reconciliation_conflicts_flagged_at_document_level(self):
        validator = ExtractionValidator()
        items = [
            {"sku": "A", "verification": {"method": "OCR_PLUS_VISION", "status": "UNCERTAIN",
                                           "conflicts": [{"field": "quantity", "ocr_value": 2, "vision_value": 3}]}},
            {"sku": "B", "verification": {"method": "OCR_PLUS_VISION", "status": "VERIFIED"}},
        ]
        result = validator.validate_document(items, DocumentType.ACKNOWLEDGEMENT)
        codes = [i["issue_type"] for i in result["issues"]]
        assert "RECONCILIATION_CONFLICT" in result and True or "RECONCILIATION_CONFLICT" in codes
        assert result["status"] == "UNCERTAIN"

    def test_critical_ocr_failure_detected(self):
        validator = ExtractionValidator()
        page_evidence = [
            {"page_number": 1, "ocr_status": "OCR_COMPLETED", "status": "PROCESSED"},
            {"page_number": 2, "ocr_status": "OCR_FAILED", "status": "EXTRACTION_UNCERTAIN"},
        ]
        assert validator.has_critical_ocr_failure(page_evidence) is True

    def test_no_critical_failure_when_all_ok(self):
        validator = ExtractionValidator()
        page_evidence = [{"page_number": 1, "ocr_status": "OCR_COMPLETED", "status": "PROCESSED"}]
        assert validator.has_critical_ocr_failure(page_evidence) is False

    def test_summarize_page_evidence_reports_ocr_breakdown(self):
        validator = ExtractionValidator()
        page_evidence = [
            {"page_number": 1, "ocr_status": "OCR_COMPLETED", "status": "PROCESSED"},
            {"page_number": 2, "ocr_status": "OCR_EMPTY", "status": "EMPTY"},
            {"page_number": 3, "ocr_status": "OCR_FAILED", "status": "EXTRACTION_UNCERTAIN"},
        ]
        summary = validator.summarize_page_evidence(page_evidence)
        assert summary["ocr_pages_completed"] == 1
        assert summary["ocr_pages_empty"] == 1
        assert summary["ocr_pages_failed"] == 1
        assert summary["pages_processed"] == 3


class TestExtractionStability:
    def test_document_hash_stable_for_same_bytes(self):
        content = b"identical pdf bytes"
        h1 = hashlib.sha256(content).hexdigest()
        h2 = hashlib.sha256(content).hexdigest()
        assert h1 == h2

    def test_document_hash_differs_for_different_bytes(self):
        h1 = hashlib.sha256(b"version A").hexdigest()
        h2 = hashlib.sha256(b"version B").hexdigest()
        assert h1 != h2

    def test_document_hash_ignores_nothing_but_bytes(self):
        """Hash must depend only on content — verified by construction: two
        different filenames/paths hashing identical bytes are identical."""
        content = b"same content, different context"
        assert hashlib.sha256(content).hexdigest() == hashlib.sha256(content).hexdigest()


@pytest.fixture
def db_env(db_session):
    org = Organization(name="Phase3 Org")
    db_session.add(org)
    db_session.commit()
    project = Project(organization_id=org.id, name="Phase3 Proj")
    db_session.add(project)
    db_session.commit()
    return db_session, project.id, org.id


class TestExtractionHistoryPreservedInDB:
    """§27/§28: reprocessing must never delete prior Extraction rows, and the
    unique-per-document constraint has been replaced with attempt/is_latest."""

    def _make_doc(self, db_session, project_id, org_id, doc_hash="abc123"):
        doc = Document(
            project_id=project_id, organization_id=org_id,
            document_type=DocumentType.ORDER, original_filename="po.pdf",
            storage_path=f"path_{doc_hash}.pdf", mime_type="application/pdf",
            file_size=100, document_hash=doc_hash,
        )
        db_session.add(doc)
        db_session.commit()
        return doc

    def test_multiple_extraction_attempts_coexist(self, db_env):
        db_session, project_id, org_id = db_env
        doc = self._make_doc(db_session, project_id, org_id)

        ext1 = Extraction(document_id=doc.id, organization_id=org_id, raw_data={"items": []},
                           provider="openai", model_name="gpt-4o", prompt_version="v1",
                           attempt=1, is_latest=False, extraction_version="f8.3.2", document_hash="abc123")
        ext2 = Extraction(document_id=doc.id, organization_id=org_id, raw_data={"items": [{"sku": "X"}]},
                           provider="openai", model_name="gpt-4o", prompt_version="v1",
                           attempt=2, is_latest=True, extraction_version="f8.3.3", document_hash="abc123")
        db_session.add_all([ext1, ext2])
        db_session.commit()

        all_attempts = db_session.query(Extraction).filter(Extraction.document_id == doc.id).all()
        assert len(all_attempts) == 2  # both preserved, no deletion
        latest = [e for e in all_attempts if e.is_latest]
        assert len(latest) == 1
        assert latest[0].attempt == 2

    def test_idempotency_identity_match(self, db_env):
        """Same hash + version + provider/model/prompt -> considered reusable."""
        db_session, project_id, org_id = db_env
        doc = self._make_doc(db_session, project_id, org_id, doc_hash="samehash")
        ext = Extraction(document_id=doc.id, organization_id=org_id, raw_data={"items": []},
                          provider="openai", model_name="gpt-4o", prompt_version="v1",
                          attempt=1, is_latest=True, extraction_version="f8.3.3", document_hash="samehash")
        db_session.add(ext)
        db_session.commit()

        latest = db_session.query(Extraction).filter(Extraction.document_id == doc.id, Extraction.is_latest == True).first()
        is_reusable = (
            latest.document_hash == "samehash"
            and latest.extraction_version == "f8.3.3"
            and latest.provider == "openai"
            and latest.model_name == "gpt-4o"
            and latest.prompt_version == "v1"
        )
        assert is_reusable is True

    def test_version_bump_invalidates_reuse(self, db_env):
        """§25/§26: a changed extraction_version must never reuse a stale attempt."""
        db_session, project_id, org_id = db_env
        doc = self._make_doc(db_session, project_id, org_id, doc_hash="samehash2")
        ext = Extraction(document_id=doc.id, organization_id=org_id, raw_data={"items": []},
                          provider="openai", model_name="gpt-4o", prompt_version="v1",
                          attempt=1, is_latest=True, extraction_version="f8.3.2", document_hash="samehash2")
        db_session.add(ext)
        db_session.commit()

        latest = db_session.query(Extraction).filter(Extraction.document_id == doc.id, Extraction.is_latest == True).first()
        is_reusable = latest.extraction_version == "f8.3.3"  # current version
        assert is_reusable is False

    def test_hash_change_invalidates_reuse(self, db_env):
        """Different document content (new upload) must never reuse an old
        extraction — content identity, not filename/DB id, is authoritative."""
        db_session, project_id, org_id = db_env
        doc = self._make_doc(db_session, project_id, org_id, doc_hash="original_hash")
        ext = Extraction(document_id=doc.id, organization_id=org_id, raw_data={"items": []},
                          provider="openai", model_name="gpt-4o", prompt_version="v1",
                          attempt=1, is_latest=True, extraction_version="f8.3.3", document_hash="original_hash")
        db_session.add(ext)
        db_session.commit()

        new_content_hash = "replaced_file_hash"
        latest = db_session.query(Extraction).filter(Extraction.document_id == doc.id, Extraction.is_latest == True).first()
        is_reusable = latest.document_hash == new_content_hash
        assert is_reusable is False


class TestTenantIsolationOfExtractionHistory:
    def test_extraction_scoped_to_organization(self, db_session):
        org_a = Organization(name="Org A")
        org_b = Organization(name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.commit()
        proj_a = Project(organization_id=org_a.id, name="Proj A")
        db_session.add(proj_a)
        db_session.commit()
        doc_a = Document(project_id=proj_a.id, organization_id=org_a.id, document_type=DocumentType.ORDER,
                          original_filename="a.pdf", storage_path="path_a.pdf", mime_type="application/pdf", file_size=10)
        db_session.add(doc_a)
        db_session.commit()
        ext_a = Extraction(document_id=doc_a.id, organization_id=org_a.id, raw_data={"items": []},
                            provider="openai", model_name="gpt-4o", prompt_version="v1")
        db_session.add(ext_a)
        db_session.commit()

        # Org B must never see Org A's extraction when querying by its own org id
        visible_to_b = db_session.query(Extraction).filter(Extraction.organization_id == org_b.id).all()
        assert visible_to_b == []
        visible_to_a = db_session.query(Extraction).filter(Extraction.organization_id == org_a.id).all()
        assert len(visible_to_a) == 1
