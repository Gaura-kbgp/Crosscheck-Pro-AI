"""
Phase 2 — DESIGN Vision Improvement Regression Tests.

Covers (without live API calls):
  1. DESIGN_EXTRACTION_VERSION is distinct from EXTRACTION_VERSION
  2. ORDER/ACK still use EXTRACTION_VERSION (unchanged)
  3. uncertain_vision flag wiring in openai_provider post-dedupe logic
  4. CrossCheckEngine reclassifies uncertain_vision DESIGN-only items as UNCERTAIN
  5. Normal DESIGN-only items still produce MISSING (flag not applied broadly)
  6. Vision Rules 10–12 are present in the prompt text
"""
import pytest
from uuid import uuid4

from app.worker.tasks.processing import EXTRACTION_VERSION, DESIGN_EXTRACTION_VERSION
from app.integrations.ai.prompts.design_vision_v1 import DESIGN_VISION_PROMPT_V1
from app.engines.crosscheck import CrossCheckEngine
from app.models.core import (
    CanonicalLineItem, DocumentType, MatchGroup, MatchGroupStatus,
    Severity, ItemCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item(source_type, sku, finish=None, qty=1, source_metadata=None):
    return CanonicalLineItem(
        id=uuid4(),
        project_id=uuid4(),
        organization_id=uuid4(),
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku,
        quantity=qty,
        finish=finish,
        source_metadata=source_metadata or {},
    )


def _mg(d=None, o=None, a=None, status=MatchGroupStatus.MISSING):
    proj_id = uuid4()
    org_id = uuid4()
    return MatchGroup(
        id=uuid4(),
        project_id=proj_id,
        organization_id=org_id,
        status=status,
        design_item_id=d.id if d else None,
        order_item_id=o.id if o else None,
        ack_item_id=a.id if a else None,
        design_item=d,
        order_item=o,
        ack_item=a,
    )


# ---------------------------------------------------------------------------
# 1. Cache version constants
# ---------------------------------------------------------------------------

def test_design_version_different_from_global():
    """DESIGN must use a different cache version from ORDER/ACK."""
    assert DESIGN_EXTRACTION_VERSION != EXTRACTION_VERSION

def test_design_version_value():
    assert DESIGN_EXTRACTION_VERSION == "f8.3.8"

def test_global_version_unchanged():
    """ORDER/ACK cache version must stay at f8.3.6."""
    assert EXTRACTION_VERSION == "f8.3.6"


# ---------------------------------------------------------------------------
# 2. Vision prompt Rules 10–12 present
# ---------------------------------------------------------------------------

def test_vision_prompt_has_rule_10_partial_labels():
    assert "PARTIAL OR UNREADABLE LABELS" in DESIGN_VISION_PROMPT_V1
    assert "confidence < 0.4" in DESIGN_VISION_PROMPT_V1

def test_vision_prompt_has_rule_11_revision_notes():
    assert "REVISION NOTES" in DESIGN_VISION_PROMPT_V1
    assert "Updated X to Y" in DESIGN_VISION_PROMPT_V1

def test_vision_prompt_has_rule_12_display_assignment():
    assert "DISPLAY ASSIGNMENT BY PROXIMITY" in DESIGN_VISION_PROMPT_V1
    assert "finish color" in DESIGN_VISION_PROMPT_V1


# ---------------------------------------------------------------------------
# 3. CrossCheckEngine: uncertain_vision → UNCERTAIN (not MISSING)
# ---------------------------------------------------------------------------

def test_uncertain_vision_design_only_item_stays_missing():
    """
    Option A: uncertain_vision=True must NOT change MatchGroup status.
    The item remains MISSING so genuine discrepancies are not hidden.
    The flag is preserved in source_metadata for reviewer visibility.
    """
    proj_id = uuid4()
    org_id = uuid4()
    d = _item(DocumentType.DESIGN, "BFL12", source_metadata={"uncertain_vision": True})
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    discs = CrossCheckEngine().evaluate([mg], proj_id, org_id)

    # Status must remain MISSING — not promoted to UNCERTAIN
    assert mg.status == MatchGroupStatus.MISSING
    assert any(disc.field == "item_presence" for disc in discs)
    # Flag is preserved in source_metadata (not stripped by crosscheck)
    assert d.source_metadata.get("uncertain_vision") is True


def test_uncertain_vision_low_confidence_flag_does_not_suppress_discrepancy():
    """
    Low-confidence Vision-only item must still produce a MISSING item_presence
    discrepancy so it appears in the report for human review.
    """
    proj_id = uuid4()
    org_id = uuid4()
    d = _item(DocumentType.DESIGN, "H9KB", source_metadata={"uncertain_vision": True})
    d.item_category = ItemCategory.CABINET
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    discs = CrossCheckEngine().evaluate([mg], proj_id, org_id)
    assert mg.status == MatchGroupStatus.MISSING
    assert any(disc.field == "item_presence" and disc.severity == Severity.CRITICAL for disc in discs)


def test_normal_design_only_item_still_missing():
    """
    DESIGN-only item WITHOUT uncertain_vision must still produce a MISSING
    item_presence discrepancy — the flag must not be applied broadly.
    """
    proj_id = uuid4()
    org_id = uuid4()
    d = _item(DocumentType.DESIGN, "W3036", source_metadata={})
    d.item_category = ItemCategory.CABINET  # explicit category → CRITICAL severity
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    discs = CrossCheckEngine().evaluate([mg], proj_id, org_id)

    # Status must NOT be changed to UNCERTAIN
    assert mg.status == MatchGroupStatus.MISSING
    assert any(disc.field == "item_presence" and disc.severity == Severity.CRITICAL for disc in discs)


def test_uncertain_vision_flag_not_set_means_missing():
    """Absence of uncertain_vision key defaults to standard MISSING handling."""
    proj_id = uuid4()
    org_id = uuid4()
    # source_metadata without the key at all
    d = _item(DocumentType.DESIGN, "LSC8", source_metadata={"view_type": "ELEVATION"})
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    discs = CrossCheckEngine().evaluate([mg], proj_id, org_id)
    assert mg.status == MatchGroupStatus.MISSING


# ---------------------------------------------------------------------------
# 4. uncertain_vision flag logic (openai_provider post-dedupe unit)
# ---------------------------------------------------------------------------

def _apply_uncertain_vision_flag(merged_items, vision_items):
    """
    Mirror of the flag logic in openai_provider.py _extract_structured_data
    for the vector-PDF DESIGN path — extracted here for isolated unit testing.
    """
    _text_keys = {
        ((i.get("sku") or "").strip().upper(), i.get("page_number"))
        for i in merged_items
        if i.get("sku") and i.get("page_number") is not None
    }

    all_items = merged_items + vision_items
    # simulate _dedupe_design_items (simplistic: no key conflicts in these tests)
    result = list(all_items)

    for item in result:
        sku = (item.get("sku") or "").strip().upper()
        page = item.get("page_number")
        if (sku and page is not None
                and (sku, page) not in _text_keys
                and (item.get("confidence") or 1.0) < 0.4):
            item["uncertain_vision"] = True

    return result


def test_vision_only_low_confidence_flagged():
    text_items = [{"sku": "W3036", "page_number": 5, "confidence": 0.9}]
    vision_items = [{"sku": "BFL12", "page_number": 3, "confidence": 0.2}]
    result = _apply_uncertain_vision_flag(text_items, vision_items)
    bfl12 = next(i for i in result if i["sku"] == "BFL12")
    assert bfl12.get("uncertain_vision") is True


def test_vision_only_high_confidence_not_flagged():
    text_items = []
    vision_items = [{"sku": "MCV144", "page_number": 7, "confidence": 0.85}]
    result = _apply_uncertain_vision_flag(text_items, vision_items)
    mcv = next(i for i in result if i["sku"] == "MCV144")
    assert "uncertain_vision" not in mcv


def test_text_confirmed_item_not_flagged_even_if_low_vision_confidence():
    """Item seen by text pass must NEVER be flagged, even if Vision confidence is low."""
    text_items = [{"sku": "W3036", "page_number": 5, "confidence": 0.9}]
    # Same SKU+page from Vision with low confidence — text already confirmed it
    vision_items = [{"sku": "W3036", "page_number": 5, "confidence": 0.1}]
    result = _apply_uncertain_vision_flag(text_items, vision_items)
    w3036_items = [i for i in result if i.get("sku") == "W3036"]
    for item in w3036_items:
        assert "uncertain_vision" not in item


def test_confidence_exactly_04_not_flagged():
    """Boundary: confidence == 0.4 is NOT uncertain (threshold is strictly < 0.4)."""
    text_items = []
    vision_items = [{"sku": "SHC3", "page_number": 2, "confidence": 0.4}]
    result = _apply_uncertain_vision_flag(text_items, vision_items)
    shc3 = next(i for i in result if i["sku"] == "SHC3")
    assert "uncertain_vision" not in shc3


# ---------------------------------------------------------------------------
# 5. Option A mandatory regression — uncertain_vision never suppresses discrepancies
# ---------------------------------------------------------------------------

def test_option_a_uncertain_vision_item_produces_missing_discrepancy():
    """
    Option A: an uncertain_vision=True item on DESIGN that has no ORDER/ACK match
    must produce a MISSING item_presence discrepancy, not be silently reclassified.
    This is the core invariant that prevents hiding genuine discrepancies.
    """
    proj_id = uuid4()
    org_id = uuid4()
    d = _item(DocumentType.DESIGN, "TUKT", source_metadata={"uncertain_vision": True})
    d.item_category = ItemCategory.CABINET
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    discs = CrossCheckEngine().evaluate([mg], proj_id, org_id)

    assert mg.status == MatchGroupStatus.MISSING, "uncertain_vision must not change MatchGroup status"
    assert any(disc.field == "item_presence" and disc.severity == Severity.CRITICAL for disc in discs), \
        "MISSING CABINET item must still produce a CRITICAL item_presence discrepancy"


def test_option_a_uncertain_vision_flag_preserved_in_metadata():
    """Flag must stay in source_metadata after crosscheck — not stripped."""
    proj_id = uuid4()
    org_id = uuid4()
    d = _item(DocumentType.DESIGN, "SM96", source_metadata={"uncertain_vision": True})
    mg = _mg(d=d, status=MatchGroupStatus.MISSING)

    CrossCheckEngine().evaluate([mg], proj_id, org_id)

    assert d.source_metadata.get("uncertain_vision") is True


def test_option_a_no_uncertain_match_groups_from_vision_flag():
    """
    No MatchGroup should be set to UNCERTAIN solely because of uncertain_vision.
    Option A: the crosscheck engine never touches MatchGroup.status for this flag.
    """
    proj_id = uuid4()
    org_id = uuid4()
    items = [
        _item(DocumentType.DESIGN, f"SKU{i}", source_metadata={"uncertain_vision": True})
        for i in range(5)
    ]
    mgs = [_mg(d=d, status=MatchGroupStatus.MISSING) for d in items]
    for d in items:
        d.item_category = ItemCategory.CABINET

    CrossCheckEngine().evaluate(mgs, proj_id, org_id)

    uncertain_count = sum(1 for m in mgs if m.status == MatchGroupStatus.UNCERTAIN)
    assert uncertain_count == 0, f"{uncertain_count} groups became UNCERTAIN — must be 0 with Option A"
