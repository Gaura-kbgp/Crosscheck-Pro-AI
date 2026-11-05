"""
Regression tests for session 10 fixes:
  - Issue 2: APPLIANCE misclassification via display-header description
  - Issue 1: Cross-display merging of no-finish DESIGN items → AMBIGUOUS_DUPLICATE
  - Issue 1b: Vision gate missing-finish condition
"""
import pytest
from uuid import uuid4
from app.models.core import (
    CanonicalLineItem, DocumentType, ItemCategory, MatchGroupStatus
)
from app.engines.classification import ItemClassifier
from app.engines.matching import MatchingEngine, aggregate_document_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_item(source_type, sku, qty=1, finish=None, door_style=None, view_type=None, position=None):
    item = CanonicalLineItem(
        id=uuid4(),
        project_id=uuid4(),
        organization_id=uuid4(),
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku.upper(),
        quantity=qty,
        finish=finish,
        door_style=door_style,
    )
    if view_type or position:
        item.source_metadata = {
            "view_type": view_type,
            "position": position,
        }
    return item


# ---------------------------------------------------------------------------
# Issue 2: Display-header description must NOT drive classification
# ---------------------------------------------------------------------------

class TestDisplayHeaderClassification:
    def setup_method(self):
        self.clf = ItemClassifier()

    def test_wall_cabinet_with_display_header_desc(self):
        """W1848L described as 'Display 1 – 48in Range Kitchen' must be CABINET."""
        res = self.clf.classify(raw_sku="W1848L", description="Display 1 – 48in Range Kitchen")
        assert res.category == ItemCategory.CABINET, (
            f"Expected CABINET, got {res.category} (rules: {res.evidence['matched_rules']})"
        )

    def test_wall_cabinet_right_with_display_header_desc(self):
        """W1848R described as 'Display 1 – 48in Range Kitchen' must be CABINET."""
        res = self.clf.classify(raw_sku="W1848R", description="Display 1 – 48in Range Kitchen")
        assert res.category == ItemCategory.CABINET

    def test_flat_shelf_with_display_header_desc(self):
        """FLTSHF24 described as 'Display 5 – Double Oven Kitchen' must NOT be APPLIANCE."""
        res = self.clf.classify(raw_sku="FLTSHF24", description="Display 5 – Double Oven Kitchen")
        assert res.category != ItemCategory.APPLIANCE, (
            f"FLTSHF24 classified as APPLIANCE via display header — must not be"
        )

    def test_display_header_with_em_dash(self):
        """Em-dash variant 'Display 3 — 36in Range Kitchen' is stripped."""
        res = self.clf.classify(raw_sku="W3030", description="Display 3 — 36in Range Kitchen")
        assert res.category == ItemCategory.CABINET

    def test_display_header_with_hyphen(self):
        """Hyphen variant 'Display 2 - Built-In' is stripped."""
        res = self.clf.classify(raw_sku="B24", description="Display 2 - Built-In Cabinet")
        assert res.category == ItemCategory.CABINET

    def test_real_appliance_still_classified(self):
        """A genuine appliance description still returns APPLIANCE."""
        res = self.clf.classify(raw_sku="REF36", description="36 inch refrigerator")
        assert res.category == ItemCategory.APPLIANCE

    def test_real_range_desc_not_header(self):
        """'gas range top' (no Display N prefix) is a real appliance description."""
        res = self.clf.classify(raw_sku="RNG30", description="30in gas range top")
        assert res.category == ItemCategory.APPLIANCE

    def test_non_header_range_kitchen_passthrough(self):
        """'Range kitchen hood' without 'Display N' prefix is NOT stripped → hood/range = APPLIANCE."""
        res = self.clf.classify(raw_sku="HOOD42", description="42in range hood")
        assert res.category == ItemCategory.APPLIANCE


# ---------------------------------------------------------------------------
# Issue 1: Position in aggregate_document_items group key
# ---------------------------------------------------------------------------

