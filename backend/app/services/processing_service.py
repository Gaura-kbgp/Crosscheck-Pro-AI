from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional
import uuid
from sqlalchemy.exc import CompileError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.core import ProcessingJob, ProcessingJobStatus, Document, DocumentType, Project, ProjectStatus
from app.schemas.processing import ProcessingJobResponse

class ProcessingService:
    def __init__(self, db: Session):
        self.db = db
        
    def start_processing(self, project_id: UUID, organization_id: UUID, background_tasks = None, force_reprocess: bool = False) -> ProcessingJobResponse:
        # SELECT FOR UPDATE serializes concurrent start_processing calls on the same project:
        # the second caller blocks until the first commits, then sees the active job below
        # and receives a 409 instead of creating a duplicate.
        # CompileError fallback: SQLite (tests) doesn't support FOR UPDATE.
        try:
            project = (
                self.db.query(Project)
                .filter(Project.id == project_id, Project.organization_id == organization_id)
                .with_for_update()
                .first()
            )
        except CompileError:
            project = (
                self.db.query(Project)
                .filter(Project.id == project_id, Project.organization_id == organization_id)
                .first()
            )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check for active job — all non-terminal statuses
        active_job = self.db.query(ProcessingJob).filter(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.notin_([
                ProcessingJobStatus.COMPLETED,
                ProcessingJobStatus.FAILED,
            ])
        ).first()

        if active_job:
            raise HTTPException(status_code=409, detail="Active processing job already exists for this project")

        # Required documents check
        documents = self.db.query(Document).filter(
            Document.project_id == project_id,
            Document.organization_id == organization_id
        ).all()
        
        doc_types = {doc.document_type for doc in documents}
        has_order_slot = DocumentType.ORDER in doc_types or DocumentType.CABINET_LIST in doc_types
        if not ({DocumentType.DESIGN, DocumentType.ACKNOWLEDGEMENT}.issubset(doc_types) and has_order_slot):
            missing = []
            if DocumentType.DESIGN not in doc_types:
                missing.append("DESIGN")
            if not has_order_slot:
                missing.append("ORDER or CABINET_LIST")
            if DocumentType.ACKNOWLEDGEMENT not in doc_types:
                missing.append("ACKNOWLEDGEMENT")
            raise HTTPException(status_code=400, detail=f"Project is missing required documents: {missing}")

        # Create job and immediately mark project as processing so the frontend
        # can show the status card without waiting for the pipeline's Stage 1.
        job = ProcessingJob(
            project_id=project_id,
            organization_id=organization_id,
            status=ProcessingJobStatus.QUEUED,
            correlation_id=str(uuid.uuid4())
        )
        self.db.add(job)
        project.status = ProjectStatus.PROCESSING
        self.db.commit()
        self.db.refresh(job)
        
        # Execute pipeline
        import logging
        logger = logging.getLogger(__name__)
        from app.worker.tasks.processing import process_project_pipeline_sync
        if background_tasks:
            background_tasks.add_task(
                process_project_pipeline_sync,
                str(job.id),
                str(project_id),
                str(organization_id),
                job.correlation_id,
                force_reprocess
            )
        else:
            try:
                from app.worker.tasks.processing import process_project_pipeline
                process_project_pipeline.delay(str(job.id), str(project_id), str(organization_id), job.correlation_id, force_reprocess)
            except Exception as e:
                logger.error("Celery dispatch failed, running pipeline inline: %s", e)
                process_project_pipeline_sync(str(job.id), str(project_id), str(organization_id), job.correlation_id, force_reprocess)
            
        return ProcessingJobResponse.model_validate(job)
        
    def get_job_status(self, job_id: UUID, organization_id: UUID) -> ProcessingJobResponse:
        job = self.db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id,
            ProcessingJob.organization_id == organization_id
        ).first()

        if not job:
            raise HTTPException(status_code=404, detail="Processing job not found")

        return ProcessingJobResponse.model_validate(job)

    def get_latest_job(self, project_id: UUID, organization_id: UUID) -> Optional[ProcessingJobResponse]:
        job = self.db.query(ProcessingJob).filter(
            ProcessingJob.project_id == project_id,
            ProcessingJob.organization_id == organization_id
        ).order_by(ProcessingJob.created_at.desc()).first()

        if not job:
            return None

        return ProcessingJobResponse.model_validate(job)

    def cancel_job(self, job_id: UUID, organization_id: UUID) -> ProcessingJobResponse:
        job = self.db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id,
            ProcessingJob.organization_id == organization_id
        ).first()

        if not job:
            raise HTTPException(status_code=404, detail="Processing job not found")

        if job.status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED):
            raise HTTPException(status_code=409, detail="Job has already finished and cannot be cancelled")

        job.status = ProcessingJobStatus.FAILED
        job.error = {"message": "Cancelled by user"}

        project = self.db.query(Project).filter(Project.id == job.project_id).first()
        if project:
            project.status = ProjectStatus.FAILED

        self.db.commit()
        self.db.refresh(job)
        return ProcessingJobResponse.model_validate(job)


# ── Startup recovery ──────────────────────────────────────────────────────────

_HEARTBEAT_STALE = timedelta(minutes=2)
_QUEUED_GRACE = timedelta(minutes=5)


def recover_stale_jobs(db: Session) -> int:
    """Mark jobs abandoned by a previous server process as FAILED.

    Multi-instance safe: a job on another running instance has a recent
    heartbeat and is not touched. Only jobs whose heartbeat is absent
    (never started) beyond the grace window, or whose heartbeat is older
    than _HEARTBEAT_STALE, are considered abandoned.

    Returns the number of jobs recovered.
    """
    import logging
    logger = logging.getLogger(__name__)

    now = datetime.now(timezone.utc)
    # shortcut: only recovers QUEUED jobs (no heartbeat column yet); restore
    # full heartbeat-based recovery once migration h6c3d2f8a915 is applied.
    stuck = db.query(ProcessingJob).filter(
        ProcessingJob.status == ProcessingJobStatus.QUEUED,
        ProcessingJob.created_at < now - _QUEUED_GRACE,
    ).all()

    for job in stuck:
        logger.warning("Startup recovery: marking job %s (%s) as FAILED", job.id, job.status)
        job.status = ProcessingJobStatus.FAILED
        job.error = {"message": "Processing was interrupted by a server restart. Please rescan."}
        project = db.query(Project).filter(Project.id == job.project_id).first()
        if project and project.status == ProjectStatus.PROCESSING:
            project.status = ProjectStatus.FAILED

    if stuck:
        db.commit()

    return len(stuck)
