"""
F8.3 Phase 3 (+ Phase 3.1 hardening): deterministic reconciliation between
two independent extraction passes (OCR text-based structuring and Vision
image-based extraction) for scanned documents.

This is NOT the CrossCheck matching engine — it never touches MatchGroup or
Discrepancy. Its only job is to decide whether EXTRACTION ITSELF is stable:
did two independent readings of the same source agree closely enough to be
trusted, or must a human verify what the source actually says?

Hard rule (spec §10 / Phase 3.1 non-negotiables): never use "close enough" /
fuzzy similarity as PROOF of agreement. Field values either match after
normalization, or the item is UNCERTAIN. Phase 3.1 widens which items get
COMPARED against each other (so more genuine agreements/conflicts surface
instead of being invisible single-source items) — it never loosens what
counts as agreement.
"""
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple
from app.engines.normalization import normalize_sku, normalize_text, normalize_quantity

# Fields compared between the two passes when both sides provide a value.
_COMPARABLE_FIELDS = ["quantity", "description", "finish", "door_style", "line_number", "unit_price", "total_price", "dimensions"]

# Field preference mappings for intelligent hybrid conflict resolution
_OCR_PREFERRED_FIELDS = {"sku", "quantity", "price", "unit_price", "total_price", "line_number", "dimensions", "code", "item_code"}
_VISION_PREFERRED_FIELDS = {"description", "category", "finish", "door_style", "notes", "comments", "room", "zone", "layout_context"}

# Phase 3.1 §4: known OCR character confusions, used ONLY to generate extra
# reconciliation CANDIDATES (never to rewrite a raw or canonical SKU, never
# applied globally/silently).
_OCR_SUBSTITUTION_PAIRS = [("0", "O"), ("1", "I"), ("1", "L"), ("5", "S"), ("8", "B"), ("2", "Z")]
_MAX_CANDIDATE_SUBSTITUTIONS = 2
_MAX_CANDIDATE_POSITIONS = 8

# Phase 3.1 §5/§7/§8: a candidate pair must clear this combined evidence
# score (page match + description overlap + quantity match) before it is
# even offered for field-by-field comparison. Clearing this bar is NOT
# verification — it only means the pair is worth comparing; the pair still
# goes through the same strict Rule A-D comparison as an exact-SKU match.
_CANDIDATE_SCORE_THRESHOLD = 3
_DESC_SIMILARITY_THRESHOLD = 0.6


def _norm_value(field: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field == "quantity":
        return normalize_quantity(value)
    if field in ("description", "finish", "door_style", "line_number"):
        return normalize_text(str(value))
    return value


def _desc_similarity(a: Any, b: Any) -> float:
    na, nb = normalize_text(a) or "", normalize_text(b) or ""
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _evidence_score(o: Dict[str, Any], v: Dict[str, Any]) -> int:
    """
    Combined-evidence score used to gate BOTH duplicate-SKU-group alignment
    and OCR-candidate alignment (Phase 3.1 §5/§7/§8). Never proof of
    identity by itself — only decides whether a pair is worth comparing.
    """
    score = 0
    op, vp = o.get("page_number"), v.get("page_number")
    if op is not None and vp is not None and op == vp:
        score += 2
    if _desc_similarity(o.get("description"), v.get("description")) >= _DESC_SIMILARITY_THRESHOLD:
        score += 2
    oq, vq = _norm_value("quantity", o.get("quantity")), _norm_value("quantity", v.get("quantity"))
    if oq is not None and oq == vq:
        score += 1
    return score


def _ocr_candidate_skus(sku: Optional[str]) -> Set[str]:
    """
    Phase 3.1 §4: candidate SKU spellings from known OCR character
    confusions (0/O, 1/I, 1/L, 5/S, 8/B, 2/Z). CANDIDATE GENERATION ONLY —
    never becomes the canonical/raw SKU, only used to find items worth
    evidence-gated comparison.
    """
    norm = normalize_sku(sku)
    if not norm:
        return set()
    alt_map: Dict[str, Set[str]] = {}
    for a, b in _OCR_SUBSTITUTION_PAIRS:
        alt_map.setdefault(a, set()).add(b)
        alt_map.setdefault(b, set()).add(a)

    positions = [i for i, c in enumerate(norm) if c in alt_map][:_MAX_CANDIDATE_POSITIONS]
    candidates = {norm}
    for r in range(1, _MAX_CANDIDATE_SUBSTITUTIONS + 1):
        for combo in combinations(positions, r):
            variants = [norm]
            for pos in combo:
                next_variants = []
                for variant in variants:
                    for alt in alt_map[norm[pos]]:
                        next_variants.append(variant[:pos] + alt + variant[pos + 1:])
                variants = next_variants
            candidates.update(variants)
    return candidates


@dataclass
class FieldConflict:
    field: str
    ocr_value: Any
    vision_value: Any
    resolved_value: Optional[Any] = None
    preferred_source: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "field": self.field,
            "ocr_value": self.ocr_value,
            "vision_value": self.vision_value
        }
        if self.resolved_value is not None:
            out["resolved_value"] = self.resolved_value
        if self.preferred_source:
            out["preferred_source"] = self.preferred_source
        if self.reason:
            out["reason"] = self.reason
        return out


