import pytest
from datetime import datetime, timedelta, timezone
import uuid
from app.models.core import User, Organization, Role
from app.core.security import hash_password, create_access_token, generate_secure_token

def test_register_user_success(client, db_session):
    payload = {
        "full_name": "Alice Builder",
        "email": "alice@construction.com",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "organization_name": "Alice Construction Ltd",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@construction.com"
    assert data["is_verified"] is False
    assert "user_id" in data

    # Verify user in database
    user = db_session.query(User).filter(User.email == "alice@construction.com").first()
    assert user is not None
    assert user.full_name == "Alice Builder"
    assert user.is_verified is False
    assert user.verification_token is not None
    assert user.role == Role.ADMIN
    assert user.organization.name == "Alice Construction Ltd"

def test_register_duplicate_email(client, db_session):
    payload = {
        "full_name": "Alice Builder",
        "email": "duplicate@construction.com",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]

def test_register_password_mismatch(client):
    payload = {
        "full_name": "Bob Builder",
        "email": "bob@construction.com",
        "password": "SecurePassword123!",
        "confirm_password": "DifferentPassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422

def test_login_success(client, db_session):
    org = Organization(id=uuid.uuid4(), name="Test Org", settings={})
    db_session.add(org)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="login_user@test.com",
        full_name="Login Tester",
        password_hash=hash_password("MyPassword123!"),
        role=Role.REVIEWER,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "login_user@test.com",
        "password": "MyPassword123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_user@test.com"
    assert data["user"]["role"] == "REVIEWER"

def test_login_invalid_password(client, db_session):
    org = Organization(id=uuid.uuid4(), name="Test Org", settings={})
    db_session.add(org)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="wrongpass@test.com",
        full_name="Tester",
        password_hash=hash_password("CorrectPassword123!"),
        role=Role.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "wrongpass@test.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

def test_verify_email_success(client, db_session):
    org = Organization(id=uuid.uuid4(), name="Verify Org", settings={})
    db_session.add(org)
    db_session.flush()

    token = generate_secure_token()
    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="verify_me@test.com",
        full_name="Unverified User",
        is_verified=False,
        verification_token=token,
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert "Email verified successfully" in response.json()["message"]

    db_session.refresh(user)
    assert user.is_verified is True
    assert user.verification_token is None

def test_verify_email_invalid_or_expired_token(client, db_session):
    # Invalid token
    resp1 = client.post("/api/v1/auth/verify-email", json={"token": "non-existent-token"})
    assert resp1.status_code == 400

    # Expired token
    org = Organization(id=uuid.uuid4(), name="Expired Org", settings={})
    db_session.add(org)
    db_session.flush()

    expired_token = generate_secure_token()
    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="expired@test.com",
        is_verified=False,
        verification_token=expired_token,
        verification_token_expires_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(user)
    db_session.commit()

    resp2 = client.post("/api/v1/auth/verify-email", json={"token": expired_token})
    assert resp2.status_code == 400
    assert "expired" in resp2.json()["detail"]

def test_forgot_and_reset_password_workflow(client, db_session):
    org = Organization(id=uuid.uuid4(), name="Reset Org", settings={})
    db_session.add(org)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="reset_user@test.com",
        full_name="Reset Tester",
        password_hash=hash_password("OldPassword123!"),
    )
    db_session.add(user)
    db_session.commit()

    # 1. Request password reset
    resp_forgot = client.post("/api/v1/auth/forgot-password", json={"email": "reset_user@test.com"})
    assert resp_forgot.status_code == 200

    db_session.refresh(user)
    reset_token = user.reset_token
    assert reset_token is not None

    # 2. Reset password
    resp_reset = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "BrandNewPassword123!",
        "confirm_password": "BrandNewPassword123!",
    })
    assert resp_reset.status_code == 200

    # 3. Verify old password fails and new password succeeds
    resp_old = client.post("/api/v1/auth/login", json={
        "email": "reset_user@test.com",
        "password": "OldPassword123!"
    })
    assert resp_old.status_code == 401

    resp_new = client.post("/api/v1/auth/login", json={
        "email": "reset_user@test.com",
        "password": "BrandNewPassword123!"
    })
    assert resp_new.status_code == 200

    # 4. Token cannot be reused
    resp_reuse = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "AnotherPassword123!",
        "confirm_password": "AnotherPassword123!",
    })
    assert resp_reuse.status_code == 400

def test_google_auth_url(client):
    response = client.get("/api/v1/auth/google/url")
    assert response.status_code == 200
    assert "accounts.google.com" in response.json()["url"]

def test_jwt_protected_endpoint(client, db_session):
    org = Organization(id=uuid.uuid4(), name="JWT Org", settings={})
    db_session.add(org)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        auth_id=str(uuid.uuid4()),
        organization_id=org.id,
        email="jwt_user@test.com",
        full_name="JWT Tester",
        role=Role.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({
        "sub": user.auth_id,
        "user_id": str(user.id),
        "organization_id": str(user.organization_id),
        "role": user.role.value,
        "email": user.email,
    })

    # Access /api/v1/users/me with custom token
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "jwt_user@test.com"
    assert data["role"] == "ADMIN"
