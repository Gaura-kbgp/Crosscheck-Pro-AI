"""
Regression tests for Human Review discrepancy presentation and state semantics.

These exercise the *real* CrossCheckEngine output through DiscrepancyResponse
(app/api/v1/crosscheck.py) — the single canonical presentation layer — so a
regression in either the engine's source_values keys or the response schema's
derivation is caught.
"""
import pytest
from uuid import uuid4
from app.models.core import (
    CanonicalLineItem, DocumentType, MatchGroup, MatchGroupStatus,
    Discrepancy, Severity, Organization, Project, Document, ItemCategory
)
from app.services.crosscheck_service import CrossCheckService
from app.api.v1.crosscheck import DiscrepancyResponse, compute_discrepancy_summary


def create_item(db_session, project_id, org_id, source_type, sku, qty=1, finish=None, door=None, category=ItemCategory.CABINET):
    doc = Document(
        id=uuid4(),
        project_id=project_id,
        organization_id=org_id,
        document_type=source_type,
        original_filename="test.pdf",
        storage_path=f"path_{uuid4()}.pdf",
        mime_type="application/pdf",
        file_size=100
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    item = CanonicalLineItem(
        project_id=project_id,
        organization_id=org_id,
        document_id=doc.id,
        source_type=source_type,
        raw_sku=sku,
        normalized_sku=sku,
        description="",
        quantity=qty,
        finish=finish,
        door_style=door,
        item_category=category,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def crosscheck_env(db_session):
    org = Organization(name="Presentation Org")
    db_session.add(org)
    db_session.commit()

    project = Project(organization_id=org.id, name="Presentation Proj")
    db_session.add(project)
    db_session.commit()

    service = CrossCheckService(db_session)
    return service, project.id, org.id


def _responses(db_session, project_id) -> list[DiscrepancyResponse]:
    discs = db_session.query(Discrepancy).filter(Discrepancy.project_id == project_id).all()
    return [DiscrepancyResponse.model_validate(d) for d in discs]


def _only(db_session, project_id) -> DiscrepancyResponse:
    responses = _responses(db_session, project_id)
    assert len(responses) == 1
    return responses[0]


class TestIntroducedAtIsDeterministic:
    """introduced_at must be the FIRST source (Design -> Order -> Ack, in that
    order) in which the canonical item actually exists — never inferred, and
    never a document that itself has no value for the item."""

    def test_design_present_order_missing_ack_missing(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.design_value == "PRESENT"
        assert r.order_value == "MISSING"
        assert r.ack_value == "MISSING"
        assert r.introduced_at == "DESIGN"

    def test_design_present_order_present_ack_present(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", qty=3)
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", qty=2)
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", qty=2)

        service.process_project(project_id, org_id)
        d = db_session.query(Discrepancy).filter_by(field="quantity").first()
        # Quantity attribution is a separate, unchanged rule (first divergence),
        # not the presence-based rule under test here — see test_crosscheck.py.
        assert d.introduced_at == DocumentType.ORDER

    def test_design_present_order_missing_ack_present(self, db_session, crosscheck_env):
        """Design PRESENT / Order OMITTED / Ack RESTORED -> DESIGN (first present source)."""
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.design_value == "PRESENT"
        assert r.order_value == "OMITTED"
        assert r.ack_value == "RESTORED"
        assert r.introduced_at == "DESIGN"

    def test_design_absent_order_present_ack_missing(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.design_value == "ABSENT"
        assert r.order_value == "ADDED"
        assert r.ack_value == "OMITTED"
        assert r.introduced_at == "ORDER"

    def test_design_absent_order_present_ack_present(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.design_value == "ABSENT"
        assert r.order_value == "PRESENT"
        assert r.ack_value == "PRESENT"
        assert r.introduced_at == "ORDER"

    def test_design_absent_order_absent_ack_present(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.design_value == "ABSENT"
        assert r.order_value == "ABSENT"
        assert r.ack_value == "PRESENT"
        assert r.introduced_at == "ACKNOWLEDGEMENT"


class TestAckValueNeverBlankWhenAckProcessed:
    """'Never display Ack: – when the acknowledgement source was successfully
    processed; show PRESENT or ABSENT.' (and real values for non-presence fields)"""

    def test_extra_item_added_in_ack_only(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.field == "item_presence"
        assert r.ack_value == "PRESENT"
        assert r.ack_value is not None

    def test_extra_item_added_in_order_not_acknowledged(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        # Ack was processed (project has no ack doc for this item) and explicitly
        # has no data for this SKU: must show OMITTED, never a bare dash.
        assert r.ack_value == "OMITTED"

    def test_quantity_discrepancy_shows_real_ack_number(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123", qty=3)
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123", qty=3)
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123", qty=2)

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.field == "quantity"
        assert r.ack_value == 2
        assert r.design_value == 3
        assert r.order_value == 3

    def test_sku_substitution_shows_real_ack_sku(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "A123")
        ack = create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "A123-SUB")
        ack.substitution_sku = "A123"
        db_session.commit()

        service.process_project(project_id, org_id)
        r = _only(db_session, project_id)

        assert r.field == "sku"
        assert r.ack_value == "A123-SUB"
        assert r.ack_value is not None


class TestSeverityNormalization:
    """Severity summary counters must match actual findings: backend stores
    Title Case ("Critical"/"Warning"/"Info"); the API must expose the exact
    upper-case tokens ("CRITICAL"/"WARNING"/"INFO"/"HIGH") every consumer
    (filters, summary counts, badge colors) compares against."""

    def test_severity_serialized_upper_case(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")

        service.process_project(project_id, org_id)
        d = db_session.query(Discrepancy).first()
        assert d.severity == Severity.CRITICAL  # stored Title Case

        r = DiscrepancyResponse.model_validate(d)
        dumped = r.model_dump(mode="json")
        assert dumped["severity"] == "CRITICAL"

    def test_summary_counts_match_open_findings(self, db_session, crosscheck_env):
        service, project_id, org_id = crosscheck_env
        # 1 critical (missing item, cabinet category)
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        # 1 warning (quantity change)
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "B123", qty=3)
        create_item(db_session, project_id, org_id, DocumentType.ORDER, "B123", qty=2)
        create_item(db_session, project_id, org_id, DocumentType.ACKNOWLEDGEMENT, "B123", qty=2)

        service.process_project(project_id, org_id)
        responses = _responses(db_session, project_id)
        dumped = [r.model_dump(mode="json") for r in responses]

        critical_count = sum(1 for d in dumped if d["severity"] == "CRITICAL")
        warning_count = sum(1 for d in dumped if d["severity"] == "WARNING")

        assert critical_count == 1
        assert warning_count == 1
        assert critical_count + warning_count == len(dumped)


class TestDiscrepancySummaryConsistency:
    """open_count must equal critical + high + warning + info when every
    finding is OPEN, and reviewed/escalated findings must never be double
    counted into OPEN — using the same compute_discrepancy_summary the
    /crosscheck endpoint returns to the frontend."""

    def test_open_count_equals_severity_breakdown_sum(self, db_session, crosscheck_env):
        """
        compute_discrepancy_summary is exercised directly against known
        Critical/Warning/Info rows (rather than relying on the fuzzy matcher
        to produce a specific severity mix) to reproduce the exact reported
        regression deterministically: 29 + 37 != 67 because Info was silently
        dropped from the displayed sum.
        """
        service, project_id, org_id = crosscheck_env
        mg = MatchGroup(project_id=project_id, organization_id=org_id, status=MatchGroupStatus.UNCERTAIN)
        db_session.add(mg)
        db_session.commit()

        def make_disc(field, severity):
            return Discrepancy(
                project_id=project_id, organization_id=org_id, match_group_id=mg.id,
                field=field, source_values={}, comparison_values={},
                status="OPEN", severity=severity,
            )

        discs = [
            make_disc("item_presence", Severity.CRITICAL),
            make_disc("quantity", Severity.WARNING),
            make_disc("sku", Severity.INFO),
        ]
        db_session.add_all(discs)
        db_session.commit()

        assert all(d.status == "OPEN" for d in discs)

        summary = compute_discrepancy_summary(discs)

        assert summary.open == len(discs)
        assert summary.open == summary.critical + summary.high + summary.warning + summary.info
        # Reproduces the exact reported regression: 29 + 37 != 67 because Info
        # was silently dropped from the sum — this asserts it no longer is.
        assert summary.critical == 1
        assert summary.warning == 1
        assert summary.info == 1

    def test_reviewed_and_escalated_excluded_from_open(self, db_session, crosscheck_env):
        from app.services.review_service import ReviewService
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "B123")
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "C123")
        service.process_project(project_id, org_id)

        discs = db_session.query(Discrepancy).filter(Discrepancy.project_id == project_id).all()
        assert len(discs) == 3

        ReviewService.accept_finding(db_session, discs[0].id, org_id, reviewer_id=uuid4())
        ReviewService.escalate(db_session, discs[1].id, org_id, reviewer_id=uuid4())
        # discs[2] stays OPEN

        db_session.expire_all()
        refreshed = db_session.query(Discrepancy).filter(Discrepancy.project_id == project_id).all()
        summary = compute_discrepancy_summary(refreshed)

        assert summary.open == 1
        assert summary.escalated == 1
        assert summary.reviewed == 1
        assert summary.open + summary.escalated + summary.reviewed == len(refreshed)
        # The accepted/escalated findings must not also be counted as open
        assert summary.open != len(refreshed)


class TestReviewStatusSemantics:
    """Review status must be derived consistently: ACCEPT_FINDING and
    ACKNOWLEDGE_MFR_CHANGE must produce distinct, frontend-recognized
    statuses (ACCEPTED / ACKNOWLEDGED), not a shared, unrecognized "RESOLVED"
    that the Reviewed summary counter and status filter never match."""

    def test_accept_finding_sets_accepted(self, db_session, crosscheck_env):
        from app.services.review_service import ReviewService
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        service.process_project(project_id, org_id)
        disc = db_session.query(Discrepancy).first()

        ReviewService.accept_finding(db_session, disc.id, org_id, reviewer_id=uuid4())
        db_session.refresh(disc)

        assert disc.status == "ACCEPTED"
        assert disc.status != "RESOLVED"

    def test_acknowledge_mfr_change_sets_acknowledged(self, db_session, crosscheck_env):
        from app.services.review_service import ReviewService
        service, project_id, org_id = crosscheck_env
        create_item(db_session, project_id, org_id, DocumentType.DESIGN, "A123")
        service.process_project(project_id, org_id)
        disc = db_session.query(Discrepancy).first()

        ReviewService.acknowledge_mfr_change(db_session, disc.id, org_id, reviewer_id=uuid4())
        db_session.refresh(disc)

        assert disc.status == "ACKNOWLEDGED"
        assert disc.status != "RESOLVED"
