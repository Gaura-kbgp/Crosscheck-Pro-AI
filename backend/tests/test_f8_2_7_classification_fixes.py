"""
F8.2.7 Regression Tests — Classification Defect Fixes
Tests prove that each proven classification bug from the audit is resolved.
"""
import pytest
from app.engines.classification import ItemClassifier
from app.models.core import ItemCategory


@pytest.fixture
def clf():
    return ItemClassifier()


# ===========================================================================
# F-1: DEP / FAP panel items must NOT be classified as APPLIANCE
# Root cause: 'dishwasher' or 'appliance' in description triggered APPLIANCE
# before SKU pattern (DEP/FAP prefix → PANEL) was evaluated.
# ===========================================================================

class TestDEPFAPPanelClassification:

    def test_dep1w_dishwasher_ep_ply_classified_as_panel(self, clf):
        """DEP1W: 'DISHWASHER EP PLY-1 1/2 STILE MAPLE' must be PANEL, not APPLIANCE."""
        result = clf.classify(
            raw_sku="DEP1W",
            description="DISHWASHER EP PLY-1 1/2 STILE MAPLE"
        )
        assert result.category == ItemCategory.PANEL, (
            f"DEP1W should be PANEL (Dishwasher End Panel), got {result.category}: {result.reason}"
        )
        assert result.confidence >= 0.90

    def test_dep3m_dishwasher_ep_3_stile_classified_as_panel(self, clf):
        """DEP3M: 'DISHWASHER EP PLY- 3 STILE' must be PANEL, not APPLIANCE."""
        result = clf.classify(
            raw_sku="DEP3M",
            description="DISHWASHER EP PLY- 3 STILE"
        )
        assert result.category == ItemCategory.PANEL, (
            f"DEP3M should be PANEL (Dishwasher End Panel), got {result.category}: {result.reason}"
        )

    def test_fap2434_framed_appliance_pnl_classified_as_panel(self, clf):
        """FAP2434: 'FRAMED APPLIANCE PNL 18.25-24 HISTORIC MAPLE' must be PANEL."""
        result = clf.classify(
            raw_sku="FAP2434",
            description="FRAMED APPLIANCE PNL 18.25-24 HISTORIC MAPLE"
        )
        assert result.category == ItemCategory.PANEL, (
            f"FAP2434 should be PANEL (Framed Appliance Panel), got {result.category}: {result.reason}"
        )

    def test_dep_sku_pattern_alone_classified_as_panel(self, clf):
        """DEP prefix without description must still be PANEL via SKU pattern."""
        result = clf.classify(raw_sku="DEP1W", description=None)
        assert result.category == ItemCategory.PANEL

    def test_fap_sku_pattern_alone_classified_as_panel(self, clf):
        """FAP prefix without description must still be PANEL via SKU pattern."""
        result = clf.classify(raw_sku="FAP2434", description=None)
        assert result.category == ItemCategory.PANEL

    def test_genuine_dishwasher_appliance_still_classified_correctly(self, clf):
        """A genuine dishwasher SKU/description must remain APPLIANCE."""
        result = clf.classify(
            raw_sku="DW24",
            description="Dishwasher 24 Inch Built-In"
        )
        assert result.category == ItemCategory.APPLIANCE, (
            f"DW24 with dishwasher description should remain APPLIANCE, got {result.category}"
        )

    def test_appliance_panel_compound_phrase_classified_as_panel(self, clf):
        """'Appliance panel' compound phrase must be PANEL even without DEP/FAP SKU."""
        result = clf.classify(
            raw_sku="SOMEPANEL",
            description="Appliance Panel 24W"
        )
        assert result.category == ItemCategory.PANEL

    def test_framed_appliance_compound_phrase_classified_as_panel(self, clf):
        """'Framed appliance' compound phrase must be PANEL."""
        result = clf.classify(
            raw_sku="FAP1836",
            description="Framed Appliance Panel 18W 36H"
        )
        assert result.category == ItemCategory.PANEL


# ===========================================================================
# F-2: Hood-surround / mantel architectural elements must NOT be APPLIANCE
# Root cause: bare 'hood' in APPLIANCE_KEYWORDS captured hood-ledge and
# hood-mantel descriptions before ARCHITECTURAL_KEYWORDS was checked.
# ===========================================================================

