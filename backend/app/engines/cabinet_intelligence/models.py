"""
Cabinet Code Intelligence — decision model.

A CabinetCodeDecision is the auditable output of CabinetCodeIntelligence: it
never overwrites raw extraction data (raw_code is preserved verbatim
alongside normalized_code and any candidate_variants), and it always records
*why* a classification/confidence was reached via machine-readable
reason_codes, so a human reviewer can answer "why did CrossCheckPro decide
this was a cabinet code?" without reading model internals.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import enum

from app.models.core import ItemCategory


class ConfidenceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNCERTAIN = "UNCERTAIN"


class VerificationSource(str, enum.Enum):
    MANUFACTURER_EXACT = "MANUFACTURER_EXACT"
    MANUFACTURER_ALIAS = "MANUFACTURER_ALIAS"
    SPEC_BOOK = "SPEC_BOOK"
    DOCUMENT_CONTEXT = "DOCUMENT_CONTEXT"
    NKBA_GENERIC = "NKBA_GENERIC"
    PATTERN_ONLY = "PATTERN_ONLY"
    OCR_CANDIDATE = "OCR_CANDIDATE"
    VISION_CANDIDATE = "VISION_CANDIDATE"
    NONE = "NONE"


# Categories eligible to participate in Design<->PO<->Ack physical
# discrepancy matching, per app.engines.crosscheck.CATEGORY_DISCREPANCY_POLICY
# (kept as a local, read-only mirror for UI/reporting convenience — the
# actual enforcement stays solely in crosscheck.py, never duplicated here).
_CABINET_CANDIDATE_CATEGORIES = {ItemCategory.CABINET, ItemCategory.PANEL, ItemCategory.FILLER}


@dataclass
class CabinetCodeDecision:
    raw_code: Optional[str]
    normalized_code: Optional[str]

    classification: ItemCategory
    is_verified: bool
    confidence_level: ConfidenceLevel
    confidence_score: float
    verification_source: VerificationSource

    evidence: Dict[str, Any] = field(default_factory=dict)
    exclusion_reason: Optional[str] = None
    candidate_variants: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def is_cabinet_candidate(self) -> bool:
        return self.classification in _CABINET_CANDIDATE_CATEGORIES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_code": self.raw_code,
            "normalized_code": self.normalized_code,
            "classification": self.classification.value,
            "is_cabinet_candidate": self.is_cabinet_candidate,
            "is_verified": self.is_verified,
            "confidence_level": self.confidence_level.value,
            "confidence_score": self.confidence_score,
            "verification_source": self.verification_source.value,
            "evidence": self.evidence,
            "exclusion_reason": self.exclusion_reason,
            "candidate_variants": self.candidate_variants,
            "reason_codes": self.reason_codes,
            "notes": self.notes,
        }
