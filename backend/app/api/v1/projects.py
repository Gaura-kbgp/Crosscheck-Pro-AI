from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
import uuid
from typing import List

from app.api.dependencies import get_db, get_current_user, RequireRole
from app.schemas.user import AuthenticatedUser
from app.schemas.project import ProjectResponse, ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService
from app.models.core import Role

router = APIRouter()

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN, Role.REVIEWER])),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    return service.create_project(user.organization_id, project_in)

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    return service.list_projects(user.organization_id)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    return service.get_project(project_id, user.organization_id)

@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN, Role.REVIEWER])),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    return service.update_project(project_id, user.organization_id, project_in)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    user: AuthenticatedUser = Depends(RequireRole([Role.ADMIN])),
    db: Session = Depends(get_db)
):
    service = ProjectService(db)
    service.delete_project(project_id, user.organization_id)
