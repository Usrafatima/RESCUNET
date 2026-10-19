"""
Tests for RescuNet Priority Scoring and Queue Logic.

Covers:
1. Priority scoring formula
2. Waiting time calculation
3. Priority queue generation
4. Resource availability awareness
5. Deterministic ranking
6. Edge cases and fallbacks
"""

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app.services.priority_service import (
    calculate_priority_score,
    _compute_waiting_time,
    _default_factors,
    _priority_label_from_score,
    _find_suitable_resource,
    generate_priority_queue,
    SCORING_WEIGHTS,
    WAITING_TIME_MAX_MINUTES,
)
from agent.models import PriorityFactors


# ─── Priority Score Calculation Tests ────────────────────────────────────


class TestPriorityScoreCalculation:
    """Test the deterministic priority scoring formula."""

    def test_critical_incident_scores_high(self):
        """A critical incident with many people should score high."""
        factors = PriorityFactors(
            severity=95,
            people_affected=90,
            urgency=95,
            resource_need=85,
            reason="Critical emergency",
        )
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=10.0,
            resource_available=True,
        )
        assert score >= 85.0

    def test_low_priority_incident_scores_low(self):
        """A low-severity incident with few people should score lower."""
        factors = PriorityFactors(
            severity=20,
            people_affected=15,
            urgency=20,
            resource_need=10,
            reason="Minor issue",
        )
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=0.0,
            resource_available=True,
        )
        assert score < 40.0

    def test_score_clamped_to_100(self):
        """Score should never exceed 100."""
        factors = PriorityFactors(
            severity=100,
            people_affected=100,
            urgency=100,
            resource_need=100,
            reason="Maximum everything",
        )
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=60.0,
            resource_available=True,
        )
        assert score <= 100.0

    def test_score_clamped_to_0(self):
        """Score should never go below 0."""
        factors = PriorityFactors(
            severity=0,
            people_affected=0,
            urgency=0,
            resource_need=0,
            reason="Zero everything",
        )
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=0.0,
            resource_available=False,
        )
        assert score >= 0.0

    def test_weights_sum_to_one(self):
        """Scoring weights should sum to 1.0."""
        total = sum(SCORING_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_custom_weights_override(self):
        """Custom weights should override defaults."""
        factors = PriorityFactors(
            severity=50,
            people_affected=50,
            urgency=50,
            resource_need=50,
            reason="Test",
        )
        # All weight on severity
        custom = {
            "severity": 1.0,
            "people_affected": 0.0,
            "urgency": 0.0,
            "waiting_time": 0.0,
            "resource_availability": 0.0,
        }
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=0.0,
            resource_available=True,
            weights=custom,
        )
        assert score == 50.0

    def test_unavailable_resource_penalizes_score(self):
        """Incidents with no available resource should score lower."""
        factors = PriorityFactors(
            severity=80,
            people_affected=70,
            urgency=80,
            resource_need=70,
            reason="Test",
        )
        score_available = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=5.0,
            resource_available=True,
        )
        score_unavailable = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=5.0,
            resource_available=False,
        )
        # Resource unavailable should penalize score
        assert score_available > score_unavailable

    def test_waiting_time_increases_score(self):
        """Longer waiting time should increase priority score."""
        factors = PriorityFactors(
            severity=50,
            people_affected=50,
            urgency=50,
            resource_need=50,
            reason="Test",
        )
        score_short = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=1.0,
            resource_available=True,
        )
        score_long = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=20.0,
            resource_available=True,
        )
        assert score_long > score_short


# ─── Waiting Time Calculation Tests ─────────────────────────────────────


class TestWaitingTimeCalculation:
    """Test waiting time computation from ISO timestamps."""

    def test_zero_waiting_time(self):
        """An incident created now should have near-zero waiting time."""
        now = datetime.now(timezone.utc).isoformat()
        seconds, display = _compute_waiting_time(now)
        assert seconds < 5.0
        assert "s" in display

    def test_minutes_formatting(self):
        """Incidents older than 60s should show minutes."""
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        seconds, display = _compute_waiting_time(past.isoformat())
        assert seconds > 300
        assert "5m" in display or "m" in display

    def test_hours_formatting(self):
        """Incidents older than 60min should show hours."""
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        seconds, display = _compute_waiting_time(past.isoformat())
        assert seconds > 7200
        assert "2h" in display

    def test_invalid_timestamp_returns_zero(self):
        """Invalid timestamp should return 0."""
        seconds, display = _compute_waiting_time("not-a-date")
        assert seconds == 0.0
        assert display == "0m"


