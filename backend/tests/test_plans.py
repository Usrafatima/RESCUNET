"""
Tests for Adaptive Rescue Planning.

Focus:
- proposals are versioned, never applied automatically
- replanning triggers (route closed, resource unavailable, high-urgency arrival)
- stale recommendations cannot overwrite newer decisions
- human approval is always required and recorded in the audit trail
- shortages escalate to human review instead of inventing an assignment
"""

import json

import pytest

from app.models.plans import RouteCreate, RouteStatus, RouteUpdate
from app.services import plan_service, route_service


def _create_incident(client, description, people=2, lat=24.8610, lng=67.0100, auto=False):
    payload = {
        "description": description,
        "people_affected": people,
        "latitude": lat,
        "longitude": lng,
    }
    if auto:
        payload["auto_plan"] = True
    res = client.post("/api/incidents", json=payload)
    assert res.status_code == 201
    return res.json()


def _add_medical_resource(resource_id="RES-T90", lat=24.8700, lng=67.0200):
    """Insert an extra capable medical resource for re-assignment tests."""
    from agent.resource_db import _get_connection
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO resources
            (resource_id, name, type, status, latitude, longitude,
             equipment, max_people, created_at, updated_at)
        VALUES (?, ?, 'medical', 'available', ?, ?, ?, ?, ?, ?)
        """,
        (resource_id, f"Extra Medical {resource_id}", lat, lng,
         json.dumps(["first_aid", "oxygen"]), 10, now, now),
    )
    conn.commit()
    conn.close()


def _resource_status(client, resource_id):
    res = client.get("/api/resources")
    return next(r["status"] for r in res.json() if r["resource_id"] == resource_id)


MEDICAL_SOS = "Severe chest pain, patient cannot breathe, need medical help immediately"


class TestProposalGeneration:
    def test_proposal_is_versioned_and_pending(self, client, isolated_resources):
        incident = _create_incident(client, MEDICAL_SOS)
        res = client.post(f"/api/incidents/{incident['incident_id']}/plan", json={})
        assert res.status_code == 201
        plan = res.json()
        assert plan["version"] == 1
        assert plan["status"] == "pending_approval"
        assert plan["assignment"]["resource_id"] == "RES-001"
        assert plan["rationale"]

    def test_proposal_moves_incident_to_awaiting_approval(self, client, isolated_resources):
        incident = _create_incident(client, MEDICAL_SOS)
        client.post(f"/api/incidents/{incident['incident_id']}/plan", json={})
        current = client.get(f"/api/incidents/{incident['incident_id']}").json()
        assert current["status"] == "awaiting_approval"

    def test_versions_increment(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        client.post(f"/api/incidents/{incident_id}/plan", json={})
        second = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        assert second["version"] == 2
        assert second["previous_plan_id"]

    def test_unknown_incident_404(self, client, isolated_resources):
        assert client.post("/api/incidents/RSN-404404/plan", json={}).status_code == 404


class TestApproval:
    def test_approval_creates_assignment_and_deploys_resource(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        plan = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()

        res = client.post(
            f"/api/plans/{plan['plan_id']}/approve",
            json={"approver": "Ops Lead", "decision_reason": "Confirmed by radio"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["resource"]["id"] == "RES-001"
        assert body["real_world_dispatch"] is False
        assert "No real-world dispatch" in body["message"]

        assert client.get(f"/api/incidents/{incident_id}").json()["status"] == "dispatched"
        assert _resource_status(client, "RES-001") == "deployed"
        approved = client.get(f"/api/plans/{plan['plan_id']}").json()
        assert approved["status"] == "approved"
        assert approved["decided_by"] == "Ops Lead"

    def test_approval_requires_named_approver(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        plan = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        res = client.post(
            f"/api/plans/{plan['plan_id']}/approve", json={"approver": "   "}
        )
        assert res.status_code == 422

    def test_rejection_assigns_nothing(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        plan = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()

        res = client.post(
            f"/api/plans/{plan['plan_id']}/reject",
            json={"approver": "Ops Lead", "decision_reason": "Insufficient evidence"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "rejected"
        assert _resource_status(client, "RES-001") == "available"
        assert client.get(f"/api/incidents/{incident_id}").json()["status"] != "dispatched"

    def test_double_approval_of_same_plan_conflicts(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        plan = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        first = client.post(
            f"/api/plans/{plan['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert first.status_code == 200
        second = client.post(
            f"/api/plans/{plan['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert second.status_code == 409


class TestStaleGuard:
    def test_older_proposal_cannot_be_approved_after_newer_exists(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        v2 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()

        res = client.post(
            f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert res.status_code == 409
        assert "stale" in res.json()["detail"].lower()

        ok = client.post(
            f"/api/plans/{v2['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert ok.status_code == 200

    def test_legacy_approval_blocked_while_proposal_pending(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        client.post(f"/api/incidents/{incident_id}/plan", json={})

        res = client.post(
            f"/api/agent/approve/{incident_id}",
            json={"resource_id": "RES-001", "distance_km": 1.0,
                  "reason": "Closest medical team"},
        )
        assert res.status_code == 409
        assert "pending review" in res.json()["detail"]

    def test_legacy_approval_works_without_proposals(self, client, isolated_resources):
        """The pre-existing approval flow keeps working unchanged."""
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        res = client.post(
            f"/api/agent/approve/{incident_id}",
            json={"resource_id": "RES-001", "distance_km": 1.0,
                  "reason": "Closest medical team"},
        )
        assert res.status_code == 200
        # ...and it is recorded in the plan history + audit trail
        plans = client.get(f"/api/incidents/{incident_id}/plans").json()
        assert plans["total"] == 1
        assert plans["plans"][0]["status"] == "approved"
        events = client.get(f"/api/incidents/{incident_id}/audit").json()["events"]
        assert any(e["event_type"] == "legacy_approval" for e in events)


class TestReplanningTriggers:
    def test_route_closure_proposes_revised_plan(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(
            f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert _resource_status(client, "RES-001") == "deployed"

        # Close the access route that only RES-001 uses.
        route = route_service.create_route(
            RouteCreate(
                name="Alpha Access Road",
                from_lat=24.8600,
                from_lng=67.0090,
                to_lat=24.8620,
                to_lng=67.0110,
                status=RouteStatus.open,
                scope_resource_id="RES-001",
            )
        )
        res = client.patch(
            f"/api/routes/{route['route_id']}",
            json={"status": "closed", "restriction_reason": "flood water",
                  "actor": "Ops Lead"},
        )
        assert res.status_code == 200
        body = res.json()
        assert incident_id in body["affected_assignments"]
        assert len(body["plans_proposed"]) == 1

        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        v2 = next(p for p in plans if p["version"] == 2)
        assert v2["trigger"] == "route_closed"
        assert v2["status"] == "pending_approval"
        assert v2["assignment"]["resource_id"] == "RES-T90"
        assert v2["previous_plan_id"] == v1["plan_id"]
        assert "Alpha Access Road" in v2["rationale"]

    def test_revised_plan_reassigns_after_approval(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})

        route = route_service.create_route(
            RouteCreate(
                name="Alpha Access Road",
                from_lat=24.8600, from_lng=67.0090,
                to_lat=24.8620, to_lng=67.0110,
                status=RouteStatus.open,
                scope_resource_id="RES-001",
            )
        )
        client.patch(
            f"/api/routes/{route['route_id']}",
            json={"status": "closed", "restriction_reason": "flood water"},
        )

        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        v2 = next(p for p in plans if p["version"] == 2)
        res = client.post(
            f"/api/plans/{v2['plan_id']}/approve",
            json={"approver": "Ops Lead", "decision_reason": "Route blocked, rerouted"},
        )
        assert res.status_code == 200
        assert res.json()["resource"]["id"] == "RES-T90"
        assert res.json()["released_resource_id"] == "RES-001"

        assert _resource_status(client, "RES-001") == "available"
        assert _resource_status(client, "RES-T90") == "deployed"

    def test_open_route_change_does_not_trigger_replan(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})

        route = route_service.create_route(
            RouteCreate(name="Open Road", from_lat=24.85, from_lng=67.01,
                        to_lat=24.87, to_lng=67.01, status=RouteStatus.open)
        )
        res = client.patch(
            f"/api/routes/{route['route_id']}", json={"status": "open"}
        )
        assert res.json()["plans_proposed"] == []

    def test_resource_unavailable_triggers_replan(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})

        res = client.patch(
            "/api/resources/RES-001/status",
            params={"status": "unavailable", "actor": "Ops Lead"},
        )
        assert res.status_code == 200
        report = res.json()["replan"]
        assert report["plans_proposed"]
        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        v2 = next(p for p in plans if p["version"] == 2)
        assert v2["trigger"] == "resource_unavailable"
        assert v2["assignment"]["resource_id"] == "RES-T90"

    def test_high_urgency_arrival_generates_proposal(self, client, isolated_resources):
        incident = _create_incident(client, MEDICAL_SOS, auto=True)
        assert incident["status"] == "awaiting_approval"
        plans = client.get(f"/api/incidents/{incident['incident_id']}/plans").json()
        assert plans["total"] == 1
        assert plans["plans"][0]["trigger"] == "new_high_urgency"

    def test_low_urgency_arrival_generates_no_proposal(self, client, isolated_resources):
        incident = _create_incident(
            client, "Not urgent: need one blanket, no injuries", auto=True
        )
        assert incident["status"] == "queued"
        plans = client.get(f"/api/incidents/{incident['incident_id']}/plans").json()
        assert plans["total"] == 0


class TestReplanEvaluation:
    def test_dry_run_changes_nothing(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})
        client.patch(
            "/api/resources/RES-001/status", params={"status": "unavailable"}
        )  # creates v2 proposal

        dry = client.get("/api/replan/changes").json()
        assert dry["plans_proposed"] == []

        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        assert len(plans) == 2  # unchanged by the dry run

    def test_pending_proposal_is_marked_stale_when_conditions_change(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})

        # Change 1: the assigned resource becomes unavailable → proposal v2
        client.patch("/api/resources/RES-001/status", params={"status": "unavailable"})
        # Change 2: the *proposed* resource becomes unavailable too → v2 stale
        client.patch("/api/resources/RES-T90/status", params={"status": "unavailable"})

        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        v2 = next(p for p in plans if p["version"] == 2)
        assert v2["status"] == "stale"
        assert len(plans) >= 3  # a replacement proposal was generated

    def test_shortage_is_reported_and_needs_review(self, client, isolated_resources):
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        for rid in ("RES-001", "RES-002", "RES-003", "RES-004", "RES-005"):
            client.patch(
                f"/api/resources/{rid}/status", params={"status": "unavailable"}
            )

        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        assert plans, "a proposal should exist for the high-urgency incident"
        latest = plans[0]
        assert latest["assignment"]["resource_id"] is None
        assert latest["shortages"]

        res = client.post(
            f"/api/plans/{latest['plan_id']}/approve", json={"approver": "Ops Lead"}
        )
        assert res.status_code == 422

        report = client.post("/api/replan").json()
        assert incident_id in report["unresolved_incidents"]

    def test_triggers_endpoint_documents_policy(self, client, isolated_resources):
        body = client.get("/api/replan/triggers").json()
        ids = {t["trigger"] for t in body["triggers"]}
        assert {"route_closed", "resource_unavailable", "new_high_urgency"} <= ids
        assert "Human approval" in body["policy"]


class TestAuditTrail:
    def test_full_history_is_recorded(self, client, isolated_resources):
        _add_medical_resource()
        incident_id = _create_incident(client, MEDICAL_SOS)["incident_id"]
        v1 = client.post(f"/api/incidents/{incident_id}/plan", json={}).json()
        client.post(f"/api/plans/{v1['plan_id']}/approve", json={"approver": "Ops Lead"})
        route = route_service.create_route(
            RouteCreate(name="Alpha Access Road", from_lat=24.8600, from_lng=67.0090,
                        to_lat=24.8620, to_lng=67.0110, status=RouteStatus.open,
                        scope_resource_id="RES-001")
        )
        client.patch(f"/api/routes/{route['route_id']}",
                     json={"status": "closed", "restriction_reason": "flood"})
        plans = client.get(f"/api/incidents/{incident_id}/plans").json()["plans"]
        v2 = next(p for p in plans if p["version"] == 2)
        client.post(
            f"/api/plans/{v2['plan_id']}/approve",
            json={"approver": "Duty Manager", "decision_reason": "Rerouted to backup team"},
        )

        events = client.get(f"/api/incidents/{incident_id}/audit").json()["events"]
        types = [e["event_type"] for e in events]
        assert "plan_proposed" in types
        assert "plan_approved" in types
        assert any(
            e["event_type"] == "plan_proposed" and e["detail"]["version"] == 2
            for e in events
        )
        approved = [e for e in events if e["event_type"] == "plan_approved"]
        assert {e["detail"]["version"] for e in approved} == {1, 2}
        assert all(e["detail"].get("real_world_dispatch") is False for e in approved)
        assert all(e["actor"] for e in events)
