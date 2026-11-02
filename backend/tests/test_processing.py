import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.models.core import Organization, User, Role, Project, Document, DocumentType, ProcessingJob, ProcessingJobStatus, CanonicalLineItem, Extraction
import jwt
from app.core.config import settings
from app.worker.tasks.processing import process_project_pipeline
import json

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

def test_start_processing_success(client: TestClient, db_session, monkeypatch):
    org = Organization(name="Org A")
    db_session.add(org)
    db_session.commit()
    
    user = User(auth_id="auth-a", organization_id=org.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user)
    
    project = Project(organization_id=org.id, name="Project A")
    db_session.add(project)
    db_session.commit()
    
    # Add required documents
    for dtype in [DocumentType.DESIGN, DocumentType.ORDER, DocumentType.ACKNOWLEDGEMENT]:
        doc = Document(
            project_id=project.id,
            organization_id=org.id,
            document_type=dtype,
            original_filename="test.pdf",
            storage_path=f"path_{dtype.value}.pdf",
            mime_type="application/pdf",
            file_size=100
        )
        db_session.add(doc)
    db_session.commit()
    
    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Mock celery task to avoid Redis connection error
    monkeypatch.setattr("celery.app.task.Task.delay", lambda *args, **kwargs: None)
    
    response = client.post(f"/api/v1/projects/{project.id}/process", headers=headers)
    assert response.status_code == 201
    
    job_id = response.json()["id"]
    
    # Get status
    status_res = client.get(f"/api/v1/jobs/{job_id}/status", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "QUEUED"

def test_start_processing_missing_docs(client: TestClient, db_session):
    org = Organization(name="Org B")
    db_session.add(org)
    db_session.commit()
    
    user = User(auth_id="auth-b", organization_id=org.id, email="b@b.com", role=Role.ADMIN)
    project = Project(organization_id=org.id, name="Project B")
    db_session.add(user)
    db_session.add(project)
    db_session.commit()
    
    # Only adding DESIGN
    doc = Document(
        project_id=project.id,
        organization_id=org.id,
        document_type=DocumentType.DESIGN,
        original_filename="test.pdf",
        storage_path="path.pdf",
        mime_type="application/pdf",
        file_size=100
    )
    db_session.add(doc)
    db_session.commit()
    
    token = create_test_token("auth-b")
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(f"/api/v1/projects/{project.id}/process", headers=headers)
    assert response.status_code == 400
    assert "missing required documents" in response.json()["detail"]

def test_processing_task_pipeline_success(db_session, engine, monkeypatch):
    org = Organization(name="Org C")
    db_session.add(org)
    db_session.commit()
    
    project = Project(organization_id=org.id, name="Project C")
    db_session.add(project)
    db_session.commit()
    
    # Add required documents
    for dtype in [DocumentType.DESIGN, DocumentType.ORDER, DocumentType.ACKNOWLEDGEMENT]:
        doc = Document(
            project_id=project.id,
            organization_id=org.id,
            document_type=dtype,
            original_filename="test.pdf",
            storage_path=f"path_{dtype.value}.pdf",
            mime_type="application/pdf",
            file_size=100
        )
        db_session.add(doc)
    
    job = ProcessingJob(
        project_id=project.id,
        organization_id=org.id,
        status=ProcessingJobStatus.QUEUED,
        correlation_id="corr-123"
    )
    db_session.add(job)
    db_session.commit()
    
    # Mock Gemini extraction
    class MockGeminiProvider:
        def extract_structured_data(self, *args, **kwargs):
            return {
                "items": [
                    {
                        "sku": "  CAB-123  ",
                        "description": "Cabinet Base",
                        "quantity": "2 EA",
                        "dimensions": {"width": " 36 "},
                        "confidence": 0.95,
                        "price": "100.00"
                    }
                ]
            }
            
    monkeypatch.setattr("app.worker.tasks.processing.get_ai_provider", lambda: MockGeminiProvider())
    monkeypatch.setattr("app.integrations.storage.StorageService.get_file", lambda self, path: b"%PDF-1.4 dummy bytes")
    # Document extraction now runs concurrently, so each _get_db() call needs a
    # genuinely independent Session (as production's real SessionLocal()
    # factory provides) rather than one shared Session object, which isn't
    # thread-safe. Sessions bind to the same test engine, but that engine is a
    # single in-memory sqlite connection (StaticPool) shared by every session —
    # unlike production's real Postgres connection pool, where concurrent
    # sessions get genuinely independent connections, one raw sqlite3
    # connection cannot safely drive simultaneous operations from multiple
    # threads even via separate ORM Session wrappers. A lock around each
    # session's lifetime (acquired on creation, released on close) serializes
    # just the connection usage — this is a sqlite test-driver limitation, not
    # something that exists against Postgres in production.
    import threading
    from sqlalchemy.orm import sessionmaker
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session_lock = threading.Lock()

    def _locked_session_factory():
        session_lock.acquire()
        session = TestSessionLocal()
        real_close = session.close
        def _unlocking_close():
            try:
                real_close()
            finally:
                session_lock.release()
        session.close = _unlocking_close
        return session

    monkeypatch.setattr("app.worker.tasks.processing.SessionLocal", _locked_session_factory)
    
    # Call the task synchronously
    process_project_pipeline(str(job.id), str(project.id), str(org.id), "corr-123")
    
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.COMPLETED

    # Verify extraction created
    extractions = db_session.query(Extraction).all()
    assert len(extractions) == 3
    
    # Verify canonical line items created and normalized
    items = db_session.query(CanonicalLineItem).all()
    assert len(items) == 3
    
    # Check normalization
    assert items[0].raw_sku == "  CAB-123  "
    assert items[0].normalized_sku == "CAB-123"
    assert items[0].quantity == 2
    assert items[0].dimensions.get("width") == 36.0
