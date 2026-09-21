import re
import json
from typing import Optional, Dict, Any, Union, List, Tuple, Set

# Sentinel string for explicitly missing or unspecified data
NOT_SPECIFIED_IN_SOURCE = "NOT_SPECIFIED_IN_SOURCE"
EXTRACTION_UNCERTAIN = "EXTRACTION_UNCERTAIN"


def normalize_sku(raw_sku: Optional[str]) -> Optional[str]:
    """
    Non-destructively normalizes an SKU:
    - Trims leading/trailing whitespace
    - Normalizes internal multiple spaces to a single space
    - Uppercase
    - Preserves all meaningful tokens, hyphens, and delimiters without lossy global stripping.
    """
    if not raw_sku:
        return None
    cleaned = str(raw_sku).strip()
    if not cleaned or cleaned.upper() in ["NONE", "NULL", "N/A", "-"]:
        return None
    # Normalize excessive internal whitespace to single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.upper()


def extract_sku_tokens(sku: Optional[str]) -> List[str]:
    """
    Extracts distinct alphanumeric tokens from an SKU while preserving token integrity.
    E.g. "B36-1TD BUTT" -> ["B36", "1TD", "BUTT"]
    "CAB_24_L" -> ["CAB", "24", "L"]
    """
    if not sku:
        return []
    # Split by spaces, hyphens, underscores, dots, slashes
    tokens = re.split(r'[\s\-_\./]+', str(sku).strip().upper())
    return [t for t in tokens if t]


def _decompose_tokens(tokens: List[str]) -> Set[str]:
    """Decomposes compound alphanumeric tokens for structural subset comparison."""
    sub = set()
    for t in tokens:
        sub.add(t)
        for part in re.findall(r'[A-Z]+|\d+', t):
            sub.add(part)
    return sub


LEFT_ORIENTATIONS = {"L", "LH", "LEFT", "BLL"}
RIGHT_ORIENTATIONS = {"R", "RH", "RIGHT", "BLR"}
ORIENTATION_TOKENS = LEFT_ORIENTATIONS | RIGHT_ORIENTATIONS


def has_orientation_conflict(tokens1: Set[str], tokens2: Set[str]) -> bool:
    """Returns True if tokens represent opposing/conflicting orientations (e.g. Left vs Right)."""
    is_left1 = bool(tokens1.intersection(LEFT_ORIENTATIONS))
    is_right1 = bool(tokens1.intersection(RIGHT_ORIENTATIONS))
    is_left2 = bool(tokens2.intersection(LEFT_ORIENTATIONS))
    is_right2 = bool(tokens2.intersection(RIGHT_ORIENTATIONS))
    return (is_left1 and is_right2) or (is_right1 and is_left2)


def are_skus_equivalent(sku1: Optional[str], sku2: Optional[str]) -> Tuple[bool, float, str]:
    """
    Determines if two SKUs are equivalent without destructive assumptions.
    Returns (is_equivalent, confidence, match_type).
    """
    norm1 = normalize_sku(sku1)
    norm2 = normalize_sku(sku2)

    if not norm1 and not norm2:
        return False, 0.0, "BOTH_EMPTY"
    if not norm1 or not norm2:
        return False, 0.0, "ONE_EMPTY"

    # Tier 1: Exact string match
    if norm1 == norm2:
        return True, 1.0, "EXACT_MATCH"

    # Tier 2: Punctuation/delimiter equivalence (e.g. "B36-1TD" vs "B36 1TD")
    tokens1 = extract_sku_tokens(norm1)
    tokens2 = extract_sku_tokens(norm2)

    if tokens1 == tokens2 and tokens1:
        return True, 0.98, "DELIMITER_EQUIVALENCE"

    # Tier 3: Compacted comparison ONLY if tokens are identical when concatenated
    compact1 = "".join(tokens1)
    compact2 = "".join(tokens2)
    if compact1 == compact2 and compact1:
        return True, 0.95, "COMPACT_EQUIVALENCE"

    # Tier 4: Token subset / modifier match (e.g. "B36 1TD" vs "B36 1TD BUTT", "SB33" vs "SB33 BUTT")
    d1 = _decompose_tokens(tokens1)
    d2 = _decompose_tokens(tokens2)
    if d1 and d2:
        orient1 = d1.intersection(ORIENTATION_TOKENS)
        orient2 = d2.intersection(ORIENTATION_TOKENS)
        if has_orientation_conflict(orient1, orient2):
            # Opposing orientation modifiers (e.g. Left vs Right) must never match
            return False, 0.0, "ORIENTATION_MISMATCH"

        if d1.issubset(d2) or d2.issubset(d1):
            return True, 0.90, "TOKEN_SUBSET_MATCH"

    return False, 0.0, "NO_MATCH"


