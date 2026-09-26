from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import UUID4
from typing import Optional, List
from datetime import datetime
from app.models.core import ItemCategory, SpecBookStatus, SpecBookRowStatus


class ManufacturerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    # is_global is intentionally NOT accepted here — global manufacturers are
    # system/seed data only; a tenant can never create or flip one via this
    # API (see ManufacturerService for why).


class ManufacturerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)


class ManufacturerResponse(BaseModel):
    id: UUID4
    organization_id: Optional[UUID4] = None
    name: str
    is_global: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManufacturerCodeCreate(BaseModel):
    code: str = Field(..., min_length=1)
    description: Optional[str] = None
    category: ItemCategory
    alias_group: Optional[str] = None
    is_primary_alias: bool = True
    is_current: bool = True
    source_version: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class ManufacturerCodeUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[ItemCategory] = None
    alias_group: Optional[str] = None
    is_primary_alias: Optional[bool] = None
    is_current: Optional[bool] = None
    source_version: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class ManufacturerCodeResponse(BaseModel):
    id: UUID4
    manufacturer_id: UUID4
    code: str
    normalized_code: str
    category: ItemCategory
    description: Optional[str] = None
    alias_group: Optional[str] = None
    is_primary_alias: bool
    is_current: bool
    source_version: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkImportRowError(BaseModel):
    row: int
    code: Optional[str] = None
    reason: str


class BulkImportPreview(BaseModel):
    total_rows: int
    valid: int
    duplicates: int
    invalid: int
    errors: List[BulkImportRowError] = Field(default_factory=list)


class BulkImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    skipped_invalid: int
    errors: List[BulkImportRowError] = Field(default_factory=list)


class SpecBookResponse(BaseModel):
    id: UUID4
    manufacturer_id: UUID4
    original_filename: str
    mime_type: str
    file_size: int
    status: SpecBookStatus
    source_version: Optional[str] = None
    error: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpecBookRowResponse(BaseModel):
    id: UUID4
    spec_book_id: UUID4
    manufacturer_id: UUID4
    raw_code: str
    normalized_code: str
    description: Optional[str] = None
    category: ItemCategory
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None
    status: SpecBookRowStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpecBookRowUpdate(BaseModel):
    """Lets a reviewer correct an AI misread before approving. raw_code can be
    corrected too (e.g. AI misread '8T36B-2' for 'BT36B-2') — this is a human
    review edit, not a silent AI auto-correction, and is only ever applied to
    this staging row, never retroactively to already-approved dictionary
    entries."""
    raw_code: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    category: Optional[ItemCategory] = None


class ApproveRowsRequest(BaseModel):
    row_ids: Optional[List[UUID4]] = None
    approve_all: bool = False


class ApproveRowsResult(BaseModel):
    approved: int
    skipped_duplicates: int
    errors: List[BulkImportRowError] = Field(default_factory=list)
