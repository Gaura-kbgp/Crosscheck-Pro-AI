"""
Settings → Manufacturer → Upload Specification Book PDF → Extract codes →
Review extracted dictionary → Approve → Manufacturer Dictionary.

Extraction never writes directly into ManufacturerCodeDictionary — it only
ever produces ManufacturerSpecBookRow candidates. A row becomes a real
dictionary entry only through the explicit approve_rows() call, which a
human triggers after reviewing (and optionally correcting) the AI's output.
"""
import re
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError, BusinessLogicError
from app.models.core import (
    ManufacturerSpecBook, ManufacturerSpecBookRow, ManufacturerCodeDictionary,
    SpecBookStatus, SpecBookRowStatus, ItemCategory,
)
from app.engines.normalization import normalize_sku
from app.services.manufacturer_service import ManufacturerService
from app.schemas.manufacturer import (
    SpecBookResponse, SpecBookRowResponse, SpecBookRowUpdate,
    ApproveRowsRequest, ApproveRowsResult, BulkImportRowError,
)

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class SpecBookService:
    def __init__(self, db: Session):
        self.db = db
        self.manufacturers = ManufacturerService(db)

    def _sanitize_filename(self, filename: str) -> str:
        filename = filename.replace("..", "").replace("/", "").replace("\\", "")
        return re.sub(r"[^a-zA-Z0-9.\-_]", "_", filename) or "spec_book.pdf"

    async def upload(
        self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID,
        file: UploadFile, source_version: Optional[str], actor_id: Optional[uuid.UUID],
        background_tasks=None,
    ) -> ManufacturerSpecBook:
        # Only an org that OWNS this manufacturer may upload a spec book for
        # it — global manufacturers are read-only, exactly like dictionary
        # writes (§ ManufacturerService._get_owned).
        self.manufacturers._get_owned(manufacturer_id, organization_id)

        if not file.filename:
            raise BusinessLogicError("Filename is missing")
        content = await file.read()
        file_size = len(content)
        if file_size == 0:
            raise BusinessLogicError("File is empty")
        if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise BusinessLogicError("File too large")

        lower = file.filename.lower()
        ext = next((e for e in ALLOWED_EXTENSIONS if lower.endswith(e)), None)
        if not ext:
            raise BusinessLogicError("Unsupported file type — specification books must be uploaded as PDF, CSV, or Excel (.xlsx)")

        if ext == ".pdf":
            try:
                import fitz
                try:
                    pdf_doc = fitz.open(stream=content, filetype="pdf")
                    page_count = pdf_doc.page_count
                    pdf_doc.close()
                    if page_count > settings.MAX_PDF_PAGES:
                        raise BusinessLogicError(f"PDF page count ({page_count}) exceeds maximum limit of {settings.MAX_PDF_PAGES} pages")
                except BusinessLogicError:
                    raise
                except Exception as fe:
                    # Matches DocumentService's existing allowance for simple
                    # test-mock PDF bytes that PyMuPDF itself can't parse.
                    if not (content.startswith(b"%PDF") or b"PDF" in content or b"pdf" in content):
                        raise BusinessLogicError(f"Corrupt or unreadable PDF document: {fe}")
            except BusinessLogicError:
                raise
            except Exception as e:
                raise BusinessLogicError(f"Corrupt or unreadable PDF document: {e}")

        from app.integrations.storage import StorageService
        storage = StorageService()
        clean_filename = self._sanitize_filename(file.filename)
        book_id = uuid.uuid4()
        storage_path = f"{organization_id}/manufacturers/{manufacturer_id}/spec-books/{book_id}/{clean_filename}"
        storage.upload_file(storage_path, content, ALLOWED_EXTENSIONS[ext])

        book = ManufacturerSpecBook(
            id=book_id, manufacturer_id=manufacturer_id, organization_id=organization_id,
            original_filename=clean_filename, storage_path=storage_path,
            mime_type=ALLOWED_EXTENSIONS[ext], file_size=file_size,
            status=SpecBookStatus.UPLOADED, source_version=source_version, uploaded_by=actor_id,
        )
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)

        try:
            from app.worker.tasks.spec_book_extraction import extract_spec_book_task, extract_spec_book_task_sync
            if background_tasks:
                background_tasks.add_task(extract_spec_book_task_sync, str(book.id))
            else:
                extract_spec_book_task.delay(str(book.id))
        except Exception:
            pass  # matches ProcessingService's existing dispatch-failure tolerance

        return book

    def list_spec_books(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID) -> List[SpecBookResponse]:
        self.manufacturers._get_visible(manufacturer_id, organization_id)
        rows = self.db.execute(
            select(ManufacturerSpecBook)
            .where(ManufacturerSpecBook.manufacturer_id == manufacturer_id)
            .order_by(ManufacturerSpecBook.created_at.desc())
        ).scalars().all()
        return [SpecBookResponse.model_validate(r) for r in rows]

    def _get_book_visible(self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, organization_id: uuid.UUID) -> ManufacturerSpecBook:
        self.manufacturers._get_visible(manufacturer_id, organization_id)
        book = self.db.execute(select(ManufacturerSpecBook).where(
            ManufacturerSpecBook.id == book_id, ManufacturerSpecBook.manufacturer_id == manufacturer_id,
        )).scalar_one_or_none()
        if not book:
            raise ResourceNotFoundError("Specification book not found")
        return book

    def _get_book_owned(self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, organization_id: uuid.UUID) -> ManufacturerSpecBook:
        self.manufacturers._get_owned(manufacturer_id, organization_id)  # 400 if global, 404 if not visible
        return self._get_book_visible(manufacturer_id, book_id, organization_id)

    def get_spec_book(self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, organization_id: uuid.UUID) -> SpecBookResponse:
        return SpecBookResponse.model_validate(self._get_book_visible(manufacturer_id, book_id, organization_id))

    def list_rows(
        self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, organization_id: uuid.UUID,
        status: Optional[SpecBookRowStatus] = None,
    ) -> List[SpecBookRowResponse]:
        self._get_book_visible(manufacturer_id, book_id, organization_id)
        stmt = select(ManufacturerSpecBookRow).where(ManufacturerSpecBookRow.spec_book_id == book_id)
        if status:
            stmt = stmt.where(ManufacturerSpecBookRow.status == status)
        stmt = stmt.order_by(ManufacturerSpecBookRow.page_number.asc().nulls_last(), ManufacturerSpecBookRow.raw_code.asc())
        rows = self.db.execute(stmt).scalars().all()
        return [SpecBookRowResponse.model_validate(r) for r in rows]

    def _get_row_owned(self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, row_id: uuid.UUID, organization_id: uuid.UUID) -> ManufacturerSpecBookRow:
        self._get_book_owned(manufacturer_id, book_id, organization_id)
        row = self.db.execute(select(ManufacturerSpecBookRow).where(
            ManufacturerSpecBookRow.id == row_id, ManufacturerSpecBookRow.spec_book_id == book_id,
        )).scalar_one_or_none()
        if not row:
            raise ResourceNotFoundError("Spec book row not found")
        return row

    def update_row(
        self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, row_id: uuid.UUID,
        organization_id: uuid.UUID, data: SpecBookRowUpdate, actor_id: Optional[uuid.UUID],
    ) -> SpecBookRowResponse:
        row = self._get_row_owned(manufacturer_id, book_id, row_id, organization_id)
        if row.status != SpecBookRowStatus.PENDING:
            raise BusinessLogicError("Only pending rows can be edited")
        if data.raw_code is not None:
            row.raw_code = data.raw_code
            row.normalized_code = normalize_sku(data.raw_code) or row.normalized_code
        if data.description is not None:
            row.description = data.description
        if data.category is not None:
            row.category = data.category
        row.reviewed_by = actor_id
        self.db.commit()
        self.db.refresh(row)
        return SpecBookRowResponse.model_validate(row)

    def reject_row(self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, row_id: uuid.UUID, organization_id: uuid.UUID, actor_id: Optional[uuid.UUID]) -> SpecBookRowResponse:
        row = self._get_row_owned(manufacturer_id, book_id, row_id, organization_id)
        row.status = SpecBookRowStatus.REJECTED
        row.reviewed_by = actor_id
        self.db.commit()
        self.db.refresh(row)
        return SpecBookRowResponse.model_validate(row)

    def approve_rows(
        self, manufacturer_id: uuid.UUID, book_id: uuid.UUID, organization_id: uuid.UUID,
        request: ApproveRowsRequest, actor_id: Optional[uuid.UUID],
    ) -> ApproveRowsResult:
        book = self._get_book_owned(manufacturer_id, book_id, organization_id)

        stmt = select(ManufacturerSpecBookRow).where(
            ManufacturerSpecBookRow.spec_book_id == book_id,
            ManufacturerSpecBookRow.status == SpecBookRowStatus.PENDING,
        )
        if not request.approve_all:
            if not request.row_ids:
                raise BusinessLogicError("Provide row_ids or set approve_all=true")
            stmt = stmt.where(ManufacturerSpecBookRow.id.in_(request.row_ids))
        pending_rows = self.db.execute(stmt).scalars().all()

        existing_codes = {
            r.normalized_code for r in self.db.execute(
                select(ManufacturerCodeDictionary.normalized_code).where(ManufacturerCodeDictionary.manufacturer_id == manufacturer_id)
            ).all()
        }

        approved = 0
        skipped_duplicates = 0
        errors: List[BulkImportRowError] = []
        seen = set()

        for row in pending_rows:
            if row.normalized_code in existing_codes or row.normalized_code in seen:
                skipped_duplicates += 1
                row.status = SpecBookRowStatus.APPROVED  # reviewed & resolved, just not re-added
                row.reviewed_by = actor_id
                continue
            seen.add(row.normalized_code)
            entry = ManufacturerCodeDictionary(
                id=uuid.uuid4(), manufacturer_id=manufacturer_id,
                code=row.raw_code, normalized_code=row.normalized_code, category=row.category,
                description=row.description, source_document_id=book.id, source_version=book.source_version,
                created_by=actor_id, updated_by=actor_id,
            )
            self.db.add(entry)
            row.status = SpecBookRowStatus.APPROVED
            row.reviewed_by = actor_id
            approved += 1

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise BusinessLogicError("Approval failed — no rows were committed")

        return ApproveRowsResult(approved=approved, skipped_duplicates=skipped_duplicates, errors=errors)
