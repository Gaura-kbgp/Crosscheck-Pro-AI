from pydantic import BaseModel, ConfigDict
from pydantic.types import UUID4
from typing import Optional
from datetime import datetime
from app.models.core import Role

class UserResponse(BaseModel):
    id: UUID4
    auth_id: str
    organization_id: UUID4
    email: str
    full_name: Optional[str] = None
    role: Role
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuthenticatedUser(BaseModel):
    user_id: UUID4
    organization_id: UUID4
    role: Role
    auth_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str
