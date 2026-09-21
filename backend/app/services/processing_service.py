from uuid import UUID
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.core import ProcessingJob, ProcessingJobStatus, Document, DocumentType, Project
from app.schemas.processing import ProcessingJobResponse

class ProcessingService:
    def __init__(self, db: Session):
        self.db = db
        
    def start_processing(self, project_id: UUID, organization_id: UUID, background_tasks = None) -> ProcessingJobResponse:
        # Check if project exists and belongs to organization
        project = self.db.query(Project).filter(
            Project.id == project_id,
            Project.organization_id == organization_id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Check for active job
        active_job = self.db.query(ProcessingJob).filter(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.in_([
                ProcessingJobStatus.QUEUED,
                ProcessingJobStatus.VALIDATING,
                ProcessingJobStatus.EXTRACTING,
                ProcessingJobStatus.NORMALIZING
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
        required_types = {DocumentType.DESIGN, DocumentType.ORDER, DocumentType.ACKNOWLEDGEMENT}
        if not required_types.issubset(doc_types):
            missing = required_types - doc_types
            raise HTTPException(status_code=400, detail=f"Project is missing required documents: {[d.value for d in missing]}")

        # Create job
        job = ProcessingJob(
            project_id=project_id,
            organization_id=organization_id,
            status=ProcessingJobStatus.QUEUED,
            correlation_id=str(uuid.uuid4())
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Execute pipeline
        try:
            from app.worker.tasks.processing import process_project_pipeline_sync
            if background_tasks:
                background_tasks.add_task(
                    process_project_pipeline_sync,
                    str(job.id),
                    str(project_id),
                    str(organization_id),
                    job.correlation_id
                )
            else:
                from app.worker.tasks.processing import process_project_pipeline
                process_project_pipeline.delay(str(job.id), str(project_id), str(organization_id), job.correlation_id)
        except Exception:
            # Fallback if something fails during import or dispatch
            pass
            
        return ProcessingJobResponse.model_validate(job)
        
    def get_job_status(self, job_id: UUID, organization_id: UUID) -> ProcessingJobResponse:
        job = self.db.query(ProcessingJob).filter(
            ProcessingJob.id == job_id,
            ProcessingJob.organization_id == organization_id
        ).first()
        
        if not job:
            raise HTTPException(status_code=404, detail="Processing job not found")
            
        return ProcessingJobResponse.model_validate(job)
