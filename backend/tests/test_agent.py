"""
Tests for RescuNet AI Agent layer.

Covers:
1. Distance calculation (Haversine)
2. Resource database initialization and seeding
3. Agent tools (get_incident, find_available_resources, etc.)
4. Agent API endpoint
5. AgentRecommendation Pydantic model validation
6. analyze_incident with structured_output_model

These tests do NOT require a live Gemini API call.
The LLM is mocked for integration tests.
"""

import json
import math
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent.tools.incident_tools import _haversine_km


# ─── Distance Calculation Tests ───────────────────────────────────────

class TestHaversineDistance:
    """Test the Haversine distance calculation function."""

    def test_same_point_returns_zero(self):
        """A point compared to itself should be 0 km."""
        assert _haversine_km(24.8607, 67.0011, 24.8607, 67.0011) == 0.0

    def test_known_distance(self):
        """Test a known distance between two points."""
        # Karachi to Lahore (Haversine straight-line) is approximately 1,033 km
        distance = _haversine_km(24.8607, 67.0011, 31.5204, 74.3587)
        assert 1000 < distance < 1100

    def test_short_distance(self):
        """Test a short distance between nearby points."""
        # Two points ~1 km apart
        distance = _haversine_km(24.8607, 67.0011, 24.8615, 67.0020)
        assert 0.05 < distance < 0.5

    def test_antipodal_points(self):
        """Test opposite sides of the Earth (~20,000 km)."""
        distance = _haversine_km(0, 0, 0, 180)
        assert 20000 < distance < 20100

    def test_returns_float(self):
        """Distance should be a float rounded to 2 decimal places."""
        distance = _haversine_km(24.8607, 67.0011, 24.8615, 67.0020)
        assert isinstance(distance, float)


# ─── Resource Database Tests ──────────────────────────────────────────

class TestResourceDatabase:
    """Test resource database initialization and querying."""

    def test_init_creates_database(self, tmp_path, monkeypatch):
        """Database should be created on init."""
        from agent import resource_db

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        resource_db.init_resource_db()
        assert db_path.exists()

    def test_seed_data_loaded(self, tmp_path, monkeypatch):
        """Seed resources should be loaded on init."""
        from agent import resource_db

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        resource_db.init_resource_db()

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) as c FROM resources").fetchone()["c"]
        conn.close()
        assert count == 5

    def test_resource_types_correct(self, tmp_path, monkeypatch):
        """Seed resources should have correct types."""
        from agent import resource_db

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        resource_db.init_resource_db()

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT type FROM resources ORDER BY resource_id").fetchall()
        types = [row["type"] for row in rows]
        conn.close()
        assert "medical" in types
        assert "rescue" in types
        assert "supplies" in types

    def test_idempotent_init(self, tmp_path, monkeypatch):
        """Calling init twice should not duplicate resources."""
        from agent import resource_db

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        resource_db.init_resource_db()
        resource_db.init_resource_db()  # second call

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) as c FROM resources").fetchone()["c"]
        conn.close()
        assert count == 5


# ─── Agent Tool Tests (Mocked Backend) ────────────────────────────────

