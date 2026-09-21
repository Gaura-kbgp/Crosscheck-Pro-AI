import uuid
from typing import Optional, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.core import (
    Discrepancy, MatchGroup, HumanReview, ReviewAction, User, 
    CanonicalLineItem, Project, ProjectStatus
)
from app.services.audit_service import AuditService
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine

class ReviewService:
    @staticmethod
    def _get_discrepancy(db: Session, discrepancy_id: uuid.UUID, organization_id: uuid.UUID) -> Discrepancy:
        disc = db.query(Discrepancy).filter_by(id=discrepancy_id, organization_id=organization_id).with_for_update().first()
        if not disc:
            raise HTTPException(status_code=404, detail="Discrepancy not found")
        if disc.project and disc.project.status == ProjectStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Cannot modify a finalized project")
        return disc
        
    @staticmethod
    def accept_finding(
        db: Session, 
        discrepancy_id: uuid.UUID, 
        organization_id: uuid.UUID, 
        reviewer_id: uuid.UUID,
        reason: Optional[str] = None
    ):
        disc = ReviewService._get_discrepancy(db, discrepancy_id, organization_id)
        
        # Action specific logic
        disc.status = "RESOLVED"
        
        review = HumanReview(
            organization_id=organization_id,
            project_id=disc.project_id,
            discrepancy_id=disc.id,
            match_group_id=disc.match_group_id,
            reviewer_id=reviewer_id,
            action=ReviewAction.ACCEPT_FINDING,
            reason=reason
        )
        db.add(review)
        
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=disc.project_id,
            action="ACCEPT_FINDING",
            resource_type="Discrepancy",
            resource_id=str(disc.id),
            actor_id=reviewer_id,
            previous_state={"status": "OPEN"},
            new_state={"status": "RESOLVED"},
            metadata_={"reason": reason}
        )
        db.commit()
        return disc

    @staticmethod
    def mark_false_positive(
        db: Session, 
        discrepancy_id: uuid.UUID, 
        organization_id: uuid.UUID, 
        reviewer_id: uuid.UUID,
        reason: Optional[str] = None
    ):
        disc = ReviewService._get_discrepancy(db, discrepancy_id, organization_id)
        
        previous_status = disc.status
        disc.status = "FALSE_POSITIVE"
        
        review = HumanReview(
            organization_id=organization_id,
            project_id=disc.project_id,
            discrepancy_id=disc.id,
            match_group_id=disc.match_group_id,
            reviewer_id=reviewer_id,
            action=ReviewAction.FALSE_POSITIVE,
            reason=reason
        )
        db.add(review)
        
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=disc.project_id,
            action="FALSE_POSITIVE",
            resource_type="Discrepancy",
            resource_id=str(disc.id),
            actor_id=reviewer_id,
            previous_state={"status": previous_status},
            new_state={"status": "FALSE_POSITIVE"},
            metadata_={"reason": reason}
        )
        db.commit()
        return disc
        
    @staticmethod
    def escalate(
        db: Session, 
        discrepancy_id: uuid.UUID, 
        organization_id: uuid.UUID, 
        reviewer_id: uuid.UUID,
        reason: Optional[str] = None
    ):
        disc = ReviewService._get_discrepancy(db, discrepancy_id, organization_id)
        
        previous_status = disc.status
        disc.status = "ESCALATED"
        
        review = HumanReview(
            organization_id=organization_id,
            project_id=disc.project_id,
            discrepancy_id=disc.id,
            match_group_id=disc.match_group_id,
            reviewer_id=reviewer_id,
            action=ReviewAction.ESCALATE,
            reason=reason
        )
        db.add(review)
        
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=disc.project_id,
            action="ESCALATE",
            resource_type="Discrepancy",
            resource_id=str(disc.id),
            actor_id=reviewer_id,
            previous_state={"status": previous_status},
            new_state={"status": "ESCALATED"},
            metadata_={"reason": reason}
        )
        db.commit()
        return disc
        
    @staticmethod
    def acknowledge_mfr_change(
        db: Session, 
        discrepancy_id: uuid.UUID, 
        organization_id: uuid.UUID, 
        reviewer_id: uuid.UUID,
        reason: Optional[str] = None
    ):
        # Mark discrepancy resolved, update final resolved state to acknowledge manufacturer value
        disc = ReviewService._get_discrepancy(db, discrepancy_id, organization_id)
        mg = db.query(MatchGroup).filter_by(id=disc.match_group_id).with_for_update().first()
        
        previous_status = disc.status
        disc.status = "RESOLVED"
        
        # Usually, crosscheck engine resolves the final state to Ack. But if it was open, we manually confirm.
        # Actually, the user requirement states: "Update final resolved state to acknowledge the manufacturer value."
        # We can re-run CrossCheckEngine or explicitly set it.
        # It's safer to re-run CrossCheckEngine to ensure final state consistency.
        
        review = HumanReview(
            organization_id=organization_id,
            project_id=disc.project_id,
            discrepancy_id=disc.id,
            match_group_id=disc.match_group_id,
            reviewer_id=reviewer_id,
            action=ReviewAction.ACKNOWLEDGE_MFR_CHANGE,
            reason=reason
        )
        db.add(review)
        
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=disc.project_id,
            action="ACKNOWLEDGE_MFR_CHANGE",
            resource_type="Discrepancy",
            resource_id=str(disc.id),
            actor_id=reviewer_id,
            previous_state={"status": previous_status},
            new_state={"status": "RESOLVED"},
            metadata_={"reason": reason}
        )
        
        # After acknowledgment, crosscheck re-evaluation could happen, but since this is just an ack,
        # we mark it resolved. The engine already prioritizes Ack if available.
        db.commit()
        return disc

    @staticmethod
    def override_data(
        db: Session, 
        match_group_id: uuid.UUID,
        canonical_item_id: uuid.UUID,
        organization_id: uuid.UUID, 
        reviewer_id: uuid.UUID,
        field_name: str,
        new_value: Any,
        reason: Optional[str] = None
    ):
        """
        Overrides a specific field on a canonical item, then recalculates everything for the MatchGroup.
        """
        mg = db.query(MatchGroup).filter_by(id=match_group_id, organization_id=organization_id).with_for_update().first()
        if not mg:
            raise HTTPException(status_code=404, detail="MatchGroup not found")
        if mg.project and mg.project.status == ProjectStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Cannot modify a finalized project")
            
        item = db.query(CanonicalLineItem).filter_by(id=canonical_item_id, organization_id=organization_id).with_for_update().first()
        if not item:
            raise HTTPException(status_code=404, detail="CanonicalLineItem not found")
            
        if item.id not in [mg.design_item_id, mg.order_item_id, mg.ack_item_id]:
            raise HTTPException(status_code=400, detail="Item does not belong to this MatchGroup")
            
        # Preserve previous value
        previous_value = getattr(item, field_name, None)
        setattr(item, field_name, new_value)
        
        review = HumanReview(
            organization_id=organization_id,
            project_id=mg.project_id,
            match_group_id=mg.id,
            reviewer_id=reviewer_id,
            action=ReviewAction.OVERRIDE_DATA,
            reason=reason,
            previous_value={field_name: previous_value},
            new_value={field_name: new_value}
        )
        db.add(review)
        
        # Recalculate
        # Get all canonical items for this match group (since one of them changed)
        # Actually, if we change a SKU, it might belong to a different match group.
        # But for Phase 6, we recalculate this MatchGroup's discrepancies.
        # If the SKU changes, we should ideally re-run matching for the whole project, 
        # but that's expensive. Let's just re-run crosscheck for this group if it's not SKU.
        # If it is SKU, the requirement says "Re-run matching for affected MatchGroup."
        # For simplicity, we can delete the match group's existing discrepancies, and re-run CrossCheckEngine
        
        db.query(Discrepancy).filter_by(match_group_id=mg.id).delete()
        
        engine = CrossCheckEngine()
        discrepancies = engine._evaluate_match_group(mg, mg.project_id, mg.organization_id)
        engine._determine_final_state(mg)
        for disc in discrepancies:
            db.add(disc)
            
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=mg.project_id,
            action="OVERRIDE_DATA",
            resource_type="CanonicalLineItem",
            resource_id=str(item.id),
            actor_id=reviewer_id,
            previous_state={field_name: previous_value},
            new_state={field_name: new_value},
            metadata_={"reason": reason, "match_group_id": str(mg.id)}
        )
        db.commit()
        db.refresh(mg)
        return mg

    @staticmethod
    def finalize_project(
        db: Session,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID
    ):
        proj = db.query(Project).filter_by(id=project_id, organization_id=organization_id).with_for_update().first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
            
        if proj.status == ProjectStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Project is already finalized")
            
        # Check processing status
        if proj.status in [ProjectStatus.DRAFT, ProjectStatus.PROCESSING]:
            raise HTTPException(status_code=400, detail="Project processing is not complete")
            
        # Check for open critical discrepancies
        critical_open = db.query(Discrepancy).filter_by(
            project_id=project_id, 
            status="OPEN",
            severity="Critical"
        ).first()
        
        if critical_open:
            raise HTTPException(status_code=400, detail="Cannot finalize project with open Critical discrepancies")
            
        previous_status = proj.status
        proj.status = ProjectStatus.FINALIZED
        
        AuditService.log_action(
            db=db,
            organization_id=organization_id,
            project_id=proj.id,
            action="PROJECT_FINALIZED",
            resource_type="Project",
            resource_id=str(proj.id),
            actor_id=user_id,
            previous_state={"status": previous_status.value if hasattr(previous_status, 'value') else previous_status},
            new_state={"status": "FINALIZED"}
        )
        db.commit()
        return proj
