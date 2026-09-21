from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from typing import List, Optional
import uuid

from app.models.core import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id_and_org(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[Project]:
        stmt = (
            select(Project)
            .options(selectinload(Project.documents))
            .where(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_org(self, organization_id: uuid.UUID) -> List[Project]:
        stmt = (
            select(Project)
            .options(selectinload(Project.documents))
            .where(Project.organization_id == organization_id)
            .order_by(Project.updated_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, organization_id: uuid.UUID, project_in: ProjectCreate) -> Project:
        project = Project(
            organization_id=organization_id,
            **project_in.model_dump()
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, project: Project, update_in: ProjectUpdate) -> Project:
        update_data = update_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        self.db.commit()
        self.db.refresh(project)
        return project
        
    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()
