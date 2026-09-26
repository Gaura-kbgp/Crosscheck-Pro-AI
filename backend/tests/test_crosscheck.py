import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.models.core import CanonicalLineItem, DocumentType, MatchGroup, MatchGroupStatus, Discrepancy, Severity, Organization, Project, User, Role, Document
from app.services.crosscheck_service import CrossCheckService
import jwt
from app.core.config import settings

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
import jwt
from app.core.config import settings

def create_item(db_session, project_id, org_id, source_type, sku, qty=1, finish=None, door=None, desc=""):
    doc = Document(
        id=uuid4(),
        project_id=project_id,
        organization_id=org_id,
        document_type=source_type,
        original_filename="test.pdf",
        storage_path=f"path_{uuid4()}.pdf",
        mime_type="application/pdf",
        file_size=100
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    item = CanonicalLineItem(
        project_id=project_id,
        organization_id=org_id,
        document_id=doc.id,
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku,
        description=desc,
        quantity=qty,
        finish=finish,
        door_style=door
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item

@pytest.fixture
def crosscheck_env(db_session):
    org = Organization(name="CrossCheck Org")
    db_session.add(org)
    db_session.commit()
    
    project = Project(organization_id=org.id, name="CrossCheck Proj")
    db_session.add(project)
    db_session.commit()
    
    service = CrossCheckService(db_session)
    return service, project.id, org.id

def test_exact_matching(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")
    
    res = service.process_project(project_id, org_id)
    assert res["match_groups_count"] == 1
    
    mg = db_session.query(MatchGroup).first()
    assert mg.status == MatchGroupStatus.MATCHED
    assert not mg.discrepancies

def test_missing_order(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")

    res = service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    assert mg.status == MatchGroupStatus.MISSING
    assert len(mg.discrepancies) == 1
    assert mg.discrepancies[0].field == "item_presence"
    # Deterministic 3-way attribution: Design is the first (and only) source
    # where the item exists, so it is where the discrepancy is introduced —
    # not ORDER, which never carried the item at all.
    assert mg.discrepancies[0].introduced_at == DocumentType.DESIGN

def test_extra_order(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")
    
    service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    assert mg.status == MatchGroupStatus.EXTRA
    assert len(mg.discrepancies) == 1
    assert mg.discrepancies[0].field == "item_presence"
    assert mg.discrepancies[0].introduced_at == DocumentType.ORDER

def test_quantity_change_at_order(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", qty=3)
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", qty=2)
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", qty=2)
    
    service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    assert mg.status == MatchGroupStatus.CHANGED
    assert len(mg.discrepancies) == 1
    d = mg.discrepancies[0]
    assert d.field == "quantity"
    assert d.introduced_at == DocumentType.ORDER

def test_quantity_change_at_ack(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", qty=3)
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", qty=3)
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", qty=2)
    
    service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    assert mg.status == MatchGroupStatus.CHANGED
    assert len(mg.discrepancies) == 1
    d = mg.discrepancies[0]
    assert d.field == "quantity"
    assert d.introduced_at == DocumentType.ACKNOWLEDGEMENT

def test_finish_change(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", finish="WHITE")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", finish="WHITE")
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", finish="OAK")
    
    service.process_project(project_id, org_id)
    d = db_session.query(Discrepancy).first()
    assert d.field == "finish"
    assert d.introduced_at == DocumentType.ACKNOWLEDGEMENT
    assert d.severity == Severity.WARNING

def test_door_style_change(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", door="Shaker")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", door="Shaker")
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", door="Slab")
    
    service.process_project(project_id, org_id)
    d = db_session.query(Discrepancy).first()
    assert d.field == "door_style"
    assert d.introduced_at == DocumentType.ACKNOWLEDGEMENT

def test_sku_mismatch(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "B456")
    
    service.process_project(project_id, org_id)
    mgs = db_session.query(MatchGroup).all()
    assert len(mgs) == 2
    statuses = set(mg.status for mg in mgs)
    assert statuses == {MatchGroupStatus.MISSING, MatchGroupStatus.EXTRA}

def test_duplicate_sku(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")
    
    service.process_project(project_id, org_id)
    mgs = db_session.query(MatchGroup).all()
    # F8.2.5: Identical SKU lines within the same document aggregate cleanly into a single match group with quantity discrepancy
    assert len(mgs) == 1
    assert mgs[0].status == MatchGroupStatus.CHANGED
    assert len(mgs[0].discrepancies) == 1
    assert mgs[0].discrepancies[0].field == "quantity"

def test_fuzzy_matching(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "", desc="Base Cabinet 36 inch")
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "", desc="Base Cabinet 36 inch Wood")
    
    service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    assert mg.status in [MatchGroupStatus.CHANGED, MatchGroupStatus.MATCHED, MatchGroupStatus.MISSING]

def test_reverted_change(db_session, crosscheck_env):
    service, project_id, org_id = crosscheck_env
    create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", qty=3)
    create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", qty=2)
    create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", qty=3)
    
    service.process_project(project_id, org_id)
    mg = db_session.query(MatchGroup).first()
    # F8.2.6 evaluates quantity across full 3-way sequence at first divergence point (ORDER)
    assert len(mg.discrepancies) == 1
    d1 = mg.discrepancies[0]
    assert d1.field == "quantity"
    assert d1.introduced_at == DocumentType.ORDER
    assert "revert" in d1.explanation.lower()

def test_tenant_isolation_crosscheck(client: TestClient, db_session):
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add(org1)
    db_session.add(org2)
    db_session.commit()
    
    user1 = User(auth_id="auth-1", organization_id=org1.id, email="1@1.com", role=Role.ADMIN)
    user2 = User(auth_id="auth-2", organization_id=org2.id, email="2@2.com", role=Role.ADMIN)
    db_session.add(user1)
    db_session.add(user2)
    
    project1 = Project(organization_id=org1.id, name="Project 1")
    db_session.add(project1)
    db_session.commit()
    
    create_item(db_session, project1.id, org1.id, DocumentType.DESIGN, "A123")
    create_item(db_session, project1.id, org1.id, DocumentType.ORDER, "A123")
    CrossCheckService(db_session).process_project(project1.id, org1.id)
    
    token1 = create_test_token("auth-1")
    token2 = create_test_token("auth-2")
    
    # Org 1 can access
    resp = client.get(f"/api/v1/projects/{project1.id}/crosscheck", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["match_groups"]) == 1
    
    # Org 2 cannot access Org 1 project crosscheck
    resp2 = client.get(f"/api/v1/projects/{project1.id}/crosscheck", headers={"Authorization": f"Bearer {token2}"})
    assert resp2.status_code == 404