class TestGetIncidentTool:
    """Test the get_incident tool with mocked backend."""

    def test_get_incident_found(self):
        """Should return incident details when found."""
        from agent.tools.incident_tools import get_incident

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "incident_id": "RSN-000001",
            "description": "Diabetic needs insulin",
            "people_affected": 2,
            "latitude": 24.8607,
            "longitude": 67.0011,
            "status": "queued",
        }

        with patch("agent.tools.incident_tools.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_response)))
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            result = get_incident(incident_id="RSN-000001")
            data = json.loads(result)
            assert data["incident_id"] == "RSN-000001"

    def test_get_incident_not_found(self):
        """Should return error when incident not found."""
        from agent.tools.incident_tools import get_incident

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("agent.tools.incident_tools.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_response)))
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            result = get_incident(incident_id="RSN-999999")
            data = json.loads(result)
            assert "error" in data

    def test_get_incident_connection_error(self):
        """Should return error when backend is unreachable."""
        from agent.tools.incident_tools import get_incident

        with patch("agent.tools.incident_tools.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value.__enter__ = MagicMock(return_value=mock_instance)
            mock_client.return_value.__exit__ = MagicMock(return_value=False)
            result = get_incident(incident_id="RSN-000001")
            data = json.loads(result)
            assert "error" in data


class TestFindAvailableResourcesTool:
    """Test the find_available_resources tool."""

    def test_find_all_available(self, tmp_path, monkeypatch):
        """Should return all available resources."""
        from agent import resource_db
        from agent.tools.incident_tools import find_available_resources

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        result = find_available_resources(incident_type="any")
        data = json.loads(result)
        assert len(data) == 5
        assert all(r["status"] == "available" for r in data)

    def test_find_medical_resources(self, tmp_path, monkeypatch):
        """Should return only medical resources when filtered."""
        from agent import resource_db
        from agent.tools.incident_tools import find_available_resources

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        result = find_available_resources(incident_type="medical")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["type"] == "medical"

    def test_find_rescue_resources(self, tmp_path, monkeypatch):
        """Should return rescue resources."""
        from agent import resource_db
        from agent.tools.incident_tools import find_available_resources

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        result = find_available_resources(incident_type="rescue")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["type"] == "rescue"


class TestGetResourceStatusTool:
    """Test the get_resource_status tool."""

    def test_get_existing_resource(self, tmp_path, monkeypatch):
        """Should return resource details."""
        from agent import resource_db
        from agent.tools.incident_tools import get_resource_status

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        result = get_resource_status(resource_id="RES-001")
        data = json.loads(result)
        assert data["resource_id"] == "RES-001"
        assert data["name"] == "Medical Team Alpha"
        assert data["status"] == "available"

    def test_get_nonexistent_resource(self, tmp_path, monkeypatch):
        """Should return error for missing resource."""
        from agent import resource_db
        from agent.tools.incident_tools import get_resource_status

        db_path = tmp_path / "test_resources.db"
        monkeypatch.setattr(resource_db, "DATABASE_PATH", db_path)
        monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)

        result = get_resource_status(resource_id="RES-999")
        data = json.loads(result)
        assert "error" in data


class TestCalculateDistanceTool:
    """Test the calculate_distance tool."""

    def test_distance_calculation(self):
        """Should calculate correct distance."""
        from agent.tools.incident_tools import calculate_distance

        result = calculate_distance(
            origin_latitude=24.8607,
            origin_longitude=67.0011,
            destination_latitude=24.8615,
            destination_longitude=67.0020,
        )
        data = json.loads(result)
        assert "distance_km" in data
        assert 0.05 < data["distance_km"] < 0.5

    def test_distance_zero_for_same_point(self):
        """Same point should return 0 km."""
        from agent.tools.incident_tools import calculate_distance

        result = calculate_distance(
            origin_latitude=24.8607,
            origin_longitude=67.0011,
            destination_latitude=24.8607,
            destination_longitude=67.0011,
        )
        data = json.loads(result)
        assert data["distance_km"] == 0.0


# ─── AgentRecommendation Model Tests ──────────────────────────────────

class TestAgentRecommendationModel:
    """Test AgentRecommendation Pydantic model validation."""

    def test_valid_recommendation(self):
        """Should validate a complete recommendation."""
        from agent.models import AgentRecommendation

        rec = AgentRecommendation(
            incident_id="RSN-000001",
            analysis="Medical emergency requiring insulin.",
            classification={
                "type": "medical",
                "priority": "critical",
                "people_affected": 2,
                "immediate_need": "insulin",
            },
            recommended_action={
                "resource_id": "RES-001",
                "resource_name": "Medical Team Alpha",
                "resource_type": "medical",
                "distance_km": 1.8,
                "reason": "Nearest available medical responder",
            },
            human_approval_required=True,
        )
        assert rec.incident_id == "RSN-000001"
        assert rec.recommended_action.resource_id == "RES-001"
        assert rec.recommended_action.resource_type == "medical"
        assert rec.human_approval_required is True
        assert rec.analysis == "Medical emergency requiring insulin."

    def test_model_dump_returns_all_fields(self):
        """model_dump should include all expected fields."""
        from agent.models import AgentRecommendation

        rec = AgentRecommendation(
            incident_id="RSN-000001",
            analysis="Rescue emergency.",
            classification={
                "type": "rescue",
                "priority": "high",
                "people_affected": 5,
                "immediate_need": "extrication",
            },
            recommended_action={
                "resource_id": "RES-002",
                "resource_name": "Rescue Team Bravo",
                "resource_type": "rescue",
                "distance_km": 3.2,
                "reason": "Closest rescue team",
            },
            human_approval_required=True,
        )
        d = rec.model_dump()
        assert "analysis" in d
        assert "classification" in d
        assert "recommended_action" in d
        assert d["recommended_action"]["resource_type"] == "rescue"

    def test_invalid_type_enum_rejected(self):
        """Invalid incident type should be rejected."""
        from agent.models import AgentRecommendation
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentRecommendation(
                incident_id="RSN-000001",
                analysis="test",
                classification={
                    "type": "invalid_type",
                    "priority": "critical",
                    "people_affected": 1,
                    "immediate_need": "test",
                },
                recommended_action={
                    "resource_id": "RES-001",
                    "resource_name": "Test",
                    "resource_type": "medical",
                    "distance_km": 1.0,
                    "reason": "test",
                },
                human_approval_required=True,
            )

    def test_invalid_priority_enum_rejected(self):
        """Invalid priority should be rejected."""
        from agent.models import AgentRecommendation
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentRecommendation(
                incident_id="RSN-000001",
                analysis="test",
                classification={
                    "type": "medical",
                    "priority": "urgent",
                    "people_affected": 1,
                    "immediate_need": "test",
                },
                recommended_action={
                    "resource_id": "RES-001",
                    "resource_name": "Test",
                    "resource_type": "medical",
                    "distance_km": 1.0,
                    "reason": "test",
                },
                human_approval_required=True,
            )

    def test_human_approval_defaults_true(self):
        """human_approval_required should default to True."""
        from agent.models import AgentRecommendation

        rec = AgentRecommendation(
            incident_id="RSN-000001",
            analysis="test",
            classification={
                "type": "other",
                "priority": "low",
                "people_affected": 1,
                "immediate_need": "general",
            },
            recommended_action={
                "resource_id": "RES-001",
                "resource_name": "Test",
                "resource_type": "other",
                "distance_km": 1.0,
                "reason": "test",
            },
        )
        assert rec.human_approval_required is True


# ─── Agent API Endpoint Tests ─────────────────────────────────────────

VALID_INCIDENT = {
    "description": "My father is diabetic and urgently needs insulin.",
    "people_affected": 2,
    "latitude": 24.8607,
    "longitude": 67.0011,
}


class TestAgentEndpoint:
    """Test the POST /api/agent/analyze/{incident_id} endpoint."""

    def test_analyze_nonexistent_incident_returns_404(self, client):
        """Should return 404 for nonexistent incident."""
        response = client.post("/api/agent/analyze/RSN-999999")
        assert response.status_code == 404

    def test_analyze_existing_incident(self, client):
        """Should trigger agent analysis for existing incident."""
        # Create an incident first
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        # Mock the agent analysis - with structured recommendation
        mock_result = {
            "incident_id": incident_id,
            "analysis": "Medical emergency. Recommended: Medical Team Alpha.",
            "status": "recommendation_ready",
            "human_approval_required": True,
            "recommendation": {
                "incident_id": incident_id,
                "analysis": "Medical emergency requiring insulin.",
                "classification": {
                    "type": "medical",
                    "priority": "critical",
                    "people_affected": 2,
                    "immediate_need": "insulin",
                },
                "recommended_action": {
                    "resource_id": "RES-001",
                    "resource_name": "Medical Team Alpha",
                    "resource_type": "medical",
                    "reason": "Nearest available medical responder",
                    "distance_km": 1.8,
                },
                "human_approval_required": True,
            },
        }

        with patch("app.routes.agent.analyze_incident", return_value=mock_result):
            response = client.post(f"/api/agent/analyze/{incident_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["incident_id"] == incident_id
            assert data["status"] == "recommendation_ready"
            assert data["human_approval_required"] is True
            assert data["recommendation"] is not None
            assert data["recommendation"]["recommended_action"]["resource_id"] == "RES-001"

    def test_analyze_returns_human_approval_required(self, client):
        """Every analysis must require human approval."""
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        mock_result = {
            "incident_id": incident_id,
            "analysis": "Critical medical incident.",
            "status": "recommendation_ready",
            "human_approval_required": True,
            "recommendation": None,
        }

        with patch("app.routes.agent.analyze_incident", return_value=mock_result):
            response = client.post(f"/api/agent/analyze/{incident_id}")
            assert response.json()["human_approval_required"] is True

    def test_analyze_agent_failure_returns_500(self, client):
        """Should return 500 when agent fails."""
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        with patch("app.routes.agent.analyze_incident", return_value=None):
            response = client.post(f"/api/agent/analyze/{incident_id}")
            assert response.status_code == 500

    def test_analyze_medical_incident_classification(self, client):
        """Medical incident should be classified as medical type."""
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        mock_result = {
            "incident_id": incident_id,
            "analysis": "Type: medical\nPriority: critical",
            "status": "recommendation_ready",
            "human_approval_required": True,
            "recommendation": {
                "incident_id": incident_id,
                "analysis": "Medical emergency requiring insulin.",
                "classification": {
                    "type": "medical",
                    "priority": "critical",
                    "people_affected": 2,
                    "immediate_need": "insulin",
                },
                "recommended_action": {
                    "resource_id": "RES-001",
                    "resource_name": "Medical Team Alpha",
                    "resource_type": "medical",
                    "reason": "Medical emergency",
                    "distance_km": 1.8,
                },
                "human_approval_required": True,
            },
        }

        with patch("app.routes.agent.analyze_incident", return_value=mock_result):
            response = client.post(f"/api/agent/analyze/{incident_id}")
            data = response.json()
            assert data["recommendation"]["classification"]["type"] == "medical"

    def test_analyze_null_recommendation(self, client):
        """Should return null recommendation when extraction fails."""
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        mock_result = {
            "incident_id": incident_id,
            "analysis": "I analyzed the incident but could not determine a recommendation.",
            "status": "recommendation_ready",
            "human_approval_required": True,
            "recommendation": None,
        }

        with patch("app.routes.agent.analyze_incident", return_value=mock_result):
            response = client.post(f"/api/agent/analyze/{incident_id}")
            data = response.json()
            assert data["recommendation"] is None
            assert data["analysis"] is not None


# ─── analyze_incident with structured_output_model ────────────────────

class TestAnalyzeIncidentStructured:
    """Test that analyze_incident uses structured_output_model correctly."""

    def test_returns_structured_recommendation(self):
        """Should return structured recommendation when agent produces valid output."""
        from agent.rescuenet_agent import analyze_incident
        from agent.models import AgentRecommendation

        mock_recommendation = AgentRecommendation(
            incident_id="RSN-000001",
            analysis="Medical emergency requiring insulin. Medical Team Alpha is nearest.",
            classification={
                "type": "medical",
                "priority": "critical",
                "people_affected": 2,
                "immediate_need": "insulin",
            },
            recommended_action={
                "resource_id": "RES-001",
                "resource_name": "Medical Team Alpha",
                "resource_type": "medical",
                "distance_km": 1.8,
                "reason": "Nearest medical responder with insulin equipment",
            },
            human_approval_required=True,
        )

        mock_result = MagicMock()
        mock_result.structured_output = mock_recommendation
        mock_result.message = {"content": [{"text": "Analysis complete."}]}

        with patch("agent.rescuenet_agent.create_agent") as mock_create:
            mock_agent_instance = MagicMock(return_value=mock_result)
            mock_create.return_value = mock_agent_instance
            result = analyze_incident("RSN-000001")

        assert result is not None
        assert result["recommendation"] is not None
        assert result["recommendation"]["recommended_action"]["resource_id"] == "RES-001"
        assert result["recommendation"]["recommended_action"]["resource_name"] == "Medical Team Alpha"
        assert result["recommendation"]["recommended_action"]["distance_km"] == 1.8
        assert result["recommendation"]["recommended_action"]["resource_type"] == "medical"
        assert result["recommendation"]["analysis"] == "Medical emergency requiring insulin. Medical Team Alpha is nearest."
        assert result["recommendation"]["human_approval_required"] is True
        assert result["analysis"] == "Medical emergency requiring insulin. Medical Team Alpha is nearest."
        assert result["human_approval_required"] is True

    def test_returns_null_when_no_structured_output(self):
        """Should return null recommendation when structured_output is None."""
        from agent.rescuenet_agent import analyze_incident

        mock_result = MagicMock()
        mock_result.structured_output = None
        mock_result.message = {"content": [{"text": "I analyzed the incident but no structured output."}]}

        with patch("agent.rescuenet_agent.create_agent") as mock_create:
            mock_agent_instance = MagicMock(return_value=mock_result)
            mock_create.return_value = mock_agent_instance
            result = analyze_incident("RSN-000001")

        assert result is not None
        assert result["recommendation"] is None
        assert result["analysis"] == "I analyzed the incident but no structured output."

    def test_returns_none_on_agent_exception(self):
        """Should return None when agent raises exception."""
        from agent.rescuenet_agent import analyze_incident

        with patch("agent.rescuenet_agent.create_agent") as mock_create:
            mock_create.return_value = MagicMock(side_effect=Exception("API error"))
            result = analyze_incident("RSN-000001")

        assert result is None

    def test_resource_id_from_tool_not_invented(self):
        """Resource IDs must match what tools return."""
        from agent.rescuenet_agent import analyze_incident
        from agent.models import AgentRecommendation

        mock_recommendation = AgentRecommendation(
            incident_id="RSN-000001",
            analysis="Supply Team Charlie (RES-003) is closest.",
            classification={
                "type": "supplies",
                "priority": "medium",
                "people_affected": 10,
                "immediate_need": "water and food",
            },
            recommended_action={
                "resource_id": "RES-003",
                "resource_name": "Supply Team Charlie",
                "resource_type": "supplies",
                "distance_km": 3.5,
                "reason": "Closest supply resource with water and food",
            },
            human_approval_required=True,
        )

        mock_result = MagicMock()
        mock_result.structured_output = mock_recommendation
        mock_result.message = {"content": [{"text": "Analysis complete."}]}

        with patch("agent.rescuenet_agent.create_agent") as mock_create:
            mock_create.return_value = MagicMock(return_value=mock_result)
            result = analyze_incident("RSN-000001")

        assert result["recommendation"]["recommended_action"]["resource_id"] == "RES-003"
        assert result["recommendation"]["recommended_action"]["resource_name"] == "Supply Team Charlie"

    def test_structured_output_called_with_model(self):
        """Verify structured_output_model parameter is passed to agent call."""
        from agent.rescuenet_agent import analyze_incident
        from agent.models import AgentRecommendation

        mock_result = MagicMock()
        mock_result.structured_output = None
        mock_result.message = {"content": [{"text": "text"}]}

        with patch("agent.rescuenet_agent.create_agent") as mock_create:
            mock_agent_instance = MagicMock(return_value=mock_result)
            mock_create.return_value = mock_agent_instance
            analyze_incident("RSN-000001")

            # Verify agent was called with structured_output_model
            mock_agent_instance.assert_called_once()
            call_kwargs = mock_agent_instance.call_args
            assert call_kwargs[1].get("structured_output_model") == AgentRecommendation
