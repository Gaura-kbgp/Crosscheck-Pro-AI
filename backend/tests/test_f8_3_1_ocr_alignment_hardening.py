"""
F8.3 Phase 3.1 tests: OCR-safe SKU candidate generation and evidence-gated
alignment widening (duplicate-SKU groups, OCR-candidate near-misses).

These tests exist because the Phase 3 diagnostic audit (real Mark Kitchen
run) found that ~20 of ~82 unaligned OCR_ONLY/VISION_ONLY items shared an
EXACT normalized SKU with a counterpart on the other pass but were never
compared because they were part of a duplicate-SKU group (same SKU ordered
more than once), which the original _align() intentionally excluded as
"ambiguous." Every test here has an explicit negative counterpart per the
spec's requirement that no new normalization rule ships without one.
"""
from app.engines.reconciliation import reconcile_items, _ocr_candidate_skus, _align


class TestOCRCandidateGeneration:
    def test_known_substitution_pairs_included(self):
        # B -> 8 is a known OCR confusion pair
        candidates = _ocr_candidate_skus("BFHC12")
        assert "8FHC12" in candidates

    def test_original_sku_always_included(self):
        candidates = _ocr_candidate_skus("BFHC12")
        assert "BFHC12" in candidates

    def test_unrelated_characters_never_substituted(self):
        """No global/unsafe substitution: characters outside the known
        confusion set (e.g. 'F', 'H', 'C') must never be varied."""
        candidates = _ocr_candidate_skus("BFHC12")
        for cand in candidates:
            assert cand[1] == "F" and cand[2] == "H" and cand[3] == "C", (
                f"unexpected substitution outside known pairs: {cand}"
            )

    def test_empty_sku_yields_no_candidates(self):
        assert _ocr_candidate_skus(None) == set()
        assert _ocr_candidate_skus("") == set()

    def test_candidate_set_is_bounded(self):
        """Combinatorial explosion guard: a long SKU with many substitutable
        characters must still yield a bounded candidate set, not blow up."""
        candidates = _ocr_candidate_skus("BOISBOISBOISBOIS")
        assert len(candidates) < 5000


class TestDuplicateGroupEvidenceAlignment:
    def test_duplicate_sku_group_aligns_via_page_and_description(self):
        """Two OCR items and two Vision items share the same SKU (a cabinet
        ordered twice) — previously entirely excluded from alignment. With
        matching pages and descriptions, both pairs must now align and, since
        every field agrees, both must be VERIFIED."""
        ocr_items = [
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 15},
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 16},
        ]
        vision_items = [
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 15},
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 16},
        ]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 2
        assert all(r.verification_method == "OCR_PLUS_VISION" for r in results)
        assert all(r.evidence_status == "VERIFIED" for r in results)
        assert all(r.alignment_basis == "DUPLICATE_GROUP_EVIDENCE" for r in results)

    def test_duplicate_sku_group_without_evidence_stays_unaligned(self):
        """Negative case: same duplicate SKU, but nothing (page, description,
        quantity) corroborates which OCR instance goes with which Vision
        instance — must NOT be blindly paired by list order."""
        ocr_items = [
            {"sku": "W3930", "description": None, "quantity": None, "page_number": None},
            {"sku": "W3930", "description": None, "quantity": None, "page_number": None},
        ]
        vision_items = [
            {"sku": "W3930", "description": None, "quantity": None, "page_number": None},
            {"sku": "W3930", "description": None, "quantity": None, "page_number": None},
        ]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 4
        assert all(r.verification_method in ("OCR_ONLY", "VISION_ONLY") for r in results)

    def test_duplicate_group_asymmetric_counts_leaves_excess_unaligned(self):
        """3 OCR instances vs 2 Vision instances of the same SKU: at most 2
        pairs can align; the extra OCR instance must remain single-source,
        never dropped, never force-paired."""
        ocr_items = [
            {"sku": "WST3657B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": p}
            for p in (3, 4, 4)
        ]
        vision_items = [
            {"sku": "WST3657B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": p}
            for p in (3, 4)
        ]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 3  # 2 aligned pairs (as 2 results) + 1 leftover OCR_ONLY
        aligned = [r for r in results if r.verification_method == "OCR_PLUS_VISION"]
        ocr_only = [r for r in results if r.verification_method == "OCR_ONLY"]
        assert len(aligned) == 2
        assert len(ocr_only) == 1

    def test_duplicate_group_conflicting_field_stays_uncertain(self):
        """Evidence-gated alignment must not weaken the field-comparison
        rules: if an aligned duplicate pair disagrees on quantity, it is
        UNCERTAIN with a preserved conflict, never silently VERIFIED."""
        ocr_items = [{"sku": "FLTS39", "description": "Filler Strip", "quantity": 1, "page_number": 16}]
        vision_items = [{"sku": "FLTS39", "description": "Filler Strip", "quantity": 2, "page_number": 16}]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 1
        assert results[0].evidence_status == "UNCERTAIN"
        assert any(c.field == "quantity" for c in results[0].conflicts)


