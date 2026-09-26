import uuid
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case
from app.core.exceptions import ResourceNotFoundError

from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.models.core import Project, Discrepancy, ProjectStatus
from app.services.manufacturer_service import ManufacturerService

class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjectRepository(db)

    def _assert_manufacturer_visible(self, manufacturer_id: Optional[uuid.UUID], organization_id: uuid.UUID) -> None:
        """A project's manufacturer_id must be a manufacturer this org can
        actually see (global, or its own) — otherwise a project could be
        linked to another organization's PRIVATE manufacturer dictionary by
        guessing its id, leaking that dictionary into this org's Cabinet
        Code Intelligence classification results. Raises ResourceNotFoundError
        (404, never 403) if not visible, so the id's existence is never
        confirmed to an org that can't see it."""
        if manufacturer_id is None:
            return
        ManufacturerService(self.db)._get_visible(manufacturer_id, organization_id)

    def _enrich_single_project(self, project: Project) -> ProjectResponse:
        docs = project.documents or []
        doc_types = [
            d.document_type.value if hasattr(d.document_type, "value") else str(d.document_type)
            for d in docs
        ]
        doc_count = len(docs)

        disc_stmt = select(
            func.count(Discrepancy.id).label("total"),
            func.count(case((Discrepancy.status != "OPEN", 1))).label("resolved"),
        ).where(Discrepancy.project_id == project.id)
        disc_row = self.db.execute(disc_stmt).first()
        total_disc = disc_row[0] if disc_row else 0
        resolved_disc = disc_row[1] if disc_row else 0

        status_str = (
            project.status.value
            if hasattr(project.status, "value")
            else str(project.status)
        )
        if status_str in ("FINALIZED", "COMPLETED"):
            progress_pct = 100
        elif status_str == "PROCESSING":
            progress_pct = 70
        elif status_str == "REVIEW_REQUIRED":
            if total_disc > 0:
                progress_pct = 70 + int((resolved_disc / total_disc) * 30)
            else:
                progress_pct = 90
        elif status_str == "FAILED":
            progress_pct = 25
        else:  # DRAFT
            if doc_count == 0:
                progress_pct = 0
            elif doc_count == 1:
                progress_pct = 33
            elif doc_count == 2:
                progress_pct = 66
            else:
                progress_pct = 100

        return ProjectResponse(
            id=project.id,
            organization_id=project.organization_id,
            name=project.name,
            customer_name=project.customer_name,
            dealer_name=project.dealer_name,
            manufacturer_id=project.manufacturer_id,
            manufacturer_name=project.manufacturer.name if project.manufacturer else None,
            status=project.status,
            document_count=doc_count,
            uploaded_document_types=doc_types,
            discrepancy_count=total_disc,
            resolved_discrepancy_count=resolved_disc,
            progress_percentage=progress_pct,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def get_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> ProjectResponse:
        project = self.repository.get_by_id_and_org(project_id, organization_id)
        if not project:
            raise ResourceNotFoundError(message="Project not found")
        return self._enrich_single_project(project)

    def list_projects(self, organization_id: uuid.UUID) -> List[ProjectResponse]:
        projects = self.repository.list_by_org(organization_id)
        if not projects:
            return []

        project_ids = [p.id for p in projects]
        disc_stmt = (
            select(
                Discrepancy.project_id,
                func.count(Discrepancy.id).label("total"),
                func.count(case((Discrepancy.status != "OPEN", 1))).label("resolved"),
            )
            .where(Discrepancy.project_id.in_(project_ids))
            .group_by(Discrepancy.project_id)
        )
        disc_map: Dict[uuid.UUID, Tuple[int, int]] = {
            row[0]: (row[1], row[2]) for row in self.db.execute(disc_stmt).all()
        }

        results: List[ProjectResponse] = []
        for p in projects:
            docs = p.documents or []
            doc_types = [
                d.document_type.value if hasattr(d.document_type, "value") else str(d.document_type)
                for d in docs
            ]
            doc_count = len(docs)
            total_disc, resolved_disc = disc_map.get(p.id, (0, 0))

            status_str = (
                p.status.value if hasattr(p.status, "value") else str(p.status)
            )
            if status_str in ("FINALIZED", "COMPLETED"):
                progress_pct = 100
            elif status_str == "PROCESSING":
                progress_pct = 70
            elif status_str == "REVIEW_REQUIRED":
                if total_disc > 0:
                    progress_pct = 70 + int((resolved_disc / total_disc) * 30)
                else:
                    progress_pct = 90
            elif status_str == "FAILED":
                progress_pct = 25
            else:  # DRAFT
                if doc_count == 0:
                    progress_pct = 0
                elif doc_count == 1:
                    progress_pct = 33
                elif doc_count == 2:
                    progress_pct = 66
                else:
                    progress_pct = 100

            results.append(
                ProjectResponse(
                    id=p.id,
                    organization_id=p.organization_id,
                    name=p.name,
                    customer_name=p.customer_name,
                    dealer_name=p.dealer_name,
                    manufacturer_id=p.manufacturer_id,
                    manufacturer_name=p.manufacturer.name if p.manufacturer else None,
                    status=p.status,
                    document_count=doc_count,
                    uploaded_document_types=doc_types,
                    discrepancy_count=total_disc,
                    resolved_discrepancy_count=resolved_disc,
                    progress_percentage=progress_pct,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
        return results

    def create_project(self, organization_id: uuid.UUID, project_in: ProjectCreate) -> ProjectResponse:
        self._assert_manufacturer_visible(project_in.manufacturer_id, organization_id)
        project = self.repository.create(organization_id, project_in)
        return self._enrich_single_project(project)

    def update_project(self, project_id: uuid.UUID, organization_id: uuid.UUID, update_in: ProjectUpdate) -> ProjectResponse:
        project = self.repository.get_by_id_and_org(project_id, organization_id)
        if not project:
            raise ResourceNotFoundError(message="Project not found")
        if "manufacturer_id" in update_in.model_fields_set:
            self._assert_manufacturer_visible(update_in.manufacturer_id, organization_id)
        updated = self.repository.update(project, update_in)
        return self._enrich_single_project(updated)

    def delete_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        project = self.repository.get_by_id_and_org(project_id, organization_id)
        if not project:
            raise ResourceNotFoundError(message="Project not found")
        self.repository.delete(project)

