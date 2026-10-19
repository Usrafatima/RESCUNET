"""
Tests for RescuNet safe resource reset service and endpoint.

Verifies:
1. Resource inspection reports accurate statuses and classifications.
2. Orphaned reset only touches orphaned/mismatched assignments and preserves active ones.
3. Targeted reset frees specified resource or incident.
4. Demo reset frees only [DEMO] assignments.
5. Full reset frees all test resources and updates incidents/plans consistently.
6. Original resource properties (IDs, coordinates, equipment, capacities) are strictly preserved.
7. Dry-run makes zero modifications to databases.
8. Safe rerun (idempotency).
9. Guarded API endpoint behaves securely according to environment and confirmation.
"""

import json
import pytest
from fastapi.testclient import TestClient

import agent.resource_db as rdb
from app.main import app
from app.services.approval_service import approve_recommendation
from app.models.response_plan import ApprovalRequest
from app.services.resource_reset_service import (
    inspect_resources_and_assignments,
    reset_test_resources,
)


@pytest.fixture(autouse=True)
def _seed_resources(tmp_path, monkeypatch):
    """Ensure tests run against isolated temporary resource database."""
    monkeypatch.setattr(rdb, "DATABASE_PATH", tmp_path / "test_resources.db")
    monkeypatch.setattr(rdb, "DATABASE_DIR", tmp_path)
    rdb.init_resource_db()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def _create_and_dispatch(client, description="Test incident", resource_id="RES-001"):
    """Helper to create an incident and dispatch a resource to it."""
    resp = client.post(
        "/api/incidents",
        json={
            "description": description,
            "people_affected": 2,
            "latitude": 24.8607,
            "longitude": 67.0011,
        },
    )
    inc_id = resp.json()["incident_id"]

    approve_req = ApprovalRequest(
        resource_id=resource_id,
        distance_km=1.2,
        reason="Testing dispatch",
        approver="test_operator",
    )
    approve_resp = approve_recommendation(inc_id, approve_req)
    assert approve_resp is not None
    return inc_id


class TestInspection:
    def test_inspect_initial_state(self):
        report = inspect_resources_and_assignments()
        assert report["counts"]["total"] == 5
        assert report["counts"]["available"] == 5
        assert report["counts"]["deployed"] == 0

    def test_inspect_with_deployed_resource(self, client):
        inc_id = _create_and_dispatch(client, "Medical emergency", "RES-001")
        report = inspect_resources_and_assignments()

        assert report["counts"]["deployed"] == 1
        assert report["counts"]["available"] == 4

        res = next(r for r in report["resources"] if r["resource_id"] == "RES-001")
        assert res["status"] == "deployed"
        assert res["assigned_incident_id"] == inc_id
        assert res["classification"] == "active_dispatched"


class TestOrphanedReset:
    def test_orphaned_assignment_is_released(self, client):
        # Manually create an orphaned deployment (incident does not exist)
        rdb.update_resource_status("RES-002", "deployed", assigned_incident_id="RSN-NONEXISTENT")

        # Create a genuinely active assignment
        active_inc = _create_and_dispatch(client, "Active incident", "RES-001")

        # Run orphaned reset
        res = reset_test_resources(mode="orphaned", dry_run=False, create_backup=False)

        assert res["released_count"] == 1
        assert res["released_resources"][0]["resource_id"] == "RES-002"
        assert res["preserved_active_count"] == 1

        # Check RES-002 is now available
        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        assert resources["RES-002"]["status"] == "available"
        assert resources["RES-002"]["assigned_incident_id"] is None

        # Check RES-001 is STILL deployed
        assert resources["RES-001"]["status"] == "deployed"
        assert resources["RES-001"]["assigned_incident_id"] == active_inc

    def test_mismatched_assignment_is_released(self, client):
        # RES-001 assigned to incident
        inc_id = _create_and_dispatch(client, "Medical incident", "RES-001")

        # Suppose RES-003 was somehow marked deployed to the same incident (superseded)
        rdb.update_resource_status("RES-003", "deployed", assigned_incident_id=inc_id)

        res = reset_test_resources(mode="orphaned", dry_run=False, create_backup=False)

        # RES-003 should be released because the active plan for inc_id is RES-001
        assert res["released_count"] == 1
        assert res["released_resources"][0]["resource_id"] == "RES-003"

        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        assert resources["RES-003"]["status"] == "available"
        assert resources["RES-001"]["status"] == "deployed"


