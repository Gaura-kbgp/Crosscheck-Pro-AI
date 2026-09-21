from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import uuid
from typing import List

from app.api.dependencies import get_db, get_current_user, RequireRole
from app.schemas.user import AuthenticatedUser
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.models.core import Role, DocumentType

router = APIRouter()

@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN, Role.REVIEWER])),
    db: Session = Depends(get_db)
):
    service = DocumentService(db)
    return await service.upload_document(project_id, user.organization_id, file, document_type)

@router.get("/projects/{project_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = DocumentService(db)
    return service.list_documents(project_id, user.organization_id)

@router.get("/projects/{project_id}/documents/{document_id}")
def get_document_url(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = DocumentService(db)
    url = service.get_document_url(document_id, project_id, user.organization_id)
    return {"url": url}

@router.delete("/projects/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN, Role.REVIEWER])),
    db: Session = Depends(get_db)
):
    service = DocumentService(db)
    service.delete_document(document_id, project_id, user.organization_id)
    return None
