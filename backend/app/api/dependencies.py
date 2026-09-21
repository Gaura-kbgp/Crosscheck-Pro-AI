from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Generator

from app.db.session import SessionLocal
from app.core.security import verify_jwt_token
from app.models.core import User, Role
from app.schemas.user import AuthenticatedUser

security = HTTPBearer()

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AuthenticatedUser:
    token = credentials.credentials
    payload = verify_jwt_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    auth_id = payload.get("sub")
    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier"
        )
    
    stmt = select(User).where((User.auth_id == auth_id) | (User.email == payload.get("email", "")))
    user = db.execute(stmt).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in database"
        )
        
    return AuthenticatedUser(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        auth_id=user.auth_id,
        email=user.email,
        full_name=user.full_name,
    )

class RequireRole:
    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles
        
    def __call__(self, user: AuthenticatedUser = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