def resolve_field_conflict(
    field: str,
    ocr_val: Any,
    vision_val: Any,
    is_spatial_doc: bool = False
) -> Tuple[Any, str, str]:
    """
    Intelligent field-level resolver:
    - Printed / Tabular documents (Orders, Invoices, Acknowledgements, Tables):
        * Codes / SKUs / Quantities / Prices / Line numbers -> OCR preferred (deterministic)
        * Descriptions / Categories / Layout context -> Vision preferred (spatial understanding)
    - Drawings / Blueprints / Spatial diagrams:
        * Spatial annotations / descriptions / layout -> Vision preferred
    """
    if is_spatial_doc:
        if vision_val is not None and str(vision_val).strip() != "":
            return vision_val, "VISION", "Preferred Vision for diagram / spatial drawing context"
        return ocr_val, "OCR", "Fallback to OCR value"

    if field in _OCR_PREFERRED_FIELDS:
        if ocr_val is not None and str(ocr_val).strip() != "":
            return ocr_val, "OCR", f"Preferred OCR deterministic reading for {field}"
        return vision_val, "VISION", f"Fallback to Vision value for {field}"
    else:
        if vision_val is not None and str(vision_val).strip() != "":
            return vision_val, "VISION", f"Preferred Vision layout & descriptive context for {field}"
        return ocr_val, "OCR", f"Fallback to OCR value for {field}"


@dataclass
class ReconciledItem:
    item: Dict[str, Any]
    evidence_status: str  # "VERIFIED" | "UNCERTAIN"
    verification_method: str  # "OCR_PLUS_VISION" | "VISION_ONLY" | "OCR_ONLY" | "UNALIGNED"
    conflicts: List[FieldConflict] = field(default_factory=list)
    alignment_basis: Optional[str] = None  # None for exact-SKU alignment; else "DUPLICATE_GROUP_EVIDENCE" / "OCR_CANDIDATE_EVIDENCE"

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.item)
        out["evidence_status"] = self.evidence_status
        out["verification"] = {
            "method": self.verification_method,
            "status": self.evidence_status,
        }
        if self.conflicts:
            out["verification"]["conflicts"] = [c.to_dict() for c in self.conflicts]
        if self.alignment_basis:
            out["verification"]["alignment_basis"] = self.alignment_basis
        return out


def _candidate_key(item: Dict[str, Any]) -> Optional[str]:
    sku = normalize_sku(item.get("sku"))
    return sku or None


