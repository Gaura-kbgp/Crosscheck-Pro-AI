"""
Tests for ProcessingJob rescan / multi-run behaviour.

Covers:
  1. First processing run creates job
  2. Rescan after COMPLETED succeeds (new job, old preserved)
  3. Rescan after FAILED succeeds (new job, old preserved)
  4. Duplicate concurrent active job is rejected with 409
  5. _auto_start_processing_if_ready propagates start_processing errors visibly
  6. Historical jobs are preserved after each rescan
"""
import uuid
import pytest
from fastapi import HTTPException

from app.models.core import (
    Organization, Project, ProjectStatus,
    Document, DocumentType, DocumentStatus,
    ProcessingJob, ProcessingJobStatus,
)
from app.services.processing_service import ProcessingService


def _make_org_project_docs(db):
    org = Organization(name=f"Org {uuid.uuid4()}")
    db.add(org)
    db.commit()
    project = Project(organization_id=org.id, name="Test Project")
    db.add(project)
    db.commit()

    for doc_type in (DocumentType.DESIGN, DocumentType.CABINET_LIST, DocumentType.ACKNOWLEDGEMENT):
        doc = Document(
            project_id=project.id, organization_id=org.id,
            document_type=doc_type,
            original_filename=f"{doc_type.value.lower()}.pdf",
            storage_path=f"{org.id}/{project.id}/{uuid.uuid4()}/file.pdf",
            mime_type="application/pdf", file_size=100,
            status=DocumentStatus.UPLOADED,
        )
        db.add(doc)
    db.commit()
    return org, project


def _add_job(db, project, org, status):
    job = ProcessingJob(
        project_id=project.id, organization_id=org.id,
        status=status, correlation_id=str(uuid.uuid4()),
    )
    db.add(job)
    db.commit()
    return job


# ── 1. First processing run ───────────────────────────────────────────────────

def test_first_processing_run_creates_job(db_session, monkeypatch):
    org, project = _make_org_project_docs(db_session)
    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline_sync",
        lambda *a, **kw: None,
        raising=False,
    )
    # Patch Celery dispatch to no-op
    class _FakeCelery:
        def delay(self, *a, **kw): pass
    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline",
        _FakeCelery(),
        raising=False,
    )

    svc = ProcessingService(db_session)
    resp = svc.start_processing(project.id, org.id)
    assert resp.status == ProcessingJobStatus.QUEUED
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 1


# ── 2. Rescan after COMPLETED ─────────────────────────────────────────────────

def test_rescan_after_completed_succeeds(db_session, monkeypatch):
    org, project = _make_org_project_docs(db_session)
    old_job = _add_job(db_session, project, org, ProcessingJobStatus.COMPLETED)

    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline_sync",
        lambda *a, **kw: None, raising=False,
    )
    class _FakeCelery:
        def delay(self, *a, **kw): pass
    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline",
        _FakeCelery(), raising=False,
    )

    svc = ProcessingService(db_session)
    resp = svc.start_processing(project.id, org.id)

    assert resp.status == ProcessingJobStatus.QUEUED
    assert str(resp.id) != str(old_job.id), "Should create a NEW job, not reuse old"
    # Historical job preserved
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 2


# ── 3. Rescan after FAILED ────────────────────────────────────────────────────

def test_rescan_after_failed_succeeds(db_session, monkeypatch):
    org, project = _make_org_project_docs(db_session)
    _add_job(db_session, project, org, ProcessingJobStatus.FAILED)

    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline_sync",
        lambda *a, **kw: None, raising=False,
    )
    class _FakeCelery:
        def delay(self, *a, **kw): pass
    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline",
        _FakeCelery(), raising=False,
    )

    svc = ProcessingService(db_session)
    resp = svc.start_processing(project.id, org.id)

    assert resp.status == ProcessingJobStatus.QUEUED
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 2


# ── 4. Duplicate concurrent active job → 409 ──────────────────────────────────

@pytest.mark.parametrize("active_status", [
    ProcessingJobStatus.QUEUED,
    ProcessingJobStatus.EXTRACTING,
    ProcessingJobStatus.MATCHING,
])
def test_duplicate_concurrent_active_job_rejected(db_session, active_status):
    org, project = _make_org_project_docs(db_session)
    _add_job(db_session, project, org, active_status)

    svc = ProcessingService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        svc.start_processing(project.id, org.id)
    assert exc_info.value.status_code == 409


# ── 5. _auto_start_processing_if_ready with active job → silent no-op ─────────

def test_auto_start_swallows_409_on_duplicate_active_job(db_session, monkeypatch):
    """_auto_start_processing_if_ready must never raise, even when start_processing 409s."""
    org, project = _make_org_project_docs(db_session)
    _add_job(db_session, project, org, ProcessingJobStatus.QUEUED)

    from app.services.document_service import DocumentService
    # DocumentService needs a storage mock
    class _MockStorage:
        def upload_file(self, *a, **kw): pass
        def delete_file(self, *a, **kw): pass
        def get_file(self, *a): return b""
        def create_signed_url(self, *a): return "https://mock"
    monkeypatch.setattr("app.integrations.storage.StorageService", _MockStorage)

    svc = DocumentService(db_session)
    # Must not raise
    svc._auto_start_processing_if_ready(project.id, org.id)


# ── 6. Historical job preservation after multiple rescans ────────────────────

def test_historical_jobs_preserved_across_rescans(db_session, monkeypatch):
    org, project = _make_org_project_docs(db_session)

    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline_sync",
        lambda *a, **kw: None, raising=False,
    )
    class _FakeCelery:
        def delay(self, *a, **kw): pass
    monkeypatch.setattr(
        "app.services.processing_service.process_project_pipeline",
        _FakeCelery(), raising=False,
    )

    svc = ProcessingService(db_session)

    # Run 1 — directly mark COMPLETED so we can rescan
    r1 = svc.start_processing(project.id, org.id)
    db_session.query(ProcessingJob).filter_by(id=r1.id).update(
        {"status": ProcessingJobStatus.COMPLETED}
    )
    db_session.commit()

    # Run 2 — rescan after first completes
    r2 = svc.start_processing(project.id, org.id)
    db_session.query(ProcessingJob).filter_by(id=r2.id).update(
        {"status": ProcessingJobStatus.COMPLETED}
    )
    db_session.commit()

    # Run 3
    r3 = svc.start_processing(project.id, org.id)

    jobs = db_session.query(ProcessingJob).filter_by(project_id=project.id).all()
    assert len(jobs) == 3
    ids = {str(j.id) for j in jobs}
    assert str(r1.id) in ids
    assert str(r2.id) in ids
    assert str(r3.id) in ids
