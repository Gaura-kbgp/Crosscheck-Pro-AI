import pytest
from app.engines.normalization import (
    normalize_sku,
    extract_sku_tokens,
    are_skus_equivalent,
    normalize_quantity,
    parse_and_normalize_dimensions,
    are_dimensions_equivalent,
    normalize_text
)

def test_unseen_sku_normalization():
    # Unseen generic SKUs
    assert normalize_sku("  cab-24-l  ") == "CAB-24-L"
    assert normalize_sku("X36   2DR") == "X36 2DR"
    assert normalize_sku("base123-r") == "BASE123-R"
    assert normalize_sku("WALL_3012_L") == "WALL_3012_L"
    assert normalize_sku("abc  1td   ext") == "ABC 1TD EXT"
    assert normalize_sku("kitchen-x-42") == "KITCHEN-X-42"
    assert normalize_sku(None) is None
    assert normalize_sku("null") is None
    assert normalize_sku("-") is None

def test_sku_tokens_preservation():
    tokens = extract_sku_tokens("CAB-24-L")
    assert tokens == ["CAB", "24", "L"]

    tokens2 = extract_sku_tokens("B36 1TD BUTT")
    assert tokens2 == ["B36", "1TD", "BUTT"]

    tokens3 = extract_sku_tokens("WALL_3012/R")
    assert tokens3 == ["WALL", "3012", "R"]

def test_sku_equivalence_without_global_stripping():
    # Exact
    is_eq, conf, reason = are_skus_equivalent("CAB-24-L", "CAB-24-L")
    assert is_eq is True
    assert conf == 1.0

    # Delimiter variation
    is_eq, conf, reason = are_skus_equivalent("B36-1TD-BUTT", "B36 1TD BUTT")
    assert is_eq is True
    assert conf >= 0.95

    # Compact variation
    is_eq, conf, reason = are_skus_equivalent("B361TDBUTT", "B36 1TD BUTT")
    assert is_eq is True
    assert conf >= 0.95

    # Non-equivalent SKUs must NOT match
    is_eq, conf, reason = are_skus_equivalent("CAB-24-L", "CAB-24-R")
    assert is_eq is False

    is_eq, conf, reason = are_skus_equivalent("BASE123", "WALL123")
    assert is_eq is False

def test_quantity_normalization():
    assert normalize_quantity(1) == 1
    assert normalize_quantity("01") == 1
    assert normalize_quantity("1.0") == 1
    assert normalize_quantity("Qty: 2") == 2
    assert normalize_quantity("QTY 12 EA") == 12
    assert normalize_quantity("3 PCS") == 3
    assert normalize_quantity(None) is None
    assert normalize_quantity("N/A") is None

def test_dimension_normalization_and_equivalence():
    # Explicit W axis
    dim1 = parse_and_normalize_dimensions("12\"")
    dim2 = parse_and_normalize_dimensions("12 W")
    assert dim1 is not None and dim2 is not None
    assert dim1["width"] == 12.0
    assert dim2["width"] == 12.0

    is_eq, _ = are_dimensions_equivalent(dim1, dim2)
    assert is_eq is True

    # 3-axis explicit: 36W x 12H x 24D
    dim3d_1 = parse_and_normalize_dimensions("36W x 12H x 24D")
    dim3d_2 = parse_and_normalize_dimensions({"width": 36, "height": 12, "depth": 24})
    assert dim3d_1["width"] == 36.0 and dim3d_1["height"] == 12.0 and dim3d_1["depth"] == 24.0
    is_eq, _ = are_dimensions_equivalent(dim3d_1, dim3d_2)
    assert is_eq is True

    # Mismatch axis
    dim3d_mismatch = parse_and_normalize_dimensions("36W x 15H x 24D")
    is_eq, reason = are_dimensions_equivalent(dim3d_1, dim3d_mismatch)
    assert is_eq is False
    assert "HEIGHT" in reason

    # Opening equivalence
    dim_op1 = parse_and_normalize_dimensions("30\" opening")
    dim_op2 = parse_and_normalize_dimensions({"opening": "30\" opening"})
    is_eq, _ = are_dimensions_equivalent(dim_op1, dim_op2)
    assert is_eq is True

    # Unspecified comparison: should not declare contradiction
    is_eq, reason = are_dimensions_equivalent(None, "24 W")
    assert is_eq is True
    assert reason == "ONE_UNSPECIFIED"

def test_text_normalization():
    assert normalize_text("  White  ") == "WHITE"
    assert normalize_text("Natural Oak") == "NATURAL OAK"
    assert normalize_text(None) is None
