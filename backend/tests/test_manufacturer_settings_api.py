"""
Manufacturer Settings & Cabinet Code Dictionary Management — API tests.

Covers manufacturer CRUD, dictionary CRUD (add/duplicate-prevent/update/
deactivate/alias), bulk import (valid + invalid + preview/commit agreement),
tenant isolation, and IDOR (an org must never read or write another org's
private manufacturer/dictionary, whether directly or by attaching a project
to it). Also verifies the full Project -> Manufacturer -> Dictionary ->
Cabinet Code Intelligence integration still produces the expected
classification when the dictionary is populated through this new API
(not the direct-DB seeding Phase A used).
"""
import io
import jwt
import pytest
from app.core.config import settings
from app.models.core import Organization, User, Project, Role, ItemCategory


def create_test_token(sub: str):
    payload = {"sub": sub, "aud": "authenticated"}
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def org_admin(db_session):
    org = Organization(name="Org A")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="admin-a", organization_id=org.id, email="admin-a@a.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    token = create_test_token("admin-a")
    return {"Authorization": f"Bearer {token}"}, org, user


@pytest.fixture
def org_b_admin(db_session):
    org = Organization(name="Org B")
    db_session.add(org)
    db_session.commit()
    user = User(auth_id="admin-b", organization_id=org.id, email="admin-b@b.com", role=Role.ADMIN)
    db_session.add(user)
    db_session.commit()
    token = create_test_token("admin-b")
    return {"Authorization": f"Bearer {token}"}, org, user


@pytest.fixture
def org_a_viewer(db_session, org_admin):
    _, org, _ = org_admin
    user = User(auth_id="viewer-a", organization_id=org.id, email="viewer-a@a.com", role=Role.VIEWER)
    db_session.add(user)
    db_session.commit()
    token = create_test_token("viewer-a")
    return {"Authorization": f"Bearer {token}"}


class TestManufacturerCRUD:
    def test_create_and_list_manufacturer(self, client, org_admin):
        headers, org, user = org_admin
        res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "Yorktowne"
        assert body["is_global"] is False
        assert body["organization_id"] == str(org.id)

        list_res = client.get("/api/v1/manufacturers", headers=headers)
        assert list_res.status_code == 200
        names = [m["name"] for m in list_res.json()]
        assert "Yorktowne" in names

    def test_viewer_cannot_create_manufacturer(self, client, org_a_viewer):
        res = client.post("/api/v1/manufacturers", headers=org_a_viewer, json={"name": "Yorktowne"})
        assert res.status_code == 403

    def test_viewer_can_list_manufacturers(self, client, org_admin, org_a_viewer):
        headers, _, _ = org_admin
        client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        res = client.get("/api/v1/manufacturers", headers=org_a_viewer)
        assert res.status_code == 200

    def test_update_manufacturer(self, client, org_admin):
        headers, _, _ = org_admin
        create = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktown"})
        mfr_id = create.json()["id"]
        res = client.patch(f"/api/v1/manufacturers/{mfr_id}", headers=headers, json={"name": "Yorktowne"})
        assert res.status_code == 200
        assert res.json()["name"] == "Yorktowne"

    def test_cannot_set_is_global_via_create(self, client, org_admin):
        headers, _, _ = org_admin
        res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Sneaky", "is_global": True})
        assert res.status_code == 201
        assert res.json()["is_global"] is False  # field ignored, never accepted


class TestManufacturerTenantIsolationAndIDOR:
    def test_org_b_cannot_see_org_a_private_manufacturer(self, client, org_admin, org_b_admin):
        headers_a, _, _ = org_admin
        headers_b, _, _ = org_b_admin
        create = client.post("/api/v1/manufacturers", headers=headers_a, json={"name": "Org A Secret Mfr"})
        mfr_id = create.json()["id"]

        list_res = client.get("/api/v1/manufacturers", headers=headers_b)
        assert mfr_id not in [m["id"] for m in list_res.json()]

    def test_org_b_cannot_read_org_a_dictionary_by_guessing_id(self, client, org_admin, org_b_admin):
        headers_a, _, _ = org_admin
        headers_b, _, _ = org_b_admin
        create = client.post("/api/v1/manufacturers", headers=headers_a, json={"name": "Org A Mfr"})
        mfr_id = create.json()["id"]

        res = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers_b)
        assert res.status_code == 404  # never 403 — existence must not leak

    def test_org_b_cannot_write_org_a_manufacturer_by_guessing_id(self, client, org_admin, org_b_admin):
        headers_a, _, _ = org_admin
        headers_b, _, _ = org_b_admin
        create = client.post("/api/v1/manufacturers", headers=headers_a, json={"name": "Org A Mfr"})
        mfr_id = create.json()["id"]

        res = client.patch(f"/api/v1/manufacturers/{mfr_id}", headers=headers_b, json={"name": "Hijacked"})
        assert res.status_code in (400, 404)

        res2 = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers_b, json={"code": "X1", "category": "CABINET"})
        assert res2.status_code in (400, 404)

    def test_project_cannot_be_linked_to_another_orgs_private_manufacturer(self, client, org_admin, org_b_admin):
        """IDOR via a different path: attaching Org B's project to Org A's
        private manufacturer would leak Org A's dictionary into Org B's
        Cabinet Code Intelligence — must be rejected at project write time."""
        headers_a, _, _ = org_admin
        headers_b, _, org_b = org_b_admin
        create = client.post("/api/v1/manufacturers", headers=headers_a, json={"name": "Org A Mfr"})
        mfr_id = create.json()["id"]

        proj_res = client.post("/api/v1/projects", headers=headers_b, json={"name": "Org B Project", "manufacturer_id": mfr_id})
        assert proj_res.status_code == 404


