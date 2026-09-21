from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import UUID4
from typing import Optional, List
from datetime import datetime
from app.models.core import ProjectStatus

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    customer_name: Optional[str] = None
    dealer_name: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    customer_name: Optional[str] = None
    dealer_name: Optional[str] = None
    status: Optional[ProjectStatus] = None

class ProjectResponse(BaseModel):
    id: UUID4
    organization_id: UUID4
    name: str
    customer_name: Optional[str] = None
    dealer_name: Optional[str] = None
    status: ProjectStatus
    document_count: int = 0
    uploaded_document_types: List[str] = Field(default_factory=list)
    discrepancy_count: int = 0
    resolved_discrepancy_count: int = 0
    progress_percentage: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

