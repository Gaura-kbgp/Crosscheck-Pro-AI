import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_user, RequireRole
from app.models.core import User, Role, AuditLog
from app.services.review_service import ReviewService
from app.schemas.review import ReviewActionRequest, DiscrepancyResponse, MatchGroupResponse, AuditLogResponse
from app.schemas.project import ProjectResponse

router = APIRouter()

@router.post("/discrepancies/{discrepancy_id}/review")
def review_discrepancy(
    discrepancy_id: uuid.UUID,
    request: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([Role.ADMIN, Role.REVIEWER]))
):
    """
    Perform a review action on a discrepancy or data.
    Supported actions: ACCEPT_FINDING, FALSE_POSITIVE, ESCALATE, ACKNOWLEDGE_MFR_CHANGE, OVERRIDE_DATA
    """
    if request.action == "ACCEPT_FINDING":
        res = ReviewService.accept_finding(
            db, discrepancy_id, current_user.organization_id, current_user.user_id, request.reason
        )
        return {"status": "success", "discrepancy_id": str(res.id), "new_status": res.status}
    elif request.action == "FALSE_POSITIVE":
        res = ReviewService.mark_false_positive(
            db, discrepancy_id, current_user.organization_id, current_user.user_id, request.reason
        )
        return {"status": "success", "discrepancy_id": str(res.id), "new_status": res.status}
    elif request.action == "ESCALATE":
        res = ReviewService.escalate(
            db, discrepancy_id, current_user.organization_id, current_user.user_id, request.reason
        )
        return {"status": "success", "discrepancy_id": str(res.id), "new_status": res.status}
    elif request.action == "ACKNOWLEDGE_MFR_CHANGE":
        res = ReviewService.acknowledge_mfr_change(
            db, discrepancy_id, current_user.organization_id, current_user.user_id, request.reason
        )
        return {"status": "success", "discrepancy_id": str(res.id), "new_status": res.status}
    elif request.action == "OVERRIDE_DATA":
        if not request.match_group_id or not request.canonical_item_id or not request.field_name:
            raise HTTPException(status_code=400, detail="Missing fields for OVERRIDE_DATA")
        res = ReviewService.override_data(
            db=db,
            match_group_id=request.match_group_id,
            canonical_item_id=request.canonical_item_id,
            organization_id=current_user.organization_id,
            reviewer_id=current_user.user_id,
            field_name=request.field_name,
            new_value=request.new_value,
            reason=request.reason
        )
        return {"status": "success", "match_group_id": str(res.id)}
    else:
        raise HTTPException(status_code=400, detail="Invalid review action")

@router.post("/projects/{project_id}/finalize", response_model=ProjectResponse)
def finalize_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([Role.ADMIN, Role.REVIEWER]))
):
    """
    Finalize a project.
    """
    return ReviewService.finalize_project(
        db=db,
        project_id=project_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id
    )

@router.get("/projects/{project_id}/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    project_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole([Role.ADMIN, Role.REVIEWER, Role.VIEWER]))
):
    """
    Retrieve audit logs for a project.
    """
    logs = db.query(AuditLog).filter_by(
        project_id=project_id,
        organization_id=current_user.organization_id
    ).order_by(AuditLog.created_at.asc()).offset(offset).limit(limit).all()
    
    return logs
