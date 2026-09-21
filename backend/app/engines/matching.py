from typing import List, Dict, Optional, Tuple, Set, Any
from uuid import uuid4, UUID

from app.models.core import CanonicalLineItem, MatchGroup, MatchGroupStatus, DocumentType, ItemCategory
from app.engines.normalization import (
    normalize_sku,
    normalize_text,
    are_skus_equivalent,
    are_dimensions_equivalent,
    parse_and_normalize_dimensions,
    check_canonical_equivalence
)


class CanonicalMatchingUnit:
    """
    Encapsulates a document-level aggregated purchasing entity.
    Maintains full traceability back to raw CanonicalLineItem records.
    """
    def __init__(self, raw_items: List[CanonicalLineItem]):
        self.raw_items = raw_items
        self.primary_item = raw_items[0]
        self.id = self.primary_item.id
        self.sku = normalize_sku(self.primary_item.raw_sku or self.primary_item.normalized_sku)
        raw_cat = getattr(self.primary_item, "item_category", None)
        if not raw_cat or raw_cat == ItemCategory.UNKNOWN:
            from app.engines.classification import ItemClassifier
            classifier = ItemClassifier()
            res = classifier.classify(
                raw_sku=self.primary_item.raw_sku,
                description=self.primary_item.description,
                dimensions=self.primary_item.dimensions
            )
            self.category = res.category
            self.primary_item.item_category = res.category
        else:
            self.category = raw_cat
        
        # Calculate aggregate quantity across all identical line items in the document
        total_qty = 0
        has_qty = False
        for item in raw_items:
            if item.quantity is not None:
                has_qty = True
                total_qty += item.quantity
        self.aggregate_quantity = total_qty if has_qty else None
        
        # Attach aggregate info to primary item non-destructively for downstream engines
        self.primary_item.aggregate_quantity = self.aggregate_quantity
        if not self.primary_item.source_metadata:
            self.primary_item.source_metadata = {}
        if isinstance(self.primary_item.source_metadata, dict):
            self.primary_item.source_metadata["aggregate_quantity"] = self.aggregate_quantity
            self.primary_item.source_metadata["raw_line_count"] = len(raw_items)
            self.primary_item.source_metadata["raw_line_ids"] = [str(i.id) for i in raw_items]
            self.primary_item.source_metadata["raw_quantities"] = [i.quantity for i in raw_items]

        # Merge descriptions, dimensions, finishes from raw lines if primary was incomplete
        self.description = self.primary_item.description
        self.dimensions = self.primary_item.dimensions
        self.finish = self.primary_item.finish
        self.door_style = self.primary_item.door_style
        self.modifications = self.primary_item.modifications
        self.substitution_sku = getattr(self.primary_item, "substitution_sku", None)

        for item in raw_items[1:]:
            if not self.description and item.description:
                self.description = item.description
            if not self.dimensions and item.dimensions:
                self.dimensions = item.dimensions
            if not self.finish and item.finish:
                self.finish = item.finish
            if not self.door_style and item.door_style:
                self.door_style = item.door_style
            if not self.substitution_sku and getattr(item, "substitution_sku", None):
                self.substitution_sku = item.substitution_sku


def aggregate_document_items(items: List[CanonicalLineItem]) -> List[CanonicalMatchingUnit]:
    """
    Groups identical normalized SKUs within the SAME document into CanonicalMatchingUnits.
    Does NOT aggregate different variants (e.g. BT18-2-L vs BT18-2-R).
    Preserves all raw items without loss.
    """
    groups: Dict[str, List[CanonicalLineItem]] = {}
    
    for item in items:
        norm_sku = normalize_sku(item.raw_sku or item.normalized_sku)
        if not norm_sku:
            # Items without SKU are kept as independent units
            groups[f"UNNAMED_{item.id}"] = [item]
            continue
        
        # Create group key incorporating finish/door_style if explicitly specified to protect variant integrity
        fin = normalize_text(item.finish or "") or ""
        door = normalize_text(item.door_style or "") or ""
        group_key = f"{norm_sku}__FIN_{fin}__DOOR_{door}"
        
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(item)

    units: List[CanonicalMatchingUnit] = []
    for raw_group in groups.values():
        units.append(CanonicalMatchingUnit(raw_group))
    return units


