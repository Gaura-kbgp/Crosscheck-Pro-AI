"""
Cabinet Code Intelligence tests.

Every new classification/normalization behavior here has both a positive and
a negative counterpart, per the spec's explicit requirement that a false
UNCERTAIN is acceptable but a false VERIFIED is not. The most important
single property under test is backward compatibility: with no manufacturer
configured, CabinetCodeIntelligence.analyze_candidate() must return exactly
the same category/confidence the pre-existing ItemClassifier already
produces for the same inputs.
"""
import uuid
import pytest

from app.models.core import (
    DocumentType, ItemCategory, Manufacturer, ManufacturerCodeDictionary,
    Organization, Project,
)
from app.engines.classification import ItemClassifier
from app.engines.cabinet_intelligence import CabinetCodeIntelligence
from app.engines.cabinet_intelligence.models import ConfidenceLevel, VerificationSource
from app.engines.normalization import normalize_sku


@pytest.fixture
def db_env(db_session):
    org = Organization(name="CCI Org")
    db_session.add(org)
    db_session.commit()
    project = Project(organization_id=org.id, name="CCI Proj")
    db_session.add(project)
    db_session.commit()
    return db_session, project.id, org.id


@pytest.fixture
def cci_no_manufacturer(db_env):
    db_session, _, _ = db_env
    return CabinetCodeIntelligence(db_session, manufacturer_id=None)


def _seed_manufacturer(db_session, org_id=None):
    m = Manufacturer(id=uuid.uuid4(), organization_id=org_id, name=f"TestMfr-{uuid.uuid4().hex[:6]}")
    db_session.add(m)
    db_session.commit()
    return m


def _seed_code(db_session, manufacturer_id, code, category, alias_group=None, is_primary_alias=True):
    row = ManufacturerCodeDictionary(
        id=uuid.uuid4(),
        manufacturer_id=manufacturer_id,
        code=code,
        normalized_code=normalize_sku(code),
        category=category,
        alias_group=alias_group,
        is_primary_alias=is_primary_alias,
    )
    db_session.add(row)
    db_session.commit()
    return row


class TestBackwardCompatibilityWithNoManufacturer:
    """Critical requirement: identical output to the unmodified ItemClassifier
    when Project.manufacturer_id is NULL."""

    @pytest.mark.parametrize("sku,description", [
        ("B36", None),
        ("W3030", None),
        ("BT36B-2", "Base w/ 2 Roll-Out Trays"),
        ("21AHSDX7230", "ALCOVE HOOD DELUXE SOFFIT"),
        ("FREIGHTSURCHARGE", "Freight Surcharge"),
        ("STARTMOLD696", "Starter Molding"),
        ("SUCTIONCUPNONCHG", "Suction Cup Non-Charge"),
        (None, None),
        ("ORDER123", None),
    ])
    def test_identical_category_and_confidence(self, cci_no_manufacturer, sku, description):
        plain = ItemClassifier().classify(raw_sku=sku, description=description, source_type=DocumentType.ACKNOWLEDGEMENT)
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=description, source_type=DocumentType.ACKNOWLEDGEMENT)
        assert decision.classification == plain.category
        assert decision.confidence_score == plain.confidence

    def test_raw_sku_never_overwritten(self, cci_no_manufacturer):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku="BpFhC12", description="cabinet")
        assert decision.raw_code == "BpFhC12"


class TestGenericCodesRemainCandidatesNotAutoVerified:
    @pytest.mark.parametrize("sku", ["B36", "W3030", "DB24", "SB36", "BW2430"])
    def test_generic_nkba_style_code_never_high_confidence_without_manufacturer(self, cci_no_manufacturer, sku):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=None)
        assert decision.confidence_level != ConfidenceLevel.HIGH
        assert decision.is_verified is False


class TestManufacturerStyleCodesNotRejected:
    @pytest.mark.parametrize("sku", ["BT36B-2", "BT18-2-L", "24UT3693B-4", "21AHSDX7230"])
    def test_not_forced_to_unknown_merely_for_unusual_shape(self, cci_no_manufacturer, sku):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=None)
        # Must not be silently discarded — it's still a real classification
        # attempt (possibly UNKNOWN/LOW without more evidence, never crashes).
        assert decision.raw_code == sku
        assert decision.classification is not None


