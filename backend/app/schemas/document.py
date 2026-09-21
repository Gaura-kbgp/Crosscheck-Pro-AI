from pydantic import BaseModel, ConfigDict
from pydantic.types import UUID4
from datetime import datetime
from app.models.core import DocumentType, DocumentStatus

class DocumentResponse(BaseModel):
    id: UUID4
    project_id: UUID4
    organization_id: UUID4
    document_type: DocumentType
    original_filename: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