class TestTargetedReset:
    def test_targeted_resource_release(self, client):
        inc1 = _create_and_dispatch(client, "Incident 1", "RES-001")
        inc2 = _create_and_dispatch(client, "Incident 2", "RES-002")

        res = reset_test_resources(
            mode="targeted",
            resource_ids=["RES-001"],
            dry_run=False,
            create_backup=False,
        )

        assert res["released_count"] == 1
        assert res["released_resources"][0]["resource_id"] == "RES-001"

        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        assert resources["RES-001"]["status"] == "available"
        assert resources["RES-002"]["status"] == "deployed"

    def test_targeted_incident_release(self, client):
        inc1 = _create_and_dispatch(client, "Incident 1", "RES-001")
        inc2 = _create_and_dispatch(client, "Incident 2", "RES-002")

        res = reset_test_resources(
            mode="targeted",
            incident_ids=[inc1],
            dry_run=False,
            create_backup=False,
        )

        assert res["released_count"] == 1
        assert res["released_resources"][0]["resource_id"] == "RES-001"
        inc_resp = client.get(f"/api/incidents/{inc1}").json()
        assert inc_resp["status"] == "dispatched"

        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        assert resources["RES-001"]["status"] == "available"
        assert resources["RES-002"]["status"] == "deployed"


class TestDemoReset:
    def test_demo_only_reset(self, client):
        demo_inc = _create_and_dispatch(client, "[DEMO] Flash flood rescue", "RES-002")
        real_inc = _create_and_dispatch(client, "Real user test emergency", "RES-001")

        res = reset_test_resources(mode="demo", dry_run=False, create_backup=False)

        assert res["released_count"] == 1
        assert res["released_resources"][0]["resource_id"] == "RES-002"

        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        assert resources["RES-002"]["status"] == "available"
        assert resources["RES-001"]["status"] == "deployed"


class TestAllReset:
    def test_all_reset_releases_and_preserves_identities(self, client):
        inc1 = _create_and_dispatch(client, "Test A", "RES-001")
        inc2 = _create_and_dispatch(client, "Test B", "RES-002")

        # Snapshot resource properties before reset
        before_res = {r["resource_id"]: r for r in rdb.get_all_resources()}

        res = reset_test_resources(mode="all", dry_run=False, create_backup=False)

        assert res["released_count"] == 2
        after_res = {r["resource_id"]: r for r in rdb.get_all_resources()}

        # Verify all are now available
        for r_id, r in after_res.items():
            assert r["status"] == "available"
            assert r["assigned_incident_id"] is None

            # Verify original properties are preserved
            orig = before_res[r_id]
            assert r["name"] == orig["name"]
            assert r["type"] == orig["type"]
            assert r["latitude"] == orig["latitude"]
            assert r["longitude"] == orig["longitude"]
            assert r["equipment"] == orig["equipment"]
            assert r["max_people"] == orig["max_people"]

        # Verify incident statuses are NOT changed/reset and records are preserved (Requirement 4)
        inc_resp1 = client.get(f"/api/incidents/{inc1}").json()
        inc_resp2 = client.get(f"/api/incidents/{inc2}").json()
        assert inc_resp1["status"] == "dispatched"
        assert inc_resp2["status"] == "dispatched"


class TestDryRunAndIdempotency:
    def test_dry_run_makes_no_changes(self, client):
        inc1 = _create_and_dispatch(client, "Test", "RES-001")

        sim = reset_test_resources(mode="all", dry_run=True, create_backup=False)
        assert sim["released_count"] == 1

        # Database state should remain deployed
        res = rdb.get_all_resources()
        r1 = next(r for r in res if r["resource_id"] == "RES-001")
        assert r1["status"] == "deployed"

    def test_idempotent_rerun(self, client):
        _create_and_dispatch(client, "Test", "RES-001")

        # First run releases
        res1 = reset_test_resources(mode="all", dry_run=False, create_backup=False)
        assert res1["released_count"] == 1

        # Second run does nothing and succeeds cleanly
        res2 = reset_test_resources(mode="all", dry_run=False, create_backup=False)
        assert res2["released_count"] == 0


