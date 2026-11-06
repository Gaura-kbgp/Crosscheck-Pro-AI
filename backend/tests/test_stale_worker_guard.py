"""
Regression tests for the stale-worker concurrency guard in processing.py.

Scenario being tested:
  1. Celery worker fetches old document and starts Stage 2 extraction.
  2. replace_document commits (old_doc deleted, stale MG/D wiped).
  3. Worker's extraction mock completes (or is already done).
  4. Stage 3 guard detects old_doc no longer exists → job FAILED.
  5. No CanonicalLineItems, MatchGroups, or Discrepancies are written.

We simulate step 2 as a side-effect inside the AI extraction mock, which fires
during Stage 2. The pipeline then enters Stage 3 against a DB where old_doc is gone.
"""
import pytest
import uuid
from sqlalchemy.orm import sessionmaker

from app.models.core import (
    Organization, Project, ProjectStatus,
    Document, DocumentType, DocumentStatus,
    ProcessingJob, ProcessingJobStatus,
    CanonicalLineItem, MatchGroup, Discrepancy,
)


def _make_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def _guard_db_session(db_session):
    """Redirect _run_pipeline's _get_db() to the test database engine."""
    TestSession = _make_session_factory(db_session.bind)
    return TestSession


def _setup_project_with_doc(db_session, auth_id="auth-sw"):
    org = Organization(name=f"Org {auth_id}")
    db_session.add(org)
    db_session.commit()
    project = Project(organization_id=org.id, name="Stale Worker Project")
    db_session.add(project)
    db_session.commit()
    old_doc_id = uuid.uuid4()
    doc = Document(
        id=old_doc_id,
        project_id=project.id, organization_id=org.id,
        document_type=DocumentType.DESIGN, original_filename="design.pdf",
        storage_path=f"{org.id}/{project.id}/{old_doc_id}/design.pdf",
        mime_type="application/pdf", file_size=100,
        status=DocumentStatus.UPLOADED,
        document_hash="deadbeef",
    )
    db_session.add(doc)
    db_session.commit()
    job = ProcessingJob(
        project_id=project.id, organization_id=org.id,
        status=ProcessingJobStatus.QUEUED,
        correlation_id=str(uuid.uuid4()),
    )
    db_session.add(job)
    db_session.commit()
    return org, project, doc, job


def test_stale_worker_guard_stage3(db_session, _guard_db_session, monkeypatch):
    """Stage 3 guard: when old_doc is deleted during Stage 2 extraction
    (simulating replace_document committing), the pipeline must fail with
    FAILED and write zero CanonicalLineItems."""
    org, project, old_doc, job = _setup_project_with_doc(db_session, "auth-sw-s3")

    # Redirect pipeline's _get_db to the test engine so all pipeline sessions
    # see the same in-memory database as the test.
    monkeypatch.setattr("app.worker.tasks.processing._get_db", _guard_db_session)

    extraction_called = []

    class MockAI:
        provider_name = "mock"
        model_name = "mock-model"

        def extract_structured_data(self, file_bytes, mime_type, prompt, schema, **kwargs):
            # Simulate replace_document committing during extraction:
            # delete old_doc from the shared test database.
            s = _guard_db_session()
            try:
                s.query(Document).filter_by(id=old_doc.id).delete()
                s.commit()
            finally:
                s.close()
            extraction_called.append(True)
            return {"items": [{"sku": "ABC123", "quantity": 1}]}

    class MockStorage:
        def get_file(self, path):
            return b"%PDF-1.4 mock"
        def upload_file(self, *a, **kw): pass
        def delete_file(self, *a, **kw): pass
        def create_signed_url(self, *a): return "https://mock/file"

    monkeypatch.setattr("app.worker.tasks.processing.get_ai_provider", lambda: MockAI())
    monkeypatch.setattr("app.integrations.storage.StorageService", MockStorage)

    from app.worker.tasks.processing import _run_pipeline
    _run_pipeline(str(job.id), str(project.id), str(org.id), "test-corr", force_reprocess=True)

    # Extraction was called (Stage 2 ran), confirming the guard fires AFTER the replace.
    assert extraction_called, "AI extraction should have been called during Stage 2"

    db_session.expire_all()

    # Guard must have fired: no CanonicalLineItems written.
    assert db_session.query(CanonicalLineItem).filter_by(project_id=project.id).count() == 0, \
        "No CanonicalLineItems should be written after the stale-worker guard fires"

    # Job must be FAILED (not COMPLETED).
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED, \
        f"Job should be FAILED, got {job.status}"


def test_stale_worker_guard_stage4(db_session, _guard_db_session, monkeypatch):
    """Stage 4 guard: even if Stage 3 committed CanonicalLineItems before the
    replacement, Stage 4 detects the missing document and fails before writing
    MatchGroups or Discrepancies."""
    org, project, old_doc, job = _setup_project_with_doc(db_session, "auth-sw-s4")

    class MockAI:
        provider_name = "mock"
        model_name = "mock-model"

        def extract_structured_data(self, file_bytes, mime_type, prompt, schema, **kwargs):
            return {"items": [{"sku": "W2430", "quantity": 2}]}

    class MockStorage:
        def get_file(self, path): return b"%PDF-1.4 mock"
        def upload_file(self, *a, **kw): pass
        def delete_file(self, *a, **kw): pass
        def create_signed_url(self, *a): return "https://mock/file"

    # Inject deletion of old_doc right before Stage 4's guard check.
    # _update_job_status(MATCHING) fires immediately before the Stage 4 guard,
    # so intercepting it simulates replace_document committing after Stage 3
    # but before Stage 4.
    import app.worker.tasks.processing as processing_module
    original_update = processing_module._update_job_status

    def _hooked_update(job_id, new_status, error=None, project_id=None):
        if str(new_status) == str(ProcessingJobStatus.MATCHING):
            s = _guard_db_session()
            try:
                s.query(Document).filter_by(id=old_doc.id).delete()
                s.commit()
            finally:
                s.close()
        return original_update(job_id, new_status, error=error, project_id=project_id)

    monkeypatch.setattr("app.worker.tasks.processing.get_ai_provider", lambda: MockAI())
    monkeypatch.setattr("app.integrations.storage.StorageService", MockStorage)
    monkeypatch.setattr("app.worker.tasks.processing._get_db", _guard_db_session)
    monkeypatch.setattr("app.worker.tasks.processing._update_job_status", _hooked_update)

    from app.worker.tasks.processing import _run_pipeline
    _run_pipeline(str(job.id), str(project.id), str(org.id), "test-corr", force_reprocess=True)

    db_session.expire_all()

    # Stage 3 committed CanonicalLineItems, but replace_document deleted old_doc
    # (and would have cascade-deleted them in PostgreSQL). In SQLite the rows
    # may still exist but no MatchGroups or Discrepancies should be written.
    assert db_session.query(MatchGroup).filter_by(project_id=project.id).count() == 0, \
        "No MatchGroups should be written after Stage 4 guard fires"
    assert db_session.query(Discrepancy).filter_by(project_id=project.id).count() == 0, \
        "No Discrepancies should be written after Stage 4 guard fires"

    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED, \
        f"Job should be FAILED, got {job.status}"
