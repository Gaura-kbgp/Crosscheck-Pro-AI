import re
from typing import Dict, Any, Optional, List, Tuple
from app.models.core import DocumentType, ItemCategory
from app.engines.normalization import normalize_quantity, parse_and_normalize_dimensions, normalize_sku


class ValidationIssue:
    def __init__(self, field: str, issue_type: str, message: str, severity: str = "WARNING"):
        self.field = field
        self.issue_type = issue_type
        self.message = message
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "issue_type": self.issue_type,
            "message": self.message,
            "severity": self.severity
        }


class ExtractionValidator:
    """
    Validates extraction evidence prior to normalization and cross-check.
    Ensures:
    - Quantities are positive integers within plausible range (1-999)
    - SKUs are present and not corrupt/empty
    - Dimensions conform to numeric or standard structured dimensions
    - Confidence scores are bounded [0.0, 1.0]
    - Preserves data even on warning, flagging issues for auditability and Human Review.
    """

    def validate_item(
        self,
        item_data: Dict[str, Any],
        doc_type: DocumentType
    ) -> Tuple[bool, List[ValidationIssue], Dict[str, Any]]:
        """
        Validates raw extracted item dict.
        Returns: (is_valid, list_of_issues, validated_metadata)
        """
        issues: List[ValidationIssue] = []
        is_valid = True

        raw_sku = item_data.get("sku")
        raw_qty = item_data.get("quantity")
        raw_dims = item_data.get("dimensions")
        raw_conf = item_data.get("confidence")

        # 1. SKU validation
        norm_sku = normalize_sku(raw_sku)
        if not norm_sku:
            issues.append(ValidationIssue(
                field="sku",
                issue_type="EMPTY_SKU",
                message="Extracted item has missing or empty SKU",
                severity="WARNING"
            ))
            is_valid = False
        else:
            # Check for suspicious concatenated SKU patterns (e.g. unbroken string > 18 chars without delimiters)
            if len(norm_sku) > 18 and not any(c in str(raw_sku) for c in ["-", "/", " ", "_", "+"]):
                issues.append(ValidationIssue(
                    field="sku",
                    issue_type="SUSPICIOUS_MERGED_SKU",
                    message=f"Extracted SKU '{raw_sku}' has abnormal continuous length ({len(norm_sku)}) suggesting multiple merged labels",
                    severity="WARNING"
                ))

        # 2. Quantity validation
        norm_qty = normalize_quantity(raw_qty)
        if raw_qty is not None and norm_qty is None:
            issues.append(ValidationIssue(
                field="quantity",
                issue_type="INVALID_QUANTITY",
                message=f"Raw quantity '{raw_qty}' could not be parsed deterministically",
                severity="WARNING"
            ))
        elif norm_qty is not None and norm_qty < 0:
            issues.append(ValidationIssue(
                field="quantity",
                issue_type="NEGATIVE_QUANTITY",
                message=f"Negative quantity {norm_qty} is invalid",
                severity="ERROR"
            ))
            is_valid = False
        elif norm_qty is not None and norm_qty > 500:
            issues.append(ValidationIssue(
                field="quantity",
                issue_type="UNUSUALLY_LARGE_QUANTITY",
                message=f"Quantity {norm_qty} exceeds standard threshold (500)",
                severity="WARNING"
            ))

        # 3. Dimension validation
        if raw_dims is not None:
            parsed_dims = parse_and_normalize_dimensions(raw_dims)
            if parsed_dims is None and raw_dims != {}:
                issues.append(ValidationIssue(
                    field="dimensions",
                    issue_type="UNPARSEABLE_DIMENSIONS",
                    message=f"Dimensions '{raw_dims}' could not be parsed to standard numeric envelope",
                    severity="INFO"
                ))

        # 4. Confidence validation
        conf_val = 1.0
        if raw_conf is not None:
            try:
                conf_val = float(raw_conf)
                if conf_val < 0.0 or conf_val > 1.0:
                    issues.append(ValidationIssue(
                        field="confidence",
                        issue_type="OUT_OF_BOUNDS_CONFIDENCE",
                        message=f"Confidence score {conf_val} outside [0.0, 1.0]",
                        severity="WARNING"
                    ))
                    conf_val = max(0.0, min(1.0, conf_val))
            except (ValueError, TypeError):
                conf_val = 1.0

        metadata = {
            "is_valid": is_valid,
            "issues": [i.to_dict() for i in issues],
            "confidence": conf_val
        }

        return is_valid, issues, metadata

    @staticmethod
    def _leading_line_number(line_number: Optional[str]) -> Optional[int]:
        """Extracts the top-level (non-decimal) integer part of a line number
        like '5' or '*47'. Decimal sub-lines ('5.1') belong to their parent
        and are intentionally excluded from the top-level sequence scan."""
        if not line_number:
            return None
        s = str(line_number).lstrip("*").strip()
        m = re.match(r'^(\d+)(\.\d+)?$', s)
        if not m or m.group(2):
            return None
        return int(m.group(1))

    def validate_document(self, items: List[Dict[str, Any]], doc_type: DocumentType) -> Dict[str, Any]:
        """
        F8.3: document-level completeness checks, run once per extraction
        (as opposed to validate_item, which runs per line item). Pure and
        deterministic — never mutates `items`, never blocks the pipeline,
        only surfaces signal for Human Review:
          - EMPTY_EXTRACTION: zero items despite a non-trivial source document.
          - LINE_NUMBER_GAP: a gap in the document's own top-level line
            numbering (Order/Acknowledgement only — Design has none) that
            may mean extraction missed a row. Never auto-declared "missing";
            only flagged for a human to check against the source.
          - RECONCILIATION_CONFLICT (Phase 3): items where the OCR and Vision
            passes disagreed on a field — both values are preserved on the
            item itself; this just counts how many need human attention.
        Returns {"status": "VALID"|"UNCERTAIN", "item_count", "issues": [...]}.
        """
        issues: List[ValidationIssue] = []
        item_count = len(items)

        conflicted = [it for it in items if (it.get("verification") or {}).get("conflicts")]
        if conflicted:
            issues.append(ValidationIssue(
                field="verification",
                issue_type="RECONCILIATION_CONFLICT",
                message="Document extraction could not be fully verified. Please review the flagged pages/items before finalizing.",
                severity="WARNING"
            ))

        if item_count == 0:
            issues.append(ValidationIssue(
                field="items",
                issue_type="EMPTY_EXTRACTION",
                message=f"Extraction returned zero items for this {getattr(doc_type, 'value', doc_type)} document. "
                        "If the source document visibly contains line items, this extraction should be reviewed.",
                severity="WARNING"
            ))

        top_level_numbers = sorted({
            n for item in items
            if (n := self._leading_line_number(item.get("line_number"))) is not None
        })
        if len(top_level_numbers) >= 2:
            full_range = set(range(top_level_numbers[0], top_level_numbers[-1] + 1))
            gaps = sorted(full_range - set(top_level_numbers))
            if gaps:
                issues.append(ValidationIssue(
                    field="line_number",
                    issue_type="LINE_NUMBER_GAP",
                    message=f"Line numbers {gaps} are missing from the sequence "
                            f"{top_level_numbers[0]}-{top_level_numbers[-1]}. This may mean the source genuinely "
                            "skips these numbers, or that extraction missed them — verify against the source "
                            "before treating them as absent.",
                    severity="INFO"
                ))

        status = "UNCERTAIN" if any(i.severity == "WARNING" for i in issues) else "VALID"
        return {
            "status": status,
            "item_count": item_count,
            "issues": [i.to_dict() for i in issues],
        }

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return re.sub(r'\s+', ' ', text or '').strip().lower()

    def validate_evidence(
        self,
        item_data: Dict[str, Any],
        page_evidence: List[Dict[str, Any]]
    ) -> Tuple[str, List[ValidationIssue]]:
        """
        F8.3 Phase 2 §17-19: validates an item's self-reported page_number /
        source_text against the DETERMINISTIC page evidence PyMuPDF actually
        extracted (never the other way around — the AI's claim is never
        trusted as evidence on its own; this is what prevents hallucinated
        evidence). Returns (evidence_status, issues) where evidence_status is
        "VERIFIED" or "UNCERTAIN". Never raises, never drops the item.
        """
        issues: List[ValidationIssue] = []
        page_number = item_data.get("page_number")
        source_text = (item_data.get("source_text") or "").strip()

        if not page_number and not source_text:
            issues.append(ValidationIssue(
                field="source_evidence", issue_type="EMPTY_EVIDENCE",
                message="Item has no page_number or source_text — extraction did not report where this "
                        "came from in the source document.",
                severity="INFO"
            ))
            return "UNCERTAIN", issues

        page = next((p for p in page_evidence if p.get("page_number") == page_number), None)
        if page_number and page is None:
            issues.append(ValidationIssue(
                field="source_evidence", issue_type="INVALID_EVIDENCE",
                message=f"Item claims page_number={page_number}, which does not exist in this document's "
                        f"extracted pages ({len(page_evidence)} page(s) processed).",
                severity="WARNING"
            ))
            return "UNCERTAIN", issues

        if page is None or page.get("status") != "PROCESSED" or not page.get("raw_text"):
            # Scanned/vision page, or a page with no verifiable text layer —
            # honestly uncertain, not falsely verified.
            return "UNCERTAIN", issues

        if not source_text:
            issues.append(ValidationIssue(
                field="source_evidence", issue_type="EMPTY_EVIDENCE",
                message=f"Item claims page_number={page_number} but has no source_text to verify against that page.",
                severity="INFO"
            ))
            return "UNCERTAIN", issues

        page_text_norm = self._normalize_for_match(page["raw_text"])
        source_text_norm = self._normalize_for_match(source_text)
        sku_norm = self._normalize_for_match(str(item_data.get("sku") or ""))

        text_matches = bool(source_text_norm) and source_text_norm in page_text_norm
        sku_matches = bool(sku_norm) and sku_norm in page_text_norm

        if text_matches or sku_matches:
            return "VERIFIED", issues

        issues.append(ValidationIssue(
            field="source_evidence", issue_type="SOURCE_TEXT_MISMATCH",
            message=f"Item's source_text/sku was not found on page {page_number} as extracted from the "
                    "source document — the claimed evidence could not be verified.",
            severity="WARNING"
        ))
        return "UNCERTAIN", issues

    def summarize_page_evidence(self, page_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bounded, DB-safe summary of a document's page coverage — never
        persists full per-page raw text or block coordinate arrays.
        F8.3 Phase 3 §17/§18: also reports OCR-specific coverage when present
        (ocr_status on each page entry) so a whole scanned document is never
        silently reported as verified when OCR genuinely failed on a page."""
        ocr_pages = [p for p in page_evidence if p.get("ocr_status")]
        summary = {
            "pages_processed": len(page_evidence),
            "pages_with_text_evidence": sum(1 for p in page_evidence if p.get("status") == "PROCESSED"),
            "pages_uncertain": sum(1 for p in page_evidence if p.get("status") != "PROCESSED"),
            "page_statuses": [
                {"page_number": p.get("page_number"), "status": p.get("status"), "extraction_method": p.get("extraction_method")}
                for p in page_evidence
            ],
        }
        if ocr_pages:
            summary["ocr_pages_completed"] = sum(1 for p in ocr_pages if p.get("ocr_status") == "OCR_COMPLETED")
            summary["ocr_pages_empty"] = sum(1 for p in ocr_pages if p.get("ocr_status") == "OCR_EMPTY")
            summary["ocr_pages_failed"] = sum(1 for p in ocr_pages if p.get("ocr_status") == "OCR_FAILED")
        return summary

    def has_critical_ocr_failure(self, page_evidence: List[Dict[str, Any]]) -> bool:
        """§18: a page that failed OCR entirely (not just empty — a genuine
        processing failure) means the document must not be silently reported
        as fully verified."""
        return any(p.get("ocr_status") == "OCR_FAILED" for p in page_evidence)
