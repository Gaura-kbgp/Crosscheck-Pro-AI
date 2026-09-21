import sys
import uuid
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.processing_service import ProcessingService
from app.models.core import Project

def run(project_id_str):
    db = SessionLocal()
    try:
        project_id = uuid.UUID(project_id_str)
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            print("Project not found")
            return
            
        service = ProcessingService(db)
        
        # Fake background tasks
        class DummyTasks:
            def add_task(self, func, *args, **kwargs):
                func(*args, **kwargs)
                
        bg = DummyTasks()
        
        # Clean up any stuck jobs
        from app.models.core import ProcessingJob, ProcessingJobStatus
        stuck_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status != ProcessingJobStatus.COMPLETED,
            ProcessingJob.status != ProcessingJobStatus.FAILED
        ).all()
        for j in stuck_jobs:
            j.status = ProcessingJobStatus.FAILED
        db.commit()
        
        # Start new processing
        print("Starting processing...")
        job = service.start_processing(project_id, project.organization_id, bg)
        print(f"Started job {job.id}, status: {job.status}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run("62ad3f7b-2a1d-4156-9ffb-e7475a815c37")
