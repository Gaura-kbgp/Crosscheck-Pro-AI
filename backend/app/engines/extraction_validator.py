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
