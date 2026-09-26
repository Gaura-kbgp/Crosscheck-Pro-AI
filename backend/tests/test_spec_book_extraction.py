"""
Settings → Manufacturer → Upload Specification Book PDF → Extract codes →
Review extracted dictionary → Approve → Manufacturer Dictionary.

The AI extraction call and file storage are mocked (same pattern as
test_documents.py's mock_storage) so these tests run deterministically and
without real OpenAI cost — a separate manual live smoke test (not part of
this automated suite) exercises the real extract_spec_book_codes() call.
"""
import io
import uuid
import jwt
import pytest
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.models.core import (
    Organization, User, Role, Manufacturer, ManufacturerCodeDictionary,
    ManufacturerSpecBook, ManufacturerSpecBookRow, SpecBookStatus, SpecBookRowStatus, ItemCategory,
)
from app.engines.normalization import normalize_sku


def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


FAKE_PDF_BYTES = b"%PDF-1.4\n%fake spec book for tests\n"

FAKE_EXTRACTED_ITEMS = [
    {"code": "BT36B-2", "description": "Base w/ 2 Roll-Out Trays", "category": "CABINET", "confidence": 0.95, "page_number": 3, "source_text": "BT36B-2 ... Base w/ 2 Roll-Out Trays"},
    {"code": "FREIGHTSURCHARGE", "description": "Freight Surcharge", "category": "COMMERCIAL_CHARGE", "confidence": 0.9, "page_number": 12, "source_text": "Freight Surcharge line"},
    {"code": "??AMBIGUOUS1", "description": None, "category": "NOT_A_REAL_CATEGORY", "confidence": 0.2, "page_number": 5, "source_text": "??AMBIGUOUS1"},
]


@pytest.fixture
def org_admin(db_session):
    org = Organization(name="SpecBook Org")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="sb-admin", organization_id=org.id, email="sb-admin@a.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    token = create_test_token("sb-admin")
    return {"Authorization": f"Bearer {token}"}, org, user


@pytest.fixture
def org_b_admin(db_session):
    org = Organization(name="SpecBook Org B")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="sb-admin-b", organization_id=org.id, email="sb-admin-b@b.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    token = create_test_token("sb-admin-b")
    return {"Authorization": f"Bearer {token}"}


class _MockSessionWrapper:
    """Matches the established pattern in test_processing.py: a background
    task's own SessionLocal() call bypasses FastAPI's get_db dependency
    override entirely, so it must be monkeypatched directly to the test's
    in-memory session or it will try to reach a real database."""
    def __init__(self, sess):
        self.sess = sess

    def __getattr__(self, name):
        if name == "close":
            return lambda: None
        return getattr(self.sess, name)


@pytest.fixture(autouse=True)
def mock_storage_and_ai(db_session, monkeypatch):
    monkeypatch.setattr("app.worker.tasks.spec_book_extraction.SessionLocal", lambda: _MockSessionWrapper(db_session))
    with patch("app.integrations.storage.StorageService") as mock_storage_cls, \
         patch("app.worker.tasks.spec_book_extraction.get_ai_provider") as mock_get_ai:
        mock_storage = mock_storage_cls.return_value
        mock_storage.upload_file.return_value = None
        mock_storage.get_file.return_value = FAKE_PDF_BYTES

        mock_ai = MagicMock()
        mock_ai.extract_spec_book_codes.return_value = list(FAKE_EXTRACTED_ITEMS)
        mock_get_ai.return_value = mock_ai

        yield mock_storage, mock_ai


def _make_manufacturer(client, headers):
    res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
    return res.json()["id"]


