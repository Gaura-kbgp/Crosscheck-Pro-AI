"""
Settings → NKBA Reference Library: storage-only PDF reference documents.
No extraction, no impact on Cabinet Code Intelligence classification —
purely a versioned reference shelf, global across organizations but
deletable only by the uploading org.
"""
import io
import jwt
import pytest
from unittest.mock import patch

from app.core.config import settings
from app.models.core import Organization, User, Role


def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


FAKE_PDF_BYTES = b"%PDF-1.4\n%fake NKBA reference doc\n"


@pytest.fixture
def org_admin(db_session):
    org = Organization(name="NKBA Org A")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="nkba-admin", organization_id=org.id, email="nkba-admin@a.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_test_token('nkba-admin')}"}, org


@pytest.fixture
def org_b_admin(db_session):
    org = Organization(name="NKBA Org B")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="nkba-admin-b", organization_id=org.id, email="nkba-admin-b@b.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_test_token('nkba-admin-b')}"}


@pytest.fixture(autouse=True)
def mock_storage():
    with patch("app.integrations.storage.StorageService") as mock_cls:
        instance = mock_cls.return_value
        instance.upload_file.return_value = None
        instance.delete_file.return_value = None
        instance.create_signed_url.return_value = "https://mock-storage.local/nkba.pdf"
        yield instance


class TestUpload:
    def test_upload_and_list(self, client, org_admin):
        headers, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(
            "/api/v1/nkba-reference-documents", headers=headers,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        )
        assert res.status_code == 201
        assert res.json()["label"] == "NKBA 5th Edition"

        listed = client.get("/api/v1/nkba-reference-documents", headers=headers).json()
        assert any(d["label"] == "NKBA 5th Edition" for d in listed)

    def test_viewer_cannot_upload(self, client, org_admin, db_session):
        headers, org = org_admin
        viewer = User(auth_id="nkba-viewer", organization_id=org.id, email="v@a.com", role=Role.VIEWER)
        db_session.add(viewer)
        db_session.commit()
        viewer_headers = {"Authorization": f"Bearer {create_test_token('nkba-viewer')}"}
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(
            "/api/v1/nkba-reference-documents", headers=viewer_headers,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        )
        assert res.status_code == 403

    def test_label_required(self, client, org_admin):
        headers, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        res = client.post(
            "/api/v1/nkba-reference-documents", headers=headers,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": ""},
        )
        assert res.status_code in (400, 422)

    def test_non_pdf_rejected(self, client, org_admin):
        headers, _ = org_admin
        f = io.BytesIO(b"not a pdf")
        res = client.post(
            "/api/v1/nkba-reference-documents", headers=headers,
            files={"file": ("nkba.txt", f, "text/plain")}, data={"label": "NKBA 5th Edition"},
        )
        assert res.status_code == 400


class TestGlobalVisibilityAndOwnership:
    def test_visible_to_every_organization(self, client, org_admin, org_b_admin):
        headers_a, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        client.post(
            "/api/v1/nkba-reference-documents", headers=headers_a,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        )
        listed_b = client.get("/api/v1/nkba-reference-documents", headers=org_b_admin).json()
        assert any(d["label"] == "NKBA 5th Edition" for d in listed_b)  # public reference, visible cross-org

    def test_other_org_cannot_delete(self, client, org_admin, org_b_admin):
        headers_a, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        doc_id = client.post(
            "/api/v1/nkba-reference-documents", headers=headers_a,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        ).json()["id"]

        res = client.delete(f"/api/v1/nkba-reference-documents/{doc_id}", headers=org_b_admin)
        assert res.status_code == 400

    def test_uploading_org_can_delete_its_own(self, client, org_admin):
        headers, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        doc_id = client.post(
            "/api/v1/nkba-reference-documents", headers=headers,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        ).json()["id"]

        res = client.delete(f"/api/v1/nkba-reference-documents/{doc_id}", headers=headers)
        assert res.status_code == 204
        listed = client.get("/api/v1/nkba-reference-documents", headers=headers).json()
        assert doc_id not in [d["id"] for d in listed]

    def test_download_url(self, client, org_admin):
        headers, _ = org_admin
        f = io.BytesIO(FAKE_PDF_BYTES)
        doc_id = client.post(
            "/api/v1/nkba-reference-documents", headers=headers,
            files={"file": ("nkba.pdf", f, "application/pdf")}, data={"label": "NKBA 5th Edition"},
        ).json()["id"]
        res = client.get(f"/api/v1/nkba-reference-documents/{doc_id}/download-url", headers=headers)
        assert res.status_code == 200
        assert "url" in res.json()