class TestAggregateDocumentItemsPositionKey:

    def test_same_sku_no_finish_different_displays_stay_separate(self):
        """
        TUKT with no finish in Display 2 and TUKT with no finish in Display 6
        must NOT be merged — they are physically separate cabinets.
        """
        d2 = make_item(DocumentType.DESIGN, "TUKT", finish=None,
                       view_type="ELEVATION", position="Display 2: Built-In")
        d6 = make_item(DocumentType.DESIGN, "TUKT", finish=None,
                       view_type="ELEVATION", position="Display 6 Mudroom")
        units = aggregate_document_items([d2, d6])
        assert len(units) == 2, (
            f"Expected 2 separate units for Display 2 and Display 6 TUKT, got {len(units)}"
        )

    def test_same_sku_no_finish_same_display_merges(self):
        """
        Two TUKT items with no finish from the same display (same position key)
        still merge normally.
        """
        a = make_item(DocumentType.DESIGN, "TUKT", qty=1, finish=None,
                      view_type="ELEVATION", position="Display 2: Built-In")
        b = make_item(DocumentType.DESIGN, "TUKT", qty=2, finish=None,
                      view_type="ELEVATION", position="Display 2: Built-In")
        units = aggregate_document_items([a, b])
        assert len(units) == 1
        assert units[0].aggregate_quantity == 3

    def test_same_sku_different_finishes_always_separate(self):
        """Existing behavior: different finishes → different units (unchanged)."""
        a = make_item(DocumentType.DESIGN, "SM96", finish="SAGEWOOD",
                      view_type="ELEVATION", position="Display 1: Range Kitchen")
        b = make_item(DocumentType.DESIGN, "SM96", finish="CASHMERE",
                      view_type="ELEVATION", position="Display 3: Range Kitchen")
        units = aggregate_document_items([a, b])
        assert len(units) == 2

    def test_items_without_view_type_still_merge_on_sku_finish(self):
        """ORDER and ACK items (no view_type) are unaffected by the position change."""
        a = make_item(DocumentType.ORDER, "W3030", qty=1, finish="SAGEWOOD")
        b = make_item(DocumentType.ORDER, "W3030", qty=1, finish="SAGEWOOD")
        units = aggregate_document_items([a, b])
        assert len(units) == 1
        assert units[0].aggregate_quantity == 2

    def test_different_displays_no_finish_quantities_preserved(self):
        """Quantity from each separate display unit is correct (qty=1 each, not merged qty=2)."""
        d2 = make_item(DocumentType.DESIGN, "QR96", qty=1, finish=None,
                       view_type="ELEVATION", position="Display 2: Built-In")
        d6 = make_item(DocumentType.DESIGN, "QR96", qty=1, finish=None,
                       view_type="ELEVATION", position="Display 6 Mudroom")
        units = aggregate_document_items([d2, d6])
        assert len(units) == 2
        assert all(u.aggregate_quantity == 1 for u in units)


# ---------------------------------------------------------------------------
# Issue 1b: Vision gate — missing-finish ELEVATION pages flagged
# ---------------------------------------------------------------------------

