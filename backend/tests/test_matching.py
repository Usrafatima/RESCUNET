"""
Tests for the resource matching service.

Focus:
- hard constraints: availability, capability, capacity, route restrictions
- every candidate explains itself (reasons / blockers)
- unavailable resources are never proposed
- insufficient information → requires_human_review instead of an invented answer
"""

import pytest

from app.services import matching_service, route_service
from app.models.plans import RouteCreate, RouteStatus, RouteUpdate


def _incident(
    incident_id="RSN-M0001",
    description="Heart attack, need medical help immediately",
    people=2,
    lat=24.8610,
    lng=67.0100,
    incident_type="medical",
):
    return {
        "incident_id": incident_id,
        "description": description,
        "people_affected": people,
        "latitude": lat,
        "longitude": lng,
        "status": "queued",
        "incident_type": incident_type,
    }


def _set(resource_id, status, assigned_incident_id=None, equipment=None):
    from agent.resource_db import _get_connection, update_resource_status
    import json as _json

    update_resource_status(resource_id, status, assigned_incident_id)
    if equipment is not None:
        conn = _get_connection()
        conn.execute(
            "UPDATE resources SET equipment = ? WHERE resource_id = ?",
            (_json.dumps(equipment), resource_id),
        )
        conn.commit()
        conn.close()


class TestHardConstraints:
    def test_available_capable_resource_is_feasible(self, isolated_resources):
        result = matching_service.match_resources(_incident(), "medical")
        best = result.best
        assert best is not None
        assert best.resource_id == "RES-001"
        assert best.feasible is True
        joined = " ".join(best.reasons).lower()
        assert "available" in joined
        assert "capacity" in joined
        assert "no closed route" in joined

    def test_deployed_resource_is_never_assigned(self, isolated_resources):
        _set("RES-001", "deployed", assigned_incident_id="RSN-OTHER")
        result = matching_service.match_resources(_incident(), "medical")
        candidate = next(c for c in result.candidates if c.resource_id == "RES-001")
        assert candidate.feasible is False
        assert any("unavailable resources are never assigned" in b for b in candidate.blockers)
        if result.best:
            assert result.best.resource_id != "RES-001"

    def test_capability_mismatch_is_a_blocker(self, isolated_resources):
        result = matching_service.match_resources(_incident(), "fire")
        supplies = next(c for c in result.candidates if c.resource_id == "RES-003")
        assert supplies.feasible is False
        assert any("capability" in b.lower() for b in supplies.blockers)

    def test_capacity_shortfall_is_a_blocker(self, isolated_resources):
        result = matching_service.match_resources(
            _incident(people=50, incident_type="medical"), "medical"
        )
        alpha = next(c for c in result.candidates if c.resource_id == "RES-001")
        assert alpha.feasible is False
        assert any("capacity" in b.lower() for b in alpha.blockers)

    def test_no_required_capability_for_other_type(self, isolated_resources):
        result = matching_service.match_resources(
            _incident(description="Situation unclear, please advise", incident_type="other"),
            "other",
        )
        assert result.required_capabilities == []
        assert result.requires_human_review is True
        assert any("could not be determined" in r for r in result.review_reasons)


class TestRouteRestrictions:
    def test_closed_corridor_blocking_path_adds_blocker(self, isolated_resources):
        # Corridor crossing the straight line RES-002 (24.8590, 67.0035) → incident.
        route_service.create_route(
            RouteCreate(
                name="Test Corridor",
                from_lat=24.8500,
                from_lng=67.0060,
                to_lat=24.8700,
                to_lng=67.0060,
                status=RouteStatus.closed,
                restriction_reason="flooding",
            )
        )
        incident = _incident(incident_type="rescue", description="Trapped in vehicle")
        result = matching_service.match_resources(incident, "rescue")
        bravo = next(c for c in result.candidates if c.resource_id == "RES-002")
        assert bravo.feasible is False
        assert any("RTE-000001" in b and "closed" in b.lower() for b in bravo.blockers)

    def test_open_route_does_not_block(self, isolated_resources):
        route_service.create_route(
            RouteCreate(
                name="Open Corridor",
                from_lat=24.8500,
                from_lng=67.0060,
                to_lat=24.8700,
                to_lng=67.0060,
                status=RouteStatus.open,
            )
        )
        incident = _incident(incident_type="rescue", description="Trapped in vehicle")
        result = matching_service.match_resources(incident, "rescue")
        bravo = next(c for c in result.candidates if c.resource_id == "RES-002")
        assert bravo.feasible is True

    def test_scoped_route_only_blocks_its_resource(self, isolated_resources):
        route = route_service.create_route(
            RouteCreate(
                name="Bravo Access Road",
                from_lat=24.8580,
                from_lng=67.0030,
                to_lat=24.8600,
                to_lng=67.0040,
                status=RouteStatus.closed,
                restriction_reason="bridge collapsed",
                scope_resource_id="RES-002",
            )
        )
        incident = _incident(incident_type="rescue", description="Trapped in vehicle")
        result = matching_service.match_resources(incident, "rescue")
        bravo = next(c for c in result.candidates if c.resource_id == "RES-002")
        assert bravo.feasible is False
        assert any("Bravo Access Road" in b for b in bravo.blockers)

        # The same corridor must not affect other resources' evaluations.
        others = [c for c in result.candidates if c.resource_id != "RES-002"]
        assert all(not any("Bravo Access Road" in b for b in c.blockers) for c in others)

        # Re-opening the route removes the restriction.
        route_service.update_route(
            route["route_id"],
            RouteUpdate(status=RouteStatus.open),
        )
        result2 = matching_service.match_resources(incident, "rescue")
        bravo2 = next(c for c in result2.candidates if c.resource_id == "RES-002")
        assert bravo2.feasible is True


class TestShortagesAndReview:
    def test_no_feasible_candidate_requests_human_review(self, isolated_resources):
        for resource_id in ("RES-001", "RES-002", "RES-003", "RES-004", "RES-005"):
            _set(resource_id, "unavailable")
        result = matching_service.match_resources(_incident(), "medical")
        assert result.best is None
        assert result.requires_human_review is True
        assert result.shortages
        assert any("No resource satisfies" in s for s in result.shortages)

    def test_shortage_notes_unavailable_capable_resources(self, isolated_resources):
        _set("RES-001", "deployed", assigned_incident_id="RSN-OTHER")
        result = matching_service.match_resources(_incident(), "medical")
        assert any("already deployed" in s for s in result.shortages)

    def test_candidates_are_ordered_best_first(self, isolated_resources):
        result = matching_service.match_resources(
            _incident(incident_type="other"), "other"
        )
        feasible = [c for c in result.candidates if c.feasible]
        scores = [c.match_score for c in feasible]
        assert scores == sorted(scores, reverse=True)
        assert result.best.resource_id == feasible[0].resource_id
