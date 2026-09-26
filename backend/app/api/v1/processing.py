from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api.dependencies import get_db, get_current_user
from app.schemas.user import AuthenticatedUser
from app.schemas.processing import ProcessingJobResponse
from app.schemas.extraction import ExtractionResponse, CanonicalLineItemResponse
from app.services.processing_service import ProcessingService
from app.models.core import Extraction, CanonicalLineItem, Document

router = APIRouter()

@router.post("/projects/{project_id}/process", response_model=ProcessingJobResponse, status_code=201)
def start_processing(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    force_reprocess: bool = Query(False, description="F8.3 Phase 3: bypass extraction idempotency and re-extract every document even if an identical prior attempt exists."),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    service = ProcessingService(db)
    return service.start_processing(project_id, current_user.organization_id, background_tasks, force_reprocess)

@router.get("/projects/{project_id}/jobs/latest", response_model=ProcessingJobResponse)
def get_latest_job(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    service = ProcessingService(db)
    return service.get_latest_job(project_id, current_user.organization_id)

@router.get("/jobs/{job_id}/status", response_model=ProcessingJobResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    service = ProcessingService(db)
    return service.get_job_status(job_id, current_user.organization_id)

@router.post("/jobs/{job_id}/cancel", response_model=ProcessingJobResponse)
def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    service = ProcessingService(db)
    return service.cancel_job(job_id, current_user.organization_id)

@router.get("/documents/{document_id}/extraction", response_model=ExtractionResponse)
def get_document_extraction(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    extraction = db.query(Extraction).filter(
        Extraction.document_id == document_id,
        Extraction.organization_id == current_user.organization_id
    ).first()
    if not extraction:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Extraction not found")
    return ExtractionResponse.model_validate(extraction)

@router.get("/documents/{document_id}/line-items", response_model=List[CanonicalLineItemResponse])
def get_document_line_items(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    # Verify document belongs to org first
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == current_user.organization_id
    ).first()
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
        
    line_items = db.query(CanonicalLineItem).filter(
        CanonicalLineItem.document_id == document_id,
        CanonicalLineItem.organization_id == current_user.organization_id
    ).all()
    
    return [CanonicalLineItemResponse.model_validate(item) for item in line_items]
