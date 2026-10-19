"""
Tests for RescuNet dispatch lifecycle.

Covers the full post-approval flow:
1. Approval changes incident status to DISPATCHED
2. Approved resource changes AVAILABLE → DEPLOYED
3. Resource is associated with the response plan
4. Deployed resource is no longer returned by find_available_resources()
5. A second incident cannot dispatch the same resource while deployed
6. Refreshing preserves DISPATCHED status
7. Repeated approval is idempotent
8. Invalid/unavailable resource cannot be dispatched
9. real_world_dispatch remains false
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

VALID_INCIDENT = {
    "description": "Building collapse with people trapped",
    "people_affected": 5,
    "latitude": 24.8607,
    "longitude": 67.0011,
}

SECOND_INCIDENT = {
    "description": "Medical emergency - diabetic needs insulin",
    "people_affected": 2,
    "latitude": 24.8610,
    "longitude": 67.0015,
}


@pytest.fixture(autouse=True)
def _seed_resources(tmp_path, monkeypatch):
    """Seed the resource database for dispatch tests."""
    import agent.resource_db as rdb

    monkeypatch.setattr(rdb, "DATABASE_PATH", tmp_path / "test_resources.db")
    monkeypatch.setattr(rdb, "DATABASE_DIR", tmp_path)
    rdb.init_resource_db()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def incident_id(client):
    """Create an incident and return its ID."""
    resp = client.post("/api/incidents", json=VALID_INCIDENT)
    return resp.json()["incident_id"]


@pytest.fixture()
def second_incident_id(client):
    """Create a second incident."""
    resp = client.post("/api/incidents", json=SECOND_INCIDENT)
    return resp.json()["incident_id"]


class TestDispatchLifecycle:
    """Test that approval triggers a full dispatch lifecycle."""

    def test_approval_sets_incident_to_dispatched(self, client, incident_id):
        """Approving an incident should set status to dispatched."""
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.5,
                "reason": "Medical emergency needs medical team",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dispatched"

        # Verify incident is persisted as dispatched
        inc = client.get(f"/api/incidents/{incident_id}")
        assert inc.json()["status"] == "dispatched"

    def test_approval_deploys_resource(self, client, incident_id):
        """Approved resource should change from available to deployed."""
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-002",
                "distance_km": 2.1,
                "reason": "Rescue team available",
            },
        )

        # Check resource status via API
        resources = client.get("/api/resources").json()
        res = next(r for r in resources if r["resource_id"] == "RES-002")
        assert res["status"] == "deployed"
        assert res["assigned_incident_id"] == incident_id

    def test_resource_appears_in_response_plan(self, client, incident_id):
        """Resource info in response should show deployed status."""
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-003",
                "distance_km": 3.0,
                "reason": "Supply team for food and water",
            },
        )
        resource = resp.json()["resource"]
        assert resource["id"] == "RES-003"
        assert resource["name"] == "Supply Team Charlie"
        assert resource["status"] == "deployed"

    def test_deployed_resource_not_returned_as_available(self, client, incident_id):
        """A deployed resource should not appear in find_available_resources."""
        from agent.resource_db import get_all_resources
        from agent.tools.incident_tools import find_available_resources
        import json

        # Before approval — resource is available
        before = json.loads(find_available_resources(incident_type="medical"))
        ids_before = [r["resource_id"] for r in before]
        assert "RES-001" in ids_before

        # Approve and deploy
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.5,
                "reason": "Medical emergency",
            },
        )

        # After approval — resource is no longer available
        after = json.loads(find_available_resources(incident_type="medical"))
        ids_after = [r["resource_id"] for r in after]
        assert "RES-001" not in ids_after

    def test_second_incident_cannot_dispatch_same_resource(self, client, incident_id, second_incident_id):
        """A deployed resource should be rejected for a second dispatch."""
        # Deploy RES-001 for first incident
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.5,
                "reason": "Medical emergency",
            },
        )

        # Try to dispatch RES-001 for second incident — should fail
        resp = client.post(
            f"/api/agent/approve/{second_incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 0.8,
                "reason": "Another medical emergency",
            },
        )
        assert resp.status_code == 409  # Conflict — resource unavailable

    def test_dispatched_status_persists_on_refresh(self, client, incident_id):
        """Dispatched status should survive page refresh (re-fetch from DB)."""
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-004",
                "distance_km": 4.0,
                "reason": "Fire response needed",
            },
        )

        # Simulate "page refresh" — re-fetch from backend
        inc = client.get(f"/api/incidents/{incident_id}").json()
        assert inc["status"] == "dispatched"

        # Resource should still be deployed
        resources = client.get("/api/resources").json()
        res = next(r for r in resources if r["resource_id"] == "RES-004")
        assert res["status"] == "deployed"

    def test_idempotent_approval_returns_same_state(self, client, incident_id):
        """Repeating approval should return the same dispatched state."""
        payload = {
            "resource_id": "RES-005",
            "distance_km": 5.0,
            "reason": "Shelter team",
        }

        resp1 = client.post(f"/api/agent/approve/{incident_id}", json=payload)
        resp2 = client.post(f"/api/agent/approve/{incident_id}", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["status"] == "dispatched"
        assert resp2.json()["status"] == "dispatched"
        assert resp1.json()["resource"]["id"] == resp2.json()["resource"]["id"]

    def test_unavailable_resource_cannot_be_dispatched(self, client, incident_id, second_incident_id):
        """A resource that is already deployed should be rejected."""
        # Deploy RES-002
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-002",
                "distance_km": 2.0,
                "reason": "Rescue team",
            },
        )

        # Second incident tries same resource
        resp = client.post(
            f"/api/agent/approve/{second_incident_id}",
            json={
                "resource_id": "RES-002",
                "distance_km": 3.0,
                "reason": "Another rescue",
            },
        )
        assert resp.status_code == 409

    def test_real_world_dispatch_is_always_false(self, client, incident_id):
        """real_world_dispatch must always be False."""
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.5,
                "reason": "Medical emergency",
            },
        )
        assert resp.json()["real_world_dispatch"] is False

    def test_response_plan_status_is_dispatched(self, client, incident_id):
        """The response plan status should be 'dispatched'."""
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.5,
                "reason": "Medical emergency",
            },
        )
        assert resp.json()["status"] == "dispatched"

    def test_multiple_resources_can_be_deployed_independently(self, client, incident_id, second_incident_id):
        """Different resources should be deployable for different incidents."""
        # Deploy RES-001 for first incident
        resp1 = client.post(
            f"/api/agent/approve/{incident_id}",
            json={"resource_id": "RES-001", "distance_km": 1.5, "reason": "Medical"},
        )
        assert resp1.status_code == 200

        # Deploy RES-002 for second incident (different resource)
        resp2 = client.post(
            f"/api/agent/approve/{second_incident_id}",
            json={"resource_id": "RES-002", "distance_km": 2.0, "reason": "Rescue"},
        )
        assert resp2.status_code == 200

        # Both should be dispatched
        inc1 = client.get(f"/api/incidents/{incident_id}").json()
        inc2 = client.get(f"/api/incidents/{second_incident_id}").json()
        assert inc1["status"] == "dispatched"
        assert inc2["status"] == "dispatched"

        # Both resources should be deployed
        resources = client.get("/api/resources").json()
        res1 = next(r for r in resources if r["resource_id"] == "RES-001")
        res2 = next(r for r in resources if r["resource_id"] == "RES-002")
        assert res1["status"] == "deployed"
        assert res2["status"] == "deployed"
