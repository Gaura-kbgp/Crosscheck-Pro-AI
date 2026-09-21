from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime
from app.models.core import ReportFormat, ReportStatus

class ReportCreateRequest(BaseModel):
    format: ReportFormat = Field(default=ReportFormat.PDF, description="Report format: PDF or CSV")

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    report_id: Optional[UUID] = None
    project_id: UUID
    format: ReportFormat
    status: ReportStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        if self.report_id is None:
            self.report_id = self.id

class ReportStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    report_id: Optional[UUID] = None
    project_id: UUID
    format: ReportFormat
    status: ReportStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    error: Optional[Any] = None

    def model_post_init(self, __context: Any) -> None:
        if self.report_id is None:
            self.report_id = self.id

class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
