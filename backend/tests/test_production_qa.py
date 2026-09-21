import pytest
import uuid
import time
import jwt
from app.core.config import settings
from app.models.core import (
    Organization, User, Project, Document, DocumentType, DocumentStatus,
    CanonicalLineItem, MatchGroup, Discrepancy, MatchGroupStatus, Severity,
    Role, ProjectStatus, HumanReview, ReviewAction, AuditLog
)
from app.services.crosscheck_service import CrossCheckService
from app.services.report_service import ReportService
from app.services.review_service import ReviewService

def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

@pytest.fixture
def multi_org_setup(db_session):
    # Org A
    org_a = Organization(name="Organization Alpha")
    db_session.add(org_a)
    db_session.commit()

    admin_a = User(auth_id="auth-admin-a", email="admin@alpha.com", role=Role.ADMIN, organization_id=org_a.id)
    rev_a = User(auth_id="auth-rev-a", email="rev@alpha.com", role=Role.REVIEWER, organization_id=org_a.id)
    view_a = User(auth_id="auth-view-a", email="view@alpha.com", role=Role.VIEWER, organization_id=org_a.id)
    db_session.add_all([admin_a, rev_a, view_a])
    db_session.commit()

    proj_a = Project(name="Alpha Project", status=ProjectStatus.COMPLETED, organization_id=org_a.id)
    db_session.add(proj_a)
    db_session.commit()

    doc_a = Document(
        project_id=proj_a.id,
        organization_id=org_a.id,
        document_type=DocumentType.DESIGN,
        original_filename="alpha_design.pdf",
        storage_path=f"{org_a.id}/{proj_a.id}/doc_a.pdf",
        mime_type="application/pdf",
        file_size=1000,
        status=DocumentStatus.COMPLETED
    )
    db_session.add(doc_a)
    db_session.commit()

    mg_a = MatchGroup(
        project_id=proj_a.id,
        organization_id=org_a.id,
        status=MatchGroupStatus.MATCHED,
        final_sku="ALPHA-SKU-1",
        final_quantity=1
    )
    db_session.add(mg_a)
    db_session.commit()

    disc_a = Discrepancy(
        project_id=proj_a.id,
        organization_id=org_a.id,
        match_group_id=mg_a.id,
        field="quantity",
        source_values={"design": 1},
        comparison_values={"order": 1},
        severity=Severity.INFO,
        status="OPEN"
    )
    db_session.add(disc_a)
    db_session.commit()

    # Org B
    org_b = Organization(name="Organization Beta")
    db_session.add(org_b)
    db_session.commit()

    admin_b = User(auth_id="auth-admin-b", email="admin@beta.com", role=Role.ADMIN, organization_id=org_b.id)
    proj_b = Project(name="Beta Project", status=ProjectStatus.COMPLETED, organization_id=org_b.id)
    db_session.add_all([admin_b, proj_b])
    db_session.commit()

    return {
        "org_a": org_a,
        "admin_a": admin_a,
        "rev_a": rev_a,
        "view_a": view_a,
        "proj_a": proj_a,
        "doc_a": doc_a,
        "mg_a": mg_a,
        "disc_a": disc_a,
        "org_b": org_b,
        "admin_b": admin_b,
        "proj_b": proj_b
    }

# =================================================================
# 1. TENANT ISOLATION QA
# =================================================================

def test_tenant_isolation_project_access(client, multi_org_setup):
    admin_b = multi_org_setup["admin_b"]
    proj_a = multi_org_setup["proj_a"]

    token_b = create_test_token(admin_b.auth_id)
    headers_b = {
        "Authorization": f"Bearer {token_b}"
    }

    # Org B user attempts to access Org A project -> 404
    res = client.get(f"/api/v1/projects/{proj_a.id}", headers=headers_b)
    assert res.status_code in [403, 404]

def test_tenant_isolation_reports_access(client, multi_org_setup):
    admin_b = multi_org_setup["admin_b"]
    proj_a = multi_org_setup["proj_a"]

    token_b = create_test_token(admin_b.auth_id)
    headers_b = {
        "Authorization": f"Bearer {token_b}"
    }

    # Org B user attempts to create or fetch report for Org A project
    res_create = client.post(f"/api/v1/projects/{proj_a.id}/reports", json={"format": "PDF"}, headers=headers_b)
    assert res_create.status_code in [403, 404]

    res_csv = client.get(f"/api/v1/projects/{proj_a.id}/reports/csv", headers=headers_b)
    assert res_csv.status_code in [403, 404]

def test_tenant_isolation_crosscheck_access(client, multi_org_setup):
    admin_b = multi_org_setup["admin_b"]
    proj_a = multi_org_setup["proj_a"]

    token_b = create_test_token(admin_b.auth_id)
    headers_b = {
        "Authorization": f"Bearer {token_b}"
    }

    res = client.get(f"/api/v1/projects/{proj_a.id}/crosscheck", headers=headers_b)
    assert res.status_code in [403, 404]

# =================================================================
# 2. RBAC QA
# =================================================================

