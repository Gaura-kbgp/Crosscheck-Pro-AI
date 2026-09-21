import pytest
import uuid
import jwt
from app.models.core import Organization, User, Project, Role, ProjectStatus

from app.core.config import settings

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

def test_tenant_isolation(client, db_session):
    org_a = Organization(name="Org A")
    db_session.add(org_a)
    org_b = Organization(name="Org B")
    db_session.add(org_b)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user_a)
    user_b = User(auth_id="auth-b", organization_id=org_b.id, email="b@b.com", role=Role.ADMIN)
    db_session.add(user_b)
    db_session.commit()

    project_a = Project(organization_id=org_a.id, name="Project A")
    db_session.add(project_a)
    project_b = Project(organization_id=org_b.id, name="Project B")
    db_session.add(project_b)
    db_session.commit()

    token_a = create_test_token("auth-a")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Test User A lists projects -> only sees Project A
    response = client.get("/api/v1/projects", headers=headers_a)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Project A"

    # Test User A tries to get Project B -> 404
    response = client.get(f"/api/v1/projects/{project_b.id}", headers=headers_a)
    assert response.status_code == 404

    # Test User A tries to delete Project B -> 404
    response = client.delete(f"/api/v1/projects/{project_b.id}", headers=headers_a)
    assert response.status_code == 404

    # Test User A creates project in Org A
    response = client.post("/api/v1/projects", headers=headers_a, json={"name": "New A"})
    assert response.status_code == 201
    assert response.json()["organization_id"] == str(org_a.id)

def test_rbac(client, db_session):
    org = Organization(name="Org")
    db_session.add(org)
    db_session.commit()
    
    user = User(auth_id="auth-viewer", organization_id=org.id, email="v@v.com", role=Role.VIEWER)
    db_session.add(user)
    db_session.commit()
    
    token = create_test_token("auth-viewer")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Viewer cannot create project
    response = client.post("/api/v1/projects", headers=headers, json={"name": "New"})
    assert response.status_code == 403
