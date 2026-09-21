import pytest
from fastapi.testclient import TestClient
import uuid
from app.models.core import User, Organization, Role
from app.core.security import create_access_token, hash_password

def test_get_and_patch_user_profile(client: TestClient, db_session):
    org = Organization(id=uuid.uuid4(), name="Test Settings Org")
    db_session.add(org)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        auth_id="auth_settings_123",
        organization_id=org.id,
        email="user_settings@example.com",
        full_name="Original Name",
        role=Role.ADMIN,
        is_verified=True,
        password_hash=hash_password("OldPassword123!"),
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": user.auth_id, "email": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    # Test GET /users/me
    res = client.get("/api/v1/users/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "user_settings@example.com"
    assert res.json()["full_name"] == "Original Name"

    # Test PATCH /users/me
    patch_res = client.patch("/api/v1/users/me", json={"full_name": "Updated John Doe"}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "Updated John Doe"

    # Test POST /users/me/change-password with invalid current password
    bad_pw_res = client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "WrongPassword", "new_password": "NewSecretPassword123!"},
        headers=headers
    )
    assert bad_pw_res.status_code == 400

    # Test POST /users/me/change-password with valid current password
    good_pw_res = client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "OldPassword123!", "new_password": "NewSecretPassword123!"},
        headers=headers
    )
    assert good_pw_res.status_code == 200
    assert good_pw_res.json()["message"] == "Password updated successfully"

def test_organization_endpoints_rbac(client: TestClient, db_session):
    org = Organization(id=uuid.uuid4(), name="Acme Construction Inc", settings={"density": "comfortable"})
    db_session.add(org)
    db_session.flush()

    admin_user = User(
        id=uuid.uuid4(),
        auth_id="auth_admin_org",
        organization_id=org.id,
        email="admin_org@example.com",
        role=Role.ADMIN,
        is_verified=True,
    )
    viewer_user = User(
        id=uuid.uuid4(),
        auth_id="auth_viewer_org",
        organization_id=org.id,
        email="viewer_org@example.com",
        role=Role.VIEWER,
        is_verified=True,
    )
    db_session.add_all([admin_user, viewer_user])
    db_session.commit()

    admin_token = create_access_token({"sub": admin_user.auth_id, "email": admin_user.email})
    viewer_token = create_access_token({"sub": viewer_user.auth_id, "email": viewer_user.email})

    # Viewer can GET organization details
    res_viewer = client.get("/api/v1/organizations/me", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 200
    assert res_viewer.json()["name"] == "Acme Construction Inc"
    assert res_viewer.json()["user_count"] == 2

    # Viewer CANNOT update organization (RBAC 403 Forbidden)
    patch_viewer = client.patch(
        "/api/v1/organizations/me",
        json={"name": "Hacked Name"},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert patch_viewer.status_code == 403

    # Admin CAN update organization
    patch_admin = client.patch(
        "/api/v1/organizations/me",
        json={"name": "Acme Global Solutions", "settings": {"density": "compact", "auto_refresh": True}},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert patch_admin.status_code == 200
    assert patch_admin.json()["name"] == "Acme Global Solutions"
    assert patch_admin.json()["settings"]["density"] == "compact"
