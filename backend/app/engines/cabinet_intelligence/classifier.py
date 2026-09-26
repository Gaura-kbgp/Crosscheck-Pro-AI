"""
Cabinet Code Intelligence — the manufacturer-aware classification layer.

Decision hierarchy (spec-required, evidence-gated at every tier):

    exact manufacturer dictionary match       -> HIGH,   MANUFACTURER_EXACT
    manufacturer dictionary alias match       -> HIGH,   MANUFACTURER_ALIAS
    (spec-book evidence — reserved, not built)
    existing generic ItemClassifier           -> MEDIUM/LOW/UNCERTAIN, NKBA_GENERIC / PATTERN_ONLY / DOCUMENT_CONTEXT / NONE

Critical backward-compatibility rule: when no manufacturer is configured for
a project (the dictionary lookup is unconfigured), this class calls the
existing ItemClassifier with EXACTLY the same arguments it already receives
today, and never modifies `category`/`confidence` — only ADDS the richer
CabinetCodeDecision wrapper. Every existing classification test must see
identical `item_category`/`category_confidence` output in that case.

This module never fabricates a cabinet code, never treats a SKU pattern as
proof of identity, and never treats an unresolved OCR/Vision conflict as
resolved — it only adds manufacturer verification ON TOP of the existing,
unmodified classifier and reconciliation output.
"""
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.core import DocumentType, ItemCategory
from app.engines.classification import ItemClassifier
from app.engines.normalization import normalize_sku
from app.engines.cabinet_intelligence.dictionary import ManufacturerCodeDictionaryLookup
from app.engines.cabinet_intelligence.models import CabinetCodeDecision, ConfidenceLevel, VerificationSource

# Categories the existing ItemClassifier can return that represent a
# confident non-cabinet exclusion (§12/§13) — mirrored here only to choose a
# reason code, never to change the category itself.
_EXCLUSION_REASON_CODES = {
    ItemCategory.COMMERCIAL_CHARGE: "NON_CABINET_CHARGE",
    ItemCategory.MOLDING: "NON_CABINET_MOLDING",
    ItemCategory.ACCESSORY: "NON_CABINET_ACCESSORY",
    ItemCategory.APPLIANCE: "NON_CABINET_APPLIANCE",
    ItemCategory.ARCHITECTURAL_ANNOTATION: "NON_CABINET_ANNOTATION",
}