class TestHoodSurroundArchitecturalClassification:

    def test_24mwtldx72_alcove_hood_deluxe_mantel_classified_as_architectural(self, clf):
        """24MWTLDX72: 'ALCOVE HOOD DELUXE MANTEL' must be ARCHITECTURAL_ANNOTATION."""
        result = clf.classify(
            raw_sku="24MWTLDX72",
            description="ALCOVE HOOD DELUXE MANTEL"
        )
        assert result.category == ItemCategory.ARCHITECTURAL_ANNOTATION, (
            f"24MWTLDX72 should be ARCHITECTURAL_ANNOTATION (alcove mantel), got {result.category}: {result.reason}"
        )

    def test_ledge72_alcove_hood_ledge_classified_as_architectural(self, clf):
        """LEDGE72: 'ALCOVE HOOD LEDGE' must be ARCHITECTURAL_ANNOTATION, not APPLIANCE."""
        result = clf.classify(
            raw_sku="LEDGE72",
            description="ALCOVE HOOD LEDGE"
        )
        assert result.category == ItemCategory.ARCHITECTURAL_ANNOTATION, (
            f"LEDGE72 should be ARCHITECTURAL_ANNOTATION (alcove hood ledge), got {result.category}: {result.reason}"
        )

    def test_mantel_description_classified_as_architectural(self, clf):
        """Any item with 'mantel' in description must be ARCHITECTURAL_ANNOTATION."""
        result = clf.classify(
            raw_sku="MNTL72",
            description="Fireplace Mantel Hood Surround"
        )
        assert result.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_alcove_description_classified_as_architectural(self, clf):
        """Any item with 'alcove' in description must be ARCHITECTURAL_ANNOTATION."""
        result = clf.classify(
            raw_sku="ALC36",
            description="Alcove Framing 36W"
        )
        assert result.category == ItemCategory.ARCHITECTURAL_ANNOTATION

    def test_mwtldx_sku_pattern_classified_as_architectural(self, clf):
        """MWTLDX token in SKU (mantel deluxe variant) must match ARCHITECTURAL_SKU_PATTERNS."""
        result = clf.classify(raw_sku="24MWTLDX72", description=None)
        assert result.category == ItemCategory.ARCHITECTURAL_ANNOTATION, (
            f"24MWTLDX72 SKU should match ARCHITECTURAL via MWTLDX pattern, got {result.category}"
        )

    def test_genuine_range_hood_appliance_still_classified_correctly(self, clf):
        """A genuine 'Range Hood' appliance must remain APPLIANCE, not become ARCHITECTURAL.
        Uses a description WITHOUT 'cabinet' to avoid CABINET keyword taking priority.
        The key assertion: bare 'hood' in a non-architectural context stays APPLIANCE.
        """
        result = clf.classify(
            raw_sku="HOOD36",
            description="36 Inch Range Hood Ventilation"
        )
        # 'hood' alone does NOT appear in ARCHITECTURAL_KEYWORDS.
        # Only compound phrases like 'hood ledge', 'alcove hood' trigger ARCHITECTURAL.
        # 'ventilation' is in APPLIANCE_KEYWORDS, so this should remain APPLIANCE.
        assert result.category == ItemCategory.APPLIANCE, (
            f"Range Hood should remain APPLIANCE, got {result.category}: {result.reason}"
        )


# ===========================================================================
# F-3: Hutch Molding must be classified as MOLDING, not UNKNOWN
# Root cause: 'AC8HM8' prefix not matched; description 'BASE HUTCH MLD 8'
# lacked a molding keyword match.
# ===========================================================================

class TestHutchMoldingClassification:

    def test_ac8hm8_arts_crafts_hutch_mld_classified_as_molding(self, clf):
        """AC8HM8: 'ARTS & CRAFTS BASE HUTCH MLD 8' must be MOLDING, not UNKNOWN."""
        result = clf.classify(
            raw_sku="AC8HM8",
            description="ARTS & CRAFTS BASE HUTCH MLD 8"
        )
        assert result.category == ItemCategory.MOLDING, (
            f"AC8HM8 hutch molding should be MOLDING, got {result.category}: {result.reason}"
        )

    def test_hutch_mld_phrase_classified_as_molding(self, clf):
        """'hutch mld' compound phrase in description must trigger MOLDING."""
        result = clf.classify(
            raw_sku="HM6",
            description="6 Inch Hutch Mld Profile"
        )
        assert result.category == ItemCategory.MOLDING

    def test_starter_molding_classified_as_molding(self, clf):
        """'STARTER MOLDING 6H' must be MOLDING."""
        result = clf.classify(
            raw_sku="STARTMLD696",
            description="Starter Molding 6H"
        )
        assert result.category == ItemCategory.MOLDING


