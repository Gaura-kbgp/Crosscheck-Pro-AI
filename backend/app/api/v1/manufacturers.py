import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, RequireRole
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.schemas.user import AuthenticatedUser
from app.models.core import Role, ItemCategory, SpecBookRowStatus
from app.schemas.manufacturer import (
    ManufacturerCreate, ManufacturerUpdate, ManufacturerResponse,
    ManufacturerCodeCreate, ManufacturerCodeUpdate, ManufacturerCodeResponse,
    BulkImportPreview, BulkImportResult,
    SpecBookResponse, SpecBookRowResponse, SpecBookRowUpdate,
    ApproveRowsRequest, ApproveRowsResult,
)
from app.services.manufacturer_service import ManufacturerService
from app.services.spec_book_service import SpecBookService

router = APIRouter()

upload_limiter = RateLimiter(
    limit=settings.UPLOAD_RATE_LIMIT,
    window_seconds=settings.UPLOAD_RATE_WINDOW_SECONDS,
    name="manufacturer_upload",
)


@router.get("", response_model=List[ManufacturerResponse])
def list_manufacturers(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).list_manufacturers(user.organization_id)


@router.post("", response_model=ManufacturerResponse, status_code=201)
def create_manufacturer(
    body: ManufacturerCreate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).create_manufacturer(user.organization_id, body, user.user_id)


@router.patch("/{manufacturer_id}", response_model=ManufacturerResponse)
def update_manufacturer(
    manufacturer_id: uuid.UUID,
    body: ManufacturerUpdate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).update_manufacturer(manufacturer_id, user.organization_id, body, user.user_id)


@router.get("/{manufacturer_id}/codes", response_model=List[ManufacturerCodeResponse])
def list_codes(
    manufacturer_id: uuid.UUID,
    search: Optional[str] = None,
    category: Optional[ItemCategory] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).list_codes(manufacturer_id, user.organization_id, search, category)


@router.post("/{manufacturer_id}/codes", response_model=ManufacturerCodeResponse, status_code=201)
def create_code(
    manufacturer_id: uuid.UUID,
    body: ManufacturerCodeCreate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).create_code(manufacturer_id, user.organization_id, body, user.user_id)


@router.patch("/{manufacturer_id}/codes/{code_id}", response_model=ManufacturerCodeResponse)
def update_code(
    manufacturer_id: uuid.UUID,
    code_id: uuid.UUID,
    body: ManufacturerCodeUpdate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).update_code(manufacturer_id, code_id, user.organization_id, body, user.user_id)


@router.post("/{manufacturer_id}/codes/{code_id}/deactivate", response_model=ManufacturerCodeResponse)
def deactivate_code(
    manufacturer_id: uuid.UUID,
    code_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return ManufacturerService(db).deactivate_code(manufacturer_id, code_id, user.organization_id, user.user_id)


@router.delete("/{manufacturer_id}/codes/{code_id}", status_code=204)
def delete_code(
    manufacturer_id: uuid.UUID,
    code_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    ManufacturerService(db).delete_code(manufacturer_id, code_id, user.organization_id)


@router.post("/{manufacturer_id}/codes/import/preview", response_model=BulkImportPreview, dependencies=[Depends(upload_limiter)])
async def preview_import(
    manufacturer_id: uuid.UUID,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return ManufacturerService(db).preview_import(manufacturer_id, user.organization_id, file.filename or "", content)


@router.post("/{manufacturer_id}/codes/import/commit", response_model=BulkImportResult, dependencies=[Depends(upload_limiter)])
async def commit_import(
    manufacturer_id: uuid.UUID,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    content = await file.read()
    return ManufacturerService(db).commit_import(manufacturer_id, user.organization_id, file.filename or "", content, user.user_id)


# ---- Specification Book: Upload -> Extract -> Review -> Approve ----------

@router.post("/{manufacturer_id}/spec-books", response_model=SpecBookResponse, status_code=201, dependencies=[Depends(upload_limiter)])
async def upload_spec_book(
    manufacturer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_version: Optional[str] = Form(None),
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return await SpecBookService(db).upload(manufacturer_id, user.organization_id, file, source_version, user.user_id, background_tasks)


@router.get("/{manufacturer_id}/spec-books", response_model=List[SpecBookResponse])
def list_spec_books(
    manufacturer_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).list_spec_books(manufacturer_id, user.organization_id)


@router.get("/{manufacturer_id}/spec-books/{book_id}", response_model=SpecBookResponse)
def get_spec_book(
    manufacturer_id: uuid.UUID,
    book_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).get_spec_book(manufacturer_id, book_id, user.organization_id)


@router.get("/{manufacturer_id}/spec-books/{book_id}/rows", response_model=List[SpecBookRowResponse])
def list_spec_book_rows(
    manufacturer_id: uuid.UUID,
    book_id: uuid.UUID,
    status: Optional[SpecBookRowStatus] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).list_rows(manufacturer_id, book_id, user.organization_id, status)


@router.patch("/{manufacturer_id}/spec-books/{book_id}/rows/{row_id}", response_model=SpecBookRowResponse)
def update_spec_book_row(
    manufacturer_id: uuid.UUID,
    book_id: uuid.UUID,
    row_id: uuid.UUID,
    body: SpecBookRowUpdate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).update_row(manufacturer_id, book_id, row_id, user.organization_id, body, user.user_id)


@router.post("/{manufacturer_id}/spec-books/{book_id}/rows/{row_id}/reject", response_model=SpecBookRowResponse)
def reject_spec_book_row(
    manufacturer_id: uuid.UUID,
    book_id: uuid.UUID,
    row_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).reject_row(manufacturer_id, book_id, row_id, user.organization_id, user.user_id)


@router.post("/{manufacturer_id}/spec-books/{book_id}/approve", response_model=ApproveRowsResult)
def approve_spec_book_rows(
    manufacturer_id: uuid.UUID,
    book_id: uuid.UUID,
    body: ApproveRowsRequest,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db),
):
    return SpecBookService(db).approve_rows(manufacturer_id, book_id, user.organization_id, body, user.user_id)
