import re
from typing import Optional, Dict, Any, List, Tuple
from app.models.core import ItemCategory, DocumentType
from app.engines.normalization import normalize_sku, extract_sku_tokens, normalize_text


class ClassificationResult:
    def __init__(
        self,
        category: ItemCategory,
        confidence: float,
        evidence: Dict[str, Any],
        reason: str
    ):
        self.category = category
        self.confidence = round(confidence, 2)
        self.evidence = evidence
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "reason": self.reason
        }


class ItemClassifier:
    """
    Generic, evidence-based item and category classifier.
    Categorizes line items into:
    - CABINET
    - ACCESSORY
    - FILLER
    - PANEL
    - MOLDING
    - APPLIANCE
    - ARCHITECTURAL_ANNOTATION
    - UNKNOWN

    Avoids manufacturer-specific hardcoding. Uses SKU structure, description keywords,
    drawing annotations, dimension context, and confidence scoring.
    """

    COMMERCIAL_CHARGE_KEYWORDS = [
        "freight", "surcharge", "tariff", "shipping", "handling", "delivery fee",
        "fuel surcharge", "upcharge", "non charge", "non-charge"
    ]

    # Keyword sets for description analysis
    APPLIANCE_KEYWORDS = [
        "refrigerator", "fridge", "dishwasher", "range", "cooktop", "microwave",
        "micro hood", "mw hood", "range hood", "hood", "wall oven", "double oven",
        "oven", "disposal", "trash compactor", "wine cooler", "wine cooler", "beverage center",
        "ice maker", "cooker", "ventilation", "blower", "sink", "faucet", "appliance",
        "freezer", "cook top"
    ]

    ARCHITECTURAL_KEYWORDS = [
        "wall opening", "window", "door opening", "door frame", "room dimension",
        "ceiling height", "soffit", "bulkhead", "pass thru", "column", "beam",
        "electrical", "plumbing", "rough opening", "drywall", "stud", "framing",
        "casing", "floor plan", "drawing note", "elevation note",
        # Hood surround / mantel architectural elements
        # These must appear BEFORE APPLIANCE_KEYWORDS so 'hood ledge', 'mantel' etc.
        # are not captured by the bare 'hood' appliance keyword.
        "mantel", "alcove", "hood ledge", "hood surround", "hood mantel",
        "alcove hood", "ledge"
    ]

    FILLER_KEYWORDS = [
        "filler", "flr", "overlay filler", "fluted filler", "base filler",
        "wall filler", "tall filler", "column filler", "corner filler", "fill strip"
    ]

    PANEL_KEYWORDS = [
        "end panel", "finished end", "refrigerator panel", "dishwasher panel",
        "island panel", "decorative panel", "wainscot panel", "panel skin",
        "side panel", "back panel", "base end panel", "wall end panel", "tall end panel",
        # Compound phrases that contain appliance-adjacent words but describe panels.
        # These MUST be checked before APPLIANCE_KEYWORDS to prevent 'dishwasher'
        # or 'appliance' in a panel description from triggering APPLIANCE classification.
        "dishwasher end",    # DEP items: 'DISHWASHER END PANEL', 'DISHWASHER EP PLY'
        "dishwasher ep",     # DEP items: 'DISHWASHER EP PLY-1 1/2 STILE'
        "appliance panel",   # FAP items: 'FRAMED APPLIANCE PANEL'
        "appliance pnl",     # FAP items with PNL abbreviation
        "framed appliance",  # FAP items: 'FRAMED APPLIANCE PNL'
        "deluxe back panel", # DBP items: back panel behind cabinets
        "back panel",        # General back panel
    ]

    MOLDING_KEYWORDS = [
        "molding", "moulding", "crown molding", "crown", "scribe molding", "scribe",
        "light rail", "toe kick", "base shoe", "valance", "decorative trim",
        "outside corner molding", "inside corner molding", "batten", "fascia", "trim",
        # Hutch molding / Arts & Crafts molding accessories
        "hutch mld", "hutch molding", "hutch mould",
        "base hutch", "starter molding", "starter mld",
        # MLD suffix is a common manufacturer abbreviation for molding
        " mld ", " mld",
    ]

    COMPOUND_CABINET_KEYWORDS = [
        "base tray cab", "tray cab", "tray cabinet", "base cabinet", "wall cabinet",
        "tall cabinet", "stacked wall cabinet", "stacked wall", "sink base cabinet",
        "drawer base cabinet", "blind base cabinet", "utility cabinet", "oven cabinet",
        "pantry cabinet", "corner base cabinet"
    ]

    ACCESSORY_KEYWORDS = [
        "rollout", "roll out", "roll-out", "tray divider", "rollout tray", "roll out tray",
        "lazy susan", "trash pullout", "waste basket", "cutlery divider", "spice rack",
        "spice pullout", "organizer", "stemware holder", "wine rack", "corbel",
        "decorative leg", "post", "knob", "pull", "hardware", "touch up kit",
        "touch-up", "hinge", "bracket", "shelf kit",
        # Factory service/finish accessories
        "repair kit",    # RR: 'REPAIR KIT' — manufacturer-included service kit
        "touch-up kit",  # RK-SB, RKPP: 'TOUCH UP KIT-...'
        "touchup kit",
        "mullion",       # 2CMUL2: glass door mullion — factory accessory
        "mull front",    # MULL-FRONT: mullion front accessory
        "mull-front",
    ]

    CABINET_KEYWORDS = [
        "base cab", "wall cab", "tall cab", "utility cab", "sink base cab",
        "drawer base cab", "blind base cab", "cabinet", "vanity",
        "drawer base", "sink base", "corner base", "corner wall", "pantry",
        "blind base", "blind wall", "diagonal corner", "lazy susan cabinet", "tray base"
    ]

    # Structural regex patterns for SKUs
    COMMERCIAL_CHARGE_SKU_PATTERNS = [
        r'.*(FREIGHT|TARIFF|SURCHARGE|SHIPPING|DELIVERY|UPCHARGE|NONCHG|NONCHARGE).*'
    ]

    APPLIANCE_SKU_PATTERNS = [
        r'^(REF|FRIDGE|DW|DISH|RNG|RANGE|MW|MICROWAVE|HOOD|OV|OVN|OVEN|COOK|AP|APPL|SINK|FAUCET|ELX)[\.\-_0-9A-Z]*$',
        r'^(GR|PWS|WS|PRO|ICB|BI|MIE|WOLF|SUB|MONO|ZEPH|THERM)[0-9]+.*$',
        r'.*[\.\-_](REF|DW|DISH|RNG|RANGE|MW|HOOD|OVEN|OVN|SINK|APPL)[\.\-_0-9A-Z]*$'
    ]

    ARCHITECTURAL_SKU_PATTERNS = [
        r'^(WALL|WIN|WINDOW|DR|DOOR|ROOM|CLG|HT|ELEC|PLUMB|ARCH|OPENING|PASS)[.\-_0-9A-Z]*$',
        r'.*(AHSDX|MNTLDX|MWTLDX|CLME|SMCRN|MANTEL|LEDGE|SOFFIT|BULKHEAD|HEADER).*',
        r'^(RO|DIM|NOTE)[.\-_][0-9A-Z]*$'
    ]

    FILLER_SKU_PATTERNS = [
        r'^(BF|WF|TF|FLR|FIL|FILLER|FF)[0-9]*[A-Z0-9]*$',
        r'.*FILLER.*'
    ]

    PANEL_SKU_PATTERNS = [
        r'^(EP|BEP|WEP|REP|TEP|PNL|PANEL|FSKIN|DEP|DLEP|FAP|DBP|DLBP)[0-9]*[A-Z0-9]*$',
        r'.*PANEL.*'
    ]

    MOLDING_SKU_PATTERNS = [
        r'^(SCM|CM|TK|LR|VAL|SHOE|TRIM|MOLD|MLD|BM|QR)[0-9]*[A-Z0-9]*$',
        r'^(VALANCE|TOEKICK|CROWN)[0-9]*[A-Z0-9]*$'
    ]

    ACCESSORY_SKU_PATTERNS = [
        r'^(ROT|TD|TP|CR|LEG|POST|CRB|TUK|WR|SR|SBK)[0-9]*[A-Z0-9]*$',
        r'^(PULLOUT|ORGANIZER)[0-9]*[A-Z0-9]*$'
    ]

    CABINET_SKU_PATTERNS = [
        r'^(B|BT|SB|DB|CB|PB|BBC|BLB|VB|VSB|VDB|3DB|4DB)[0-9]+.*$', # Base / Vanity / Tray / Corner
        r'^(W|WST|WW|WDC|WBC|WTC|WCR)[0-9]+.*$',                    # Wall / Stacked Wall
        r'^(T|U|PC|UTIL|OC|OVC|DOC|TOC)[0-9]+.*$',                  # Tall / Utility
        r'^(CAB|CABINET)[0-9]+.*$'                                  # Generic cabinet prefix
    ]

    def classify(
        self,
        raw_sku: Optional[str] = None,
        description: Optional[str] = None,
        dimensions: Optional[Any] = None,
        modifications: Optional[Any] = None,
        source_metadata: Optional[Any] = None,
        source_type: Optional[DocumentType] = None
    ) -> ClassificationResult:
        """
        Classifies an item based on multi-source evidence.
        """
        norm_sku = normalize_sku(raw_sku) or ""
        tokens = extract_sku_tokens(norm_sku)
        desc_norm = normalize_text(description or "") or ""
        
        evidence: Dict[str, Any] = {
            "sku": norm_sku,
            "tokens": tokens,
            "description": desc_norm,
            "has_dimensions": bool(dimensions),
            "matched_rules": []
        }

        # 1. Description-based exact and strong keyword matches (highest confidence)
        if desc_norm:
            # Check Commercial Charge keywords (e.g. "freight surcharge", "tariff", "shipping fee")
            for kw in self.COMMERCIAL_CHARGE_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:commercial_charge:{kw}")
                    return ClassificationResult(
                        ItemCategory.COMMERCIAL_CHARGE, 0.99, evidence,
                        f"Description identifies commercial surcharge / fee ('{kw}')"
                    )

            # Check Architectural keywords first (e.g. "window trim frame opening", "wall opening", "rough opening")
            for kw in self.ARCHITECTURAL_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:architectural:{kw}")
                    return ClassificationResult(
                        ItemCategory.ARCHITECTURAL_ANNOTATION, 0.98, evidence,
                        f"Description explicitly identifies architectural drawing element ('{kw}')"
                    )

            # Check Panel keywords (e.g. "refrigerator panel", "end panel", "panel skin")
            for kw in self.PANEL_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:panel:{kw}")
                    return ClassificationResult(
                        ItemCategory.PANEL, 0.95, evidence,
                        f"Description identifies panel ('{kw}')"
                    )

            # Check Filler keywords
            for kw in self.FILLER_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:filler:{kw}")
                    return ClassificationResult(
                        ItemCategory.FILLER, 0.95, evidence,
                        f"Description identifies filler ('{kw}')"
                    )

            # Check Molding keywords
            for kw in self.MOLDING_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:molding:{kw}")
                    return ClassificationResult(
                        ItemCategory.MOLDING, 0.95, evidence,
                        f"Description identifies molding / trim ('{kw}')"
                    )

            # Check Compound Cabinet keywords (e.g. "base tray cab", "stacked wall cabinet", "base cabinet")
            for kw in self.COMPOUND_CABINET_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:compound_cabinet:{kw}")
                    return ClassificationResult(
                        ItemCategory.CABINET, 0.95, evidence,
                        f"Description identifies cabinet ('{kw}')"
                    )

            # Check Accessory keywords
            for kw in self.ACCESSORY_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:accessory:{kw}")
                    return ClassificationResult(
                        ItemCategory.ACCESSORY, 0.95, evidence,
                        f"Description identifies cabinet accessory / hardware ('{kw}')"
                    )

            # Check General Cabinet keywords (e.g. "cabinet", "vanity", "pantry")
            for kw in self.CABINET_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:cabinet:{kw}")
                    return ClassificationResult(
                        ItemCategory.CABINET, 0.95, evidence,
                        f"Description identifies cabinet ('{kw}')"
                    )

            # Appliance keywords (only if not a panel/filler/cabinet/molding/annotation)
            for kw in self.APPLIANCE_KEYWORDS:
                if re.search(r'\b' + re.escape(kw) + r'\b', desc_norm, re.IGNORECASE):
                    evidence["matched_rules"].append(f"description_keyword:appliance:{kw}")
                    return ClassificationResult(
                        ItemCategory.APPLIANCE, 0.98, evidence,
                        f"Description explicitly identifies appliance ('{kw}')"
                    )

        # 2. SKU Structure and Token-Based Classification
        if norm_sku:
            # Check Commercial Charge SKU patterns
            for pat in self.COMMERCIAL_CHARGE_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:commercial_charge:{pat}")
                    return ClassificationResult(
                        ItemCategory.COMMERCIAL_CHARGE, 0.98, evidence,
                        f"SKU structure matches commercial fee / surcharge code ('{norm_sku}')"
                    )

            # Check Appliance SKU patterns
            for pat in self.APPLIANCE_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:appliance:{pat}")
                    return ClassificationResult(
                        ItemCategory.APPLIANCE, 0.92, evidence,
                        f"SKU structure matches appliance placeholder/code ('{norm_sku}')"
                    )

            # Check Architectural SKU patterns
            for pat in self.ARCHITECTURAL_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:architectural:{pat}")
                    return ClassificationResult(
                        ItemCategory.ARCHITECTURAL_ANNOTATION, 0.92, evidence,
                        f"SKU structure matches architectural annotation code ('{norm_sku}')"
                    )

            # Check Filler SKU patterns
            for pat in self.FILLER_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:filler:{pat}")
                    return ClassificationResult(
                        ItemCategory.FILLER, 0.90, evidence,
                        f"SKU matches filler code structure ('{norm_sku}')"
                    )

            # Check Panel SKU patterns
            for pat in self.PANEL_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:panel:{pat}")
                    return ClassificationResult(
                        ItemCategory.PANEL, 0.90, evidence,
                        f"SKU matches panel code structure ('{norm_sku}')"
                    )

            # Check Molding SKU patterns
            for pat in self.MOLDING_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:molding:{pat}")
                    return ClassificationResult(
                        ItemCategory.MOLDING, 0.90, evidence,
                        f"SKU matches molding/trim code structure ('{norm_sku}')"
                    )

            # Check Accessory SKU patterns
            for pat in self.ACCESSORY_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:accessory:{pat}")
                    return ClassificationResult(
                        ItemCategory.ACCESSORY, 0.90, evidence,
                        f"SKU matches accessory code structure ('{norm_sku}')"
                    )

            # Check Cabinet SKU patterns
            for pat in self.CABINET_SKU_PATTERNS:
                if re.match(pat, norm_sku):
                    evidence["matched_rules"].append(f"sku_pattern:cabinet:{pat}")
                    return ClassificationResult(
                        ItemCategory.CABINET, 0.92, evidence,
                        f"SKU matches standard cabinet code structure ('{norm_sku}')"
                    )

        # 3. Structural Token Inspection for Compound SKUs
        for token in tokens:
            if token in ["FILLER", "FLR", "BF", "WF", "TF"]:
                evidence["matched_rules"].append(f"token:filler:{token}")
                return ClassificationResult(ItemCategory.FILLER, 0.85, evidence, f"Token indicates filler ({token})")
            if token in ["PANEL", "BEP", "WEP", "REP", "TEP"]:
                evidence["matched_rules"].append(f"token:panel:{token}")
                return ClassificationResult(ItemCategory.PANEL, 0.85, evidence, f"Token indicates panel ({token})")
            if token in ["CROWN", "SCM", "TOEKICK", "TK", "VALANCE", "VAL", "SHOE", "TRIM"]:
                evidence["matched_rules"].append(f"token:molding:{token}")
                return ClassificationResult(ItemCategory.MOLDING, 0.85, evidence, f"Token indicates molding ({token})")
            if token in ["ROT", "ROLLOUT", "DIVIDER", "ORGANIZER", "CORBEL"]:
                evidence["matched_rules"].append(f"token:accessory:{token}")
                return ClassificationResult(ItemCategory.ACCESSORY, 0.85, evidence, f"Token indicates accessory ({token})")
            if token in ["REF", "FRIDGE", "DW", "DISH", "RANGE", "RNG", "MW", "HOOD", "OVEN", "SINK"]:
                evidence["matched_rules"].append(f"token:appliance:{token}")
                return ClassificationResult(ItemCategory.APPLIANCE, 0.85, evidence, f"Token indicates appliance ({token})")

        # 4. Fallback: If SKU is completely uninformative or ambiguous, abstain to UNKNOWN
        if not norm_sku and not desc_norm:
            evidence["matched_rules"].append("empty_sku_and_desc")
            return ClassificationResult(
                ItemCategory.UNKNOWN, 0.0, evidence,
                "No SKU or description provided for classification"
            )

        # If SKU exists but doesn't match any known pattern
        # If it has standard cabinet 3D dimensions (width >= 9, depth >= 12, height >= 12), consider weak cabinet candidate
        if dimensions and isinstance(dimensions, dict):
            w = dimensions.get("width")
            h = dimensions.get("height")
            d = dimensions.get("depth")
            if w and h and d and isinstance(w, (int, float)) and isinstance(h, (int, float)) and isinstance(d, (int, float)):
                if w >= 9 and h >= 12 and d >= 12:
                    evidence["matched_rules"].append("dimensional_heuristic:cabinet")
                    return ClassificationResult(
                        ItemCategory.CABINET, 0.70, evidence,
                        "Dimensions match typical 3D cabinet envelope"
                    )

        # Genuinely ambiguous item -> UNKNOWN (preserve for Human Review)
        evidence["matched_rules"].append("ambiguous_unmatched")
        return ClassificationResult(
            ItemCategory.UNKNOWN, 0.40, evidence,
            f"Item '{norm_sku}' does not match standard cabinet, appliance, or accessory patterns"
        )
