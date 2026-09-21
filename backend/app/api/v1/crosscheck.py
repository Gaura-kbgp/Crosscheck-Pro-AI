from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional, Any, Dict
from uuid import UUID
from app.api.dependencies import get_db, get_current_user
from app.models.core import User, MatchGroup, Discrepancy, MatchGroupStatus, Severity
from app.services.crosscheck_service import CrossCheckService
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

from app.schemas.extraction import CanonicalLineItemResponse

# Schema Definitions
class DiscrepancyResponse(BaseModel):
    id: UUID
    match_group_id: UUID
    field: str
    source_values: Optional[Any] = None
    comparison_values: Optional[Any] = None
    introduced_at: Optional[str] = None
    status: str
    severity: Severity
    explanation: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class MatchGroupResponse(BaseModel):
    id: UUID
    project_id: UUID
    status: MatchGroupStatus
    design_item_id: Optional[UUID] = None
    order_item_id: Optional[UUID] = None
    ack_item_id: Optional[UUID] = None
    design_item: Optional[CanonicalLineItemResponse] = None
    order_item: Optional[CanonicalLineItemResponse] = None
    ack_item: Optional[CanonicalLineItemResponse] = None
    final_sku: Optional[str] = None
    final_quantity: Optional[int] = None
    final_dimensions: Optional[Any] = None
    final_finish: Optional[str] = None
    final_door_style: Optional[str] = None
    final_modifications: Optional[Any] = None
    final_price: Optional[str] = None
    final_status: Optional[str] = None
    discrepancies: Optional[List[DiscrepancyResponse]] = []
    created_at: datetime
    
    class Config:
        from_attributes = True

class CrossCheckResponse(BaseModel):
    match_groups: List[MatchGroupResponse]
    discrepancies: List[DiscrepancyResponse]

@router.get("/projects/{project_id}/crosscheck", response_model=CrossCheckResponse)
def get_crosscheck(
    project_id: UUID,
    severity: Optional[str] = Query(None),
    match_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.core import Project
    from sqlalchemy.orm import selectinload
    project = db.scalars(select(Project).where(Project.id == project_id, Project.organization_id == current_user.organization_id)).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch Match Groups with relationships eagerly loaded
    mg_query = (
        select(MatchGroup)
        .where(
            MatchGroup.project_id == project_id,
            MatchGroup.organization_id == current_user.organization_id
        )
        .options(
            selectinload(MatchGroup.discrepancies),
            selectinload(MatchGroup.design_item),
            selectinload(MatchGroup.order_item),
            selectinload(MatchGroup.ack_item)
        )
    )
    if match_status and isinstance(match_status, str):
        try:
            status_enum = MatchGroupStatus(match_status)
            mg_query = mg_query.where(MatchGroup.status == status_enum)
        except ValueError:
            pass

    match_groups = db.scalars(mg_query).all()

    # Fetch Discrepancies
    d_query = select(Discrepancy).where(
        Discrepancy.project_id == project_id,
        Discrepancy.organization_id == current_user.organization_id
    )
    if severity and isinstance(severity, str):
        try:
            sev_enum = Severity(severity)
            d_query = d_query.where(Discrepancy.severity == sev_enum)
        except ValueError:
            pass

    discrepancies = db.scalars(d_query).all()

    return {
        "match_groups": match_groups,
        "discrepancies": discrepancies
    }

@router.get("/projects/{project_id}/match-groups", response_model=List[MatchGroupResponse])
def get_match_groups(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    match_groups = db.scalars(
        select(MatchGroup).where(
            MatchGroup.project_id == project_id,
            MatchGroup.organization_id == current_user.organization_id
        )
    ).all()
    return match_groups

@router.get("/match-groups/{match_group_id}", response_model=MatchGroupResponse)
def get_match_group(
    match_group_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    mg = db.scalars(
        select(MatchGroup).where(
            MatchGroup.id == match_group_id,
            MatchGroup.organization_id == current_user.organization_id
        )
    ).first()
    if not mg:
        raise HTTPException(status_code=404, detail="MatchGroup not found")
    return mg

@router.post("/projects/{project_id}/crosscheck/run")
def run_crosscheck(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify project
    service = CrossCheckService(db)
    result = service.process_project(project_id, current_user.organization_id)
    return {"message": "CrossCheck completed successfully", "data": result}
