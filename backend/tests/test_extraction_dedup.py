"""
Regression coverage for OpenAIProvider._dedupe_design_items — the text
pass and the Vision pass over a DESIGN PDF commonly both see the same
physical cabinet/trim callout, and this must be merged into one item, not
double-counted (observed live: a 3-count SHFB96FOL turned out to be two
real items plus one text/Vision duplicate).
"""
from app.integrations.ai.openai_provider import OpenAIProvider


def _provider():
    return OpenAIProvider()


def test_same_sku_same_page_is_merged():
    provider = _provider()
    items = [
        {"sku": "SHFB96FOL", "page_number": 7, "quantity": 2, "finish": None, "confidence": 1.0},
        {"sku": "SHFB96FOL", "page_number": 7, "quantity": 2, "finish": None, "confidence": 0.9},
    ]
    result = provider._dedupe_design_items(items)
    assert len(result) == 1


def test_same_sku_different_page_is_kept_separate():
    provider = _provider()
    items = [
        {"sku": "SHFB96FOL", "page_number": 7, "quantity": 2, "finish": None},
        {"sku": "SHFB96FOL", "page_number": 13, "quantity": 3, "finish": None, "notes": "Doorstyle changed to apex"},
    ]
    result = provider._dedupe_design_items(items)
    assert len(result) == 2


def test_merge_fills_in_missing_fields_from_either_pass():
    provider = _provider()
    items = [
        {"sku": "W1848L", "page_number": 2, "quantity": 1, "finish": None, "confidence": 0.6},
        {"sku": "W1848L", "page_number": 2, "quantity": 1, "finish": "Monroe Sagewood", "confidence": 0.95},
    ]
    result = provider._dedupe_design_items(items)
    assert len(result) == 1
    merged = result[0]
    assert merged["finish"] == "Monroe Sagewood"
    assert merged["confidence"] == 0.95


def test_items_without_page_number_are_never_dropped():
    # A page marker wasn't available for these (e.g. a single-image
    # drawing) — dedup has no safe key to merge on, so both must pass
    # through untouched rather than being silently discarded.
    provider = _provider()
    items = [
        {"sku": "TUKT", "page_number": None, "quantity": 1},
        {"sku": "TUKT", "page_number": None, "quantity": 1},
    ]
    result = provider._dedupe_design_items(items)
    assert len(result) == 2