# ─── Priority Label Tests ───────────────────────────────────────────────


class TestPriorityLabelFromScore:
    """Test score-to-label mapping."""

    def test_critical_label(self):
        assert _priority_label_from_score(90) == "critical"

    def test_high_label(self):
        assert _priority_label_from_score(75) == "high"

    def test_medium_label(self):
        assert _priority_label_from_score(50) == "medium"

    def test_low_label(self):
        assert _priority_label_from_score(20) == "low"


# ─── Default Factors Tests ──────────────────────────────────────────────


class TestDefaultFactors:
    """Test default factor generation for unanalyzed incidents."""

    def test_critical_keywords_boost_severity(self):
        """Incidents with 'trapped' or 'collapse' should get high severity."""
        incident = {
            "description": "People trapped in building collapse",
            "people_affected": 3,
            "incident_type": "rescue",
        }
        factors = _default_factors(incident)
        assert factors.severity >= 80

    def test_medical_keywords_boost_severity(self):
        """Medical keywords should boost severity."""
        incident = {
            "description": "Medical emergency, person injured",
            "people_affected": 1,
            "incident_type": "medical",
        }
        factors = _default_factors(incident)
        assert factors.severity >= 60

    def test_people_affected_scaling(self):
        """More people should result in higher people_affected score."""
        incident_few = {
            "description": "General incident",
            "people_affected": 1,
            "incident_type": "other",
        }
        incident_many = {
            "description": "General incident",
            "people_affected": 15,
            "incident_type": "other",
        }
        few_factors = _default_factors(incident_few)
        many_factors = _default_factors(incident_many)
        assert many_factors.people_affected > few_factors.people_affected


# ─── Priority Queue Generation Tests ────────────────────────────────────


