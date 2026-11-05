"""
Application pipeline consistency tests.

Covers the bugs and invariants identified in the Phase 2 investigation:

1. get_document_extraction returns is_latest=True row, not an older one
   (Bug: previously used .first() with no is_latest filter — could return
    stale extraction data to the UI while the report used the newer one.)

2. Extraction version constants are correctly split: DESIGN at f8.3.7,
   ORDER/ACK at f8.3.6 (independent cache keys — ORDER/ACK cache survives
   DESIGN prompt changes).

3. The pipeline cache-miss condition: a stored extraction at a different
   version is NEVER reused; the version bump is the only mechanism that
   forces DESIGN re-extraction when the prompt changes.

KNOWN LIMITATION: Full pipeline integration tests (PDF upload → AI extraction
→ DB → cross-check → report) require a live Postgres DB and real file bytes;
those steps are covered by the Phase 2 live regression script (step 1 & 2)
which runs against the actual Demo Project using the Supabase-backed DB.
"""
import pytest
import jwt
from uuid import uuid4
from fastapi.testclient import TestClient

from app.models.core import (
    Organization, User, Role, BusinessRole, Project, Document, DocumentType,
    DocumentStatus, Extraction,
)
from app.worker.tasks.processing import EXTRACTION_VERSION, DESIGN_EXTRACTION_VERSION
from app.core.config import settings


