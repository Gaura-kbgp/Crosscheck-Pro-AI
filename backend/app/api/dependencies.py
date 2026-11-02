from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
        # Auto-provision Supabase user if valid email in payload
        email = payload.get("email")
        if email:
            import uuid
            from app.models.core import Organization, BusinessRole
            user_meta = payload.get("user_metadata", {}) or {}
            full_name = user_meta.get("full_name") or user_meta.get("name") or email.split("@")[0]
            org_name = user_meta.get("organization_name") or f"{full_name}'s Org"
            raw_business_role = user_meta.get("business_role")
            business_role = None
            if raw_business_role:
                try:
                    business_role = BusinessRole(raw_business_role)
                except ValueError:
                    business_role = None

            org = Organization(id=uuid.uuid4(), name=org_name, business_role=business_role, settings={})
            db.add(org)
            db.flush()
            
            user = User(
                id=uuid.uuid4(),
                auth_id=str(auth_id),
                organization_id=org.id,
                email=email.lower().strip(),
                full_name=full_name,
                role=Role.ADMIN,
                is_verified=True,
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                # A brand-new user's first authenticated request is often two
                # concurrent calls (e.g. the frontend fetching the profile and
                # the organization at once) — both see "no user yet" and race
                # to insert. The loser hits auth_id's unique constraint here;
                # instead of crashing with a 500, fall back to the row the
                # winner just created.
                db.rollback()
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
            db.refresh(user)

            # P2-1: pre-checked sample project so the first screen is never
            # empty. Best-effort — a seeding failure must never block login.
            try:
                from app.services.sample_data_service import create_sample_project
                create_sample_project(db, org.id)
            except Exception:
                pass
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found in database"
            )
    else:
        # Keep auth_id synced if matched by email
        if user.auth_id != auth_id:
            user.auth_id = str(auth_id)
            db.commit()
            db.refresh(user)
        
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
