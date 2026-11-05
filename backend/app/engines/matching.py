import re
from collections import Counter
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
        # When dedup annotated a quantity_resolution (FLOORPLAN vs ELEVATION),
        # use the evidence-based resolved_quantity instead of the raw winner qty.
        if len(raw_items) == 1:
            qr = (raw_items[0].source_metadata or {}).get("quantity_resolution") or {}
            if qr.get("resolved_quantity") is not None:
                self.aggregate_quantity = qr["resolved_quantity"]

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
        self.finish_status = getattr(self.primary_item, "finish_status", None)
        self.door_style = self.primary_item.door_style
        self.door_style_status = getattr(self.primary_item, "door_style_status", None)
        self.modifications = self.primary_item.modifications
        self.notes = getattr(self.primary_item, "notes", None)
        self.substitution_sku = getattr(self.primary_item, "substitution_sku", None)

        for item in raw_items[1:]:
            if not self.description and item.description:
                self.description = item.description
            if not self.dimensions and item.dimensions:
                self.dimensions = item.dimensions
            if not self.finish and item.finish:
                self.finish = item.finish
                self.finish_status = getattr(item, "finish_status", None)
            if not self.door_style and item.door_style:
                self.door_style = item.door_style
                self.door_style_status = getattr(item, "door_style_status", None)
            if not self.notes and getattr(item, "notes", None):
                self.notes = item.notes
            if not self.substitution_sku and getattr(item, "substitution_sku", None):
                self.substitution_sku = item.substitution_sku


_VIEW_TYPE_PRIORITY = {"SCHEDULE": 4, "ELEVATION": 3, "FLOORPLAN": 2, "LEGEND": 1}


def _dedup_view_types(items: List[CanonicalLineItem]) -> List[CanonicalLineItem]:
    """
    Within the same display, same SKU/finish/door — keep only the highest-priority
    view_type items (SCHEDULE > ELEVATION > FLOORPLAN > LEGEND). Items without
    view_type pass through unchanged. This prevents FLOORPLAN+ELEVATION double-counting
    for designs that show each display in multiple views.
    """
    no_vt: List[CanonicalLineItem] = []
    vt_groups: Dict[str, List[CanonicalLineItem]] = {}

    for item in items:
        meta = item.source_metadata or {}
        vt = meta.get("view_type")
        if not vt:
            no_vt.append(item)
            continue
        pos = meta.get("position", "") or ""
        m = re.search(r'display\s*(\d+)', pos, re.IGNORECASE)
        display_key = f"display_{m.group(1)}" if m else (normalize_text(pos) or "unknown")
        norm_sku = normalize_sku(item.raw_sku or item.normalized_sku) or ""
        # Intentionally excludes finish/door — FLOORPLAN headers often carry
        # finish while ELEVATION rows inherit nothing; the outer aggregation
        # handles variant splitting after dedup.
        key = f"{norm_sku}__POS_{display_key}"
        vt_groups.setdefault(key, []).append(item)

    result = list(no_vt)
    for group in vt_groups.values():
        max_p = max(_VIEW_TYPE_PRIORITY.get((i.source_metadata or {}).get("view_type", ""), 0) for i in group)
        same_prio = [i for i in group if _VIEW_TYPE_PRIORITY.get((i.source_metadata or {}).get("view_type", ""), 0) == max_p]
        # Within the same view_type at max priority, prefer items with explicit
        # finish/door_style over blank ones — the same cabinet sometimes appears
        # on multiple pages (e.g. in a schedule table AND a floorplan overview),
        # and only some of those instances have finish inherited from the display
        # header. Keeping the blank-finish instance alongside the explicit one
        # creates two aggregate groups for the same SKU → AMBIGUOUS_DUPLICATE.
        with_finish = [i for i in same_prio if (i.finish or "").strip() or (i.door_style or "").strip()]
        winners = with_finish if with_finish else same_prio
        # Inherit finish/door_style from dropped lower-priority items when winner
        # has none. Never delete an occurrence simply because another has a finish.
        dropped = [i for i in group if i not in winners]
        dropped_fps = [i for i in dropped if (i.source_metadata or {}).get("view_type") == "FLOORPLAN"]
        for w in winners:
            if not (w.finish or "").strip():
                for d in dropped:
                    if (d.finish or "").strip():
                        w.finish = d.finish
                        break
            if not (w.door_style or "").strip():
                for d in dropped:
                    if (d.door_style or "").strip():
                        w.door_style = d.door_style
                        break
            # Quantity resolution: compare FLOORPLAN vs winner counts; store evidence
            # but do NOT overwrite the original extracted quantity.
            # FLOORPLAN sees all positions from above; ELEVATION sees only visible face.
            if dropped_fps:
                fp_qty = max((i.quantity or 0) for i in dropped_fps)
                fp_pages = [
                    str((i.source_metadata or {}).get("page_number") or "")
                    for i in dropped_fps
                    if (i.source_metadata or {}).get("page_number")
                ]
                w_vt = (w.source_metadata or {}).get("view_type", "ELEVATION")
                w_qty = w.quantity or 0
                if fp_qty > w_qty:
                    resolved, method, confidence, qty_src = fp_qty, "floorplan_higher_inferred", "INFERRED", "FLOORPLAN"
                elif fp_qty == w_qty:
                    resolved, method, confidence, qty_src = fp_qty, "views_agree", "HIGH", "AGREED"
                else:  # elevation shows more than floorplan — unusual, flag for review
                    resolved, method, confidence, qty_src = w_qty, "elevation_higher_flagged", "NEEDS_REVIEW", w_vt
                qr: Dict[str, Any] = {
                    "resolved_quantity": resolved,
                    "quantity_source": qty_src,
                    "resolution_method": method,
                    "confidence_status": confidence,
                    "conflicting_views": {w_vt: w_qty, "FLOORPLAN": fp_qty},
                }
                if fp_pages:
                    qr["floorplan_pages"] = fp_pages
                new_meta = dict(w.source_metadata or {})
                new_meta["quantity_resolution"] = qr
                w.source_metadata = new_meta
        result.extend(winners)
    return result