CABINET_KEYWORD_ANCHORS = {
    "BASE", "WALL", "TALL", "VANITY", "SINK", "DRAWER", "DOOR", "BUTT",
    "FLUSH", "PANEL", "HUTCH", "COLUMN", "PENINSULA", "WASTE", "BASKET",
    "FILLER", "CORNER", "SPICE", "RACK", "TRAY", "ROLLOUT", "END", "EXTENDED",
    "OVEN", "MICROWAVE", "BLIND", "ANGLE", "DIAGONAL", "FRAME", "GLASS"
}

STOPWORDS = {
    "THE", "AND", "OR", "IN", "ON", "AT", "TO", "FOR", "WITH", "BY", "OF",
    "A", "AN", "EA", "EACH", "PC", "PCS", "CABINET", "YORKTOWNE", "KITCHEN"
}


def check_canonical_equivalence(
    sku1: Optional[str],
    desc1: Optional[str] = None,
    dims1: Any = None,
    cat1: Any = None,
    sku2: Optional[str] = None,
    desc2: Optional[str] = None,
    dims2: Any = None,
    cat2: Any = None,
    substitution_sku2: Optional[str] = None
) -> Tuple[bool, float, str, str]:
    """
    Evaluates canonical equivalence between two line items across documents.
    Returns: (is_equivalent, confidence, equivalence_type, evidence)

    Equivalence types:
    - EXACT: Exact normalized string match
    - NORMALIZED_EXACT: Delimiter/punctuation/token equivalence
    - EXPLICIT_SUBSTITUTION: Documented manufacturer substitution in Ack
    - MANUFACTURER_VARIANT: Documented/evidence-backed manufacturer code variation supported by description keyword overlap + shared dimensions
    - AMBIGUOUS: Vague similarity without sufficient corroborating evidence
    - NO_MATCH: Completely distinct items
    """
    # 1. Category check: Incompatible major category groups cannot match (only when both are known)
    if cat1 is not None and cat2 is not None:
        cat1_val = getattr(cat1, "value", str(cat1))
        cat2_val = getattr(cat2, "value", str(cat2))
        
        if cat1_val not in ["UNKNOWN", None, ""] and cat2_val not in ["UNKNOWN", None, ""]:
            non_cabinet_groups = {
                "APPLIANCE": "APPLIANCE",
                "ARCHITECTURAL_ANNOTATION": "ANNOTATION",
                "COMMERCIAL_CHARGE": "COMMERCIAL_CHARGE"
            }
            g1 = non_cabinet_groups.get(cat1_val, "PHYSICAL_CABINET_COMPONENT")
            g2 = non_cabinet_groups.get(cat2_val, "PHYSICAL_CABINET_COMPONENT")
            if g1 != g2:
                return False, 0.0, "CATEGORY_MISMATCH", f"Category conflict: {cat1_val} vs {cat2_val}"

    norm1 = normalize_sku(sku1)
    norm2 = normalize_sku(sku2)

    # 2. Check explicit substitution in document 2 (e.g. Ack substitution)
    if substitution_sku2 and norm1:
        sub_eq, sub_conf, _ = are_skus_equivalent(norm1, substitution_sku2)
        if sub_eq:
            return True, 0.95, "EXPLICIT_SUBSTITUTION", f"Explicit substitution: {norm2} replaces {substitution_sku2}"

    if not norm1 and not norm2:
        text1 = normalize_text(desc1 or "") or ""
        text2 = normalize_text(desc2 or "") or ""
        if text1 and text2 and (text1 == text2 or text1 in text2 or text2 in text1):
            return True, 0.85, "NORMALIZED_EXACT", "Matching descriptions without SKU"
        return False, 0.0, "BOTH_EMPTY", "Both SKUs empty"
    if not norm1 or not norm2:
        return False, 0.0, "ONE_EMPTY", "One SKU empty"

    # 3. Exact Match
    if norm1 == norm2:
        return True, 1.0, "EXACT", "Exact normalized SKU match"

    # 4. Standard Normalized Equivalence
    is_eq, conf, match_type = are_skus_equivalent(norm1, norm2)
    if is_eq:
        if match_type in ["EXACT_MATCH", "DELIMITER_EQUIVALENCE", "COMPACT_EQUIVALENCE"]:
            return True, conf, "NORMALIZED_EXACT", f"Normalized delimiter equivalence ({match_type})"
        if match_type == "TOKEN_SUBSET_MATCH":
            # Validate with dimensions if both are present
            if dims1 and dims2:
                dim_eq, dim_reason = are_dimensions_equivalent(dims1, dims2)
                if not dim_eq:
                    return False, 0.0, "AMBIGUOUS", f"Dimension conflict on token subset ({dim_reason})"
            return True, conf, "NORMALIZED_EXACT", "Token subset match with compatible dimensions"

    # 5. Evidence-Backed Manufacturer Variant Equivalence
    # Extract numbers from both SKUs and descriptions
    nums1 = set(re.findall(r'\d+', norm1))
    nums2 = set(re.findall(r'\d+', norm2))
    shared_nums = nums1.intersection(nums2)

    text1 = normalize_text(desc1 or "") or ""
    text2 = normalize_text(desc2 or "") or ""
    desc_nums1 = set(re.findall(r'\d+', text1))
    desc_nums2 = set(re.findall(r'\d+', text2))
    all_nums1 = nums1 | desc_nums1
    all_nums2 = nums2 | desc_nums2

    # Dimension equivalence check
    dim_match = False
    if dims1 and dims2:
        dim_eq, _ = are_dimensions_equivalent(dims1, dims2)
        dim_match = dim_eq

    # OCR confusion support (e.g. 'S' <-> '5', '12' in 'BPS12' vs 'BP52' with 12 in description)
    ocr_num_match = bool(shared_nums)
    if not ocr_num_match:
        norm1_trans = norm1.replace('S', '5')
        norm2_trans = norm2.replace('S', '5')
        t_nums1 = set(re.findall(r'\d+', norm1_trans)) | desc_nums1
        t_nums2 = set(re.findall(r'\d+', norm2_trans)) | desc_nums2
        if t_nums1.intersection(t_nums2):
            ocr_num_match = True

    # Check for primary dimensional number conflicts (e.g. width 36 vs 24, 30 vs 36, 21 vs 15)
    # Dimensional numbers are typically numbers >= 10 or prominent width/depth indicators
    dim_nums1 = {n for n in nums1 if int(n) >= 10}
    dim_nums2 = {n for n in nums2 if int(n) >= 10}
    if dim_nums1 and dim_nums2 and not (dim_nums1.intersection(all_nums2) or dim_nums2.intersection(all_nums1)):
        # Both SKUs have major dimensional numbers that do NOT match in either SKU or description
        return False, 0.0, "DIMENSION_CONFLICT", f"Conflicting dimensional numbers: {dim_nums1} vs {dim_nums2}"

    # Check orientation compatibility (L vs R)
    tokens1 = extract_sku_tokens(norm1)
    tokens2 = extract_sku_tokens(norm2)
    orient1 = set(tokens1).intersection(ORIENTATION_TOKENS)
    orient2 = set(tokens2).intersection(ORIENTATION_TOKENS)
    desc_orient1 = {w for w in ['LEFT', 'RIGHT', 'LH', 'RH'] if re.search(r'\b' + w + r'\b', text1)}
    desc_orient2 = {w for w in ['LEFT', 'RIGHT', 'LH', 'RH'] if re.search(r'\b' + w + r'\b', text2)}
    norm_desc_orient1 = {'L' if x in ['LEFT', 'LH'] else 'R' for x in desc_orient1}
    norm_desc_orient2 = {'L' if x in ['LEFT', 'LH'] else 'R' for x in desc_orient2}
    all_orient1 = orient1 | norm_desc_orient1
    all_orient2 = orient2 | norm_desc_orient2
    if has_orientation_conflict(all_orient1, all_orient2):
        return False, 0.0, "ORIENTATION_MISMATCH", f"Orientation conflict: {all_orient1} vs {all_orient2}"

    # Description keyword overlap
    words1 = set(re.findall(r'[A-Z0-9/]+', text1)) - STOPWORDS
    words2 = set(re.findall(r'[A-Z0-9/]+', text2)) - STOPWORDS
    common_words = words1.intersection(words2)
    shared_anchors = common_words.intersection(CABINET_KEYWORD_ANCHORS)

    # Structural character overlap between SKU alpha parts
    letters1 = set(re.findall(r'[A-Z]', norm1))
    letters2 = set(re.findall(r'[A-Z]', norm2))
    common_letters = letters1.intersection(letters2)
    alpha_overlap = len(common_letters) / max(len(letters1 | letters2), 1)

    has_dimension_backing = bool(shared_nums) or dim_match or ocr_num_match or bool(dim_nums1.intersection(all_nums2)) or bool(dim_nums2.intersection(all_nums1))
    has_description_backing = (len(shared_anchors) >= 1) or (len(common_words) >= 2)

    if has_dimension_backing and has_description_backing and alpha_overlap >= 0.6:
        evidence_str = f"Shared dimensions ({shared_nums or dim_nums1.intersection(all_nums2) or 'matched dimensions'}) and keywords {sorted(list(common_words))}"
        return True, 0.92, "MANUFACTURER_VARIANT", evidence_str

    # If high description similarity but completely unverified/conflicting SKU
    if len(common_words) >= 3 and not has_dimension_backing:
        return False, 0.0, "AMBIGUOUS", "High description overlap but conflicting/unverified SKU dimensions"

    return False, 0.0, "NO_MATCH", "No matching SKU or evidence"



