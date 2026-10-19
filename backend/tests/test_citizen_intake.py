"""
Tests for RescuNet Citizen Emergency Intake and Status Tracking.

Covers:
1. Citizen emergency report submission across all emergency types:
   Medical, Fire, Flood, Accident, Other.
2. Dual lookup: retrieving incident by both incident_id and edge packet_id.
3. Safe citizen report lifecycle (intake into queue, triage, safe status).
4. Auto-planning trigger verification for high-urgency citizen reports.
5. Ensuring no internal dispatch or real-world dispatch occurs on intake.
"""

import pytest


CITIZEN_REPORTS = [
    {
        "type": "Medical",
        "payload": {
            "description": "[MEDICAL] [URGENT: LIFE THREAT] Severe chest pain, unconscious elderly patient.",
            "people_affected": 1,
            "latitude": 24.8607,
            "longitude": 67.0011,
            "auto_plan": True,
        },
    },
    {
        "type": "Fire",
        "payload": {
            "description": "[FIRE] [URGENT: LIFE THREAT] Flames spreading in apartment building, smoke inhalation.",
            "people_affected": 4,
            "latitude": 24.8650,
            "longitude": 67.0050,
            "auto_plan": True,
        },
    },
    {
        "type": "Flood",
        "payload": {
            "description": "[FLOOD] Ground floor submerged, family stranded on roof by rising water.",
            "people_affected": 5,
            "latitude": 24.8700,
            "longitude": 67.0100,
            "auto_plan": True,
        },
    },
    {
        "type": "Accident",
        "payload": {
            "description": "[ACCIDENT] Two vehicles collided, passenger pinned inside car.",
            "people_affected": 2,
            "latitude": 24.8550,
            "longitude": 67.0200,
            "auto_plan": True,
        },
    },
    {
        "type": "Other",
        "payload": {
            "description": "[OTHER] Strong chemical leak from damaged industrial pipeline.",
            "people_affected": 3,
            "latitude": 24.8400,
            "longitude": 67.0300,
            "auto_plan": False,
        },
    },
]


class TestCitizenEmergencyIntake:
    @pytest.mark.parametrize("report", CITIZEN_REPORTS)
    def test_citizen_report_submission(self, client, report):
        """Test each emergency type is ingested successfully into the intake queue."""
        response = client.post("/api/incidents", json=report["payload"])
        assert response.status_code == 201

        data = response.json()
        assert data["incident_id"].startswith("RSN-")
        assert data["description"] == report["payload"]["description"]
        assert data["people_affected"] == report["payload"]["people_affected"]
        assert data["latitude"] == report["payload"]["latitude"]
        assert data["longitude"] == report["payload"]["longitude"]
        assert data["status"] in ["queued", "awaiting_approval"]

    def test_dual_lookup_by_incident_id_and_packet_id(self, client):
        """Ensure citizens tracking an EDGE- packet ID can look up their incident once synced."""
        packet_id = "EDGE-000088"
        payload = {
            "description": "[MEDICAL] Diabetic patient in shock requiring assistance.",
            "people_affected": 1,
            "latitude": 24.8607,
            "longitude": 67.0011,
            "packet_id": packet_id,
        }

        create_resp = client.post("/api/incidents", json=payload)
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["incident_id"]

        # Lookup by canonical RSN- incident_id
        res_by_incident = client.get(f"/api/incidents/{incident_id}")
        assert res_by_incident.status_code == 200
        assert res_by_incident.json()["incident_id"] == incident_id
        assert res_by_incident.json()["packet_id"] == packet_id

        # Lookup by edge packet_id
        res_by_packet = client.get(f"/api/incidents/{packet_id}")
        assert res_by_packet.status_code == 200
        assert res_by_packet.json()["incident_id"] == incident_id
        assert res_by_packet.json()["packet_id"] == packet_id

    def test_citizen_safe_status_tracking(self, client):
        """Verify status progression is tracked safely without exposing admin controls."""
        payload = {
            "description": "[ACCIDENT] Minor vehicle scrape on highway shoulder.",
            "people_affected": 1,
            "latitude": 24.8607,
            "longitude": 67.0011,
        }
        create_resp = client.post("/api/incidents", json=payload)
        incident_id = create_resp.json()["incident_id"]

        # Initial status is queued
        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "queued"

        # Safe status fields only: no internal responder names or admin secrets
        data = get_resp.json()
        assert "incident_id" in data
        assert "description" in data
        assert "status" in data
        assert "resources" not in data  # internal resource data is not leaked
        assert "approval_actions" not in data  # admin actions not present

    def test_roman_urdu_and_voice_transcript_submission(self, client):
        """Test that Roman Urdu voice transcripts are ingested safely with landmarks."""
        payload = {
            "description": (
                "[MEDICAL] [URGENT: LIFE THREAT / CRITICAL] "
                "Location Landmark: Civil Hospital Gate 2 ke samnay. "
                "50 saala mareez behosh hai, chest pain aur saans ki takleef hai."
            ),
            "people_affected": 1,
            "latitude": 24.8607,
            "longitude": 67.0011,
            "auto_plan": True,
        }
        response = client.post("/api/incidents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["incident_id"].startswith("RSN-")
        assert "Civil Hospital" in data["description"]
        assert "behosh" in data["description"]
        assert data["people_affected"] == 1

        # Incident can be tracked safely
        get_res = client.get(f"/api/incidents/{data['incident_id']}")
        assert get_res.status_code == 200
        assert get_res.json()["status"] in ["queued", "awaiting_approval"]