def _greedy_evidence_match(
    ocr_group: List[Dict[str, Any]], vision_group: List[Dict[str, Any]]
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Phase 3.1 §5/§7/§8/§15: within a group of items that already share the
    same normalized SKU (duplicate lines — e.g. the same cabinet ordered
    twice), pair OCR and Vision instances using page/description/quantity
    evidence rather than blind index order. Never pairs across a score
    below the threshold; leftover, unmatched instances on either side stay
    single-source (never deleted, never forced into a pair).
    """
    scored: List[Tuple[int, int, int]] = []  # (score, ocr_idx, vision_idx)
    for oi, o in enumerate(ocr_group):
        for vi, v in enumerate(vision_group):
            s = _evidence_score(o, v)
            if s >= _CANDIDATE_SCORE_THRESHOLD:
                scored.append((s, oi, vi))
    scored.sort(key=lambda t: -t[0])

    used_o, used_v = set(), set()
    pairs = []
    for s, oi, vi in scored:
        if oi in used_o or vi in used_v:
            continue
        used_o.add(oi)
        used_v.add(vi)
        pairs.append((ocr_group[oi], vision_group[vi]))
    return pairs


def _align(ocr_items: List[Dict[str, Any]], vision_items: List[Dict[str, Any]]) -> List[Tuple[Optional[Dict], Optional[Dict], Optional[str]]]:
    """
    Deterministic alignment between two extraction passes. Returns
    (ocr_item, vision_item, alignment_basis) triples; every raw item from
    both passes is preserved (accounted for exactly once).

    Phase 3.1 widens alignment in two evidence-gated ways beyond the
    original exact-1:1-SKU rule:
      1. Duplicate-SKU groups (same normalized SKU appearing >1x on one or
         both sides) are now paired via page/description/quantity evidence
         instead of being left entirely unaligned (§15).
      2. Items that remain unaligned are additionally checked against
         known-OCR-confusion SKU candidates on the OTHER pass, again gated
         by page/description/quantity evidence (§4/§5).
    Neither widening auto-verifies anything — an aligned pair still goes
    through the same strict Rule A-D field comparison, so a candidate pair
    whose SKU actually differs is still recorded as a conflict, not
    silently accepted.
    """
    ocr_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for it in ocr_items:
        key = _candidate_key(it)
        if key:
            ocr_by_key.setdefault(key, []).append(it)
    vision_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for it in vision_items:
        key = _candidate_key(it)
        if key:
            vision_by_key.setdefault(key, []).append(it)

    triples: List[Tuple[Optional[Dict], Optional[Dict], Optional[str]]] = []
    consumed_ocr_ids = set()
    consumed_vision_ids = set()

    # Pass 1: exact-SKU groups (clean 1:1 always aligns; duplicate groups
    # (len > 1 on either side) are resolved via evidence-gated pairing).
    for key, ocr_group in ocr_by_key.items():
        vision_group = vision_by_key.get(key, [])
        if not vision_group:
            continue
        if len(ocr_group) == 1 and len(vision_group) == 1:
            triples.append((ocr_group[0], vision_group[0], None))
            consumed_ocr_ids.add(id(ocr_group[0]))
            consumed_vision_ids.add(id(vision_group[0]))
        else:
            for o, v in _greedy_evidence_match(ocr_group, vision_group):
                triples.append((o, v, "DUPLICATE_GROUP_EVIDENCE"))
                consumed_ocr_ids.add(id(o))
                consumed_vision_ids.add(id(v))

    # Pass 2: OCR-candidate evidence-gated alignment for items still
    # unaligned after Pass 1 — never used if Pass 1 already resolved a SKU.
    remaining_ocr = [it for it in ocr_items if id(it) not in consumed_ocr_ids]
    remaining_vision = [it for it in vision_items if id(it) not in consumed_vision_ids]
    vision_key_index: Dict[str, List[Dict[str, Any]]] = {}
    for it in remaining_vision:
        key = _candidate_key(it)
        if key:
            vision_key_index.setdefault(key, []).append(it)

    candidate_scored: List[Tuple[int, Dict[str, Any], Dict[str, Any]]] = []
    for o in remaining_ocr:
        for cand_sku in _ocr_candidate_skus(o.get("sku")):
            for v in vision_key_index.get(cand_sku, []):
                if id(v) in consumed_vision_ids:
                    continue
                s = _evidence_score(o, v)
                # Candidate alignment additionally requires the two items to
                # share a page — SKU is already uncertain here, so page
                # agreement is a hard gate, not just a scoring bonus (§7).
                if o.get("page_number") is not None and o.get("page_number") == v.get("page_number") and s >= _CANDIDATE_SCORE_THRESHOLD:
                    candidate_scored.append((s, o, v))
    candidate_scored.sort(key=lambda t: -t[0])
    for s, o, v in candidate_scored:
        if id(o) in consumed_ocr_ids or id(v) in consumed_vision_ids:
            continue
        triples.append((o, v, "OCR_CANDIDATE_EVIDENCE"))
        consumed_ocr_ids.add(id(o))
        consumed_vision_ids.add(id(v))

    for it in ocr_items:
        if id(it) not in consumed_ocr_ids:
            triples.append((it, None, None))
    for it in vision_items:
        if id(it) not in consumed_vision_ids:
            triples.append((None, it, None))

    return triples


def reconcile_items(
    ocr_items: List[Dict[str, Any]],
    vision_items: List[Dict[str, Any]],
    doc_type: Optional[Any] = None
) -> List[ReconciledItem]:
    """
    Reconciles two independent extraction passes per §9's rules A-D:
    - Primary Engine: OCR for printed/tabular documents (Orders, Invoices, Acknowledgements),
      Vision for drawings/blueprints/spatial diagrams.
    - Field-level intelligent resolution:
        * Quantities / SKUs / Prices / Numeric codes -> OCR preferred (deterministic character matching)
        * Descriptions / Categories / Spatial layout -> Vision preferred (layout & visual context)
    - Full auditability: Conflicting readings are preserved on the item in `conflicts`
      and flagged with UNCERTAIN status for human review.
    """
    triples = _align(ocr_items, vision_items)
    results: List[ReconciledItem] = []
    
    doc_type_str = str(getattr(doc_type, "value", doc_type) or "").upper()
    is_spatial = any(k in doc_type_str for k in ("DESIGN", "DRAWING", "FLOOR_PLAN", "ELEVATION", "DIAGRAM"))

    for ocr_item, vision_item, basis in triples:
        if ocr_item is not None and vision_item is not None:
            conflicts: List[FieldConflict] = []
            
            # Start base from Vision (carries page/bounding evidence) and augment with OCR
            merged = dict(vision_item)
            for k, v in ocr_item.items():
                if merged.get(k) is None and v is not None:
                    merged[k] = v

            sku_agrees = normalize_sku(ocr_item.get("sku")) == normalize_sku(vision_item.get("sku"))
            if not sku_agrees:
                resolved_sku, pref_src, reason = resolve_field_conflict(
                    "sku", ocr_item.get("sku"), vision_item.get("sku"), is_spatial
                )
                conflicts.append(FieldConflict(
                    field="sku",
                    ocr_value=ocr_item.get("sku"),
                    vision_value=vision_item.get("sku"),
                    resolved_value=resolved_sku,
                    preferred_source=pref_src,
                    reason=reason
                ))
                merged["sku"] = resolved_sku

            for f in _COMPARABLE_FIELDS:
                ov, vv = _norm_value(f, ocr_item.get(f)), _norm_value(f, vision_item.get(f))
                # Rule B: one side has no value — keep whichever side has it
                if ov is None or vv is None:
                    if ov is not None and vv is None:
                        merged[f] = ocr_item.get(f)
                    continue
                
                # Rule C: both have values that disagree
                if ov != vv:
                    resolved_val, pref_src, reason = resolve_field_conflict(
                        f, ocr_item.get(f), vision_item.get(f), is_spatial
                    )
                    conflicts.append(FieldConflict(
                        field=f,
                        ocr_value=ocr_item.get(f),
                        vision_value=vision_item.get(f),
                        resolved_value=resolved_val,
                        preferred_source=pref_src,
                        reason=reason
                    ))
                    merged[f] = resolved_val

            if conflicts:
                results.append(ReconciledItem(merged, "UNCERTAIN", "OCR_PLUS_VISION", conflicts, basis))
            else:
                # Rule A: exact agreement on every comparable, non-empty field.
                results.append(ReconciledItem(merged, "VERIFIED", "OCR_PLUS_VISION", [], basis))
        elif vision_item is not None:
            results.append(ReconciledItem(dict(vision_item), "UNCERTAIN", "VISION_ONLY", []))
        elif ocr_item is not None:
            results.append(ReconciledItem(dict(ocr_item), "UNCERTAIN", "OCR_ONLY", []))

    return results
