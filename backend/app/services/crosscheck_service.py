from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.models.core import CanonicalLineItem, MatchGroup, Discrepancy, MatchGroupStatus
from app.engines.matching import MatchingEngine
from app.engines.crosscheck import CrossCheckEngine
from uuid import UUID

class CrossCheckService:
    def __init__(self, db: Session):
        self.db = db
        self.matching_engine = MatchingEngine(fuzzy_threshold=0.7)
        self.crosscheck_engine = CrossCheckEngine()

    def process_project(self, project_id: UUID, organization_id: UUID):
        # 1. Idempotency: Clear existing Discrepancies and MatchGroups
        self.db.execute(
            delete(Discrepancy)
            .where(Discrepancy.project_id == project_id)
            .where(Discrepancy.organization_id == organization_id)
        )
        self.db.execute(
            delete(MatchGroup)
            .where(MatchGroup.project_id == project_id)
            .where(MatchGroup.organization_id == organization_id)
        )
        self.db.commit()

        # 2. Fetch all CanonicalLineItems for the project
        items = self.db.scalars(
            select(CanonicalLineItem)
            .where(CanonicalLineItem.project_id == project_id)
            .where(CanonicalLineItem.organization_id == organization_id)
        ).all()
        
        design_items = [i for i in items if i.source_type.name == "DESIGN"]
        order_items = [i for i in items if i.source_type.name == "ORDER"]
        ack_items = [i for i in items if i.source_type.name == "ACKNOWLEDGEMENT"]

        # 3. Matching
        match_groups = self.matching_engine.match_items(
            design_items, order_items, ack_items, project_id, organization_id
        )

        # 4. CrossCheck
        discrepancies = self.crosscheck_engine.evaluate(match_groups, project_id, organization_id)
        
        # 5. Update MatchGroup Status if discrepancies exist and it was MATCHED
        mg_discrepancy_map = {}
        for d in discrepancies:
            mg_discrepancy_map.setdefault(d.match_group_id, []).append(d)
            
        for mg in match_groups:
            if mg.id in mg_discrepancy_map and mg.status == MatchGroupStatus.MATCHED:
                mg.status = MatchGroupStatus.CHANGED

        # 6. Persist
        self.db.add_all(match_groups)
        self.db.add_all(discrepancies)
        self.db.commit()
        
        return {
            "match_groups_count": len(match_groups),
            "discrepancies_count": len(discrepancies)
        }
