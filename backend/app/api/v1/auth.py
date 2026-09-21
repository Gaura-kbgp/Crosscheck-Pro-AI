from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenResponse,
    VerifyEmailRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    GoogleCallbackRequest,
    MessageResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

auth_limiter = RateLimiter(
    limit=settings.AUTH_RATE_LIMIT,
    window_seconds=settings.AUTH_RATE_WINDOW_SECONDS,
    name="auth"
)

password_reset_limiter = RateLimiter(
    limit=settings.PASSWORD_RESET_RATE_LIMIT,
    window_seconds=settings.PASSWORD_RESET_RATE_WINDOW_SECONDS,
    name="password_reset"
)

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_limiter)])
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.register(request)

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_limiter)])
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.login(request)

@router.post("/verify-email", response_model=MessageResponse, dependencies=[Depends(auth_limiter)])
def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.verify_email(request.token)

@router.post("/resend-verification", response_model=MessageResponse, dependencies=[Depends(auth_limiter)])
def resend_verification(
    request: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.resend_verification(request.email)

@router.post("/forgot-password", response_model=MessageResponse, dependencies=[Depends(password_reset_limiter)])
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.forgot_password(request.email)

@router.post("/reset-password", response_model=MessageResponse, dependencies=[Depends(password_reset_limiter)])
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return service.reset_password(request.token, request.new_password)

@router.get("/google/url")
def get_google_auth_url(
    redirect_uri: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    url = service.get_google_auth_url(redirect_uri)
    return {"url": url}

@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    request: GoogleCallbackRequest,
    db: Session = Depends(get_db)
):
    service = AuthService(db)
    return await service.handle_google_callback(request.code, request.redirect_uri)