# ===========================================================================
# F-4: Repair kits and touch-up kits must be ACCESSORY, not UNKNOWN
# Root cause: 'REPAIR KIT' had no matching keyword; fell through to UNKNOWN.
# ===========================================================================

class TestRepairKitAccessoryClassification:

    def test_rr_repair_kit_classified_as_accessory(self, clf):
        """RR: 'REPAIR KIT' must be ACCESSORY, not UNKNOWN."""
        result = clf.classify(
            raw_sku="RR",
            description="REPAIR KIT"
        )
        assert result.category == ItemCategory.ACCESSORY, (
            f"RR repair kit should be ACCESSORY, got {result.category}: {result.reason}"
        )

    def test_rk_sb_touch_up_kit_classified_as_accessory(self, clf):
        """RK-SB: 'TOUCH UP KIT-SINK BASE' must be ACCESSORY."""
        result = clf.classify(
            raw_sku="RK-SB",
            description="TOUCH UP KIT-SINK BASE"
        )
        assert result.category == ItemCategory.ACCESSORY, (
            f"RK-SB touch-up kit should be ACCESSORY, got {result.category}: {result.reason}"
        )

    def test_rkpp_touch_up_kit_pg_classified_as_accessory(self, clf):
        """RKPP: 'TOUCH UP KIT-PG' must be ACCESSORY."""
        result = clf.classify(
            raw_sku="RKPP",
            description="TOUCH UP KIT-PG"
        )
        assert result.category == ItemCategory.ACCESSORY, (
            f"RKPP touch-up kit should be ACCESSORY, got {result.category}: {result.reason}"
        )

    def test_2cmul2_mullion_front_classified_as_accessory(self, clf):
        """2CMUL2: '2 ECLIPSE MULL-FRONT POS 2' must be ACCESSORY (mullion)."""
        result = clf.classify(
            raw_sku="2CMUL2",
            description="2 ECLIPSE MULL-FRONT POS 2"
        )
        assert result.category == ItemCategory.ACCESSORY, (
            f"2CMUL2 mullion should be ACCESSORY, got {result.category}: {result.reason}"
        )


# ===========================================================================
# Non-regression: existing correct classifications must not break
# ===========================================================================

class TestNonRegression:

    def test_genuine_range_appliance_unchanged(self, clf):
        result = clf.classify(raw_sku="GR606F-LP", description="Gas Range 6 Burner LP")
        assert result.category == ItemCategory.APPLIANCE

    def test_genuine_refrigerator_unchanged(self, clf):
        result = clf.classify(raw_sku="REF36", description="Built-in Refrigerator 36")
        assert result.category == ItemCategory.APPLIANCE

    def test_standard_cabinet_b30_unchanged(self, clf):
        result = clf.classify(raw_sku="B30", description="Base Cabinet 30W")
        assert result.category == ItemCategory.CABINET

    def test_standard_wall_cabinet_w3630_unchanged(self, clf):
        result = clf.classify(raw_sku="W3630", description="Wall Cabinet 36W 30H")
        assert result.category == ItemCategory.CABINET

    def test_toe_kick_molding_unchanged(self, clf):
        result = clf.classify(raw_sku="TK96", description="Toe Kick Material 4.5H")
        assert result.category == ItemCategory.MOLDING

    def test_filler_item_unchanged(self, clf):
        result = clf.classify(raw_sku="BF3", description="Base Filler 3W")
        assert result.category == ItemCategory.FILLER

    def test_commercial_charge_unchanged(self, clf):
        result = clf.classify(raw_sku="FREIGHTSURCHARGE", description="Freight Surcharge")
        assert result.category == ItemCategory.COMMERCIAL_CHARGE

    def test_end_panel_bepf334_classified_as_panel(self, clf):
        result = clf.classify(raw_sku="BEPF334", description="Base End Panel Box")
        assert result.category == ItemCategory.PANEL

    def test_dep3w_filler_end_panel_classified_as_panel(self, clf):
        result = clf.classify(raw_sku="DEP3W", description="Filler w/ End Panel")
        assert result.category == ItemCategory.PANEL

    def test_crown_molding_smcrn_classified_as_molding(self, clf):
        result = clf.classify(raw_sku="SMCRN8", description="SMALL TRADITIONAL CROWN MLD 8")
        assert result.category == ItemCategory.MOLDING
