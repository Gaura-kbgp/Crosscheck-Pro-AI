from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic.types import UUID4
from typing import Optional
from app.schemas.user import UserResponse

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)
    confirm_password: Optional[str] = None
    organization_name: Optional[str] = None

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None and "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

class RegisterResponse(BaseModel):
    message: str
    email: str
    user_id: UUID4
    is_verified: bool

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1)

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: Optional[str] = None

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None and "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v

class GoogleCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1)
    redirect_uri: Optional[str] = None

class MessageResponse(BaseModel):
    message: str