def aggregate_document_items(items: List[CanonicalLineItem]) -> List[CanonicalMatchingUnit]:
    """
    Groups identical normalized SKUs within the SAME document into CanonicalMatchingUnits.
    Does NOT aggregate different variants (e.g. BT18-2-L vs BT18-2-R).
    Preserves all raw items without loss.
    """
    items = _dedup_view_types(items)
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
        # For DESIGN items with an explicit view_type, include the display position
        # so that the same SKU with no finish in Display 2 and Display 6 never
        # merges — they represent physically separate cabinet instances.
        pos_key = ""
        meta = item.source_metadata or {}
        if meta.get("view_type"):
            pos = meta.get("position", "") or ""
            pm = re.search(r'display\s*(\d+)', pos, re.IGNORECASE)
            pos_key = f"display_{pm.group(1)}" if pm else (normalize_text(pos) or "")
        group_key = f"{norm_sku}__FIN_{fin}__DOOR_{door}__POS_{pos_key}"
        
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(item)

    units: List[CanonicalMatchingUnit] = []
    for raw_group in groups.values():
        units.append(CanonicalMatchingUnit(raw_group))
    return units


# Finish/door_style text is worded very differently between documents — a
# Design page header ("Sagewood/PHW with Nutmeg/Maple hood valance") vs an
# Order row ("MONROE PHW SAGEWOOD") describe the same display with almost no
# shared substring. Exact-string comparison misses this; comparing by
# significant word overlap instead survives the reword. These short
# connector/qualifier words are common across many unrelated displays (seen
# in real extracted data) so they must never be the ONLY basis for a match.
_CONFIG_STOPWORDS = {
    "phw", "pok", "ply", "fx", "with", "and", "the", "of", "a", "b",
    "door", "style", "finish", "hood", "valance", "construction",
}


def _significant_tokens(text: Optional[str]) -> Set[str]:
    """
    Lowercased word tokens of length >= 4, minus generic connector/qualifier
    words. Splits on ANY non-alphanumeric character, not just whitespace —
    "Sagewood/PHW" (slash-joined, common in Design page headers) must
    tokenize the same as "Sagewood PHW" (space-joined, common in Order rows).
    """
    normalized = normalize_text(text or "") or ""
    tokens = re.split(r'[^A-Z0-9]+', normalized)
    return {t.lower() for t in tokens if len(t) >= 4 and t.lower() not in _CONFIG_STOPWORDS}


def _collect_order_configs(
    order_units: List[CanonicalMatchingUnit], ack_units: List[CanonicalMatchingUnit]
) -> Set[str]:
    """
    Every significant door_style/finish word present anywhere in Order/Ack.
    A Design document can be a multi-display/multi-room catalog (e.g. a
    dealer's full showroom brief) spanning far more than this order, but
    Order/Ack items always belong to it. Used to recognize design items that
    don't correspond to ANY item in this order at all — not by guessing a
    single "correct" display, which is unsafe when the order itself spans
    several displays (a dealer ordering for multiple rooms at once).
    """
    tokens: Set[str] = set()
    for unit in list(order_units) + list(ack_units):
        tokens |= _significant_tokens(unit.door_style)
        tokens |= _significant_tokens(unit.finish)
    return tokens


