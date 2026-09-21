from pydantic import BaseModel, Field
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

class ReviewActionRequest(BaseModel):
    action: str = Field(..., description="Action to perform: ACCEPT_FINDING, FALSE_POSITIVE, ESCALATE, ACKNOWLEDGE_MFR_CHANGE, OVERRIDE_DATA")
    reason: Optional[str] = None
    
    # Used only for OVERRIDE_DATA
    match_group_id: Optional[UUID] = None
    canonical_item_id: Optional[UUID] = None
    field_name: Optional[str] = None
    new_value: Optional[Any] = None

class DiscrepancyResponse(BaseModel):
    id: UUID
    project_id: UUID
    match_group_id: UUID
    field: str
    status: str
    severity: str
    
    class Config:
        from_attributes = True

class MatchGroupResponse(BaseModel):
    id: UUID
    status: str
    
    class Config:
        from_attributes = True

class AuditLogResponse(BaseModel):
    id: UUID
    project_id: UUID
    actor_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: str
    previous_state: Optional[dict[str, Any]] = None
    new_state: Optional[dict[str, Any]] = None
    metadata_: Optional[dict[str, Any]] = Field(None, alias="metadata")
    created_at: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True