class TestOCRCandidateEvidenceAlignment:
    def test_ocr_candidate_aligns_with_page_and_description_evidence(self):
        """OCR misread 'S' as '5' in a SKU; Vision read it correctly. Same
        page and matching description are the corroborating evidence — the
        pair must be compared (not left as two disconnected single-source
        items). Since the SKU still literally differs, the result is
        UNCERTAIN with the SKU conflict preserved, never silently VERIFIED."""
        ocr_items = [{"sku": "WST30S7B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 2}]
        vision_items = [{"sku": "WST3057B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 2}]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 1
        r = results[0]
        assert r.verification_method == "OCR_PLUS_VISION"
        assert r.alignment_basis == "OCR_CANDIDATE_EVIDENCE"
        assert r.evidence_status == "UNCERTAIN"
        assert any(c.field == "sku" for c in r.conflicts)

    def test_ocr_candidate_without_page_match_stays_unaligned(self):
        """Negative case: same OCR-confusable SKUs, but different pages —
        page agreement is a hard gate for candidate alignment (§7), so this
        must NOT be compared."""
        ocr_items = [{"sku": "WST30S7B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 2}]
        vision_items = [{"sku": "WST3057B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 9}]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 2
        assert all(r.verification_method in ("OCR_ONLY", "VISION_ONLY") for r in results)

    def test_manufacturer_variant_not_treated_as_ocr_candidate(self):
        """Negative case: BPFHC12 vs BFHC12 is a known MANUFACTURER variant
        (missing 'P'), not a character substitution — it must not be found
        by the OCR-candidate generator (which only substitutes within the
        known confusion pairs, never inserts/deletes characters), so it
        stays unaligned here exactly as before Phase 3.1."""
        ocr_items = [{"sku": "BPFHC12", "description": "Full Height Cabinet", "quantity": 1, "page_number": 7}]
        vision_items = [{"sku": "BFHC12", "description": "Full Height Cabinet", "quantity": 1, "page_number": 7}]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 2
        assert all(r.verification_method in ("OCR_ONLY", "VISION_ONLY") for r in results)

    def test_true_different_item_on_same_page_not_falsely_aligned(self):
        """Two genuinely different SKUs/items on the same page, with no OCR-
        confusion relationship and no description overlap, must never align
        just because they share a page."""
        ocr_items = [{"sku": "BT36B-2", "description": "Base w/ 2 Roll-Out Trays", "quantity": 1, "page_number": 6}]
        vision_items = [{"sku": "SBA36B", "description": "Apron Sink Base", "quantity": 1, "page_number": 6}]
        results = reconcile_items(ocr_items, vision_items)
        assert len(results) == 2
        assert all(r.verification_method in ("OCR_ONLY", "VISION_ONLY") for r in results)


class TestRawItemPreservationUnderWidenedAlignment:
    def test_item_count_conserved_across_all_alignment_paths(self):
        """No matter how items get aligned (exact, duplicate-group, or
        candidate-evidence), every raw item from both passes must appear
        exactly once in the reconciled output."""
        ocr_items = [
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 15},
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 16},
            {"sku": "WST30S7B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 2},
            {"sku": "UNIQUE-OCR-ONLY", "description": "Something", "quantity": 1, "page_number": 99},
        ]
        vision_items = [
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 15},
            {"sku": "W3930", "description": "Wall Cabinet", "quantity": 1, "page_number": 16},
            {"sku": "WST3057B", "description": "Stacked Wall Cabinet", "quantity": 1, "page_number": 2},
            {"sku": "UNIQUE-VISION-ONLY", "description": "Other", "quantity": 1, "page_number": 100},
        ]
        results = reconcile_items(ocr_items, vision_items)
        total_raw_accounted = sum(2 if r.verification_method == "OCR_PLUS_VISION" else 1 for r in results)
        assert total_raw_accounted == len(ocr_items) + len(vision_items)

    def test_align_returns_none_basis_for_exact_unambiguous_match(self):
        """Regression guard: a clean, unambiguous 1:1 SKU match (the
        original Phase 3 behavior) must not be mislabeled with a Phase 3.1
        alignment_basis — it's not a widened match, it's the base case."""
        triples = _align(
            [{"sku": "BT36B-2", "page_number": 6}],
            [{"sku": "BT36B-2", "page_number": 6}],
        )
        assert len(triples) == 1
        assert triples[0][2] is None
