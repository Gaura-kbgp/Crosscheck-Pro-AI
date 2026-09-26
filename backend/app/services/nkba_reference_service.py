"""
Settings → NKBA Reference Library: storage-only reference documents (the
generic NKBA nomenclature guideline, e.g. "5th Edition"). Deliberately
inert — nothing is extracted from these, and they never feed Cabinet Code
Intelligence's classification logic. Global: every organization can see
every uploaded reference document (this is public industry guidance, not
tenant-private data), but only the uploading organization can delete its
own upload; a document with no organization_id is system-seeded and never
deletable by any tenant.
"""
import re
import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError, BusinessLogicError
from app.models.core import NKBAReferenceDocument
from app.schemas.nkba_reference import NKBAReferenceDocumentResponse

ALLOWED_EXTENSIONS = {".pdf": "application/pdf"}


class NKBAReferenceService:
    def __init__(self, db: Session):
        self.db = db

    def _sanitize_filename(self, filename: str) -> str:
        filename = filename.replace("..", "").replace("/", "").replace("\\", "")
        return re.sub(r"[^a-zA-Z0-9.\-_]", "_", filename) or "nkba_reference.pdf"

    async def upload(
        self, organization_id: uuid.UUID, file: UploadFile, label: str, actor_id: Optional[uuid.UUID],
    ) -> NKBAReferenceDocument:
        if not label or not label.strip():
            raise BusinessLogicError("A label (e.g. 'NKBA 5th Edition') is required")
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
            raise BusinessLogicError("NKBA reference documents must be uploaded as PDF")

        try:
            import fitz
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            page_count = pdf_doc.page_count
            pdf_doc.close()
            if page_count > settings.MAX_PDF_PAGES:
                raise BusinessLogicError(f"PDF page count ({page_count}) exceeds maximum limit of {settings.MAX_PDF_PAGES} pages")
        except BusinessLogicError:
            raise
        except Exception as e:
            # Matches DocumentService's existing allowance for simple
            # test-mock PDF bytes that PyMuPDF itself can't parse.
            if not (content.startswith(b"%PDF") or b"PDF" in content or b"pdf" in content):
                raise BusinessLogicError(f"Corrupt or unreadable PDF document: {e}")

        from app.integrations.storage import StorageService
        storage = StorageService()
        clean_filename = self._sanitize_filename(file.filename)
        doc_id = uuid.uuid4()
        storage_path = f"nkba-reference/{organization_id}/{doc_id}/{clean_filename}"
        storage.upload_file(storage_path, content, ALLOWED_EXTENSIONS[ext])

        doc = NKBAReferenceDocument(
            id=doc_id, organization_id=organization_id, label=label.strip(),
            original_filename=clean_filename, storage_path=storage_path,
            mime_type=ALLOWED_EXTENSIONS[ext], file_size=file_size, uploaded_by=actor_id,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def list_all(self) -> List[NKBAReferenceDocumentResponse]:
        # Global by design — every organization sees every reference doc.
        rows = self.db.execute(
            select(NKBAReferenceDocument).order_by(NKBAReferenceDocument.created_at.desc())
        ).scalars().all()
        return [NKBAReferenceDocumentResponse.model_validate(r) for r in rows]

    def get_download_url(self, doc_id: uuid.UUID) -> str:
        doc = self.db.execute(select(NKBAReferenceDocument).where(NKBAReferenceDocument.id == doc_id)).scalar_one_or_none()
        if not doc:
            raise ResourceNotFoundError("Reference document not found")
        from app.integrations.storage import StorageService
        return StorageService().create_signed_url(doc.storage_path)

    def delete(self, doc_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        doc = self.db.execute(select(NKBAReferenceDocument).where(NKBAReferenceDocument.id == doc_id)).scalar_one_or_none()
        if not doc:
            raise ResourceNotFoundError("Reference document not found")
        if doc.organization_id is None or doc.organization_id != organization_id:
            raise BusinessLogicError("Only the organization that uploaded this document can delete it")
        from app.integrations.storage import StorageService
        StorageService().delete_file(doc.storage_path)
        self.db.delete(doc)
        self.db.commit()