def normalize_quantity(raw_qty: Union[str, int, float, None]) -> Optional[int]:
    """
    Deterministically normalizes quantity to an integer.
    Supports: 1, "01", "1.0", "Qty: 1", "2 EA", "QTY 2"
    """
    if raw_qty is None:
        return None
    if isinstance(raw_qty, int):
        return raw_qty
    if isinstance(raw_qty, float):
        return int(raw_qty)

    qty_str = str(raw_qty).strip().upper()
    if not qty_str or qty_str in ["NONE", "NULL", "N/A", "-"]:
        return None

    # Match standalone numbers or numbers with Qty prefixes
    match = re.search(r'(?:QTY[:\s]*)?(\d+)(?:\.0+)?(?:\s*(?:EA|PCS|PK|PIECES))?', qty_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def parse_and_normalize_dimensions(raw_dims: Any) -> Optional[Dict[str, Any]]:
    """
    Unit-aware and axis-aware dimension parser.
    Supports:
    - Dicts: {"width": "12\"", "height": 34.5, "depth": "24 W"}
    - String representations:
      - Explicit axes: "36W x 12H x 24D", "12 W", "30\" opening", "W:36 H:12 D:24"
      - Delimited: "36 x 12 x 24", "36\" x 12\" x 24\""
    """
    if raw_dims is None or raw_dims == "" or raw_dims == "null" or raw_dims == "None":
        return None

    # Handle string input that might be JSON
    if isinstance(raw_dims, str):
        trimmed = raw_dims.strip()
        if not trimmed or trimmed.upper() in ["NONE", "NULL", "N/A", "-"]:
            return None
        if (trimmed.startswith("{") and trimmed.endsWith("}")) or (trimmed.startswith("[") and trimmed.endsWith("]")):
            try:
                raw_dims = json.loads(trimmed)
            except Exception:
                pass

    result: Dict[str, Any] = {
        "width": None,
        "height": None,
        "depth": None,
        "opening": None,
        "unit": "IN",
        "axis_certainty": "UNKNOWN",
        "raw": str(raw_dims).replace('\\', '').strip()
    }

    if isinstance(raw_dims, dict):
        # Extract explicit dictionary keys
        width_val = raw_dims.get("width") or raw_dims.get("w") or raw_dims.get("Width") or raw_dims.get("W")
        height_val = raw_dims.get("height") or raw_dims.get("h") or raw_dims.get("Height") or raw_dims.get("H")
        depth_val = raw_dims.get("depth") or raw_dims.get("d") or raw_dims.get("Depth") or raw_dims.get("D")
        opening_val = raw_dims.get("opening") or raw_dims.get("Opening")

        if opening_val:
            result["opening"] = str(opening_val).replace('\\', '').strip()
            result["axis_certainty"] = "EXPLICIT"

        def _clean_num(val: Any) -> Optional[float]:
            if val is None or str(val).strip() in ["", "null", "None"]:
                return None
            val_str = str(val).replace('\\', '').replace('"', '').replace("'", '').strip()
            m = re.search(r'(\d+(?:\.\d+)?)', val_str)
            return float(m.group(1)) if m else None

        w_num = _clean_num(width_val)
        h_num = _clean_num(height_val)
        d_num = _clean_num(depth_val)

        if w_num is not None:
            result["width"] = w_num
            result["axis_certainty"] = "EXPLICIT"
        if h_num is not None:
            result["height"] = h_num
            result["axis_certainty"] = "EXPLICIT"
        if d_num is not None:
            result["depth"] = d_num
            result["axis_certainty"] = "EXPLICIT"

        if result["width"] is not None or result["height"] is not None or result["depth"] is not None or result["opening"]:
            return result

        # Check for generic single string value inside dict
        for v in raw_dims.values():
            if isinstance(v, str) and v.strip():
                return parse_and_normalize_dimensions(v)
        return None

    # Handle string dimension
    dim_str = str(raw_dims).replace('\\', '').replace('"', '').replace("'", '').strip()

    # Check for opening
    if "OPENING" in dim_str.upper():
        result["opening"] = dim_str
        result["axis_certainty"] = "EXPLICIT"
        m = re.search(r'(\d+(?:\.\d+)?)', dim_str)
        if m:
            result["width"] = float(m.group(1))
        return result

    # Check for explicit axes pattern (e.g. "36W x 12H x 24D", "36 W x 12 H x 24 D", "12 W", "36W")
    explicit_match = False
    w_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:W|WIDTH)', dim_str, re.IGNORECASE)
    h_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:H|HEIGHT)', dim_str, re.IGNORECASE)
    d_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:D|DEPTH)', dim_str, re.IGNORECASE)

    if w_match:
        result["width"] = float(w_match.group(1))
        explicit_match = True
    if h_match:
        result["height"] = float(h_match.group(1))
        explicit_match = True
    if d_match:
        result["depth"] = float(d_match.group(1))
        explicit_match = True

    if explicit_match:
        result["axis_certainty"] = "EXPLICIT"
        return result

    # Unlabeled multi-dimension pattern: "36 x 12 x 24" or "36 × 12 × 24" or "36 x 12"
    multi_nums = re.findall(r'(\d+(?:\.\d+)?)', dim_str)
    if len(multi_nums) >= 2:
        # Standard convention: W x H x D when 3 numbers; W x H when 2 numbers
        # But mark certainty as UNLABELED so matching is careful
        result["width"] = float(multi_nums[0])
        result["height"] = float(multi_nums[1])
        if len(multi_nums) >= 3:
            result["depth"] = float(multi_nums[2])
        result["axis_certainty"] = "UNLABELED"
        return result

    # Single number without axis: "12" or "12 in" -> Width candidate
    if len(multi_nums) == 1:
        result["width"] = float(multi_nums[0])
        result["axis_certainty"] = "SINGLE_VALUE"
        return result

    return None


