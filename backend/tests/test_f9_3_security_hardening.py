import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.rate_limiter import reset_rate_limit_store, RateLimiter

client = TestClient(app)

def setup_function():
    reset_rate_limit_store()

# ── 1. Security Headers Tests ──

def test_security_headers_present():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"

# ── 2. Rate Limiting Tests ──

def test_auth_login_rate_limiting():
    reset_rate_limit_store()
    # auth_limiter limit is settings.AUTH_RATE_LIMIT (default 10)
    for i in range(settings.AUTH_RATE_LIMIT):
        res = client.post("/api/v1/auth/login", json={"email": f"rate_test_{i}@example.com", "password": "Password123!"})
        # Should be 401 or 404 (not 429 yet)
        assert res.status_code in (401, 404, 422)

    # The 11th request must return 429 Too Many Requests
    res_exceeded = client.post("/api/v1/auth/login", json={"email": "rate_exceeded@example.com", "password": "Password123!"})
    assert res_exceeded.status_code == 429
    assert "Too many requests" in res_exceeded.json()["detail"]
    assert "Retry-After" in res_exceeded.headers

def test_auth_forgot_password_rate_limiting():
    reset_rate_limit_store()
    for i in range(settings.PASSWORD_RESET_RATE_LIMIT):
        res = client.post("/api/v1/auth/forgot-password", json={"email": f"reset_test_{i}@example.com"})
        assert res.status_code in (200, 404)

    # Exceed limit
    res_exceeded = client.post("/api/v1/auth/forgot-password", json={"email": "reset_exceeded@example.com"})
    assert res_exceeded.status_code == 429
    assert "Too many requests" in res_exceeded.json()["detail"]

# ── 3. Password Input Boundary & Abuse Matrix ──

@pytest.mark.parametrize("pw_length", [1, 8, 11, 12, 13, 32, 64, 128])
def test_password_valid_length_boundaries(pw_length):
    pw = "A" * pw_length
    payload = {
        "email": f"user_{pw_length}@example.com",
        "password": pw,
        "full_name": "Test User",
        "organization_name": "Test Org"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    # Registration should succeed (201) or fail on business logic, NOT crash (500)
    assert res.status_code in (201, 400, 409, 422)

@pytest.mark.parametrize("pw_length", [129, 256, 1000, 5000])
def test_password_oversized_rejected_by_schema(pw_length):
    pw = "X" * pw_length
    payload = {
        "email": f"oversized_{pw_length}@example.com",
        "password": pw
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422 # Pydantic schema validation error

    # Check login schema caps oversized password as well
    login_res = client.post("/api/v1/auth/login", json=payload)
    assert login_res.status_code == 422

@pytest.mark.parametrize("special_pw", [
    "P@ssw0rd!#$&*",
    "Unicode_🔑_Cabinet_123",
    "Line1\nLine2\rControlChars",
    "   leading_and_trailing_spaces   ",
    "1313131313131" # 13 digits case
])
def test_password_special_characters_handling(special_pw):
    payload = {
        "email": "special_pw@example.com",
        "password": special_pw
    }
    res = client.post("/api/v1/auth/login", json=payload)
    # Should evaluate validation without server crash (500)
    assert res.status_code in (401, 404, 422)