class MatchingEngine:
    """
    Production-grade multi-tier deterministic matching engine.
    Prioritizes correctness > precision > recall.
    Abstains to UNCERTAIN on ambiguity.
    """

    def __init__(self, fuzzy_threshold: float = 0.7, **kwargs):
        self.fuzzy_threshold = fuzzy_threshold

    def match_items(
        self,
        design_items: List[CanonicalLineItem],
        order_items: List[CanonicalLineItem],
        ack_items: List[CanonicalLineItem],
        project_id: UUID,
        organization_id: UUID
    ) -> List[MatchGroup]:
        
        # 1. Pre-Matching Document-Level Aggregation into Canonical Matching Units
        design_units = aggregate_document_items(design_items)
        order_units = aggregate_document_items(order_items)
        ack_units = aggregate_document_items(ack_items)

        match_groups: List[MatchGroup] = []
        
        # Track consumed matching units for strict 1-to-1 matching
        consumed_design: Set[UUID] = set()
        consumed_order: Set[UUID] = set()
        consumed_ack: Set[UUID] = set()

        # -------------------------------------------------------------
        # Helper: Create match group and mark units consumed
        # -------------------------------------------------------------
        def _commit_match(
            d_unit: Optional[CanonicalMatchingUnit],
            o_unit: Optional[CanonicalMatchingUnit],
            a_unit: Optional[CanonicalMatchingUnit],
            status: MatchGroupStatus,
            tier: str,
            confidence: float = 1.0,
            notes: str = ""
        ) -> MatchGroup:
            mg = MatchGroup(
                id=uuid4(),
                project_id=project_id,
                organization_id=organization_id,
                status=status
            )
            if d_unit:
                mg.design_item_id = d_unit.primary_item.id
                mg.design_item = d_unit.primary_item
                consumed_design.add(d_unit.id)
            if o_unit:
                mg.order_item_id = o_unit.primary_item.id
                mg.order_item = o_unit.primary_item
                consumed_order.add(o_unit.id)
            if a_unit:
                mg.ack_item_id = a_unit.primary_item.id
                mg.ack_item = a_unit.primary_item
                consumed_ack.add(a_unit.id)

            return mg

        # -------------------------------------------------------------
        # Helper: Check if unit A and unit B are canonically equivalent
        # -------------------------------------------------------------
        def _are_units_equivalent(u1: CanonicalMatchingUnit, u2: CanonicalMatchingUnit) -> Tuple[bool, str, float, str]:
            is_eq, conf, eq_type, evidence = check_canonical_equivalence(
                sku1=u1.sku,
                desc1=u1.description,
                dims1=u1.dimensions,
                cat1=u1.category,
                sku2=u2.sku,
                desc2=u2.description,
                dims2=u2.dimensions,
                cat2=u2.category,
                substitution_sku2=u2.substitution_sku
            )
            return is_eq, eq_type, conf, evidence

        # =============================================================
        # Pass 1: Design-Anchored 3-Way & 2-Way Matching
        # =============================================================
        for d in design_units:
            if d.id in consumed_design:
                continue

            # Candidate Order units
            cand_orders = [
                o for o in order_units 
                if o.id not in consumed_order and _are_units_equivalent(d, o)[0]
            ]

            # Candidate Ack units (matching Design SKU/description, substitution, or matching Order unit)
            cand_acks = [
                a for a in ack_units
                if a.id not in consumed_ack and (
                    _are_units_equivalent(d, a)[0] or
                    any(_are_units_equivalent(o, a)[0] for o in cand_orders)
                )
            ]

            # Check if other unconsumed design units share equivalence with d
            same_d_units = [
                other_d for other_d in design_units
                if other_d.id not in consumed_design and _are_units_equivalent(d, other_d)[0]
            ]

            # Check if candidate order/ack units also match other design units in project
            order_has_competing_d = False
            if cand_orders:
                comp_d_for_o = [
                    other_d for other_d in design_units
                    if _are_units_equivalent(other_d, cand_orders[0])[0]
                ]
                if len(comp_d_for_o) > 1:
                    order_has_competing_d = True

            ack_has_competing_d = False
            if cand_acks:
                comp_d_for_a = [
                    other_d for other_d in design_units
                    if _are_units_equivalent(other_d, cand_acks[0])[0]
                ]
                if len(comp_d_for_a) > 1:
                    ack_has_competing_d = True

            is_clean_single_candidate = (
                len(same_d_units) == 1 and 
                not order_has_competing_d and 
                not ack_has_competing_d
            )

            # Case 1A: Clean 1-to-1-to-1 Match (3-way)
            if is_clean_single_candidate and len(cand_orders) == 1 and len(cand_acks) == 1:
                o_unit = cand_orders[0]
                a_unit = cand_acks[0]
                _, eq_type_oa, _, _ = _are_units_equivalent(o_unit, a_unit)
                is_changed = bool(a_unit.substitution_sku or eq_type_oa in ["MANUFACTURER_VARIANT", "EXPLICIT_SUBSTITUTION"])
                status = MatchGroupStatus.CHANGED if is_changed else MatchGroupStatus.MATCHED
                match_groups.append(_commit_match(d, o_unit, a_unit, status, "TIER_1_3WAY", 1.0, "3-way match across documents"))
                continue

            # Case 1B: Clean 1-to-1 Design & Order Match (no Ack or ambiguous unoriented Ack candidate)
            if len(same_d_units) == 1 and not order_has_competing_d and len(cand_orders) == 1:
                if len(cand_acks) == 0 or ack_has_competing_d:
                    # Clean D-O pair match; unoriented/competing Ack candidate is left unconsumed for human review in Pass 3
                    match_groups.append(_commit_match(d, cand_orders[0], None, MatchGroupStatus.MATCHED, "TIER_1_DESIGN_ORDER", 0.98, "Match between Design and Order"))
                    continue

            # Case 1C: Clean 1-to-1 Design & Ack Match (no Order)
            if is_clean_single_candidate and len(cand_orders) == 0 and len(cand_acks) == 1:
                match_groups.append(_commit_match(d, None, cand_acks[0], MatchGroupStatus.CHANGED, "TIER_1_DESIGN_ACK", 0.90, "Match between Design and Ack"))
                continue

            # Case 1D: Duplicate Ambiguity / Dimension Disambiguation
            if len(same_d_units) > 1 or len(cand_orders) > 1 or len(cand_acks) > 1 or order_has_competing_d or ack_has_competing_d:
                matched_o = None
                matched_a = None

                # Disambiguate Order using non-empty dimensions
                if d.dimensions:
                    for o in cand_orders:
                        if o.dimensions and are_dimensions_equivalent(d.dimensions, o.dimensions)[0]:
                            matched_o = o
                            break
                    target_dims = matched_o.dimensions if matched_o else d.dimensions
                    for a in cand_acks:
                        if a.dimensions and are_dimensions_equivalent(target_dims, a.dimensions)[0]:
                            matched_a = a
                            break

                if matched_o or matched_a:
                    status = MatchGroupStatus.MATCHED if (matched_o and not (matched_a and matched_a.substitution_sku)) else MatchGroupStatus.CHANGED
                    match_groups.append(_commit_match(d, matched_o, matched_a, status, "TIER_3_SKU_DIMENSIONS_DISAMBIGUATION", 0.92, "Disambiguated duplicate SKU by dimensions"))
                else:
                    # Ambiguous duplicate: Abstain ALL competing candidate units to UNCERTAIN
                    all_competing_d = set(same_d_units)
                    if order_has_competing_d:
                        all_competing_d.update(comp_d_for_o)
                    if ack_has_competing_d:
                        all_competing_d.update(comp_d_for_a)

                    for comp_d in all_competing_d:
                        if comp_d.id not in consumed_design:
                            match_groups.append(_commit_match(comp_d, None, None, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous duplicate item without distinguishing dimensions"))
                    for comp_o in cand_orders:
                        if comp_o.id not in consumed_order:
                            match_groups.append(_commit_match(None, comp_o, None, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous duplicate item without distinguishing dimensions"))
                    for comp_a in cand_acks:
                        if comp_a.id not in consumed_ack:
                            match_groups.append(_commit_match(None, None, comp_a, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous duplicate item without distinguishing dimensions"))

        # =============================================================
        # Pass 2: Order <-> Ack Matching (for items not in Design -> EXTRA)
        # =============================================================
        for o in order_units:
            if o.id in consumed_order:
                continue

            cand_acks = [
                a for a in ack_units
                if a.id not in consumed_ack and _are_units_equivalent(o, a)[0]
            ]
            same_o_units = [
                other_o for other_o in order_units
                if other_o.id not in consumed_order and _are_units_equivalent(o, other_o)[0]
            ]

            if len(same_o_units) == 1 and len(cand_acks) == 1:
                a_unit = cand_acks[0]
                status = MatchGroupStatus.CHANGED if a_unit.substitution_sku else MatchGroupStatus.EXTRA
                match_groups.append(_commit_match(None, o, a_unit, status, "TIER_1_ORDER_ACK", 0.95, "Match between Order and Ack (Extra in Design)"))
            elif len(same_o_units) > 1 or len(cand_acks) > 1:
                match_groups.append(_commit_match(None, o, None, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous extra item in Order"))
            else:
                match_groups.append(_commit_match(None, o, None, MatchGroupStatus.EXTRA, "UNMATCHED_ORDER", 1.0, "Extra item in Order"))

        # =============================================================
        # Pass 3: Remaining Unmatched Design & Ack Units
        # =============================================================
        for d in design_units:
            if d.id not in consumed_design:
                match_groups.append(_commit_match(d, None, None, MatchGroupStatus.MISSING, "UNMATCHED_DESIGN", 1.0, "Missing in Order and Acknowledgement"))

        for a in ack_units:
            if a.id not in consumed_ack:
                match_groups.append(_commit_match(None, None, a, MatchGroupStatus.EXTRA, "UNMATCHED_ACK", 1.0, "Extra item in Acknowledgement"))

        # Final status pass
        for mg in match_groups:
            mg.status = self._evaluate_match_group_status(mg)

        return match_groups

    def _evaluate_match_group_status(self, mg: MatchGroup) -> MatchGroupStatus:
        if mg.status == MatchGroupStatus.UNCERTAIN:
            return MatchGroupStatus.UNCERTAIN

        has_d = mg.design_item_id is not None
        has_o = mg.order_item_id is not None
        has_a = mg.ack_item_id is not None

        # 3-way present
        if has_d and has_o and has_a:
            sku_d = normalize_sku(mg.design_item.normalized_sku or mg.design_item.raw_sku)
            sku_o = normalize_sku(mg.order_item.normalized_sku or mg.order_item.raw_sku)
            sku_a = normalize_sku(mg.ack_item.normalized_sku or mg.ack_item.raw_sku)

            eq_do = are_skus_equivalent(sku_d, sku_o)[0]
            eq_oa = are_skus_equivalent(sku_o, sku_a)[0]
            
            # If ack has explicit substitution or different SKU, it's CHANGED
            if mg.ack_item.substitution_sku or not (eq_do and eq_oa):
                return MatchGroupStatus.CHANGED
            return MatchGroupStatus.MATCHED

        # Design + Order (No Ack yet or not in Ack)
        if has_d and has_o and not has_a:
            sku_d = normalize_sku(mg.design_item.normalized_sku or mg.design_item.raw_sku)
            sku_o = normalize_sku(mg.order_item.normalized_sku or mg.order_item.raw_sku)
            if are_skus_equivalent(sku_d, sku_o)[0]:
                return MatchGroupStatus.MATCHED
            return MatchGroupStatus.CHANGED

        # Missing from Order & Ack
        if has_d and not has_o and not has_a:
            return MatchGroupStatus.MISSING

        # Extra in Order or Ack (items absent from Design)
        if not has_d and (has_o or has_a):
            return MatchGroupStatus.EXTRA

        # Design + Ack without Order
        if has_d and not has_o and has_a:
            return MatchGroupStatus.CHANGED

        return MatchGroupStatus.UNCERTAIN