class TestPriorityQueueGeneration:
    """Test full priority queue generation."""

    def _make_incident(self, id: str, people: int, desc: str, type_: str = "other"):
        """Helper to create test incidents."""
        return {
            "incident_id": id,
            "description": desc,
            "people_affected": people,
            "latitude": 24.8607,
            "longitude": 67.0011,
            "status": "queued",
            "incident_type": type_,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_empty_queue(self):
        """No incidents should return empty queue."""
        result = generate_priority_queue([], {})
        assert result.queue == []
        assert result.total_active == 0

    def test_single_incident_at_rank_one(self):
        """A single incident should be rank #1."""
        incident = self._make_incident("RSN-000001", 2, "Medical emergency", "medical")
        result = generate_priority_queue([incident], {})
        assert len(result.queue) == 1
        assert result.queue[0].rank == 1
        assert result.queue[0].incident_id == "RSN-000001"

    def test_multiple_incidents_sorted_by_score(self):
        """Multiple incidents should be sorted by score descending."""
        incident_low = self._make_incident(
            "RSN-000001", 1, "Minor issue", "other"
        )
        incident_high = self._make_incident(
            "RSN-000002", 10, "Critical rescue emergency", "rescue"
        )
        incident_mid = self._make_incident(
            "RSN-000003", 5, "Medical emergency", "medical"
        )

        result = generate_priority_queue(
            [incident_low, incident_high, incident_mid], {}
        )

        assert len(result.queue) == 3
        # Should be sorted by score (highest first)
        assert result.queue[0].score >= result.queue[1].score
        assert result.queue[1].score >= result.queue[2].score
        # Ranks should be sequential
        assert result.queue[0].rank == 1
        assert result.queue[1].rank == 2
        assert result.queue[2].rank == 3

    def test_scoring_weights_in_response(self):
        """Response should include scoring weights."""
        result = generate_priority_queue([], {})
        assert result.scoring_weights == SCORING_WEIGHTS

    def test_waiting_time_reflected_in_queue(self):
        """Older incidents should have higher waiting time."""
        old_incident = self._make_incident("RSN-000001", 1, "Old incident")
        old_incident["created_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=15)
        ).isoformat()

        new_incident = self._make_incident("RSN-000002", 1, "New incident")

        result = generate_priority_queue([old_incident, new_incident], {})

        # Find the items
        old_item = next(
            i for i in result.queue if i.incident_id == "RSN-000001"
        )
        new_item = next(
            i for i in result.queue if i.incident_id == "RSN-000002"
        )

        assert old_item.waiting_time_seconds > new_item.waiting_time_seconds


# ─── API Endpoint Tests ─────────────────────────────────────────────────


class TestPriorityQueueEndpoint:
    """Test the GET /api/incidents/priority-queue endpoint."""

    def test_empty_queue_endpoint(self, client):
        """Should return empty queue when no active incidents."""
        response = client.get("/api/incidents/priority-queue")
        assert response.status_code == 200
        data = response.json()
        assert data["queue"] == []
        assert data["total_active"] == 0

    def test_queue_with_incidents(self, client):
        """Should return ranked queue when incidents exist."""
        # Create a few incidents
        for i in range(3):
            client.post(
                "/api/incidents",
                json={
                    "description": f"Emergency {i + 1}",
                    "people_affected": (i + 1) * 2,
                    "latitude": 24.8607 + i * 0.001,
                    "longitude": 67.0011 + i * 0.001,
                },
            )

        response = client.get("/api/incidents/priority-queue")
        assert response.status_code == 200
        data = response.json()
        assert len(data["queue"]) == 3
        assert data["total_active"] == 3
        # Should have scoring weights
        assert "scoring_weights" in data

    def test_queue_excludes_resolved(self, client):
        """Resolved incidents should not appear in the priority queue."""
        # Create an incident
        resp = client.post(
            "/api/incidents",
            json={
                "description": "Resolved incident",
                "people_affected": 1,
                "latitude": 24.8607,
                "longitude": 67.0011,
            },
        )
        incident_id = resp.json()["incident_id"]

        # Resolve it
        client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "resolved"},
        )

        response = client.get("/api/incidents/priority-queue")
        assert response.status_code == 200
        data = response.json()
        # Should not include the resolved incident
        ids = [item["incident_id"] for item in data["queue"]]
        assert incident_id not in ids

    def test_queue_includes_dispatched(self, client):
        """Dispatched incidents should still appear (active)."""
        # Create an incident
        resp = client.post(
            "/api/incidents",
            json={
                "description": "Dispatched incident",
                "people_affected": 2,
                "latitude": 24.8607,
                "longitude": 67.0011,
            },
        )
        incident_id = resp.json()["incident_id"]

        # Dispatch it
        client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "dispatched"},
        )

        response = client.get("/api/incidents/priority-queue")
        assert response.status_code == 200
        data = response.json()
        ids = [item["incident_id"] for item in data["queue"]]
        assert incident_id in ids


# ─── Priority Analysis Endpoint Tests ───────────────────────────────────


class TestPriorityAnalysisEndpoint:
    """Test the POST /api/agent/analyze-priority/{incident_id} endpoint."""

    def test_analyze_priority_nonexistent(self, client):
        """Should return 404 for nonexistent incident."""
        response = client.post("/api/agent/analyze-priority/RSN-999999")
        assert response.status_code == 404

    def test_analyze_priority_existing(self, client):
        """Should trigger priority analysis for existing incident."""
        # Create an incident
        resp = client.post(
            "/api/incidents",
            json={
                "description": "Test incident",
                "people_affected": 3,
                "latitude": 24.8607,
                "longitude": 67.0011,
            },
        )
        incident_id = resp.json()["incident_id"]

        mock_result = {
            "incident_id": incident_id,
            "priority_label": "critical",
            "factors": {
                "severity": 90,
                "people_affected": 70,
                "urgency": 85,
                "resource_need": 60,
                "reason": "Three people affected by medical emergency",
            },
            "recommended_resource_type": "medical",
        }

        with patch(
            "app.routes.agent.analyze_priority", return_value=mock_result
        ):
            response = client.post(f"/api/agent/analyze-priority/{incident_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["priority_label"] == "critical"
            assert data["factors"]["severity"] == 90

    def test_analyze_priority_agent_failure(self, client):
        """Should return 500 when agent fails."""
        resp = client.post(
            "/api/incidents",
            json={
                "description": "Test incident",
                "people_affected": 1,
                "latitude": 24.8607,
                "longitude": 67.0011,
            },
        )
        incident_id = resp.json()["incident_id"]

        with patch("app.routes.agent.analyze_priority", return_value=None):
            response = client.post(f"/api/agent/analyze-priority/{incident_id}")
            assert response.status_code == 500