class TestAPIEndpoint:
    def test_endpoint_requires_confirm_for_all(self, client):
        resp = client.post("/api/resources/reset-test?mode=all")
        assert resp.status_code == 400
        assert "confirm=true" in resp.json()["detail"]

    def test_endpoint_blocked_in_production(self, client, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ALLOW_TEST_RESET", "false")

        resp = client.post("/api/resources/reset-test?mode=orphaned")
        assert resp.status_code == 403

    def test_endpoint_succeeds_in_dev(self, client):
        _create_and_dispatch(client, "Endpoint test", "RES-001")
        resp = client.post("/api/resources/reset-test?mode=all&confirm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["released_count"] >= 1


class TestResourceResetRequirements:
    def test_reset_resources_makes_available_without_changing_incidents_or_duplicating_resources(self, client):
        """Requirement 9: Add a test confirming that resources become available
        without changing incident records or creating duplicate resources."""
        inc1 = _create_and_dispatch(client, "Medical emergency in North", "RES-001")
        inc2 = _create_and_dispatch(client, "Rescue required in South", "RES-002")

        # Capture snapshot before reset
        inc1_before = client.get(f"/api/incidents/{inc1}").json()
        inc2_before = client.get(f"/api/incidents/{inc2}").json()
        all_incidents_before = client.get("/api/incidents").json()
        all_resources_before = client.get("/api/resources").json()

        # Check deployed resources
        r1_before = next(r for r in all_resources_before if r["resource_id"] == "RES-001")
        r2_before = next(r for r in all_resources_before if r["resource_id"] == "RES-002")
        assert r1_before["status"] == "deployed"
        assert r2_before["status"] == "deployed"

        # Execute reset via endpoint with confirmation
        resp = client.post("/api/resources/reset?mode=all&confirm=true")
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["released_count"] == 2

        # 1. Resources become available with restored capacity
        all_resources_after = client.get("/api/resources").json()
        for r in all_resources_after:
            assert r["status"] == "available"
            assert r["assigned_incident_id"] is None
            assert r["max_people"] > 0

        # 2. No duplicate resources created
        ids_before = sorted([r["resource_id"] for r in all_resources_before])
        ids_after = sorted([r["resource_id"] for r in all_resources_after])
        assert ids_after == ids_before
        assert len(all_resources_after) == len(all_resources_before)

        # 3. Incident records and statuses are completely unchanged
        inc1_after = client.get(f"/api/incidents/{inc1}").json()
        inc2_after = client.get(f"/api/incidents/{inc2}").json()
        all_incidents_after = client.get("/api/incidents").json()

        assert inc1_after == inc1_before
        assert inc2_after == inc2_before
        assert inc1_after["status"] == "dispatched"
        assert inc2_after["status"] == "dispatched"
        assert len(all_incidents_after) == len(all_incidents_before)

    def test_capacity_restored_respecting_schema_and_limits(self, client):
        """Requirement 8: Ensure reset respects actual resource schema, restores configured
        capacity, and does not assume every resource has the same capacity."""
        with rdb.get_resource_db() as conn:
            conn.execute("UPDATE resources SET max_people = 1, status = 'unavailable' WHERE resource_id = 'RES-005'")
            conn.commit()

        # Reset
        res = reset_test_resources(mode="all", dry_run=False, create_backup=False)
        assert res["status"] == "success"

        resources = {r["resource_id"]: r for r in rdb.get_all_resources()}
        # RES-005 configured max_people is 50, not 1, and not generic 10
        assert resources["RES-005"]["max_people"] == 50
        assert resources["RES-005"]["status"] == "available"
        # RES-001 configured is 5
        assert resources["RES-001"]["max_people"] == 5
        # RES-003 configured is 20
        assert resources["RES-003"]["max_people"] == 20
