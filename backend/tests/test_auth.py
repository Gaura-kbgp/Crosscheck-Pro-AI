from fastapi.testclient import TestClient
from main import app
import jwt
from app.core.config import settings

client = TestClient(app)

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

def test_get_me_unauthorized():
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401

def test_get_me_invalid_token():
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid"}
    )
    assert response.status_code == 401
