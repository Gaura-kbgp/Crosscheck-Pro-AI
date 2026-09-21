import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
import httpx
import structlog
from fastapi import HTTPException, status

from app.models.core import User, Organization, Role
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    MessageResponse,
)
from app.schemas.user import UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_secure_token,
)
from app.services.email_service import email_service
from app.core.config import settings

logger = structlog.get_logger(__name__)

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, req: RegisterRequest) -> RegisterResponse:
        email = req.email.lower().strip()

        # Check existing user
        stmt = select(User).where(User.email == email)
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists."
            )

        # Derive display name and organization name
        full_name = (req.full_name or email.split("@")[0]).strip()
        org_name = req.organization_name or f"{full_name}'s Org"
        org = Organization(
            id=uuid.uuid4(),
            name=org_name,
            settings={},
        )
        self.db.add(org)
        self.db.flush()

        # Generate verification token
        verification_token = generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        # Create user
        user = User(
            id=uuid.uuid4(),
            auth_id=str(uuid.uuid4()),
            organization_id=org.id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(req.password),
            role=Role.ADMIN,
            is_verified=False,
            verification_token=verification_token,
            verification_token_expires_at=expires_at,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # Send verification email asynchronously / via email service
        try:
            email_service.send_verification_email(
                email=user.email,
                token=verification_token,
                full_name=user.full_name
            )
        except Exception as e:
            logger.error("Failed to send verification email during registration", error=str(e), user_id=str(user.id))

        return RegisterResponse(
            message="Registration successful. Please check your email to verify your account.",
            email=user.email,
            user_id=user.id,
            is_verified=user.is_verified,
        )

    def login(self, req: LoginRequest) -> TokenResponse:
        email = req.email.lower().strip()

        stmt = select(User).where(User.email == email)
        user = self.db.execute(stmt).scalar_one_or_none()

        if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        # Generate JWT token
        token_data = {
            "sub": user.auth_id,
            "user_id": str(user.id),
            "organization_id": str(user.organization_id),
            "role": user.role.value,
            "email": user.email,
        }
        access_token = create_access_token(token_data)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    def verify_email(self, token: str) -> MessageResponse:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token is required."
            )

        stmt = select(User).where(User.verification_token == token)
        user = self.db.execute(stmt).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token."
            )

        if user.verification_token_expires_at:
            expires_at = user.verification_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification token has expired. Please request a new verification link."
                )

        # Mark user verified and clear token (single use)
        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires_at = None
        self.db.commit()

        return MessageResponse(message="Email verified successfully.")

    def resend_verification(self, email_raw: str) -> MessageResponse:
        email = email_raw.lower().strip()
        stmt = select(User).where(User.email == email)
        user = self.db.execute(stmt).scalar_one_or_none()

        if user and not user.is_verified:
            token = generate_secure_token()
            user.verification_token = token
            user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            self.db.commit()

            try:
                email_service.send_verification_email(user.email, token, user.full_name)
            except Exception as e:
                logger.error("Failed to resend verification email", error=str(e))

        return MessageResponse(
            message="If an unverified account exists with this email, a new verification link has been sent."
        )

    def forgot_password(self, email_raw: str) -> MessageResponse:
        email = email_raw.lower().strip()
        stmt = select(User).where(User.email == email)
        user = self.db.execute(stmt).scalar_one_or_none()

        if user:
            reset_token = generate_secure_token()
            user.reset_token = reset_token
            user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            self.db.commit()

            try:
                email_service.send_password_reset_email(user.email, reset_token, user.full_name)
            except Exception as e:
                logger.error("Failed to send password reset email", error=str(e))

        # Always return generic message to prevent email enumeration
        return MessageResponse(
            message="If an account exists with this email, a password reset link has been sent."
        )

    def reset_password(self, token: str, new_password: str) -> MessageResponse:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is required."
            )

        stmt = select(User).where(User.reset_token == token)
        user = self.db.execute(stmt).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset link."
            )

        if user.reset_token_expires_at:
            expires_at = user.reset_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password reset link has expired. Please request a new one."
                )

        # Update password securely and invalidate reset token
        user.password_hash = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None
        self.db.commit()

        return MessageResponse(message="Password updated successfully. You can now sign in.")

    def get_google_auth_url(self, redirect_uri: str | None = None) -> str:
        callback_uri = redirect_uri or f"{settings.FRONTEND_URL}/auth/callback"
        client_id = settings.GOOGLE_CLIENT_ID
        return (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={callback_uri}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"access_type=offline&"
            f"prompt=consent"
        )

    async def handle_google_callback(self, code: str, redirect_uri: str | None = None) -> TokenResponse:
        callback_uri = redirect_uri or f"{settings.FRONTEND_URL}/auth/callback"

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google OAuth credentials are not configured on the server."
            )

        # Exchange authorization code for Google tokens
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": callback_uri,
                    "grant_type": "authorization_code",
                },
            )

            if token_resp.status_code != 200:
                logger.error("Google token exchange failed", status_code=token_resp.status_code, body=token_resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to authenticate with Google. Invalid or expired authorization code."
                )

            token_json = token_resp.json()
            access_token = token_json.get("access_token")
            id_token = token_json.get("id_token")

            # Fetch Google user profile
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if userinfo_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve Google user profile."
                )

            google_user = userinfo_resp.json()
            google_id = google_user.get("id")
            email = (google_user.get("email") or "").lower().strip()
            name = google_user.get("name") or "Google User"

            if not email or not google_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google account did not provide a verified email."
                )

        # Find or create user
        stmt = select(User).where((User.email == email) | (User.google_id == google_id))
        user = self.db.execute(stmt).scalar_one_or_none()

        if user:
            # Update google_id and mark email verified if logging in via Google
            if not user.google_id:
                user.google_id = google_id
            user.is_verified = True
            if not user.full_name and name:
                user.full_name = name
            self.db.commit()
            self.db.refresh(user)
        else:
            # Create organization and user
            org = Organization(
                id=uuid.uuid4(),
                name=f"{name}'s Org",
                settings={},
            )
            self.db.add(org)
            self.db.flush()

            user = User(
                id=uuid.uuid4(),
                auth_id=str(uuid.uuid4()),
                organization_id=org.id,
                email=email,
                full_name=name,
                google_id=google_id,
                role=Role.ADMIN,
                is_verified=True,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        # Generate custom JWT
        token_data = {
            "sub": user.auth_id,
            "user_id": str(user.id),
            "organization_id": str(user.organization_id),
            "role": user.role.value,
            "email": user.email,
        }
        app_jwt = create_access_token(token_data)

        return TokenResponse(
            access_token=app_jwt,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
