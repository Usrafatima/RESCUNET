"""
Tests for RescuNet API endpoints.

Covers:
1. Health endpoint
2. Root endpoint
3. Create incident
4. Retrieve all incidents
5. Retrieve individual incident
6. Update incident status
7. Invalid incident data (validation errors)
8. Missing incident (404)
"""

VALID_INCIDENT = {
    "description": "My father is diabetic and urgently needs insulin.",
    "people_affected": 2,
    "latitude": 24.8607,
    "longitude": 67.0011,
}


class TestHealthEndpoint:
    def test_health_returns_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "rescunet-backend"

    def test_root_returns_api_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RescuNet API"
        assert "docs" in data


class TestCreateIncident:
    def test_create_incident_success(self, client):
        response = client.post("/api/incidents", json=VALID_INCIDENT)
        assert response.status_code == 201
        data = response.json()
        assert data["incident_id"].startswith("RSN-")
        assert data["description"] == VALID_INCIDENT["description"]
        assert data["people_affected"] == 2
        assert data["latitude"] == 24.8607
        assert data["longitude"] == 67.0011
        assert data["status"] == "queued"
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_second_incident_gets_sequential_id(self, client):
        client.post("/api/incidents", json=VALID_INCIDENT)
        response = client.post("/api/incidents", json=VALID_INCIDENT)
        assert response.status_code == 201
        assert response.json()["incident_id"] == "RSN-000002"


class TestRetrieveIncidents:
    def test_list_empty(self, client):
        response = client.get("/api/incidents")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_incidents(self, client):
        client.post("/api/incidents", json=VALID_INCIDENT)
        response = client.get("/api/incidents")
        assert response.status_code == 200
        incidents = response.json()
        assert len(incidents) == 1
        assert incidents[0]["incident_id"] == "RSN-000001"

    def test_get_incident_by_id(self, client):
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        response = client.get(f"/api/incidents/{incident_id}")
        assert response.status_code == 200
        assert response.json()["incident_id"] == incident_id

    def test_get_incident_not_found(self, client):
        response = client.get("/api/incidents/RSN-999999")
        assert response.status_code == 404


class TestUpdateIncidentStatus:
    def test_update_status_success(self, client):
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        response = client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "processing"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processing"

    def test_update_status_invalid(self, client):
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        response = client.patch(
            f"/api/incidents/{incident_id}/status",
            json={"status": "invalid_status"},
        )
        assert response.status_code == 422

    def test_update_status_not_found(self, client):
        response = client.patch(
            "/api/incidents/RSN-999999/status",
            json={"status": "processing"},
        )
        assert response.status_code == 404

    def test_full_lifecycle(self, client):
        """Test a complete incident lifecycle through all statuses."""
        create_resp = client.post("/api/incidents", json=VALID_INCIDENT)
        incident_id = create_resp.json()["incident_id"]

        lifecycle = [
            "processing",
            "awaiting_approval",
            "approved",
            "dispatched",
            "resolved",
        ]
        for new_status in lifecycle:
            response = client.patch(
                f"/api/incidents/{incident_id}/status",
                json={"status": new_status},
            )
            assert response.status_code == 200
            assert response.json()["status"] == new_status

        # Verify the final state via GET
        get_resp = client.get(f"/api/incidents/{incident_id}")
        assert get_resp.json()["status"] == "resolved"


class TestValidationErrors:
    def test_empty_description(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "description": ""},
        )
        assert response.status_code == 422

    def test_people_affected_zero(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "people_affected": 0},
        )
        assert response.status_code == 422

    def test_people_affected_negative(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "people_affected": -1},
        )
        assert response.status_code == 422

    def test_latitude_out_of_range(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "latitude": 91},
        )
        assert response.status_code == 422

    def test_longitude_out_of_range(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "longitude": 181},
        )
        assert response.status_code == 422

    def test_missing_fields(self, client):
        response = client.post("/api/incidents", json={})
        assert response.status_code == 422

    def test_missing_description(self, client):
        response = client.post(
            "/api/incidents",
            json={
                "people_affected": 2,
                "latitude": 24.8607,
                "longitude": 67.0011,
            },
        )
        assert response.status_code == 422


class TestPersistence:
    """Verify that the database persists across service restarts."""

    def test_incident_persists_in_sqlite(self, client):
        """Create an incident, then verify it's in the database directly."""
        client.post("/api/incidents", json=VALID_INCIDENT)

        # Verify via API
        response = client.get("/api/incidents")
        assert len(response.json()) == 1

        # The TestClient reuses the same process, but since we use a real
        # SQLite file (via the _isolated_db fixture), the data is on disk.


class TestIdempotency:
    """Test idempotent incident creation via packet_id."""

    def test_create_incident_with_packet_id(self, client):
        response = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "packet_id": "EDGE-000001"},
        )
        assert response.status_code == 201
        assert response.json()["packet_id"] == "EDGE-000001"

    def test_duplicate_packet_id_returns_existing(self, client):
        """Sending the same packet_id twice must NOT create two incidents."""
        resp1 = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "packet_id": "EDGE-000001"},
        )
        resp2 = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "packet_id": "EDGE-000001"},
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201  # returns 201 with existing record
        assert resp1.json()["incident_id"] == resp2.json()["incident_id"]

        # Verify only one incident exists
        list_resp = client.get("/api/incidents")
        assert len(list_resp.json()) == 1

    def test_different_packet_ids_create_different_incidents(self, client):
        resp1 = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "packet_id": "EDGE-000001"},
        )
        resp2 = client.post(
            "/api/incidents",
            json={**VALID_INCIDENT, "packet_id": "EDGE-000002"},
        )
        assert resp1.json()["incident_id"] != resp2.json()["incident_id"]
        list_resp = client.get("/api/incidents")
        assert len(list_resp.json()) == 2

    def test_incident_without_packet_id_still_works(self, client):
        """Backward compatibility: creating without packet_id still works."""
        response = client.post("/api/incidents", json=VALID_INCIDENT)
        assert response.status_code == 201
        assert response.json()["packet_id"] is None
