from typing import List, Optional, Any, Dict
from uuid import UUID

from app.models.core import MatchGroup, Discrepancy, MatchGroupStatus, Severity, DocumentType, ItemCategory, CanonicalLineItem
from app.engines.normalization import (
    normalize_sku,
    normalize_quantity,
    parse_and_normalize_dimensions,
    are_dimensions_equivalent,
    normalize_text,
    are_skus_equivalent
)


def _get_item_qty(item: Optional[CanonicalLineItem]) -> Optional[int]:
    """Extracts effective aggregate quantity from item or metadata."""
    if not item:
        return None
    if hasattr(item, "aggregate_quantity") and item.aggregate_quantity is not None:
        return item.aggregate_quantity
    if item.source_metadata and isinstance(item.source_metadata, dict):
        if "aggregate_quantity" in item.source_metadata and item.source_metadata["aggregate_quantity"] is not None:
            return item.source_metadata["aggregate_quantity"]
    return item.quantity


CATEGORY_DISCREPANCY_POLICY: Dict[ItemCategory, bool] = {
    ItemCategory.CABINET: True,
    ItemCategory.PANEL: True,
    ItemCategory.FILLER: True,
    ItemCategory.MOLDING: False,
    ItemCategory.ACCESSORY: False,
    ItemCategory.ARCHITECTURAL_ANNOTATION: False,
    ItemCategory.APPLIANCE: False,
    ItemCategory.COMMERCIAL_CHARGE: False,
    ItemCategory.UNKNOWN: True,
}


