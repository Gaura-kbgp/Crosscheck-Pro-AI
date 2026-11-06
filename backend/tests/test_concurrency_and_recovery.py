"""
Regression tests for concurrent processing prevention (Fix 1) and stale-job
recovery (Fix 2).

Tests 3 and 4 (Rescan after COMPLETED/FAILED) are already covered by
test_processing_rescan.py and are not duplicated here.

Fix 1 — SELECT FOR UPDATE (concurrent duplicate prevention):
  1. Two sequential start_processing calls → second raises 409
  2. Upload auto-start followed by manual start → manual raises 409

Fix 2 — Heartbeat-based stale-job recovery:
  5. QUEUED job beyond grace window → marked FAILED by recover_stale_jobs
  6. EXTRACTING job with stale heartbeat → marked FAILED
  7. EXTRACTING job with RECENT heartbeat → NOT touched (multi-instance safety)
  8. Historical (terminal) jobs preserved after recovery
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

from app.models.core import (
    Organization, Project, ProjectStatus,
    Document, DocumentType, DocumentStatus,
    ProcessingJob, ProcessingJobStatus,
)
from app.services.processing_service import ProcessingService, recover_stale_jobs


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_org_project_docs(db):
    org = Organization(name=f"Org {uuid.uuid4()}")
    db.add(org)
    db.commit()
    project = Project(organization_id=org.id, name="Test Project")
    db.add(project)
    db.commit()
    for doc_type in (DocumentType.DESIGN, DocumentType.CABINET_LIST, DocumentType.ACKNOWLEDGEMENT):
        db.add(Document(
            project_id=project.id, organization_id=org.id,
            document_type=doc_type,
            original_filename=f"{doc_type.value.lower()}.pdf",
            storage_path=f"{org.id}/{project.id}/{uuid.uuid4()}/file.pdf",
            mime_type="application/pdf", file_size=100,
            status=DocumentStatus.UPLOADED,
        ))
    db.commit()
    return org, project


def _patch_pipeline(monkeypatch):
    """Prevent actual pipeline dispatch in start_processing calls."""
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


def _add_job(db, project, org, status, last_heartbeat_at=None, created_at=None):
    kwargs = dict(
        project_id=project.id, organization_id=org.id,
        status=status, correlation_id=str(uuid.uuid4()),
    )
    if last_heartbeat_at is not None:
        kwargs["last_heartbeat_at"] = last_heartbeat_at
    if created_at is not None:
        kwargs["created_at"] = created_at
    job = ProcessingJob(**kwargs)
    db.add(job)
    db.commit()
    return job


# ── Fix 1: concurrent duplicate prevention ────────────────────────────────────

def test_second_start_processing_raises_409(db_session, monkeypatch):
    """Two sequential start_processing calls for the same project → second is 409."""
    _patch_pipeline(monkeypatch)
    org, project = _make_org_project_docs(db_session)

    svc = ProcessingService(db_session)
    r1 = svc.start_processing(project.id, org.id)
    assert r1.status == ProcessingJobStatus.QUEUED

    with pytest.raises(HTTPException) as exc:
        svc.start_processing(project.id, org.id)
    assert exc.value.status_code == 409
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 1


def test_auto_start_then_manual_raises_409(db_session, monkeypatch):
    """_auto_start_processing_if_ready followed by manual start → 409 on the manual call."""
    _patch_pipeline(monkeypatch)
    org, project = _make_org_project_docs(db_session)

    # Simulate what the upload endpoint does: auto-start fires, creates a QUEUED job.
    from app.services.document_service import DocumentService

    class _MockStorage:
        def upload_file(self, *a, **kw): pass
        def delete_file(self, *a, **kw): pass
        def get_file(self, *a): return b""
        def create_signed_url(self, *a): return "https://mock"

    monkeypatch.setattr("app.integrations.storage.StorageService", _MockStorage)
    doc_svc = DocumentService(db_session)
    doc_svc._auto_start_processing_if_ready(project.id, org.id)

    # One QUEUED job should exist now.
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 1

    # Manual "Start Cross-Check" should be rejected.
    svc = ProcessingService(db_session)
    with pytest.raises(HTTPException) as exc:
        svc.start_processing(project.id, org.id)
    assert exc.value.status_code == 409
    assert db_session.query(ProcessingJob).filter_by(project_id=project.id).count() == 1


# ── Fix 2: stale-job recovery ─────────────────────────────────────────────────
# Note: true concurrent-thread tests are not feasible with SQLite StaticPool
# (single shared connection). The SELECT FOR UPDATE serialization is verified
# on PostgreSQL where row-level locking is supported. The sequential tests
# above cover the application-level guard that also protects SQLite paths.

def test_recover_abandoned_queued_job(db_session):
    """QUEUED job with no heartbeat and created > 5 min ago → marked FAILED."""
    org, project = _make_org_project_docs(db_session)
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    job = _add_job(db_session, project, org, ProcessingJobStatus.QUEUED, created_at=old_time)
    # Update project to PROCESSING so we can verify it's also reset.
    db_session.query(Project).filter_by(id=project.id).update({"status": ProjectStatus.PROCESSING})
    db_session.commit()

    count = recover_stale_jobs(db_session)

    assert count == 1
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED
    assert "restart" in job.error["message"].lower()
    db_session.refresh(project)
    assert project.status == ProjectStatus.FAILED


def test_recover_abandoned_extracting_job(db_session):
    """EXTRACTING job with heartbeat older than 2 min → marked FAILED."""
    org, project = _make_org_project_docs(db_session)
    stale_hb = datetime.now(timezone.utc) - timedelta(minutes=5)
    job = _add_job(
        db_session, project, org,
        ProcessingJobStatus.EXTRACTING,
        last_heartbeat_at=stale_hb,
    )
    db_session.query(Project).filter_by(id=project.id).update({"status": ProjectStatus.PROCESSING})
    db_session.commit()

    count = recover_stale_jobs(db_session)

    assert count == 1
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.FAILED


def test_active_job_with_recent_heartbeat_not_recovered(db_session):
    """EXTRACTING job with a fresh heartbeat (another running instance) → NOT touched."""
    org, project = _make_org_project_docs(db_session)
    fresh_hb = datetime.now(timezone.utc) - timedelta(seconds=20)
    job = _add_job(
        db_session, project, org,
        ProcessingJobStatus.EXTRACTING,
        last_heartbeat_at=fresh_hb,
    )

    count = recover_stale_jobs(db_session)

    assert count == 0
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.EXTRACTING, "Active job must not be touched"


def test_historical_terminal_jobs_preserved_after_recovery(db_session):
    """COMPLETED and FAILED historical jobs are never touched by recovery."""
    org, project = _make_org_project_docs(db_session)
    old_time = datetime.now(timezone.utc) - timedelta(hours=1)

    completed = _add_job(db_session, project, org, ProcessingJobStatus.COMPLETED, created_at=old_time)
    failed = _add_job(db_session, project, org, ProcessingJobStatus.FAILED, created_at=old_time)
    # Also add a stale non-terminal job to confirm recovery still runs.
    stale_queued = _add_job(db_session, project, org, ProcessingJobStatus.QUEUED, created_at=old_time)

    count = recover_stale_jobs(db_session)

    assert count == 1  # Only the stale QUEUED job
    db_session.refresh(completed)
    db_session.refresh(failed)
    assert completed.status == ProcessingJobStatus.COMPLETED
    assert failed.status == ProcessingJobStatus.FAILED


def test_recover_new_queued_job_within_grace_not_touched(db_session):
    """QUEUED job created 1 min ago (no heartbeat yet) → inside grace window, not touched."""
    org, project = _make_org_project_docs(db_session)
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    job = _add_job(db_session, project, org, ProcessingJobStatus.QUEUED, created_at=recent)

    count = recover_stale_jobs(db_session)

    assert count == 0
    db_session.refresh(job)
    assert job.status == ProcessingJobStatus.QUEUED, "Newly queued job must not be touched"