class TestUploadAndExtraction:
    def test_upload_triggers_extraction_and_creates_pending_rows(self, client, org_admin, mock_storage_and_ai):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)

        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books",
            headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")}, data={"source_version": "2026"},
        )
        assert res.status_code == 201
        book = res.json()
        # The upload response reflects state as of the commit inside upload()
        # — BEFORE the background task runs, since it executes only after
        # the response body is already serialized. Poll a follow-up GET for
        # post-extraction state instead of expecting it in this response.
        assert book["source_version"] == "2026"

        final = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book['id']}", headers=headers).json()
        assert final["status"] == "EXTRACTED"

        rows = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book['id']}/rows", headers=headers).json()
        assert len(rows) == 3
        codes = {r["raw_code"] for r in rows}
        assert "BT36B-2" in codes
        assert all(r["status"] == "PENDING" for r in rows)

    def test_unknown_ai_category_falls_back_to_unknown_never_guessed(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")})
        book_id = res.json()["id"]
        rows = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows", headers=headers).json()
        ambiguous = next(r for r in rows if r["raw_code"] == "??AMBIGUOUS1")
        assert ambiguous["category"] == "UNKNOWN"  # invalid AI category string never silently mapped to a guess

    def test_extraction_failure_marks_book_failed(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        with patch("app.worker.tasks.spec_book_extraction.get_ai_provider") as mock_get_ai:
            mock_ai = MagicMock()
            mock_ai.extract_spec_book_codes.side_effect = RuntimeError("boom")
            mock_get_ai.return_value = mock_ai
            f = io.BytesIO(FAKE_PDF_BYTES)
            book_id = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")}).json()["id"]
        book = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}", headers=headers).json()
        assert book["status"] == "FAILED"
        assert "boom" in book["error"]["message"]

    def test_non_pdf_rejected(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        f = io.BytesIO(b"not a pdf")
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.txt", f, "text/plain")})
        assert res.status_code == 400

    def test_viewer_cannot_upload(self, client, org_admin, db_session):
        headers, org, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        viewer = User(auth_id="sb-viewer", organization_id=org.id, email="v@a.com", role=Role.VIEWER)
        db_session.add(viewer)
        db_session.commit()
        viewer_headers = {"Authorization": f"Bearer {create_test_token('sb-viewer')}"}
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=viewer_headers, files={"file": ("catalog.pdf", f, "application/pdf")})
        assert res.status_code == 403


class TestReviewAndApproval:
    def _upload_and_get_rows(self, client, headers, mfr_id):
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")})
        book_id = res.json()["id"]
        rows = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows", headers=headers).json()
        return book_id, rows

    def test_edit_row_before_approval_preserves_raw_code_field_but_allows_correction(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        book_id, rows = self._upload_and_get_rows(client, headers, mfr_id)
        row = next(r for r in rows if r["raw_code"] == "BT36B-2")

        res = client.patch(
            f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows/{row['id']}",
            headers=headers, json={"description": "Base Cabinet, corrected"},
        )
        assert res.status_code == 200
        assert res.json()["description"] == "Base Cabinet, corrected"
        assert res.json()["raw_code"] == "BT36B-2"  # unrelated field untouched

    def test_reject_row_excludes_it_from_approval(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        book_id, rows = self._upload_and_get_rows(client, headers, mfr_id)
        row = next(r for r in rows if r["raw_code"] == "FREIGHTSURCHARGE")

        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows/{row['id']}/reject", headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"

        approve_res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=headers, json={"approve_all": True})
        assert approve_res.json()["approved"] == 2  # BT36B-2 and the ambiguous row, not the rejected one

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert "FREIGHTSURCHARGE" not in [c["code"] for c in codes]

    def test_approve_all_writes_into_dictionary(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        book_id, rows = self._upload_and_get_rows(client, headers, mfr_id)

        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=headers, json={"approve_all": True})
        assert res.status_code == 200
        body = res.json()
        assert body["approved"] == 3

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        code_map = {c["code"]: c for c in codes}
        assert code_map["BT36B-2"]["category"] == "CABINET"
        assert code_map["BT36B-2"]["source_version"] is None  # no source_version was given on this upload

    def test_approve_specific_rows_only(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        book_id, rows = self._upload_and_get_rows(client, headers, mfr_id)
        target = next(r for r in rows if r["raw_code"] == "BT36B-2")

        res = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve",
            headers=headers, json={"row_ids": [target["id"]]},
        )
        assert res.json()["approved"] == 1
        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert len(codes) == 1
        assert codes[0]["code"] == "BT36B-2"

    def test_approve_skips_duplicate_already_in_dictionary(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "BT36B-2", "category": "CABINET"})

        book_id, rows = self._upload_and_get_rows(client, headers, mfr_id)
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=headers, json={"approve_all": True})
        body = res.json()
        assert body["skipped_duplicates"] == 1
        assert body["approved"] == 2

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert len([c for c in codes if c["code"] == "BT36B-2"]) == 1  # never duplicated

    def test_approved_dictionary_entry_traces_back_to_spec_book(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        f = io.BytesIO(FAKE_PDF_BYTES)
        upload_res = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers,
            files={"file": ("catalog.pdf", f, "application/pdf")}, data={"source_version": "2026-Fall"},
        )
        book_id = upload_res.json()["id"]
        client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=headers, json={"approve_all": True})

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        bt = next(c for c in codes if c["code"] == "BT36B-2")
        assert bt["source_version"] == "2026-Fall"


