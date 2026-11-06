import pytest
import uuid
from io import BytesIO
import jwt
from app.models.core import Organization, User, Project, Role

from app.core.config import settings

from unittest.mock import patch

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

@pytest.fixture(autouse=True)
def mock_storage():
    with patch("app.services.document_service.StorageService") as mock:
        mock_instance = mock.return_value
        mock_instance.upload_file.return_value = "test/path.pdf"
        mock_instance.create_signed_url.return_value = "https://mock-storage.local/test.pdf"
        yield mock

def test_document_upload_success(client, db_session, mock_storage):
    org_a = Organization(name="Org A")
    db_session.add(org_a)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user_a)
    db_session.commit()

    project_a = Project(organization_id=org_a.id, name="Project A")
    db_session.add(project_a)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"PDF mock content"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
    data = {"document_type": "DESIGN"}

    response = client.post(f"/api/v1/projects/{project_a.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["original_filename"] == "test.pdf"
    assert res_data["document_type"] == "DESIGN"
    
    # Test list
    list_response = client.get(f"/api/v1/projects/{project_a.id}/documents", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # Test signed url
    url_response = client.get(f"/api/v1/projects/{project_a.id}/documents/{res_data['id']}", headers=headers)
    assert url_response.status_code == 200
    assert "mock-storage.local" in url_response.json()["url"]

def test_document_upload_invalid_mime(client, db_session):
    org_a = Organization(name="Org A")
    db_session.add(org_a)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user_a)
    project_a = Project(organization_id=org_a.id, name="Project A")
    db_session.add(project_a)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"Binary content"
    files = {"file": ("test.exe", BytesIO(file_content), "application/x-msdownload")}
    data = {"document_type": "DESIGN"}  # ORDER is rejected at boundary; use DESIGN to reach MIME check

    response = client.post(f"/api/v1/projects/{project_a.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 415

def test_document_tenant_isolation(client, db_session):
    org_a = Organization(name="Org A")
    org_b = Organization(name="Org B")
    db_session.add(org_a)
    db_session.add(org_b)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    project_b = Project(organization_id=org_b.id, name="Project B")
    db_session.add(user_a)
    db_session.add(project_b)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"PDF mock content"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
    data = {"document_type": "DESIGN"}

    response = client.post(f"/api/v1/projects/{project_b.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 404 # Project not found in Org A


def test_upload_last_required_document_auto_starts_processing(client, db_session, mock_storage, monkeypatch):
    """Friction reduction: no manual 'Start Processing' click needed once
    Design + Cabinet List + Acknowledgement are all uploaded."""
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *args, **kwargs: None)

    org = Organization(name="Org Auto")
    db_session.add(org)
    db_session.commit()

    user = User(auth_id="auth-auto", organization_id=org.id, email="auto@a.com", role=Role.ADMIN)
    db_session.add(user)
    project = Project(organization_id=org.id, name="Project Auto")
    db_session.add(project)
    db_session.commit()

    token = create_test_token("auth-auto")
    headers = {"Authorization": f"Bearer {token}"}

    def upload(doc_type: str):
        files = {"file": (f"{doc_type}.pdf", BytesIO(b"PDF mock content"), "application/pdf")}
        return client.post(
            f"/api/v1/projects/{project.id}/documents",
            headers=headers, files=files, data={"document_type": doc_type},
        )

    from app.models.core import ProcessingJob

    assert upload("DESIGN").status_code == 201
    assert upload("CABINET_LIST").status_code == 201
    # Only 2/3 types present — must not have auto-started yet.
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 0

    assert upload("ACKNOWLEDGEMENT").status_code == 201
    # Last required type uploaded — a job should now exist, with no manual
    # call to POST /projects/{id}/process.
    jobs = db_session.query(ProcessingJob).filter_by(project_id=project.id).all()
    assert len(jobs) == 1
    assert jobs[0].status.value == "QUEUED"


# ─── Document Replace tests ────────────────────────────────────────────────────

def _setup_replace(db_session, auth_id="auth-rpl", doc_type="DESIGN"):
    """Create org + user + project + one uploaded document; return (client setup dict, doc_id, project_id)."""
    import hashlib
    from app.models.core import Document, DocumentType, DocumentStatus
    org = Organization(name=f"Org {auth_id}")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id=auth_id, organization_id=org.id, email=f"{auth_id}@test.com", role=Role.ADMIN)
    db_session.add(user)
    project = Project(organization_id=org.id, name="Replace Project")
    db_session.add(project)
    db_session.commit()
    content = b"original PDF content"
    doc = Document(
        project_id=project.id, organization_id=org.id,
        document_type=DocumentType[doc_type], original_filename="orig.pdf",
        storage_path=f"{org.id}/{project.id}/{uuid.uuid4()}/orig.pdf",
        mime_type="application/pdf", file_size=len(content),
        status=DocumentStatus.UPLOADED,
        document_hash=hashlib.sha256(content).hexdigest(),
    )
    db_session.add(doc)
    db_session.commit()
    return org, user, project, doc


def test_replace_document_success(client, db_session, mock_storage):
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-ok")
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 200
    res = response.json()
    assert res["original_filename"] == "new.pdf"
    assert res["document_type"] == "DESIGN"


def test_replace_document_same_file_rejected(client, db_session, mock_storage):
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-same")
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    # Upload identical content — hash will match
    files = {"file": ("orig.pdf", BytesIO(b"original PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 400


def test_replace_document_null_hash_skips_same_file_check(client, db_session, mock_storage):
    """Pre-migration documents with null hash must not be blocked by same-file check."""
    from app.models.core import Document, DocumentType, DocumentStatus
    org = Organization(name="Org null-hash")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="auth-rpl-null", organization_id=org.id, email="null@test.com", role=Role.ADMIN)
    db_session.add(user)
    project = Project(organization_id=org.id, name="Null Hash Project")
    db_session.add(project)
    db_session.commit()
    doc = Document(
        project_id=project.id, organization_id=org.id,
        document_type=DocumentType.DESIGN, original_filename="orig.pdf",
        storage_path=f"{org.id}/{project.id}/{uuid.uuid4()}/orig.pdf",
        mime_type="application/pdf", file_size=100,
        status=DocumentStatus.UPLOADED,
        document_hash=None,  # pre-migration: no hash
    )
    db_session.add(doc)
    db_session.commit()
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("orig.pdf", BytesIO(b"original PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 200


def test_replace_document_invalid_mime(client, db_session, mock_storage):
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-mime")
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("bad.exe", BytesIO(b"binary"), "application/x-msdownload")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 415


def test_replace_document_not_found(client, db_session, mock_storage):
    org, user, project, _ = _setup_replace(db_session, auth_id="auth-rpl-404")
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{uuid.uuid4()}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 404


def test_replace_document_cross_org_isolation(client, db_session, mock_storage):
    org_a, user_a, project_a, _ = _setup_replace(db_session, auth_id="auth-rpl-corg-a")
    org_b, user_b, project_b, doc_b = _setup_replace(db_session, auth_id="auth-rpl-corg-b")
    token = create_test_token(user_a.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    # user_a tries to replace a doc that belongs to org_b
    response = client.post(
        f"/api/v1/projects/{project_b.id}/documents/{doc_b.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 404


def test_replace_legacy_order_blocked(client, db_session, mock_storage):
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-ord", doc_type="ORDER")
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 422


def test_replace_document_project_status_reset_to_draft(client, db_session, mock_storage, monkeypatch):
    """After replace, project.status must be DRAFT regardless of its prior state."""
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *args, **kwargs: None)
    from app.models.core import ProjectStatus
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-draft")
    # Put project in a post-processing state
    project.status = ProjectStatus.REVIEW_REQUIRED
    db_session.commit()
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 200
    db_session.refresh(project)
    assert project.status == ProjectStatus.DRAFT


def test_replace_document_active_job_rejected(client, db_session, mock_storage):
    """Replace must be blocked with 409 when a pipeline job is in a non-terminal state."""
    from app.models.core import ProcessingJob, ProcessingJobStatus
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-409")
    job = ProcessingJob(
        project_id=project.id, organization_id=org.id,
        status=ProcessingJobStatus.QUEUED,
        correlation_id=str(uuid.uuid4()),
    )
    db_session.add(job)
    db_session.commit()
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 409


def test_replace_document_clears_stale_results(client, db_session, mock_storage, monkeypatch):
    """Stale MatchGroups and Discrepancies must be deleted atomically with the replace."""
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *args, **kwargs: None)
    from app.models.core import MatchGroup, Discrepancy, MatchGroupStatus, Severity
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-stale")
    mg = MatchGroup(
        project_id=project.id, organization_id=org.id,
        status=MatchGroupStatus.MATCHED,
    )
    db_session.add(mg)
    db_session.flush()
    disc = Discrepancy(
        project_id=project.id, organization_id=org.id,
        match_group_id=mg.id, field="quantity",
        source_values={}, comparison_values={},
        severity=Severity.WARNING,
    )
    db_session.add(disc)
    db_session.commit()
    assert db_session.query(MatchGroup).filter_by(project_id=project.id).count() == 1
    assert db_session.query(Discrepancy).filter_by(project_id=project.id).count() == 1

    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.query(MatchGroup).filter_by(project_id=project.id).count() == 0
    assert db_session.query(Discrepancy).filter_by(project_id=project.id).count() == 0


def test_replace_document_old_doc_removed(client, db_session, mock_storage):
    """Old document row must be gone after a successful replace."""
    from app.models.core import Document
    org, user, project, doc = _setup_replace(db_session, auth_id="auth-rpl-gone")
    old_id = doc.id
    token = create_test_token(user.auth_id)
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("new.pdf", BytesIO(b"new PDF content"), "application/pdf")}
    response = client.post(
        f"/api/v1/projects/{project.id}/documents/{doc.id}/replace",
        headers=headers, files=files
    )
    assert response.status_code == 200
    assert db_session.get(Document, old_id) is None