class TestDictionaryCRUD:
    def _make_manufacturer(self, client, headers):
        res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        return res.json()["id"]

    def test_add_code(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={
            "code": "BT36B-2", "description": "Base w/ 2 Roll-Out Trays", "category": "CABINET",
        })
        assert res.status_code == 201
        body = res.json()
        assert body["code"] == "BT36B-2"
        assert body["normalized_code"] == "BT36B-2"
        assert body["category"] == "CABINET"

    def test_duplicate_code_prevented(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "BT36B-2", "category": "CABINET"})
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "bt36b-2", "category": "CABINET"})
        assert res.status_code == 400

    def test_update_code(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        create = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "B36", "category": "CABINET"})
        code_id = create.json()["id"]
        res = client.patch(f"/api/v1/manufacturers/{mfr_id}/codes/{code_id}", headers=headers, json={"description": "36in Base Cabinet"})
        assert res.status_code == 200
        assert res.json()["description"] == "36in Base Cabinet"

    def test_deactivate_code(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        create = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "B36", "category": "CABINET"})
        code_id = create.json()["id"]
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/{code_id}/deactivate", headers=headers)
        assert res.status_code == 200
        assert res.json()["is_current"] is False

    def test_search_and_category_filter(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "BT36B-2", "category": "CABINET"})
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "FREIGHTSURCHARGE", "category": "COMMERCIAL_CHARGE"})

        res = client.get(f"/api/v1/manufacturers/{mfr_id}/codes?search=BT36", headers=headers)
        assert len(res.json()) == 1
        res2 = client.get(f"/api/v1/manufacturers/{mfr_id}/codes?category=COMMERCIAL_CHARGE", headers=headers)
        assert len(res2.json()) == 1
        assert res2.json()[0]["code"] == "FREIGHTSURCHARGE"

    def test_delete_code(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        create = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "B36", "category": "CABINET"})
        code_id = create.json()["id"]
        res = client.delete(f"/api/v1/manufacturers/{mfr_id}/codes/{code_id}", headers=headers)
        assert res.status_code == 204
        list_res = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers)
        assert code_id not in [c["id"] for c in list_res.json()]


class TestAliasManagement:
    def test_add_primary_and_alias(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        mfr_id = mfr_res.json()["id"]

        primary = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={
            "code": "BFHC12", "category": "CABINET", "alias_group": "BFHC12-GROUP", "is_primary_alias": True,
        })
        alias = client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={
            "code": "BPFHC12", "category": "CABINET", "alias_group": "BFHC12-GROUP", "is_primary_alias": False,
        })
        assert primary.status_code == 201 and alias.status_code == 201

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        group_codes = [c for c in codes if c["alias_group"] == "BFHC12-GROUP"]
        assert len(group_codes) == 2
        assert sum(1 for c in group_codes if c["is_primary_alias"]) == 1