def test_rbac_viewer_cannot_mutate_projects(client, multi_org_setup):
    view_a = multi_org_setup["view_a"]
    proj_a = multi_org_setup["proj_a"]

    token_view = create_test_token(view_a.auth_id)
    headers_view = {
        "Authorization": f"Bearer {token_view}"
    }

    # VIEWER cannot create projects
    res_create = client.post("/api/v1/projects", json={"name": "Illegal Project"}, headers=headers_view)
    assert res_create.status_code == 403

    # VIEWER cannot delete projects
    res_del = client.delete(f"/api/v1/projects/{proj_a.id}", headers=headers_view)
    assert res_del.status_code == 403

def test_rbac_viewer_cannot_review(client, multi_org_setup):
    view_a = multi_org_setup["view_a"]
    disc_a = multi_org_setup["disc_a"]

    token_view = create_test_token(view_a.auth_id)
    headers_view = {
        "Authorization": f"Bearer {token_view}"
    }

    res_review = client.post(
        f"/api/v1/discrepancies/{disc_a.id}/review",
        json={"action": "ACCEPT_FINDING", "reason": "Viewer override"},
        headers=headers_view
    )
    assert res_review.status_code == 403

# =================================================================
# 3. FINALIZATION QA & IMMUTABILITY
# =================================================================

def test_finalized_project_blocks_review_mutations(db_session, multi_org_setup):
    proj_a = multi_org_setup["proj_a"]
    disc_a = multi_org_setup["disc_a"]
    rev_a = multi_org_setup["rev_a"]
    org_a = multi_org_setup["org_a"]

    # Finalize project
    ReviewService.finalize_project(db_session, proj_a.id, org_a.id, rev_a.id)

    # Attempt review on finalized project should raise error
    with pytest.raises(Exception) as exc:
        ReviewService.accept_finding(db_session, disc_a.id, org_a.id, rev_a.id, "Late review")
    assert "Cannot modify a finalized project" in str(exc.value)

# =================================================================
# 4. PERFORMANCE & SCALE QA
# =================================================================

def test_crosscheck_and_report_performance(db_session, multi_org_setup):
    org = multi_org_setup["org_a"]
    
    perf_proj = Project(name="Large Scale Test", status=ProjectStatus.PROCESSING, organization_id=org.id)
    db_session.add(perf_proj)
    db_session.commit()

    # Generate 50 line items for 3 documents
    doc_d = Document(project_id=perf_proj.id, organization_id=org.id, document_type=DocumentType.DESIGN, original_filename="d.pdf", storage_path="p1", mime_type="application/pdf", file_size=10, status=DocumentStatus.COMPLETED)
    doc_o = Document(project_id=perf_proj.id, organization_id=org.id, document_type=DocumentType.ORDER, original_filename="o.pdf", storage_path="p2", mime_type="application/pdf", file_size=10, status=DocumentStatus.COMPLETED)
    doc_a = Document(project_id=perf_proj.id, organization_id=org.id, document_type=DocumentType.ACKNOWLEDGEMENT, original_filename="a.pdf", storage_path="p3", mime_type="application/pdf", file_size=10, status=DocumentStatus.COMPLETED)
    db_session.add_all([doc_d, doc_o, doc_a])
    db_session.commit()

    items = []
    for i in range(50):
        sku = f"CAB-{i:03d}"
        items.append(CanonicalLineItem(project_id=perf_proj.id, organization_id=org.id, document_id=doc_d.id, source_type=DocumentType.DESIGN, normalized_sku=sku, quantity=2, finish="Oak"))
        items.append(CanonicalLineItem(project_id=perf_proj.id, organization_id=org.id, document_id=doc_o.id, source_type=DocumentType.ORDER, normalized_sku=sku, quantity=2 if i % 5 != 0 else 3, finish="Oak"))
        items.append(CanonicalLineItem(project_id=perf_proj.id, organization_id=org.id, document_id=doc_a.id, source_type=DocumentType.ACKNOWLEDGEMENT, normalized_sku=sku, quantity=2 if i % 5 != 0 else 3, finish="Oak"))
    db_session.add_all(items)
    db_session.commit()

    # Benchmark Matching & CrossCheck
    t0 = time.perf_counter()
    cc_service = CrossCheckService(db_session)
    result = cc_service.process_project(perf_proj.id, org.id)
    t_cc = time.perf_counter() - t0

    assert result["match_groups_count"] == 50
    assert t_cc < 3.0 # Sub-3-second crosscheck for 50 items

    # Benchmark PDF Generation
    t1 = time.perf_counter()
    rep_service = ReportService(db_session)
    pdf_bytes = rep_service.generate_pdf_bytes(perf_proj.id, org.id)
    t_pdf = time.perf_counter() - t1

    assert len(pdf_bytes) > 2000
    assert t_pdf < 3.0 # Sub-3-second PDF compilation

# =================================================================
# 5. ERROR HANDLING & SECURITY QA
# =================================================================

def test_invalid_uuid_handling(client, multi_org_setup):
    admin_a = multi_org_setup["admin_a"]
    token_a = create_test_token(admin_a.auth_id)
    headers = {
        "Authorization": f"Bearer {token_a}"
    }

    res = client.get("/api/v1/projects/not-a-valid-uuid", headers=headers)
    assert res.status_code == 422
