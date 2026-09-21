import uuid
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.core import AuditLog

class AuditService:
    @staticmethod
    def log_action(
        db: Session,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_id: Optional[uuid.UUID] = None,
        previous_state: Optional[dict[str, Any]] = None,
        new_state: Optional[dict[str, Any]] = None,
        metadata_: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> AuditLog:
        """
        Creates an immutable audit log entry. Must be called within an active transaction.
        """
        audit = AuditLog(
            organization_id=organization_id,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_state=previous_state,
            new_state=new_state,
            metadata_=metadata_,
            correlation_id=correlation_id
        )
        db.add(audit)
        # We do not commit here. The caller commits the transaction.
        return audit
