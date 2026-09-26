import pytest
import uuid
from io import BytesIO
import jwt
from app.models.core import Organization, User, Project, Role

from app.core.config import settings

from unittest.mock import patch

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

@pytest.fixture(autouse=True)
def mock_storage():
    with patch("app.services.document_service.StorageService") as mock:
        mock_instance = mock.return_value
        mock_instance.upload_file.return_value = "test/path.pdf"
        mock_instance.create_signed_url.return_value = "https://mock-storage.local/test.pdf"
        yield mock

def test_document_upload_success(client, db_session, mock_storage):
    org_a = Organization(name="Org A")
    db_session.add(org_a)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user_a)
    db_session.commit()

    project_a = Project(organization_id=org_a.id, name="Project A")
    db_session.add(project_a)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"PDF mock content"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
    data = {"document_type": "DESIGN"}

    response = client.post(f"/api/v1/projects/{project_a.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["original_filename"] == "test.pdf"
    assert res_data["document_type"] == "DESIGN"
    
    # Test list
    list_response = client.get(f"/api/v1/projects/{project_a.id}/documents", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # Test signed url
    url_response = client.get(f"/api/v1/projects/{project_a.id}/documents/{res_data['id']}", headers=headers)
    assert url_response.status_code == 200
    assert "mock-storage.local" in url_response.json()["url"]

def test_document_upload_invalid_mime(client, db_session):
    org_a = Organization(name="Org A")
    db_session.add(org_a)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    db_session.add(user_a)
    project_a = Project(organization_id=org_a.id, name="Project A")
    db_session.add(project_a)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"Binary content"
    files = {"file": ("test.exe", BytesIO(file_content), "application/x-msdownload")}
    data = {"document_type": "ORDER"}

    response = client.post(f"/api/v1/projects/{project_a.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 415

def test_document_tenant_isolation(client, db_session):
    org_a = Organization(name="Org A")
    org_b = Organization(name="Org B")
    db_session.add(org_a)
    db_session.add(org_b)
    db_session.commit()

    user_a = User(auth_id="auth-a", organization_id=org_a.id, email="a@a.com", role=Role.ADMIN)
    project_b = Project(organization_id=org_b.id, name="Project B")
    db_session.add(user_a)
    db_session.add(project_b)
    db_session.commit()

    token = create_test_token("auth-a")
    headers = {"Authorization": f"Bearer {token}"}

    file_content = b"PDF mock content"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
    data = {"document_type": "DESIGN"}

    response = client.post(f"/api/v1/projects/{project_b.id}/documents", headers=headers, files=files, data=data)
    assert response.status_code == 404 # Project not found in Org A
