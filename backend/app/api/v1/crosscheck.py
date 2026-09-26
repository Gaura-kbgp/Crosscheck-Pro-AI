from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional, Any, Dict
from uuid import UUID
from app.api.dependencies import get_db, get_current_user
from app.models.core import User, MatchGroup, Discrepancy, MatchGroupStatus, Severity
from app.services.crosscheck_service import CrossCheckService
from pydantic import BaseModel, computed_field, field_serializer
from datetime import datetime

router = APIRouter()

from app.schemas.extraction import CanonicalLineItemResponse

# Schema Definitions
class DiscrepancyResponse(BaseModel):
    """
    The single canonical presentation of a Discrepancy record: every derived
    field below (design/order/ack values, severity) is computed once, here,
    from the same source_values/introduced_at/severity the crosscheck engine
    wrote — so every consumer (Human Review, Cross-Check Matrix, filters,
    summary counts) renders identical state. introduced_at itself is not
    re-derived here: the engine (app/engines/crosscheck.py) now computes it
    deterministically from the 3-way Design -> Order -> Ack presence state,
    so the stored value is already presentation-correct.
    """
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

    def _source_get(self, key: str) -> Optional[Any]:
        if isinstance(self.source_values, dict):
            return self.source_values.get(key)
        return None

    @field_serializer("severity")
    def _serialize_severity(self, value: Severity, _info) -> str:
        # Severity is stored Title Case ("Critical"/"Warning"/"Info"); every
        # frontend comparison (filters, summary counters, badge colors)
        # expects upper case, so normalize once at the boundary.
        raw = value.value if hasattr(value, "value") else str(value)
        return raw.upper()

    @computed_field
    @property
    def field_name(self) -> str:
        return self.field

    @computed_field
    @property
    def design_value(self) -> Optional[Any]:
        return self._source_get("design")

    @computed_field
    @property
    def order_value(self) -> Optional[Any]:
        return self._source_get("order")

    @computed_field
    @property
    def ack_value(self) -> Optional[Any]:
        # The engine keys the acknowledgement source as "acknowledgement",
        # never "ack" or "ACKNOWLEDGEMENT" — matching that exactly is what
        # makes this show a real PRESENT/ABSENT/value instead of always "—".
        return self._source_get("acknowledgement")

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

class DiscrepancySummary(BaseModel):
    """
    Single source of truth for the Human Review summary counters. Computed
    here from the exact same (unfiltered) discrepancy dataset used to build
    `discrepancies` below, using the exact same status/severity strings
    DiscrepancyResponse serializes — so open == critical + high + warning +
    info always holds, and the frontend never re-derives these counts.
    """
    open: int
    escalated: int
    reviewed: int
    critical: int
    high: int
    warning: int
    info: int

class CrossCheckResponse(BaseModel):
    match_groups: List[MatchGroupResponse]
    discrepancies: List[DiscrepancyResponse]
    discrepancy_summary: DiscrepancySummary

_REVIEWED_STATUSES = {"ACCEPTED", "FALSE_POSITIVE", "ACKNOWLEDGED"}

def compute_discrepancy_summary(discrepancies) -> DiscrepancySummary:
    """
    Pure aggregation over a Discrepancy list: same status/severity semantics
    every other consumer (filters, badges, ReviewStatus type) uses. Kept as a
    standalone function so it has one implementation, testable in isolation.
    """
    return DiscrepancySummary(
        open=sum(1 for d in discrepancies if d.status == "OPEN"),
        escalated=sum(1 for d in discrepancies if d.status == "ESCALATED"),
        reviewed=sum(1 for d in discrepancies if d.status in _REVIEWED_STATUSES),
        critical=sum(1 for d in discrepancies if d.severity == Severity.CRITICAL),
        high=0,  # no discrepancy currently carries HIGH severity; kept for UI symmetry
        warning=sum(1 for d in discrepancies if d.severity == Severity.WARNING),
        info=sum(1 for d in discrepancies if d.severity == Severity.INFO),
    )

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

    # The summary always reflects every finding for the project — independent
    # of the optional `severity` filter above — so it never disagrees with
    # itself when a filter narrows the `discrepancies` list.
    all_discrepancies = db.scalars(
        select(Discrepancy).where(
            Discrepancy.project_id == project_id,
            Discrepancy.organization_id == current_user.organization_id
        )
    ).all()
    summary = compute_discrepancy_summary(all_discrepancies)

    return {
        "match_groups": match_groups,
        "discrepancies": discrepancies,
        "discrepancy_summary": summary
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
