from pydantic import BaseModel, ConfigDict
from pydantic.types import UUID4
from typing import Optional, Dict, Any
from datetime import datetime

class OrganizationResponse(BaseModel):
    id: UUID4
    name: str
    settings: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    user_count: int = 1
    project_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
