from pydantic import BaseModel, ConfigDict
from pydantic.types import UUID4
from typing import Optional
from datetime import datetime


class NKBAReferenceDocumentResponse(BaseModel):
    id: UUID4
    organization_id: Optional[UUID4] = None
    label: str
    original_filename: str
    mime_type: str
    file_size: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
