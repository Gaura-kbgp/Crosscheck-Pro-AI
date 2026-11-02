import jwt
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from app.core.config import settings

_jwks_client: "jwt.PyJWKClient | None" = None

def _get_jwks_client() -> "jwt.PyJWKClient | None":
    """Lazily builds a cached JWKS client for Supabase's asymmetric (ES256) signing keys."""
    global _jwks_client
    if _jwks_client is None and settings.SUPABASE_URL and "placeholder" not in settings.SUPABASE_URL:
        _jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json")
    return _jwks_client

def hash_password(password: str) -> str:
    """Hashes a plaintext password securely using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generates an application JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": now,
    })
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def verify_jwt_token(token: str) -> dict | None:
    """Decodes and validates an application JWT token."""
    # Supabase projects created with the modern signing-key system issue
    # asymmetric (e.g. ES256) tokens that must be verified against their
    # published JWKS, not a static shared secret.
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg", "").upper() != "HS256":
            jwks_client = _get_jwks_client()
            if jwks_client:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[header["alg"]],
                    options={"verify_aud": False}
                )
    except Exception:
        pass

    # List candidate secrets to verify custom app tokens or legacy/test tokens
    candidate_secrets = [settings.JWT_SECRET]
    supabase_secret = getattr(settings, "SUPABASE_JWT_SECRET", None)
    if supabase_secret and supabase_secret not in candidate_secrets:
        candidate_secrets.append(supabase_secret)

    for secret in candidate_secrets:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256", settings.JWT_ALGORITHM],
                options={"verify_aud": False}
            )
            return payload
        except Exception:
            continue

    if settings.APP_ENV == "test":
        try:
            return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        except Exception:
            pass

    return None

# Backward compatibility alias
def verify_supabase_jwt(token: str) -> dict | None:
    return verify_jwt_token(token)

def generate_secure_token() -> str:
    """Generates a cryptographically secure token for email verification and password reset."""
    return secrets.token_urlsafe(32)

