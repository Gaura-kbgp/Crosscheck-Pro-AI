from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
import uuid

from app.models.core import Document

class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id_and_org(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[Document]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> List[Document]:
        stmt = select(Document).where(
            Document.project_id == project_id,
            Document.organization_id == organization_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()