class TestVisionGateMissingFinish:
    """Tests for the missing-finish condition in _vision_pages_needed."""

    def setup_method(self):
        from app.integrations.ai.openai_provider import OpenAIProvider
        self.provider = OpenAIProvider.__new__(OpenAIProvider)
        # Minimal init
        self.provider.model_name = "gpt-4o"
        self.provider._MODEL_PRICING = {}

    def _make_page(self, pn, status="TEXT", n_blocks=5, raw_text="a" * 100):
        return {"page_number": pn, "status": status, "blocks": ["block"] * n_blocks, "raw_text": raw_text}

    def test_elevation_page_all_missing_finish_flagged(self):
        """Page 19 with ELEVATION items all lacking finish must be flagged."""
        page_evidence = [self._make_page(19)]
        text_items = [
            {"sku": "tukt", "quantity": 1, "finish": None, "view_type": "ELEVATION", "page_number": 19},
            {"sku": "sm96", "quantity": 1, "finish": None, "view_type": "ELEVATION", "page_number": 19},
        ]
        result = self.provider._vision_pages_needed(page_evidence, text_items)
        assert 19 in result, "Page 19 (ELEVATION items with no finish) must be flagged for Vision"

    def test_elevation_page_with_finish_not_flagged(self):
        """Page with ELEVATION items that have finish must NOT be flagged (unless another condition)."""
        page_evidence = [self._make_page(4)]
        text_items = [
            {"sku": "TUKT", "quantity": 2, "finish": "SAGEWOOD", "view_type": "ELEVATION", "page_number": 4},
            {"sku": "SM96", "quantity": 1, "finish": "SAGEWOOD", "view_type": "ELEVATION", "page_number": 4},
        ]
        result = self.provider._vision_pages_needed(page_evidence, text_items)
        assert 4 not in result, "Page 4 (ELEVATION items with finish) must NOT be flagged"

    def test_elevation_page_partial_finish_not_flagged(self):
        """If at least one ELEVATION item has a finish, page is not flagged by this condition."""
        page_evidence = [self._make_page(7)]
        text_items = [
            {"sku": "TUKT", "quantity": 1, "finish": "DEWDROP", "view_type": "ELEVATION", "page_number": 7},
            {"sku": "SM96", "quantity": 1, "finish": None, "view_type": "ELEVATION", "page_number": 7},
        ]
        result = self.provider._vision_pages_needed(page_evidence, text_items)
        # Only flagged if ALL elevation items lack finish
        assert 7 not in result, "Partial finish (some items have finish) must not trigger the condition"

    def test_mixed_view_types_non_elevation_no_finish_not_flagged(self):
        """FLOORPLAN items with no finish must NOT trigger the missing-finish Vision condition."""
        page_evidence = [self._make_page(5)]
        text_items = [
            {"sku": "W3030", "quantity": 1, "finish": None, "view_type": "FLOORPLAN", "page_number": 5},
        ]
        result = self.provider._vision_pages_needed(page_evidence, text_items)
        assert 5 not in result

    def test_empty_page_still_flagged_regardless(self):
        """EMPTY pages are still flagged via the existing condition (no regression)."""
        page_evidence = [{"page_number": 3, "status": "EMPTY", "blocks": 0, "raw_text": ""}]
        result = self.provider._vision_pages_needed(page_evidence, [])
        assert 3 in result

    def test_no_page_evidence_returns_none(self):
        """No page evidence → None (Vision all pages) — existing behavior preserved."""
        result = self.provider._vision_pages_needed([], [])
        assert result is None


# ---------------------------------------------------------------------------
# Issue 3: SHC3 is correctly MATCHED — verify no regression
# ---------------------------------------------------------------------------

class TestSHC3MatchedCorrect:
    """SHC3 DESIGN qty=2, ORDER qty=2 must result in MATCHED (not MISSING/discrepancy)."""

    def test_shc3_design_and_order_match(self):
        proj_id = uuid4()
        org_id = uuid4()
        matcher = MatchingEngine()

        d = make_item(DocumentType.DESIGN, "SHC3", qty=2, finish=None,
                      view_type="FLOORPLAN", position="Display 4: Island")
        o1 = make_item(DocumentType.ORDER, "SHC3", qty=1, finish="APEX OAK JUTE")
        o2 = make_item(DocumentType.ORDER, "SHC3", qty=1, finish="APEX OAK JUTE")

        groups = matcher.match_items([d], [o1, o2], [], proj_id, org_id)
        matched = [g for g in groups if g.status == MatchGroupStatus.MATCHED]
        assert matched, "SHC3 with matching design and order quantities must be MATCHED"
        assert all(g.status != MatchGroupStatus.UNCERTAIN for g in groups), (
            "SHC3 must not be UNCERTAIN"
        )