class CabinetCodeIntelligence:
    """
    Instantiate once per document-processing run (mirrors how ItemClassifier
    is already instantiated once per run in processing.py) so the
    manufacturer dictionary is loaded a single time (§37), not per item.
    """

    def __init__(self, db: Session, manufacturer_id: Optional[UUID] = None):
        self.dictionary = ManufacturerCodeDictionaryLookup(db, manufacturer_id)
        self.fallback_classifier = ItemClassifier()

    def analyze_candidate(
        self,
        raw_sku: Optional[str],
        description: Optional[str] = None,
        dimensions: Optional[Any] = None,
        modifications: Optional[Any] = None,
        quantity: Optional[Any] = None,
        source_type: Optional[DocumentType] = None,
        page_number: Optional[int] = None,
        source_text: Optional[str] = None,
        reconciliation_verification: Optional[dict] = None,
        candidate_skus: Optional[List[str]] = None,
    ) -> CabinetCodeDecision:
        normalized = normalize_sku(raw_sku)
        candidate_variants = [c for c in ([raw_sku] + list(candidate_skus or [])) if c]

        reconciliation_conflicts = (reconciliation_verification or {}).get("conflicts") or []
        has_unresolved_sku_conflict = any(c.get("field") == "sku" for c in reconciliation_conflicts)

        # ---- Tier 1 & 2: manufacturer dictionary (exact + curated alias) ----
        # Every candidate spelling is tried in order (primary raw_sku first,
        # then any extra spellings from an unresolved OCR/Vision conflict) —
        # a dictionary hit on ANY of them is real, curated evidence, not a
        # guess; it never changes which raw value is stored, only the
        # classification/confidence attached to it.
        if self.dictionary.is_configured:
            for spelling in [normalized] + [normalize_sku(c) for c in (candidate_skus or [])]:
                if not spelling:
                    continue
                entry = self.dictionary.exact_match(spelling)
                if entry:
                    is_alias = not entry.is_primary_alias
                    variants = self.dictionary.alias_siblings(entry)
                    return CabinetCodeDecision(
                        raw_code=raw_sku,
                        normalized_code=normalized,
                        classification=entry.category,
                        is_verified=True,
                        confidence_level=ConfidenceLevel.HIGH,
                        confidence_score=0.98,
                        verification_source=VerificationSource.MANUFACTURER_ALIAS if is_alias else VerificationSource.MANUFACTURER_EXACT,
                        evidence={
                            "manufacturer_match": True,
                            "matched_spelling": spelling,
                            "dictionary_code": entry.code,
                            "alias_group": entry.alias_group,
                            "page_number": page_number,
                            "source_text": source_text,
                        },
                        candidate_variants=list(dict.fromkeys(candidate_variants + variants)),
                        reason_codes=["MANUFACTURER_ALIAS_MATCH" if is_alias else "EXACT_MANUFACTURER_MATCH"],
                        notes=[f"Matched manufacturer dictionary entry '{entry.code}'" + (f" (alias of '{entry.code}')" if is_alias else "")],
                    )

        # ---- Tier 3 (spec-book evidence) — reserved, not implemented ----
        # No spec-book indexing exists yet (out of scope this phase); this
        # tier intentionally falls through rather than fabricating a match.

        # ---- Tier 4: existing generic classifier, UNCHANGED ----
        result = self.fallback_classifier.classify(
            raw_sku=raw_sku,
            description=description,
            dimensions=dimensions,
            modifications=modifications,
            source_type=source_type,
        )
        matched_rules = (result.evidence or {}).get("matched_rules") or []

        verification_source = VerificationSource.NONE
        reason_codes: List[str] = []
        notes: List[str] = []

        if result.category in _EXCLUSION_REASON_CODES:
            verification_source = VerificationSource.DOCUMENT_CONTEXT if any(r.startswith("description_keyword") for r in matched_rules) else VerificationSource.PATTERN_ONLY
            reason_codes.append(_EXCLUSION_REASON_CODES[result.category])
        elif any(r.startswith("description_keyword") for r in matched_rules):
            verification_source = VerificationSource.DOCUMENT_CONTEXT
            reason_codes.append("DOCUMENT_CONTEXT_MATCH")
        elif any(r.startswith("sku_pattern") for r in matched_rules):
            verification_source = VerificationSource.NKBA_GENERIC
            reason_codes.append("NKBA_PATTERN_MATCH")
        elif any(r.startswith("compound_sku_token") or r.startswith("dimensional_heuristic") for r in matched_rules):
            verification_source = VerificationSource.PATTERN_ONLY
            reason_codes.append("NKBA_PATTERN_MATCH")
        elif result.reason == "ambiguous_unmatched":
            verification_source = VerificationSource.NONE
            reason_codes.append("AMBIGUOUS_SKU")
        else:
            reason_codes.append("INSUFFICIENT_EVIDENCE")

        if self.dictionary.is_configured and normalized:
            reason_codes.append("NO_MANUFACTURER_MATCH")

        # Confidence bucketing per §24. A pure pattern/keyword match from the
        # generic classifier is never HIGH here — HIGH is reserved for real
        # manufacturer/spec-book evidence, so this tier cannot inflate
        # "verified cabinet" counts on its own.
        if result.confidence >= 0.85 and verification_source in (VerificationSource.DOCUMENT_CONTEXT, VerificationSource.NKBA_GENERIC):
            confidence_level = ConfidenceLevel.MEDIUM
        elif result.confidence >= 0.6:
            confidence_level = ConfidenceLevel.LOW
        elif result.confidence > 0:
            confidence_level = ConfidenceLevel.LOW
        else:
            confidence_level = ConfidenceLevel.UNCERTAIN

        # §24: an unresolved OCR/Vision SKU disagreement with no manufacturer
        # confirmation must never present as anything better than UNCERTAIN,
        # regardless of how confident the generic pattern/keyword match was —
        # the underlying SKU itself is in dispute.
        if has_unresolved_sku_conflict and confidence_level != ConfidenceLevel.UNCERTAIN:
            confidence_level = ConfidenceLevel.UNCERTAIN
            reason_codes.append("OCR_VISION_CONFLICT")
            notes.append("Underlying SKU has an unresolved OCR/Vision disagreement; category evidence alone cannot verify it.")
        elif reconciliation_verification and reconciliation_verification.get("status") == "VERIFIED":
            reason_codes.append("OCR_VISION_AGREEMENT")

        is_verified = confidence_level in (ConfidenceLevel.HIGH,)

        return CabinetCodeDecision(
            raw_code=raw_sku,
            normalized_code=normalized,
            classification=result.category,
            is_verified=is_verified,
            confidence_level=confidence_level,
            confidence_score=result.confidence,
            verification_source=verification_source,
            evidence={**(result.evidence or {}), "page_number": page_number, "source_text": source_text},
            exclusion_reason=result.reason if result.category in _EXCLUSION_REASON_CODES else None,
            candidate_variants=candidate_variants,
            reason_codes=reason_codes,
            notes=notes,
        )