def are_dimensions_equivalent(dim1: Any, dim2: Any) -> Tuple[bool, str]:
    """
    Compares two dimension structures for semantic equivalence.
    Returns (is_equivalent, reason).
    """
    d1 = parse_and_normalize_dimensions(dim1)
    d2 = parse_and_normalize_dimensions(dim2)

    # Both unspecified
    if not d1 and not d2:
        return True, "BOTH_UNSPECIFIED"

    # If one is unspecified, they cannot be declared changed without explicit contradiction
    if not d1 or not d2:
        return True, "ONE_UNSPECIFIED"

    # If openings exist
    if d1.get("opening") and d2.get("opening"):
        if d1["opening"].upper() == d2["opening"].upper():
            return True, "OPENING_MATCH"
        if d1.get("width") is not None and d2.get("width") is not None:
            return d1["width"] == d2["width"], "OPENING_WIDTH_COMPARISON"

    # Explicit axis comparison
    axes = ["width", "height", "depth"]
    compared_any = False
    for axis in axes:
        v1 = d1.get(axis)
        v2 = d2.get(axis)
        if v1 is not None and v2 is not None:
            compared_any = True
            if abs(v1 - v2) > 0.05: # Tolerant to minor floating point rounding
                return False, f"AXIS_{axis.upper()}_MISMATCH ({v1} vs {v2})"

    if compared_any:
        return True, "EXPLICIT_AXES_MATCH"

    # Fallback to raw string normalization if numeric parse was partial
    raw1 = re.sub(r'[\s\"\'\-]+', '', str(d1.get("raw", "")).upper())
    raw2 = re.sub(r'[\s\"\'\-]+', '', str(d2.get("raw", "")).upper())
    if raw1 == raw2 and raw1:
        return True, "RAW_NORMALIZED_MATCH"

    return True, "INSUFFICIENT_DATA_TO_CONTRADICT"


def normalize_text(val: Optional[str]) -> Optional[str]:
    """
    Normalizes descriptive text fields (finish, door style, description)
    by trimming, standardizing whitespace and case.
    """
    if val is None:
        return None
    cleaned = str(val).strip()
    if not cleaned or cleaned.upper() in ["NONE", "NULL", "N/A", "-"]:
        return None
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.upper()
