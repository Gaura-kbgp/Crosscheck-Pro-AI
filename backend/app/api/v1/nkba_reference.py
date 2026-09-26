import uuid
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, RequireRole
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.schemas.user import AuthenticatedUser
from app.models.core import Role
from app.schemas.nkba_reference import NKBAReferenceDocumentResponse
from app.services.nkba_reference_service import NKBAReferenceService

router = APIRouter()

upload_limiter = RateLimiter(
    limit=settings.UPLOAD_RATE_LIMIT,
    window_seconds=settings.UPLOAD_RATE_WINDOW_SECONDS,
    name="nkba_upload",
)


@router.get("", response_model=List[NKBAReferenceDocumentResponse])
def list_nkba_reference_documents(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return NKBAReferenceService(db).list_all()


@router.post("", response_model=NKBAReferenceDocumentResponse, status_code=201, dependencies=[Depends(upload_limiter)])
async def upload_nkba_reference_document(
    file: UploadFile = File(...),
    label: str = Form(...),
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return await NKBAReferenceService(db).upload(user.organization_id, file, label, user.user_id)


@router.get("/{doc_id}/download-url")
def get_nkba_reference_download_url(
    doc_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"url": NKBAReferenceService(db).get_download_url(doc_id)}


@router.delete("/{doc_id}", status_code=204)
def delete_nkba_reference_document(
    doc_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    NKBAReferenceService(db).delete(doc_id, user.organization_id)