class CrossCheckEngine:
    """
    Deterministic 3-Way Cross-Check and Discrepancy Evaluation Engine.
    Strictly enforces:
    - Safe Introduced-At attribution & 3-way state transitions (Design -> Order -> Ack)
    - Pre-matching aggregate quantity comparison across line splits
    - Semantic dimension equivalence
    - Proper handling of NOT_SPECIFIED_IN_SOURCE
    - Manufacturer substitution & variant capture
    - Category-aware cross-check scope via CATEGORY_DISCREPANCY_POLICY
    """

    def __init__(self):
        self.severity_rules = {
            "sku": Severity.CRITICAL,
            "item_presence": Severity.CRITICAL,
            "quantity": Severity.WARNING,
            "dimensions": Severity.WARNING,
            "finish": Severity.WARNING,
            "door_style": Severity.WARNING,
            "modifications": Severity.WARNING,
            "price": Severity.INFO,
            "notes": Severity.INFO
        }

    def evaluate(self, match_groups: List[MatchGroup], project_id: UUID, organization_id: UUID) -> List[Discrepancy]:
        discrepancies: List[Discrepancy] = []
        for mg in match_groups:
            mg_discrepancies = self._evaluate_match_group(mg, project_id, organization_id)
            discrepancies.extend(mg_discrepancies)
            self._determine_final_state(mg, mg_discrepancies)
        return discrepancies

    def _get_mg_category(self, mg: MatchGroup) -> ItemCategory:
        """Determines the governing category of a match group."""
        for item in (mg.design_item, mg.order_item, mg.ack_item):
            if item and hasattr(item, "item_category") and item.item_category and item.item_category != ItemCategory.UNKNOWN:
                return item.item_category
        for item in (mg.design_item, mg.order_item, mg.ack_item):
            if item and hasattr(item, "item_category") and item.item_category:
                return item.item_category
        return ItemCategory.UNKNOWN

    def _evaluate_match_group(self, mg: MatchGroup, project_id: UUID, organization_id: UUID) -> List[Discrepancy]:
        discrepancies: List[Discrepancy] = []

        d_item = mg.design_item
        o_item = mg.order_item
        a_item = mg.ack_item

        mg_cat = self._get_mg_category(mg)

        # Enforce Discrepancy Exclusion Policy:
        # Non-cabinet/non-eligible items remain preserved in extraction/matching audit trail
        # but do NOT generate physical purchasing discrepancies.
        if not CATEGORY_DISCREPANCY_POLICY.get(mg_cat, True):
            return []

        # =============================================================
        # 1. Missing / Extra / State Transition Item Presence Discrepancies
        # =============================================================
        # Case A: Present in Design, Missing in Order and Missing in Ack
        if mg.design_item_id and not mg.order_item_id and not mg.ack_item_id:
            sev = Severity.WARNING if mg_cat == ItemCategory.UNKNOWN else Severity.CRITICAL
            exp = (
                f"Drawing item ({d_item.raw_sku if d_item else 'Item'}) with UNKNOWN classification not found in Purchase Order — requires reviewer confirmation"
                if mg_cat == ItemCategory.UNKNOWN
                else f"SKU {d_item.raw_sku if d_item else 'Item'} present in Design but missing in Purchase Order and Acknowledgement"
            )
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "item_presence",
                {"design": "PRESENT", "order": "MISSING", "acknowledgement": "MISSING"},
                {"expected": "PRESENT", "actual": "MISSING"},
                DocumentType.ORDER,
                sev,
                exp
            ))
            return discrepancies

        # Case B: Present in Design, Omitted in Order, Restored/Added in Ack
        if mg.design_item_id and not mg.order_item_id and mg.ack_item_id:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "item_presence",
                {"design": "PRESENT", "order": "OMITTED", "acknowledgement": "RESTORED"},
                {"design_to_order": "OMITTED", "order_to_ack": "RESTORED"},
                DocumentType.ORDER,
                Severity.WARNING,
                f"State transition: Design → Order (OMITTED), Order → Ack (RESTORED). SKU {d_item.raw_sku} present in Design was omitted in Purchase Order but restored in Acknowledgement"
            ))

        # Case C: Absent in Design, Present in Order, Absent in Ack
        if not mg.design_item_id and mg.order_item_id and not mg.ack_item_id:
            sev = Severity.WARNING if mg_cat == ItemCategory.UNKNOWN else Severity.CRITICAL
            exp = (
                f"Extra item {o_item.raw_sku} with UNKNOWN classification added in Purchase Order but not acknowledged — requires review"
                if mg_cat == ItemCategory.UNKNOWN
                else f"State transition: Design → Order (ADDED), Order → Ack (OMITTED). Extra item {o_item.raw_sku} added in Purchase Order but not acknowledged by manufacturer"
            )
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "item_presence",
                {"design": "ABSENT", "order": "ADDED", "acknowledgement": "OMITTED"},
                {"design_to_order": "ADDED", "order_to_ack": "OMITTED"},
                DocumentType.ORDER,
                sev,
                exp
            ))
            return discrepancies

        # Case D: Absent in Design, Present in Order, Present in Ack
        if not mg.design_item_id and mg.order_item_id and mg.ack_item_id:
            sev = Severity.WARNING if mg_cat == ItemCategory.UNKNOWN else Severity.CRITICAL
            exp = (
                f"Extra item {o_item.raw_sku} with UNKNOWN classification added in Purchase Order and confirmed in Acknowledgement — requires review"
                if mg_cat == ItemCategory.UNKNOWN
                else f"Extra line item {o_item.raw_sku} added in Purchase Order and confirmed in Acknowledgement not found in Design Drawing"
            )
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "item_presence",
                {"design": "ABSENT", "order": "PRESENT", "acknowledgement": "PRESENT"},
                {"expected": "ABSENT", "actual": "PRESENT"},
                DocumentType.ORDER,
                sev,
                exp
            ))

        # Case E: Absent in Design, Absent in Order, Present in Ack
        if not mg.design_item_id and not mg.order_item_id and mg.ack_item_id:
            sev = Severity.WARNING if mg_cat == ItemCategory.UNKNOWN else Severity.CRITICAL
            exp = (
                f"Extra item {a_item.raw_sku} with UNKNOWN classification added in Acknowledgement — requires review"
                if mg_cat == ItemCategory.UNKNOWN
                else f"Extra line item {a_item.raw_sku} added in Acknowledgement not requested in Purchase Order or Design"
            )
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "item_presence",
                {"design": "ABSENT", "order": "ABSENT", "acknowledgement": "PRESENT"},
                {"expected": "ABSENT", "actual": "PRESENT"},
                DocumentType.ACKNOWLEDGEMENT,
                sev,
                exp
            ))
            return discrepancies

        # =============================================================
        # 2. Manufacturer Substitution & SKU Variant Discrepancy
        # =============================================================
        if mg.ack_item:
            if mg.ack_item.substitution_sku:
                discrepancies.append(self._create_discrepancy(
                    mg, project_id, organization_id, "sku",
                    {
                        "design": mg.design_item.raw_sku if mg.design_item else None,
                        "order": mg.order_item.raw_sku if mg.order_item else None,
                        "acknowledgement": mg.ack_item.raw_sku
                    },
                    {
                        "expected": mg.order_item.raw_sku if mg.order_item else mg.design_item.raw_sku,
                        "actual": mg.ack_item.raw_sku
                    },
                    DocumentType.ACKNOWLEDGEMENT,
                    Severity.WARNING,
                    f"Manufacturer substitution in Ack: {mg.ack_item.raw_sku} (replaced {mg.ack_item.substitution_sku})"
                ))
            else:
                d_sku = normalize_sku(mg.design_item.raw_sku) if mg.design_item else None
                o_sku = normalize_sku(mg.order_item.raw_sku) if mg.order_item else None
                a_sku = normalize_sku(mg.ack_item.raw_sku)
                
                # Check if Ack SKU differs from Design/Order SKU (evidence-backed manufacturer variant)
                ref_sku = o_sku or d_sku
                if ref_sku and a_sku and not are_skus_equivalent(ref_sku, a_sku)[0]:
                    discrepancies.append(self._create_discrepancy(
                        mg, project_id, organization_id, "sku",
                        {
                            "design": mg.design_item.raw_sku if mg.design_item else None,
                            "order": mg.order_item.raw_sku if mg.order_item else None,
                            "acknowledgement": mg.ack_item.raw_sku
                        },
                        {
                            "expected": ref_sku,
                            "actual": a_sku
                        },
                        DocumentType.ACKNOWLEDGEMENT,
                        Severity.INFO,
                        f"Manufacturer SKU variant in Acknowledgement: '{mg.ack_item.raw_sku}' corresponds to '{ref_sku}'"
                    ))

        # =============================================================
        # 3. Quantity Comparison with 3-Way State Sequence & First Divergence
        # =============================================================
        d_qty = _get_item_qty(mg.design_item)
        o_qty = _get_item_qty(mg.order_item)
        a_qty = _get_item_qty(mg.ack_item)

        if d_qty is not None and o_qty is not None and d_qty != o_qty:
            revert_note = f" (reverted to {a_qty} in Acknowledgement)" if (a_qty is not None and a_qty == d_qty) else (f", confirmed as {a_qty} in Acknowledgement" if a_qty is not None else "")
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "quantity",
                {"design": d_qty, "order": o_qty, "acknowledgement": a_qty},
                {"expected": d_qty, "actual": o_qty},
                DocumentType.ORDER,
                Severity.WARNING,
                f"Quantity discrepancy: Design specifies {d_qty}, but Purchase Order requested {o_qty}{revert_note}"
            ))
        elif o_qty is not None and a_qty is not None and o_qty != a_qty:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "quantity",
                {"design": d_qty, "order": o_qty, "acknowledgement": a_qty},
                {"expected": o_qty, "actual": a_qty},
                DocumentType.ACKNOWLEDGEMENT,
                Severity.WARNING,
                f"Quantity discrepancy: Order requested {o_qty}, but Acknowledgement confirmed {a_qty}"
            ))
        elif d_qty is not None and a_qty is not None and o_qty is None and d_qty != a_qty:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "quantity",
                {"design": d_qty, "order": o_qty, "acknowledgement": a_qty},
                {"expected": d_qty, "actual": a_qty},
                DocumentType.ACKNOWLEDGEMENT,
                Severity.WARNING,
                f"Quantity discrepancy: Design specifies {d_qty}, but Acknowledgement confirmed {a_qty}"
            ))

        # =============================================================
        # 4. Dimension Semantic Comparison
        # =============================================================
        d_dim = mg.design_item.dimensions if mg.design_item else None
        o_dim = mg.order_item.dimensions if mg.order_item else None
        a_dim = mg.ack_item.dimensions if mg.ack_item else None

        # Compare Design vs Order only if BOTH specify dimensions explicitly
        if d_dim is not None and o_dim is not None:
            is_eq, reason = are_dimensions_equivalent(d_dim, o_dim)
            if not is_eq:
                discrepancies.append(self._create_discrepancy(
                    mg, project_id, organization_id, "dimensions",
                    {"design": d_dim, "order": o_dim, "acknowledgement": a_dim},
                    {"expected": d_dim, "actual": o_dim},
                    DocumentType.ORDER,
                    Severity.WARNING,
                    f"Dimension mismatch between Design and Order ({reason})"
                ))
        # Compare Order vs Ack
        if o_dim is not None and a_dim is not None:
            is_eq, reason = are_dimensions_equivalent(o_dim, a_dim)
            if not is_eq:
                discrepancies.append(self._create_discrepancy(
                    mg, project_id, organization_id, "dimensions",
                    {"design": d_dim, "order": o_dim, "acknowledgement": a_dim},
                    {"expected": o_dim, "actual": a_dim},
                    DocumentType.ACKNOWLEDGEMENT,
                    Severity.WARNING,
                    f"Dimension mismatch between Order and Acknowledgement ({reason})"
                ))

        # =============================================================
        # 5. Finish & Door Style Comparison
        # =============================================================
        d_fin = normalize_text(mg.design_item.finish) if mg.design_item else None
        o_fin = normalize_text(mg.order_item.finish) if mg.order_item else None
        a_fin = normalize_text(mg.ack_item.finish) if mg.ack_item else None

        if d_fin is not None and o_fin is not None and d_fin != o_fin:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "finish",
                {"design": mg.design_item.finish, "order": mg.order_item.finish, "acknowledgement": mg.ack_item.finish if mg.ack_item else None},
                {"expected": mg.design_item.finish, "actual": mg.order_item.finish},
                DocumentType.ORDER,
                Severity.WARNING,
                f"Finish changed: Design specifies '{mg.design_item.finish}', but Order specifies '{mg.order_item.finish}'"
            ))
        if o_fin is not None and a_fin is not None and o_fin != a_fin:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "finish",
                {"design": mg.design_item.finish if mg.design_item else None, "order": mg.order_item.finish, "acknowledgement": mg.ack_item.finish},
                {"expected": mg.order_item.finish, "actual": mg.ack_item.finish},
                DocumentType.ACKNOWLEDGEMENT,
                Severity.WARNING,
                f"Finish changed: Order specifies '{mg.order_item.finish}', but Acknowledgement specifies '{mg.ack_item.finish}'"
            ))

        d_door = normalize_text(mg.design_item.door_style) if mg.design_item else None
        o_door = normalize_text(mg.order_item.door_style) if mg.order_item else None
        a_door = normalize_text(mg.ack_item.door_style) if mg.ack_item else None

        if d_door is not None and o_door is not None and d_door != o_door:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "door_style",
                {"design": mg.design_item.door_style, "order": mg.order_item.door_style, "acknowledgement": mg.ack_item.door_style if mg.ack_item else None},
                {"expected": mg.design_item.door_style, "actual": mg.order_item.door_style},
                DocumentType.ORDER,
                Severity.WARNING,
                f"Door style changed: Design specifies '{mg.design_item.door_style}', but Order specifies '{mg.order_item.door_style}'"
            ))
        if o_door is not None and a_door is not None and o_door != a_door:
            discrepancies.append(self._create_discrepancy(
                mg, project_id, organization_id, "door_style",
                {"design": mg.design_item.door_style if mg.design_item else None, "order": mg.order_item.door_style, "acknowledgement": mg.ack_item.door_style},
                {"expected": mg.order_item.door_style, "actual": mg.ack_item.door_style},
                DocumentType.ACKNOWLEDGEMENT,
                Severity.WARNING,
                f"Door style changed: Order specifies '{mg.order_item.door_style}', but Acknowledgement specifies '{mg.ack_item.door_style}'"
            ))

        return discrepancies

    def _create_discrepancy(
        self,
        mg: MatchGroup,
        project_id: UUID,
        organization_id: UUID,
        field: str,
        source_values: Dict[str, Any],
        comparison_values: Dict[str, Any],
        introduced_at: DocumentType,
        severity: Severity,
        explanation: str
    ) -> Discrepancy:
        return Discrepancy(
            project_id=project_id,
            organization_id=organization_id,
            match_group_id=mg.id,
            field=field,
            source_values=source_values,
            comparison_values=comparison_values,
            introduced_at=introduced_at,
            status="OPEN",
            severity=severity,
            confidence="HIGH",
            explanation=explanation,
            match_group=mg
        )

    def _determine_final_state(self, mg: MatchGroup, discrepancies: Optional[List[Discrepancy]] = None):
        if discrepancies is None:
            discrepancies = []
        # Hierarchy: Ack > Order > Design
        if mg.ack_item_id:
            truth_item = mg.ack_item
        elif mg.order_item_id:
            truth_item = mg.order_item
        elif mg.design_item_id:
            truth_item = mg.design_item
        else:
            return

        mg.final_sku = truth_item.raw_sku or truth_item.normalized_sku
        mg.final_quantity = _get_item_qty(truth_item)
        mg.final_dimensions = truth_item.dimensions
        mg.final_finish = truth_item.finish
        mg.final_door_style = truth_item.door_style
        mg.final_modifications = truth_item.modifications
        mg.final_price = truth_item.price
        mg.final_status = "RESOLVED_AUTO" if not discrepancies else "PENDING_REVIEW"
