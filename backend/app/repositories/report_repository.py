from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import List, Optional
import uuid

from app.models.core import Report, ReportStatus, ReportFormat

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> Report:
        report = Report(**kwargs)
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_by_id_and_org(self, report_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[Report]:
        stmt = select(Report).where(
            Report.id == report_id,
            Report.organization_id == organization_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id(self, report_id: uuid.UUID) -> Optional[Report]:
        stmt = select(Report).where(Report.id == report_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> List[Report]:
        stmt = select(Report).where(
            Report.project_id == project_id,
            Report.organization_id == organization_id
        ).order_by(Report.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_active_report_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID, format: ReportFormat
    ) -> Optional[Report]:
        stmt = select(Report).where(
            Report.project_id == project_id,
            Report.organization_id == organization_id,
            Report.format == format,
            Report.status.in_([ReportStatus.QUEUED, ReportStatus.GENERATING])
        ).order_by(Report.created_at.desc())
        return self.db.execute(stmt).scalars().first()

    def update_status(
        self, 
        report: Report, 
        status: ReportStatus, 
        storage_path: Optional[str] = None, 
        error: Optional[dict] = None,
        completed_at = None
    ) -> Report:
        report.status = status
        if storage_path is not None:
            report.storage_path = storage_path
        if error is not None:
            report.error = error
        if completed_at is not None:
            report.completed_at = completed_at
        self.db.commit()
        self.db.refresh(report)
        return report
