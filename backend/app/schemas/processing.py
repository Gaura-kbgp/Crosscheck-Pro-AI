from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from app.models.core import ProcessingJobStatus

class ProcessingJobResponse(BaseModel):
    id: UUID
    project_id: UUID
    organization_id: UUID
    status: ProcessingJobStatus
    error: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