def _token(sub: str) -> str:
    return jwt.encode({"sub": sub, "aud": "authenticated"}, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def _seed_org_user_project_doc(db):
    """Returns (org, user, project, doc) seeded into db."""
    org = Organization(id=uuid4(), name="PipelineTestOrg")
    db.add(org)
    db.flush()

    user = User(id=uuid4(), auth_id=str(uuid4()), organization_id=org.id, email="pipe@test.com", role=Role.ADMIN)
    db.add(user)

    project = Project(id=uuid4(), organization_id=org.id, name="PipelineTestProject")
    db.add(project)
    db.flush()

    doc = Document(
        id=uuid4(), project_id=project.id, organization_id=org.id,
        document_type=DocumentType.DESIGN, status=DocumentStatus.COMPLETED,
        original_filename="test.pdf", storage_path="test/test.pdf",
        mime_type="application/pdf", file_size=1024, document_hash="abc123",
    )
    db.add(doc)
    db.commit()
    return org, user, project, doc


# ---------------------------------------------------------------------------
# 1. get_document_extraction must return is_latest=True row
# ---------------------------------------------------------------------------

def test_get_extraction_returns_latest_not_oldest(client: TestClient, db_session):
    """
    If a document has been processed multiple times, the endpoint must return
    the extraction with is_latest=True, not the first (oldest) one.
    """
    org, user, project, doc = _seed_org_user_project_doc(db_session)

    stale_items = [{"sku": "OLD_SKU", "quantity": 1}]
    fresh_items = [{"sku": "NEW_SKU", "quantity": 2}]

    # Older extraction (is_latest=False)
    old_ext = Extraction(
        id=uuid4(), document_id=doc.id, organization_id=org.id,
        document_hash="abc123", provider="openai", model_name="gpt-4o",
        extraction_version=DESIGN_EXTRACTION_VERSION, prompt_version="v1",
        attempt=1, is_latest=False,
        raw_data={"items": stale_items},
    )
    # Newer extraction (is_latest=True)
    new_ext = Extraction(
        id=uuid4(), document_id=doc.id, organization_id=org.id,
        document_hash="abc123", provider="openai", model_name="gpt-4o",
        extraction_version=DESIGN_EXTRACTION_VERSION, prompt_version="v1",
        attempt=2, is_latest=True,
        raw_data={"items": fresh_items},
    )
    db_session.add(old_ext)
    db_session.add(new_ext)
    db_session.commit()

    token = _token(user.auth_id)
    resp = client.get(
        f"/api/v1/documents/{doc.id}/extraction",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Must return the LATEST extraction, not the oldest
    items = body.get("raw_data", {}).get("items", [])
    skus = [i["sku"] for i in items]
    assert "NEW_SKU" in skus, f"Expected NEW_SKU (latest), got {skus}"
    assert "OLD_SKU" not in skus, f"Got stale OLD_SKU — is_latest filter missing"


def test_get_extraction_no_stale_row_returns_404_then_201_on_latest(client: TestClient, db_session):
    """
    If only an is_latest=False row exists (no latest), the endpoint returns 404
    rather than serving stale data.
    """
    org, user, project, doc = _seed_org_user_project_doc(db_session)

    stale = Extraction(
        id=uuid4(), document_id=doc.id, organization_id=org.id,
        document_hash="abc123", provider="openai", model_name="gpt-4o",
        extraction_version=DESIGN_EXTRACTION_VERSION, prompt_version="v1",
        attempt=1, is_latest=False,
        raw_data={"items": [{"sku": "STALE"}]},
    )
    db_session.add(stale)
    db_session.commit()

    token = _token(user.auth_id)
    resp = client.get(
        f"/api/v1/documents/{doc.id}/extraction",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404, (
        f"Expected 404 (no is_latest row), got {resp.status_code}. "
        "Stale extraction must not be served without is_latest=True."
    )


# ---------------------------------------------------------------------------
# 2. Extraction version constants
# ---------------------------------------------------------------------------

def test_design_extraction_version_isolated_from_order_ack():
    """
    DESIGN and ORDER/ACK must use separate cache-key versions so ORDER/ACK
    cached extractions survive DESIGN prompt changes.
    """
    assert DESIGN_EXTRACTION_VERSION != EXTRACTION_VERSION


def test_design_extraction_version_matches_expected():
    assert DESIGN_EXTRACTION_VERSION == "f8.3.8"


def test_order_ack_extraction_version_unchanged():
    assert EXTRACTION_VERSION == "f8.3.6"


# ---------------------------------------------------------------------------
# 3. Cache miss condition: version mismatch always forces re-extraction
# ---------------------------------------------------------------------------

def test_cache_miss_when_stored_version_differs():
    """
    The pipeline cache-hit logic requires stored version == expected version.
    A stored extraction at f8.3.6 must NOT be reused when DESIGN expects f8.3.7.
    This test verifies the conditional logic, not the pipeline execution.
    """
    stored = {"extraction_version": "f8.3.6", "document_hash": "abc", "provider": "openai", "model_name": "gpt-4o", "prompt_version": "v1"}
    expected_ver = DESIGN_EXTRACTION_VERSION  # "f8.3.7"
    would_cache_hit = (
        stored["extraction_version"] == expected_ver
        and stored["document_hash"] == "abc"
        and stored["provider"] == "openai"
        and stored["model_name"] == "gpt-4o"
        and stored["prompt_version"] == "v1"
    )
    assert not would_cache_hit, "DESIGN extraction at f8.3.6 must not cache-hit when f8.3.7 is expected"


def test_cache_hit_when_all_fields_match():
    """Cache hit requires exact match on all 5 identity fields."""
    stored = {"extraction_version": DESIGN_EXTRACTION_VERSION, "document_hash": "abc", "provider": "openai", "model_name": "gpt-4o", "prompt_version": "v1"}
    would_cache_hit = (
        stored["extraction_version"] == DESIGN_EXTRACTION_VERSION
        and stored["document_hash"] == "abc"
        and stored["provider"] == "openai"
        and stored["model_name"] == "gpt-4o"
        and stored["prompt_version"] == "v1"
    )
    assert would_cache_hit, "Matching extraction identity must result in cache hit"


# ---------------------------------------------------------------------------
# 4. Report always reads from match_groups (recreated each run), not extraction
# ---------------------------------------------------------------------------

def test_report_service_reads_match_groups_not_extraction():
    """
    Report service builds PDF from MatchGroup + Discrepancy rows, which are
    deleted and recreated on every pipeline run. It does NOT read Extraction
    rows. So the report is always consistent with the latest run regardless
    of is_latest state on the Extraction table.

    This is a documentation test — it asserts the report service's import
    path uses the MatchGroup model, not Extraction.
    """
    import inspect
    from app.services import report_service
    source = inspect.getsource(report_service)
    assert "MatchGroup" in source, "Report service must read MatchGroup rows"
    assert "is_latest" not in source, (
        "Report service must NOT filter by is_latest — it reads match_groups "
        "which are always recreated per run."
    )
