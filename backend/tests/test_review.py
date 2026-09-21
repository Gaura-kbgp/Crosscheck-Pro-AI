import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.core import User, Organization, Role, Project, Discrepancy, MatchGroup, CanonicalLineItem, DocumentType
from app.models.core import HumanReview, AuditLog, ReviewAction, MatchGroupStatus, Severity
from app.core.config import settings
import jwt

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

@pytest.fixture
def test_organization(db_session: Session):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org

@pytest.fixture
def test_user(db_session: Session, test_organization: Organization):
    auth_id = str(uuid.uuid4())
    user = User(
        auth_id=auth_id,
        organization_id=test_organization.id,
        email="test@example.com",
        role=Role.ADMIN
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def headers(test_user: User):
    token = create_test_token(test_user.auth_id)
    return {"Authorization": f"Bearer {token}"}

def test_accept_finding(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    # Setup project and discrepancy
    proj = Project(organization_id=test_organization.id, name="Test")
    db_session.add(proj)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=test_organization.id, status=MatchGroupStatus.UNCERTAIN)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=test_organization.id,
        match_group_id=mg.id,
        field="quantity",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.CRITICAL
    )
    db_session.add(disc)
    db_session.commit()
    
    # Action
    response = client.post(
        f"/api/v1/discrepancies/{disc.id}/review",
        json={"action": "ACCEPT_FINDING", "reason": "Looks good"},
        headers=headers
    )
    
    assert response.status_code == 200
    
    # Verification
    db_session.refresh(disc)
    assert disc.status == "RESOLVED"
    
    hr = db_session.query(HumanReview).filter_by(discrepancy_id=disc.id).first()
    assert hr is not None
    assert hr.action == ReviewAction.ACCEPT_FINDING
    assert hr.reason == "Looks good"
    
    audit = db_session.query(AuditLog).filter_by(resource_id=str(disc.id)).first()
    assert audit is not None
    assert audit.action == "ACCEPT_FINDING"

def test_false_positive(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    proj = Project(organization_id=test_organization.id, name="Test FP")
    db_session.add(proj)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=test_organization.id, status=MatchGroupStatus.UNCERTAIN)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=test_organization.id,
        match_group_id=mg.id,
        field="price",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.WARNING
    )
    db_session.add(disc)
    db_session.commit()
    
    # Action
    response = client.post(
        f"/api/v1/discrepancies/{disc.id}/review",
        json={"action": "FALSE_POSITIVE", "reason": "Not an issue"},
        headers=headers
    )
    
    assert response.status_code == 200
    db_session.refresh(disc)
    assert disc.status == "FALSE_POSITIVE"
    
    hr = db_session.query(HumanReview).filter_by(discrepancy_id=disc.id).first()
    assert hr.action == ReviewAction.FALSE_POSITIVE

def test_escalate(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    proj = Project(organization_id=test_organization.id, name="Test Escalate")
    db_session.add(proj)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=test_organization.id, status=MatchGroupStatus.UNCERTAIN)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=test_organization.id,
        match_group_id=mg.id,
        field="sku",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.CRITICAL
    )
    db_session.add(disc)
    db_session.commit()
    
    # Action
    response = client.post(
        f"/api/v1/discrepancies/{disc.id}/review",
        json={"action": "ESCALATE", "reason": "Need manager review"},
        headers=headers
    )
    
    assert response.status_code == 200
    db_session.refresh(disc)
    assert disc.status == "ESCALATED"
    
    hr = db_session.query(HumanReview).filter_by(discrepancy_id=disc.id).first()
    assert hr.action == ReviewAction.ESCALATE

def test_override_data(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    # Needs a complete document and item structure to not crash CrossCheckEngine
    from app.models.core import Document
    proj = Project(organization_id=test_organization.id, name="Test Override")
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)
    
    doc = Document(project_id=proj.id, organization_id=test_organization.id, document_type=DocumentType.DESIGN, original_filename="test.pdf", storage_path=str(uuid.uuid4()), mime_type="application/pdf", file_size=100)
    db_session.add(doc)
    db_session.commit()
    
    item = CanonicalLineItem(
        project_id=proj.id,
        organization_id=test_organization.id,
        document_id=doc.id,
        source_type=DocumentType.DESIGN,
        quantity=3
    )
    db_session.add(item)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=test_organization.id, status=MatchGroupStatus.UNCERTAIN, design_item_id=item.id)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=test_organization.id,
        match_group_id=mg.id,
        field="quantity",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.CRITICAL
    )
    db_session.add(disc)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/discrepancies/{disc.id}/review",
        json={
            "action": "OVERRIDE_DATA",
            "reason": "Fixing typo",
            "match_group_id": str(mg.id),
            "canonical_item_id": str(item.id),
            "field_name": "quantity",
            "new_value": 5
        },
        headers=headers
    )
    
    assert response.status_code == 200
    
    db_session.refresh(item)
    assert item.quantity == 5
    
    hr = db_session.query(HumanReview).filter_by(match_group_id=mg.id).first()
    assert hr.action == ReviewAction.OVERRIDE_DATA
    
    audit = db_session.query(AuditLog).filter_by(resource_type="CanonicalLineItem").first()
    assert audit.action == "OVERRIDE_DATA"
    assert audit.new_state["quantity"] == 5

def test_finalize_project(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    from app.models.core import ProjectStatus
    proj = Project(organization_id=test_organization.id, name="Test Finalize", status=ProjectStatus.COMPLETED)
    db_session.add(proj)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/projects/{proj.id}/finalize",
        headers=headers
    )
    
    assert response.status_code == 200
    db_session.refresh(proj)
    assert proj.status == ProjectStatus.FINALIZED
    
    audit = db_session.query(AuditLog).filter_by(resource_type="Project").first()
    assert audit.action == "PROJECT_FINALIZED"

def test_finalize_project_with_critical(client: TestClient, db_session: Session, test_user: User, test_organization: Organization, headers: dict):
    from app.models.core import ProjectStatus
    proj = Project(organization_id=test_organization.id, name="Test Finalize 2", status=ProjectStatus.COMPLETED)
    db_session.add(proj)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=test_organization.id, status=MatchGroupStatus.UNCERTAIN)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=test_organization.id,
        match_group_id=mg.id,
        field="quantity",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.CRITICAL
    )
    db_session.add(disc)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/projects/{proj.id}/finalize",
        headers=headers
    )
    
    assert response.status_code == 400
    assert "Cannot finalize" in response.json()["detail"]

def test_tenant_isolation(client: TestClient, db_session: Session, test_user: User, headers: dict):
    # Test user is in org 1. We create org 2 and try to access its discrepancy.
    org2 = Organization(name="Org 2")
    db_session.add(org2)
    db_session.commit()
    
    proj = Project(organization_id=org2.id, name="Test")
    db_session.add(proj)
    db_session.commit()
    
    mg = MatchGroup(project_id=proj.id, organization_id=org2.id, status=MatchGroupStatus.UNCERTAIN)
    db_session.add(mg)
    db_session.commit()
    
    disc = Discrepancy(
        project_id=proj.id,
        organization_id=org2.id,
        match_group_id=mg.id,
        field="sku",
        source_values={},
        comparison_values={},
        status="OPEN",
        severity=Severity.CRITICAL
    )
    db_session.add(disc)
    db_session.commit()
    
    response = client.post(
        f"/api/v1/discrepancies/{disc.id}/review",
        json={"action": "ACCEPT_FINDING", "reason": "Looks good"},
        headers=headers
    )
    
    assert response.status_code == 404
