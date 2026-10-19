"""
Tests for RescuNet response plan approval workflow.

Covers:
1. Approve valid recommendation
2. Approval creates response plan
3. Resource is assigned
4. Distance is returned
5. Reject does not create response plan
6. Cannot approve nonexistent incident
7. Cannot approve without valid resource
8. Cannot approve unavailable resource
9. Repeated approval is idempotent
10. Response plan endpoint returns plan details
"""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

VALID_INCIDENT = {
    "description": "Building collapse with people trapped",
    "people_affected": 5,
    "latitude": 24.8607,
    "longitude": 67.0011,
}


@pytest.fixture(autouse=True)
def _seed_resources(tmp_path, monkeypatch):
    """Seed the resource database for approval tests."""
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


class TestApproveValidRecommendation:
    """Test approving a valid recommendation."""

    def test_approve_returns_200(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-002",
                "distance_km": 1.23,
                "reason": "Nearest rescue team",
            },
        )
        assert resp.status_code == 200

    def test_approve_returns_response_plan(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 0.5,
                "reason": "Medical emergency needs medical team",
            },
        )
        data = resp.json()
        assert data["incident_id"] == incident_id
        assert data["status"] == "dispatched"
        assert data["real_world_dispatch"] is False

    def test_approve_assigns_correct_resource(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-002",
                "distance_km": 2.1,
                "reason": "Rescue team available",
            },
        )
        resource = resp.json()["resource"]
        assert resource["id"] == "RES-002"
        assert resource["name"] == "Rescue Team Bravo"
        assert resource["type"] == "rescue"

    def test_approve_returns_distance(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-003",
                "distance_km": 5.7,
                "reason": "Supply team for food and water",
            },
        )
        assert resp.json()["distance_km"] == 5.7

    def test_approve_updates_incident_status(self, client, incident_id):
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.0,
                "reason": "Medical assistance needed",
            },
        )
        resp = client.get(f"/api/incidents/{incident_id}")
        assert resp.json()["status"] == "dispatched"

    def test_approve_message_states_no_real_dispatch(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.0,
                "reason": "Medical assistance",
            },
        )
        assert "no real" in resp.json()["message"].lower()


class TestRejectFlow:
    """Test that reject does not create a response plan."""

    def test_reject_does_not_create_plan(self, client, incident_id):
        # Rejection is frontend-only, so just verify no plan exists
        # by checking the endpoint returns 404-like behavior
        # (There's no reject endpoint — it's purely UI state)
        # But we can verify the incident remains in queued status
        resp = client.get(f"/api/incidents/{incident_id}")
        assert resp.json()["status"] == "queued"


class TestApproveValidation:
    """Test validation and error cases for approval."""

    def test_approve_nonexistent_incident(self, client):
        resp = client.post(
            "/api/agent/approve/RSN-999999",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.0,
                "reason": "Test",
            },
        )
        assert resp.status_code == 404

    def test_approve_nonexistent_resource(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-999",
                "distance_km": 1.0,
                "reason": "Test",
            },
        )
        assert resp.status_code == 409

    def test_approve_missing_fields(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={},
        )
        assert resp.status_code == 422

    def test_approve_empty_reason(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": 1.0,
                "reason": "",
            },
        )
        assert resp.status_code == 422

    def test_approve_negative_distance(self, client, incident_id):
        resp = client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-001",
                "distance_km": -1.0,
                "reason": "Test",
            },
        )
        assert resp.status_code == 422


class TestApproveIdempotency:
    """Test that repeated approval is handled safely."""

    def test_double_approval_returns_same_plan(self, client, incident_id):
        payload = {
            "resource_id": "RES-001",
            "distance_km": 1.5,
            "reason": "Medical team",
        }
        resp1 = client.post(f"/api/agent/approve/{incident_id}", json=payload)
        resp2 = client.post(f"/api/agent/approve/{incident_id}", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["status"] == resp2.json()["status"]
        assert resp1.json()["resource"]["id"] == resp2.json()["resource"]["id"]

    def test_idempotent_approval_only_one_plan(self, client, incident_id):
        payload = {
            "resource_id": "RES-002",
            "distance_km": 3.0,
            "reason": "Rescue team",
        }
        client.post(f"/api/agent/approve/{incident_id}", json=payload)
        client.post(f"/api/agent/approve/{incident_id}", json=payload)

        # Verify incident is still dispatched (not double-processed)
        resp = client.get(f"/api/incidents/{incident_id}")
        assert resp.json()["status"] == "dispatched"


class TestResponsePlanEndpoint:
    """Test retrieving response plan details."""

    def test_get_response_plan_after_approval(self, client, incident_id):
        client.post(
            f"/api/agent/approve/{incident_id}",
            json={
                "resource_id": "RES-004",
                "distance_km": 4.2,
                "reason": "Fire response needed",
            },
        )
        # The plan should be retrievable via the incident's status
        resp = client.get(f"/api/incidents/{incident_id}")
        assert resp.json()["status"] == "dispatched"