class TestBulkImport:
    def _make_manufacturer(self, client, headers):
        res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        return res.json()["id"]

    def _csv(self, rows):
        header = "code,description,category,alias_group,is_current,source_version,effective_from,effective_to\n"
        body = "\n".join(rows)
        return io.BytesIO((header + body).encode("utf-8"))

    def test_preview_valid_file(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        f = self._csv([
            "BT36B-2,Base w/ 2 Roll-Out Trays,CABINET,,true,2026,,",
            "FREIGHTSURCHARGE,Freight,COMMERCIAL_CHARGE,,true,2026,,",
        ])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/preview", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        assert res.status_code == 200
        body = res.json()
        assert body["total_rows"] == 2
        assert body["valid"] == 2
        assert body["invalid"] == 0

    def test_preview_flags_invalid_rows(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        f = self._csv([
            ",Missing code,CABINET,,true,,,",
            "B36,Valid,NOT_A_REAL_CATEGORY,,true,,,",
        ])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/preview", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        body = res.json()
        assert body["invalid"] == 2
        assert body["valid"] == 0

    def test_preview_flags_duplicates_against_existing_dictionary(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={"code": "B36", "category": "CABINET"})
        f = self._csv(["B36,dup,CABINET,,true,,,"])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/preview", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        assert res.json()["duplicates"] == 1
        assert res.json()["valid"] == 0

    def test_commit_import_persists_valid_rows_and_skips_invalid(self, client, org_admin):
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        f = self._csv([
            "BT36B-2,Base w/ 2 Roll-Out Trays,CABINET,,true,2026,,",
            ",Missing code,CABINET,,true,,,",
        ])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/commit", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        assert res.status_code == 200
        body = res.json()
        assert body["imported"] == 1
        assert body["skipped_invalid"] == 1

        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert any(c["code"] == "BT36B-2" for c in codes)

    def test_commit_never_partially_corrupts_on_duplicate_within_file(self, client, org_admin):
        """Two identical codes in one file: only one should be committed,
        never both (which would violate the unique constraint), and the
        import must not blow up half-committed."""
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        f = self._csv([
            "B36,First,CABINET,,true,,,",
            "B36,Second,CABINET,,true,,,",
        ])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/commit", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        assert res.status_code == 200
        assert res.json()["imported"] == 1
        codes = client.get(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers).json()
        assert len([c for c in codes if c["normalized_code"] == "B36"]) == 1

    def test_org_b_cannot_import_into_org_as_manufacturer(self, client, org_admin, org_b_admin):
        headers_a, _, _ = org_admin
        headers_b, _, _ = org_b_admin
        mfr_id = self._make_manufacturer(client, headers_a)
        f = self._csv(["B36,x,CABINET,,true,,,"])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/commit", headers=headers_b, files={"file": ("codes.csv", f, "text/csv")})
        assert res.status_code == 404

    def test_oversized_import_file_rejected(self, client, org_admin, monkeypatch):
        """Step 3 production audit: found the bulk-import path had no file
        size check at all (unlike spec-book/NKBA uploads), so an arbitrarily
        large CSV could be fully read into memory before any validation."""
        headers, _, _ = org_admin
        mfr_id = self._make_manufacturer(client, headers)
        monkeypatch.setattr("app.services.manufacturer_service.settings.MAX_UPLOAD_SIZE_MB", 0.001)  # ~1KB
        f = self._csv([f"CODE{i},desc,CABINET,,true,,," for i in range(500)])
        res = client.post(f"/api/v1/manufacturers/{mfr_id}/codes/import/preview", headers=headers, files={"file": ("codes.csv", f, "text/csv")})
        assert res.status_code == 400


class TestFullIntegrationProjectToClassification:
    def test_dictionary_populated_via_api_flows_into_cabinet_intelligence(self, client, db_session, org_admin):
        """Project -> Manufacturer -> Dictionary -> Cabinet Code Intelligence,
        using the dictionary exactly as a real user would populate it (via
        this API), not direct DB seeding."""
        headers, org, _ = org_admin
        mfr_res = client.post("/api/v1/manufacturers", headers=headers, json={"name": "Yorktowne"})
        mfr_id = mfr_res.json()["id"]
        client.post(f"/api/v1/manufacturers/{mfr_id}/codes", headers=headers, json={
            "code": "BT36B-2", "description": "Base w/ 2 Roll-Out Trays", "category": "CABINET",
        })

        proj_res = client.post("/api/v1/projects", headers=headers, json={"name": "Test Project", "manufacturer_id": mfr_id})
        assert proj_res.status_code == 201
        assert proj_res.json()["manufacturer_id"] == mfr_id
        assert proj_res.json()["manufacturer_name"] == "Yorktowne"

        from app.engines.cabinet_intelligence import CabinetCodeIntelligence
        import uuid as uuid_module
        cci = CabinetCodeIntelligence(db_session, manufacturer_id=uuid_module.UUID(mfr_id))
        decision = cci.analyze_candidate(raw_sku="BT36B-2", description="Base w/ 2 Roll-Out Trays")
        assert decision.classification == ItemCategory.CABINET
        assert decision.is_verified is True

    def test_project_without_manufacturer_still_works(self, client, org_admin):
        headers, _, _ = org_admin
        res = client.post("/api/v1/projects", headers=headers, json={"name": "No Mfr Project"})
        assert res.status_code == 201
        assert res.json()["manufacturer_id"] is None
        assert res.json()["manufacturer_name"] is None