class TestSpecBookTenantIsolation:
    def test_org_b_cannot_see_org_a_spec_books(self, client, org_admin, org_b_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        f = io.BytesIO(FAKE_PDF_BYTES)
        client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")})

        res = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=org_b_admin)
        assert res.status_code == 404  # manufacturer itself invisible to Org B

    def test_org_b_cannot_approve_org_a_spec_book_rows(self, client, org_admin, org_b_admin):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        f = io.BytesIO(FAKE_PDF_BYTES)
        book_id = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers, files={"file": ("catalog.pdf", f, "application/pdf")}).json()["id"]

        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=org_b_admin, json={"approve_all": True})
        assert res.status_code == 404


class TestCSVAndExcelSpecBooks:
    """Real manufacturer catalog exports are often already-structured CSV/
    Excel, not scanned PDFs. These are parsed deterministically (no AI call
    at all — see parse_tabular_spec_book) but flow through the exact same
    staging/review/approve pipeline as a PDF."""

    def test_csv_spec_book_parsed_without_any_ai_call(self, client, org_admin, mock_storage_and_ai):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        mock_storage, mock_ai = mock_storage_and_ai

        csv_bytes = (
            b"Item Code,Product Description,Product Type\n"
            b"BT36B-2,Base w/ 2 Roll-Out Trays,Cabinet\n"
            b"FREIGHTSURCHARGE,Freight Surcharge,Commercial Charge\n"
        )
        mock_storage.get_file.return_value = csv_bytes
        f = io.BytesIO(csv_bytes)
        book_id = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers,
            files={"file": ("catalog.csv", f, "text/csv")},
        ).json()["id"]

        book = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}", headers=headers).json()
        assert book["status"] == "EXTRACTED"
        assert mock_ai.extract_spec_book_codes.called is False  # deterministic path never calls AI

        rows = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows", headers=headers).json()
        assert len(rows) == 2
        row_map = {r["raw_code"]: r for r in rows}
        assert row_map["BT36B-2"]["category"] == "CABINET"
        assert row_map["BT36B-2"]["description"] == "Base w/ 2 Roll-Out Trays"
        assert row_map["FREIGHTSURCHARGE"]["category"] == "COMMERCIAL_CHARGE"
        assert row_map["BT36B-2"]["confidence"] == 1.0  # deterministic, not a probabilistic guess

    def test_xlsx_spec_book_parsed_deterministically(self, client, org_admin, mock_storage_and_ai):
        import openpyxl
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        mock_storage, mock_ai = mock_storage_and_ai

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["SKU", "Description", "Category"])
        ws.append(["WST3057B", "Stacked Wall Cabinet", "Cabinet"])
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()
        mock_storage.get_file.return_value = xlsx_bytes

        f = io.BytesIO(xlsx_bytes)
        book_id = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers,
            files={"file": ("catalog.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        ).json()["id"]

        book = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}", headers=headers).json()
        assert book["status"] == "EXTRACTED"
        rows = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/rows", headers=headers).json()
        assert len(rows) == 1
        assert rows[0]["raw_code"] == "WST3057B"

    def test_csv_without_code_column_fails_clearly(self, client, org_admin, mock_storage_and_ai):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        mock_storage, _ = mock_storage_and_ai
        csv_bytes = b"Foo,Bar\n1,2\n"
        mock_storage.get_file.return_value = csv_bytes

        f = io.BytesIO(csv_bytes)
        book_id = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers,
            files={"file": ("bad.csv", f, "text/csv")},
        ).json()["id"]

        book = client.get(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}", headers=headers).json()
        assert book["status"] == "FAILED"
        assert "code" in book["error"]["message"].lower()

    def test_csv_approval_flows_into_dictionary_same_as_pdf(self, client, org_admin, mock_storage_and_ai):
        headers, _, _ = org_admin
        mfr_id = _make_manufacturer(client, headers)
        mock_storage, _ = mock_storage_and_ai
        csv_bytes = b"Code,Description,Category\nBT36B-2,Base Cabinet,Cabinet\n"
        mock_storage.get_file.return_value = csv_bytes

        f = io.BytesIO(csv_bytes)
        book_id = client.post(
            f"/api/v1/manufacturers/{mfr_id}/spec-books", headers=headers,
            files={"file": ("catalog.csv", f, "text/csv")},
        ).json()["id"]

        res = client.post(f"/api/v1/manufacturers/{mfr_id}/spec-books/{book_id}/approve", headers=headers, json={"approve_all": True})
        assert res.json()["approved"] == 1
        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert codes[0]["code"] == "BT36B-2"