def _is_out_of_scope(unit: CanonicalMatchingUnit, order_config_tokens: Set[str]) -> bool:
    """
    True only when the unit has an explicit door_style or finish and shares
    NOT ONE significant word with anything anywhere in Order/Ack — i.e. it
    belongs to no display the order touches at all. Blank/unspecified
    fields are never treated as evidence of exclusion ("blank fields mean
    unspecified, not false").
    """
    if not order_config_tokens:
        return False
    unit_tokens = _significant_tokens(unit.door_style) | _significant_tokens(unit.finish)
    if not unit_tokens:
        return False
    return unit_tokens.isdisjoint(order_config_tokens)


def _config_tokens(unit: CanonicalMatchingUnit) -> Set[str]:
    """
    Significant words from finish/door_style, plus notes — a design line's
    free-text note ("Doorstyle changed to apex — not shown") is sometimes
    the ONLY place a display's identity survives when the structured
    finish/door_style field came back blank for that specific row.
    """
    return (
        _significant_tokens(unit.finish)
        | _significant_tokens(unit.door_style)
        | _significant_tokens(getattr(unit, "notes", None))
    )


def _best_config_match(
    reference: CanonicalMatchingUnit, candidates: List[CanonicalMatchingUnit]
) -> Optional[CanonicalMatchingUnit]:
    """
    Disambiguates same-SKU duplicate candidates (e.g. a generic trim code
    reused across several displays/rooms) by finish/door_style/notes word
    overlap when dimensions aren't available. Returns a candidate only when
    exactly one of them has the strictly highest overlap (>= 1 shared word)
    with the reference — any tie, or zero overlap across the board, abstains
    to None so the caller falls through to UNCERTAIN rather than guessing.
    """
    ref_tokens = _config_tokens(reference)
    if not ref_tokens:
        return None

    def _reliability(c: CanonicalMatchingUnit) -> int:
        # An OBSERVED finish/door_style (printed directly on this candidate's
        # own row) is stronger evidence than one INHERITED_EXPLICIT from a
        # header, which breaks a tie in token overlap without guessing.
        statuses = {getattr(c, "finish_status", None), getattr(c, "door_style_status", None)}
        return 1 if "OBSERVED" in statuses else 0

    scored = [((len(ref_tokens & _config_tokens(c)), _reliability(c)), c) for c in candidates]
    scored = [(key, c) for key, c in scored if key[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda sc: sc[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


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
        design_units_all = aggregate_document_items(design_items)
        order_units = aggregate_document_items(order_items)
        ack_units = aggregate_document_items(ack_items)

        # Design documents are sometimes a multi-display/multi-room catalog
        # spanning far more than the order being verified. Exclude design
        # items whose explicit door style/finish doesn't correspond to ANY
        # item anywhere in Order/Ack — not a single "most common" display,
        # which misfires when the order itself covers several displays —
        # instead of letting unrelated-display items collide with this
        # order's SKUs and surface as noisy EXTRA/UNCERTAIN findings (see
        # brief: "do not assume every page is the same room").
        order_config_tokens = _collect_order_configs(order_units, ack_units)
        out_of_scope_design_units = [
            u for u in design_units_all if _is_out_of_scope(u, order_config_tokens)
        ]
        design_units = [u for u in design_units_all if u not in out_of_scope_design_units]

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

            # Case 1D: Duplicate Ambiguity / Dimension or Finish-Door-Style Disambiguation
            if len(same_d_units) > 1 or len(cand_orders) > 1 or len(cand_acks) > 1 or order_has_competing_d or ack_has_competing_d:
                matched_o = None
                matched_a = None
                disambiguated_by = None

                # Disambiguate Order using non-empty dimensions first, then
                # finish/door style (e.g. a generic trim code reused across
                # several displays/rooms in a multi-display order — no
                # dimensions to compare, but each candidate's finish ties it
                # to a specific display).
                if d.dimensions:
                    for o in cand_orders:
                        if o.dimensions and are_dimensions_equivalent(d.dimensions, o.dimensions)[0]:
                            matched_o = o
                            disambiguated_by = "dimensions"
                            break
                if not matched_o:
                    matched_o = _best_config_match(d, cand_orders)
                    if matched_o:
                        disambiguated_by = "finish/door style"

                target_dims = matched_o.dimensions if matched_o else d.dimensions
                target_config_unit = matched_o or d
                if target_dims:
                    for a in cand_acks:
                        if a.dimensions and are_dimensions_equivalent(target_dims, a.dimensions)[0]:
                            matched_a = a
                            disambiguated_by = disambiguated_by or "dimensions"
                            break
                if not matched_a:
                    matched_a = _best_config_match(target_config_unit, cand_acks)
                    if matched_a:
                        disambiguated_by = disambiguated_by or "finish/door style"

                if matched_o or matched_a:
                    status = MatchGroupStatus.MATCHED if (matched_o and not (matched_a and matched_a.substitution_sku)) else MatchGroupStatus.CHANGED
                    match_groups.append(_commit_match(d, matched_o, matched_a, status, "TIER_3_SKU_DISAMBIGUATION", 0.92, f"Disambiguated duplicate SKU by {disambiguated_by}"))
                else:
                    # Ambiguous duplicate: collect all competing units
                    all_competing_d = set(same_d_units)
                    if order_has_competing_d:
                        all_competing_d.update(comp_d_for_o)
                    if ack_has_competing_d:
                        all_competing_d.update(comp_d_for_a)

                    remaining_orders = [o for o in cand_orders if o.id not in consumed_order]
                    remaining_acks = [a for a in cand_acks if a.id not in consumed_ack]

                    # Greedy rescue: DESIGN units with explicit finish/door style can be
                    # disambiguated even when the triggering unit `d` could not.
                    #
                    # To prevent first-wins from resolving genuine ambiguity:
                    #   Phase 1 — compute every unit's best ORDER/ACK proposal against a
                    #             snapshot (no consumption yet). Sort by (token count DESC,
                    #             id ASC) for full determinism across equal-richness tiers.
                    #   Phase 2 — flag ORDER/ACK items claimed by >1 DESIGN unit as
                    #             contested; both sides fall through to UNCERTAIN.
                    #   Phase 3 — commit only uncontested matches.
                    rescue_candidates = sorted(
                        [cd for cd in all_competing_d
                         if cd.id not in consumed_design and _config_tokens(cd)],
                        key=lambda cd: (len(_config_tokens(cd)), str(cd.id)),
                        reverse=True,
                    )

                    proposals: Dict[Any, Tuple[Optional["CanonicalMatchingUnit"], Optional["CanonicalMatchingUnit"]]] = {}
                    for comp_d in rescue_candidates:
                        proposals[comp_d.id] = (
                            _best_config_match(comp_d, remaining_orders),
                            _best_config_match(comp_d, remaining_acks),
                        )

                    o_claimants: Dict[Any, List] = {}
                    a_claimants: Dict[Any, List] = {}
                    for comp_d in rescue_candidates:
                        best_o, best_a = proposals[comp_d.id]
                        if best_o:
                            o_claimants.setdefault(best_o.id, []).append(comp_d)
                        if best_a:
                            a_claimants.setdefault(best_a.id, []).append(comp_d)

                    contested_d_ids: Set[Any] = set()
                    for claimants in o_claimants.values():
                        if len(claimants) > 1:
                            contested_d_ids.update(cd.id for cd in claimants)
                    for claimants in a_claimants.values():
                        if len(claimants) > 1:
                            contested_d_ids.update(cd.id for cd in claimants)

                    for comp_d in rescue_candidates:
                        if comp_d.id in contested_d_ids or comp_d.id in consumed_design:
                            continue
                        best_o, best_a = proposals[comp_d.id]
                        if best_o or best_a:
                            st = MatchGroupStatus.MATCHED if (best_o and not (best_a and best_a.substitution_sku)) else MatchGroupStatus.CHANGED
                            match_groups.append(_commit_match(comp_d, best_o, best_a, st, "TIER_3_SKU_DISAMBIGUATION", 0.92, "Disambiguated duplicate SKU by finish/door style"))
                            if best_o:
                                remaining_orders = [o for o in remaining_orders if o.id != best_o.id]
                            if best_a:
                                remaining_acks = [a for a in remaining_acks if a.id != best_a.id]

                    # Mark all remaining unresolvable units UNCERTAIN
                    for comp_d in all_competing_d:
                        if comp_d.id not in consumed_design:
                            match_groups.append(_commit_match(comp_d, None, None, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous duplicate item without distinguishing dimensions"))
                    for comp_o in remaining_orders:
                        if comp_o.id not in consumed_order:
                            match_groups.append(_commit_match(None, comp_o, None, MatchGroupStatus.UNCERTAIN, "AMBIGUOUS_DUPLICATE", 0.5, "Ambiguous duplicate item without distinguishing dimensions"))
                    for comp_a in remaining_acks:
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

        # =============================================================
        # Pass 4: Design units excluded as belonging to a display/room this
        # order never touches at all (see _collect_order_configs above)
        # =============================================================
        for d in out_of_scope_design_units:
            match_groups.append(_commit_match(
                d, None, None, MatchGroupStatus.OUT_OF_SCOPE, "SCOPE_FILTER", 1.0,
                f"Design item's door style/finish ('{d.door_style or '—'}' / '{d.finish or '—'}') "
                f"doesn't match any item in the Purchase Order or Acknowledgement"
            ))

        # Final status pass
        for mg in match_groups:
            mg.status = self._evaluate_match_group_status(mg)

        return match_groups

    def _evaluate_match_group_status(self, mg: MatchGroup) -> MatchGroupStatus:
        if mg.status in (MatchGroupStatus.UNCERTAIN, MatchGroupStatus.OUT_OF_SCOPE):
            return mg.status

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