class TestManufacturerExactMatch:
    def test_exact_dictionary_match_is_high_confidence_verified(self, db_env):
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BT36B-2", ItemCategory.CABINET)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        decision = cci.analyze_candidate(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays", source_type=DocumentType.ACKNOWLEDGEMENT)
        assert decision.classification == ItemCategory.CABINET
        assert decision.is_verified is True
        assert decision.confidence_level == ConfidenceLevel.HIGH
        assert decision.verification_source == VerificationSource.MANUFACTURER_EXACT
        assert "EXACT_MANUFACTURER_MATCH" in decision.reason_codes

    def test_exact_match_overrides_flawed_generic_keyword_misclassification(self, db_env):
        """Regression motivation: the generic classifier alone misclassifies
        BT36B-2 as ACCESSORY because its description contains 'roll-out'.
        A real manufacturer dictionary entry must correct this."""
        db_session, project_id, org_id = db_env
        plain = ItemClassifier().classify(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays")
        assert plain.category == ItemCategory.ACCESSORY  # pre-existing classifier limitation, confirmed unchanged

        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BT36B-2", ItemCategory.CABINET)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)
        decision = cci.analyze_candidate(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays")
        assert decision.classification == ItemCategory.CABINET

    def test_no_match_falls_through_to_generic_classifier(self, db_env):
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BT36B-2", ItemCategory.CABINET)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        decision = cci.analyze_candidate(raw_sku="FREIGHTSURCHARGE", description="Freight Surcharge")
        assert decision.classification == ItemCategory.COMMERCIAL_CHARGE
        assert decision.verification_source != VerificationSource.MANUFACTURER_EXACT
        assert "NO_MANUFACTURER_MATCH" in decision.reason_codes


class TestManufacturerAliasVsOCRErrorVsTrueDifferentSKU:
    def test_documented_alias_is_manufacturer_alias_not_ocr_error(self, db_env):
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BFHC12", ItemCategory.CABINET, alias_group="BFHC12-GROUP", is_primary_alias=True)
        _seed_code(db_session, mfr.id, "BPFHC12", ItemCategory.CABINET, alias_group="BFHC12-GROUP", is_primary_alias=False)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        decision = cci.analyze_candidate(raw_sku="BPFHC12", description="Full Height Cabinet")
        assert decision.classification == ItemCategory.CABINET
        assert decision.verification_source == VerificationSource.MANUFACTURER_ALIAS
        assert "MANUFACTURER_ALIAS_MATCH" in decision.reason_codes
        assert decision.is_verified is True

    def test_undocumented_variant_is_not_treated_as_alias(self, db_env):
        """Negative: a spelling NOT curated in the dictionary must not be
        silently accepted as an alias just because it looks similar."""
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BFHC12", ItemCategory.CABINET, alias_group="BFHC12-GROUP", is_primary_alias=True)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        decision = cci.analyze_candidate(raw_sku="BFHC1Z", description="Full Height Cabinet")
        assert decision.verification_source not in (VerificationSource.MANUFACTURER_EXACT, VerificationSource.MANUFACTURER_ALIAS)

    @pytest.mark.parametrize("raw,expected_primary", [
        ("BP52", "BPS12"),
        ("B18BWD18", "B18DWB"),
        ("SB36B3", "SBA36B"),
    ])
    def test_mark_kitchen_known_variants_resolve_via_dictionary(self, db_env, raw, expected_primary):
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        group = f"GROUP-{expected_primary}"
        _seed_code(db_session, mfr.id, expected_primary, ItemCategory.CABINET, alias_group=group, is_primary_alias=True)
        _seed_code(db_session, mfr.id, raw, ItemCategory.CABINET, alias_group=group, is_primary_alias=False)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        decision = cci.analyze_candidate(raw_sku=raw, description="Cabinet")
        assert decision.classification == ItemCategory.CABINET
        assert decision.verification_source == VerificationSource.MANUFACTURER_ALIAS
        assert decision.raw_code == raw  # never overwritten


class TestNonCabinetExclusion:
    @pytest.mark.parametrize("sku,description,expected", [
        ("FREIGHTSURCHARGE", "Freight Surcharge", ItemCategory.COMMERCIAL_CHARGE),
        ("TARIFFSURCHARGE", "Tariff Surcharge", ItemCategory.COMMERCIAL_CHARGE),
        ("STARTMOLD696", "Starter Molding", ItemCategory.MOLDING),
        ("SUCTIONCUPNONCHG", "Suction Cup Non-Charge", ItemCategory.COMMERCIAL_CHARGE),
    ])
    def test_known_non_cabinet_lines_excluded(self, cci_no_manufacturer, sku, description, expected):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=description)
        assert decision.classification == expected
        assert decision.is_cabinet_candidate is False
        assert decision.reason_codes and decision.reason_codes[0].startswith("NON_CABINET")


class TestAdversarialFalsePositives:
    """These must NOT be classified as CABINET merely for containing letters+numbers."""

    @pytest.mark.parametrize("sku", [
        "ORDER123", "PROJECT2026", "PAGE36", "ROOM3030", "NOTE123", "REV24",
    ])
    def test_administrative_tokens_never_become_cabinet(self, cci_no_manufacturer, sku):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=None)
        assert decision.classification != ItemCategory.CABINET or decision.confidence_level == ConfidenceLevel.UNCERTAIN

    @pytest.mark.parametrize("sku,description", [
        ("FREIGHT123", "Freight charge"),
        ("TAX36", "Sales tax"),
        ("DELIVERY24", "Delivery fee"),
    ])
    def test_commercial_looking_tokens_never_become_cabinet(self, cci_no_manufacturer, sku, description):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=sku, description=description)
        assert decision.classification != ItemCategory.CABINET


