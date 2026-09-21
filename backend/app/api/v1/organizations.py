from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select, func

from app.api.dependencies import get_db, get_current_user, RequireRole
from app.schemas.user import AuthenticatedUser
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest
from app.models.core import Organization, User, Project, Role
from app.core.exceptions import ResourceNotFoundError

router = APIRouter()

@router.get("/me", response_model=OrganizationResponse)
def get_my_organization(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    org = db.execute(stmt).scalar_one_or_none()
    if not org:
        raise ResourceNotFoundError("Organization not found")
        
    # Get user count & project count for this organization
    user_count = db.execute(
        select(func.count()).select_from(User).where(User.organization_id == org.id)
    ).scalar() or 1
    
    project_count = db.execute(
        select(func.count()).select_from(Project).where(Project.organization_id == org.id)
    ).scalar() or 0
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        settings=org.settings or {},
        created_at=org.created_at,
        updated_at=org.updated_at,
        user_count=user_count,
        project_count=project_count,
    )

@router.patch("/me", response_model=OrganizationResponse)
def update_my_organization(
    request: OrganizationUpdateRequest,
    current_user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db)
):
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    org = db.execute(stmt).scalar_one_or_none()
    if not org:
        raise ResourceNotFoundError("Organization not found")
        
    if request.name is not None and request.name.strip():
        org.name = request.name.strip()
        
    if request.settings is not None:
        current_settings = dict(org.settings or {})
        current_settings.update(request.settings)
        org.settings = current_settings
        flag_modified(org, "settings")
        
    db.commit()
    db.refresh(org)
    
    user_count = db.execute(
        select(func.count()).select_from(User).where(User.organization_id == org.id)
    ).scalar() or 1
    
    project_count = db.execute(
        select(func.count()).select_from(Project).where(Project.organization_id == org.id)
    ).scalar() or 0
    
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        settings=org.settings or {},
        created_at=org.created_at,
        updated_at=org.updated_at,
        user_count=user_count,
        project_count=project_count,
    )
