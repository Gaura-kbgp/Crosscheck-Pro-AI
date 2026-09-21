import pytest
import uuid
from unittest.mock import patch, MagicMock
from app.models.core import (
    Organization, User, Project, Document, DocumentType, DocumentStatus,
    CanonicalLineItem, MatchGroup, Discrepancy, MatchGroupStatus, Severity,
    Role, ProjectStatus, Report, ReportFormat, ReportStatus
)
from app.services.report_service import ReportService
from app.worker.tasks.reporting import generate_report_task

@pytest.fixture
def test_setup(db_session):
    org = Organization(name="Report Org")
    db_session.add(org)
    db_session.commit()

    user = User(
        auth_id="report-auth-1",
        email="report_reviewer@example.com",
        role=Role.REVIEWER,
        organization_id=org.id
    )
    db_session.add(user)
    db_session.commit()

    project = Project(
        name="Reporting Kitchen Project",
        customer_name="Alice Smith",
        dealer_name="Superior Cabinets",
        status=ProjectStatus.REVIEW_REQUIRED,
        organization_id=org.id
    )
    db_session.add(project)
    db_session.commit()

    # Documents
    doc_d = Document(
        project_id=project.id,
        organization_id=org.id,
        document_type=DocumentType.DESIGN,
        original_filename="design_v1.pdf",
        storage_path=f"{org.id}/{project.id}/d1/design_v1.pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.COMPLETED
    )
    doc_o = Document(
        project_id=project.id,
        organization_id=org.id,
        document_type=DocumentType.ORDER,
        original_filename="order_v1.pdf",
        storage_path=f"{org.id}/{project.id}/d2/order_v1.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=DocumentStatus.COMPLETED
    )
    doc_a = Document(
        project_id=project.id,
        organization_id=org.id,
        document_type=DocumentType.ACKNOWLEDGEMENT,
        original_filename="ack_v1.pdf",
        storage_path=f"{org.id}/{project.id}/d3/ack_v1.pdf",
        mime_type="application/pdf",
        file_size=3072,
        status=DocumentStatus.COMPLETED
    )
    db_session.add_all([doc_d, doc_o, doc_a])
    db_session.commit()

    # Canonical Line Items
    item_d = CanonicalLineItem(
        project_id=project.id,
        organization_id=org.id,
        document_id=doc_d.id,
        source_type=DocumentType.DESIGN,
        normalized_sku="B36",
        description="Base Cabinet 36 inch",
        quantity=2,
        dimensions={"width": 36, "height": 34.5, "depth": 24},
        finish="White Paint",
        door_style="Shaker"
    )
    item_o = CanonicalLineItem(
        project_id=project.id,
        organization_id=org.id,
        document_id=doc_o.id,
        source_type=DocumentType.ORDER,
        normalized_sku="B36",
        description="Base Cabinet 36 inch",
        quantity=3, # Discrepancy
        dimensions={"width": 36, "height": 34.5, "depth": 24},
        finish="White Paint",
        door_style="Shaker"
    )
    item_a = CanonicalLineItem(
        project_id=project.id,
        organization_id=org.id,
        document_id=doc_a.id,
        source_type=DocumentType.ACKNOWLEDGEMENT,
        normalized_sku="B36",
        description="Base Cabinet 36 inch",
        quantity=3,
        dimensions={"width": 36, "height": 34.5, "depth": 24},
        finish="White Paint",
        door_style="Shaker"
    )
    db_session.add_all([item_d, item_o, item_a])
    db_session.commit()

    # Match Group
    mg = MatchGroup(
        project_id=project.id,
        organization_id=org.id,
        design_item_id=item_d.id,
        order_item_id=item_o.id,
        ack_item_id=item_a.id,
        status=MatchGroupStatus.CHANGED,
        final_sku="B36",
        final_quantity=3,
        final_finish="White Paint",
        final_door_style="Shaker",
        final_status="RESOLVED"
    )
    db_session.add(mg)
    db_session.commit()

    # Discrepancy
    disc = Discrepancy(
        project_id=project.id,
        organization_id=org.id,
        match_group_id=mg.id,
        field="quantity",
        source_values={"design": 2, "order": 3, "acknowledgement": 3},
        comparison_values={"design": 2, "order": 3, "acknowledgement": 3},
        introduced_at=DocumentType.ORDER,
        severity=Severity.CRITICAL,
        confidence="HIGH",
        status="OPEN",
        explanation="Quantity mismatch: Design=2, Order=3"
    )
    db_session.add(disc)
    db_session.commit()

    return {
        "org": org,
        "user": user,
        "project": project,
        "match_group": mg,
        "discrepancy": disc
    }

def test_generate_csv_data_deterministic(db_session, test_setup):
    service = ReportService(db_session)
    csv_str = service.generate_csv_data(test_setup["project"].id, test_setup["org"].id)
    
    assert "project_id,project_name,match_group_id,sku,description" in csv_str
    assert "Reporting Kitchen Project" in csv_str
    assert "B36" in csv_str
    assert "quantity" in csv_str
    assert "Critical" in csv_str

def test_generate_pdf_bytes(db_session, test_setup):
    service = ReportService(db_session)
    pdf_bytes = service.generate_pdf_bytes(test_setup["project"].id, test_setup["org"].id)
    
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

def test_create_report_and_idempotency(db_session, test_setup):
    service = ReportService(db_session)
    
    # 1. Create PDF report
    report1 = service.create_report(test_setup["project"].id, test_setup["org"].id, ReportFormat.PDF)
    assert report1.status == ReportStatus.QUEUED
    assert report1.format == ReportFormat.PDF

    # 2. Repeated request returns same active report (Idempotent)
    report2 = service.create_report(test_setup["project"].id, test_setup["org"].id, ReportFormat.PDF)
    assert report1.id == report2.id

    # 3. CSV report is tracked separately
    report_csv = service.create_report(test_setup["project"].id, test_setup["org"].id, ReportFormat.CSV)
    assert report_csv.id != report1.id
    assert report_csv.format == ReportFormat.CSV

def test_process_report_job_execution(db_session, test_setup):
    service = ReportService(db_session)
    report = service.create_report(test_setup["project"].id, test_setup["org"].id, ReportFormat.PDF)
    
    with patch("app.services.report_service.StorageService.upload_file") as mock_upload:
        processed_report = service.process_report_job(report.id)
        assert processed_report.status == ReportStatus.COMPLETED
        assert processed_report.storage_path is not None
        assert processed_report.completed_at is not None
        mock_upload.assert_called_once()

import jwt
from app.core.config import settings

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

def test_report_api_endpoints(client, test_setup):
    user = test_setup["user"]
    project = test_setup["project"]
    
    token = create_test_token(user.auth_id)
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 1. Trigger Report Creation
    res = client.post(
        f"/api/v1/projects/{project.id}/reports",
        json={"format": "PDF"},
        headers=headers
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "QUEUED"
    report_id = data["report_id"]

    # 2. Get Report Status
    res_status = client.get(
        f"/api/v1/projects/{project.id}/reports/{report_id}",
        headers=headers
    )
    assert res_status.status_code == 200
    assert res_status.json()["report_id"] == report_id

    # 3. Direct CSV Export
    res_csv = client.get(
        f"/api/v1/projects/{project.id}/reports/csv",
        headers=headers
    )
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "B36" in res_csv.text

    # 4. List Reports
    res_list = client.get(
        f"/api/v1/projects/{project.id}/reports",
        headers=headers
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1