class TestAmbiguousStaysUncertain:
    def test_empty_sku_and_description_is_uncertain(self, cci_no_manufacturer):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku=None, description=None)
        assert decision.confidence_level == ConfidenceLevel.UNCERTAIN

    def test_never_promotes_low_evidence_to_verified(self, cci_no_manufacturer):
        decision = cci_no_manufacturer.analyze_candidate(raw_sku="XQ7", description=None)
        assert decision.is_verified is False


class TestOCRVisionConflictForcesUncertainty:
    """§35: an unresolved OCR/Vision SKU disagreement with no manufacturer
    confirmation must never present as more confident than UNCERTAIN."""

    def test_conflict_without_manufacturer_forces_uncertain(self, cci_no_manufacturer):
        verification = {
            "method": "OCR_PLUS_VISION",
            "status": "UNCERTAIN",
            "conflicts": [{"field": "sku", "ocr_value": "BT36B-Z", "vision_value": "BT36B-2"}],
        }
        decision = cci_no_manufacturer.analyze_candidate(
            raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays",
            reconciliation_verification=verification,
        )
        assert decision.confidence_level == ConfidenceLevel.UNCERTAIN
        assert "OCR_VISION_CONFLICT" in decision.reason_codes

    def test_conflict_resolved_by_manufacturer_evidence_on_candidate_spelling(self, db_env):
        """If the OCR-side spelling doesn't match the dictionary but the
        Vision-side conflicting spelling does, that counts as real evidence —
        it does not fabricate anything, it checks an actually-extracted value."""
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr.id, "BT36B-2", ItemCategory.CABINET)
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        verification = {
            "method": "OCR_PLUS_VISION",
            "status": "UNCERTAIN",
            "conflicts": [{"field": "sku", "ocr_value": "BT36B-Z", "vision_value": "BT36B-2"}],
        }
        decision = cci.analyze_candidate(
            raw_sku="BT36B-Z", description="Base w/ 2 Roll-Out Trays",
            reconciliation_verification=verification,
            candidate_skus=["BT36B-2"],
        )
        assert decision.classification == ItemCategory.CABINET
        assert decision.verification_source == VerificationSource.MANUFACTURER_EXACT
        assert decision.raw_code == "BT36B-Z"  # raw value from THIS item's own extraction never overwritten

    def test_no_conflict_and_verified_reconciliation_notes_agreement(self, cci_no_manufacturer):
        verification = {"method": "OCR_PLUS_VISION", "status": "VERIFIED"}
        decision = cci_no_manufacturer.analyze_candidate(
            raw_sku="BT36B-2", description="Base Cabinet", reconciliation_verification=verification,
        )
        assert "OCR_VISION_AGREEMENT" in decision.reason_codes


class TestManufacturerDictionaryIsolation:
    def test_dictionary_scoped_strictly_to_its_own_manufacturer(self, db_env):
        db_session, project_id, org_id = db_env
        mfr_a = _seed_manufacturer(db_session)
        mfr_b = _seed_manufacturer(db_session)
        _seed_code(db_session, mfr_a.id, "B36", ItemCategory.CABINET)

        cci_b = CabinetCodeIntelligence(db_session, manufacturer_id=mfr_b.id)
        decision = cci_b.analyze_candidate(raw_sku="B36", description=None)
        assert decision.verification_source != VerificationSource.MANUFACTURER_EXACT

    def test_no_dictionary_entries_behaves_like_no_manufacturer(self, db_env, cci_no_manufacturer):
        db_session, project_id, org_id = db_env
        mfr = _seed_manufacturer(db_session)  # no dictionary rows seeded
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=mfr.id)

        plain_decision = cci_no_manufacturer.analyze_candidate(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays")
        empty_dict_decision = cci.analyze_candidate(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays")
        assert plain_decision.classification == empty_dict_decision.classification
        assert plain_decision.confidence_score == empty_dict_decision.confidence_score
