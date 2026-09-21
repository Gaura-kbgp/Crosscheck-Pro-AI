import uuid
from typing import List
from fastapi import APIRouter, Depends, status, Response, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.schemas.user import AuthenticatedUser
from app.schemas.report import (
    ReportCreateRequest, ReportResponse, ReportStatusResponse, ReportListResponse
)
from app.services.report_service import ReportService
from app.models.core import Role

router = APIRouter()

@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def create_report(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: ReportCreateRequest = ReportCreateRequest(),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    report = service.create_report(
        project_id=project_id,
        organization_id=current_user.organization_id,
        format=request.format,
        background_tasks=background_tasks
    )
    return report

@router.get(
    "/projects/{project_id}/reports",
    response_model=List[ReportResponse]
)
def list_reports(
    project_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    return service.list_reports(project_id, current_user.organization_id)

@router.get(
    "/projects/{project_id}/reports/pdf"
)
def export_pdf(
    project_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    pdf_bytes = service.generate_pdf_bytes(project_id, current_user.organization_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_audit_report.pdf"'
        }
    )

@router.get(
    "/projects/{project_id}/reports/csv",
    response_class=PlainTextResponse
)
def export_csv(
    project_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    csv_data = service.generate_csv_data(project_id, current_user.organization_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_crosscheck.csv"'
        }
    )

@router.get(
    "/projects/{project_id}/reports/{report_id}",
    response_model=ReportResponse
)
def get_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    report = service.get_report(report_id, current_user.organization_id)
    if report.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found for this project")
    return report

@router.get(
    "/reports/{report_id}/status",
    response_model=ReportStatusResponse
)
def get_report_status(
    report_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    return service.get_report(report_id, current_user.organization_id)

@router.get(
    "/reports/{report_id}/download"
)
def download_report(
    report_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ReportService(db)
    report = service.get_report(report_id, current_user.organization_id)
    if not report.download_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for download or generation failed"
        )
    return {"download_url": report.download_url}
