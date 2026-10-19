"""
Tests for edge gateway API endpoints.
"""

from unittest.mock import MagicMock, patch

import pytest

from app import queue as queue_svc
from app.models import EdgePacketCreate


SAMPLE_PACKET = {
    "description": "Building fire on 5th floor",
    "people_affected": 8,
    "latitude": 24.8607,
    "longitude": 67.0011,
}


class TestRootAndHealth:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Edge Gateway" in resp.json()["name"]

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestReceiveSOS:
    def test_create_packet(self, client):
        resp = client.post("/edge/incidents", json=SAMPLE_PACKET)
        assert resp.status_code == 201
        data = resp.json()
        assert data["packet_id"].startswith("EDGE-")
        assert data["status"] == "queued"
        assert "stored locally" in data["message"]

    def test_create_multiple(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        resp = client.get("/edge/queue")
        assert len(resp.json()) == 2

    def test_invalid_payload(self, client):
        resp = client.post("/edge/incidents", json={"description": ""})
        assert resp.status_code == 422

    def test_missing_fields(self, client):
        resp = client.post("/edge/incidents", json={})
        assert resp.status_code == 422


class TestViewQueue:
    def test_empty_queue(self, client):
        resp = client.get("/edge/queue")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_shows_created_packets(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        resp = client.get("/edge/queue")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "queued"

    def test_filter_by_status(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)

        # Mark one as synced directly via service
        packets = queue_svc.list_packets()
        queue_svc.mark_synced(packets[0]["packet_id"], "RSN-000001")

        resp_queued = client.get("/edge/queue?status=queued")
        assert len(resp_queued.json()) == 1

        resp_synced = client.get("/edge/queue?status=synced")
        assert len(resp_synced.json()) == 1


class TestConnectivity:
    def test_default_is_offline(self, client):
        resp = client.get("/edge/connectivity")
        assert resp.json()["online"] is False
        assert resp.json()["mode"] == "OFFLINE"
        assert resp.json()["queued_packets"] == 0

    def test_toggle_online(self, client):
        resp = client.post("/edge/connectivity", json={"online": True})
        assert resp.json()["online"] is True
        assert resp.json()["mode"] == "ONLINE"

    def test_toggle_back_offline(self, client):
        client.post("/edge/connectivity", json={"online": True})
        resp = client.post("/edge/connectivity", json={"online": False})
        assert resp.json()["online"] is False
        assert resp.json()["mode"] == "OFFLINE"

    def test_queued_count_reflects_packets(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        resp = client.get("/edge/connectivity")
        assert resp.json()["queued_packets"] == 3

    def test_new_packets_queued_while_offline(self, client):
        """Packets submitted while offline remain queued."""
        client.post("/edge/connectivity", json={"online": False})
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)

        resp = client.get("/edge/connectivity")
        assert resp.json()["queued_packets"] == 2
        assert resp.json()["mode"] == "OFFLINE"


class TestSyncTrigger:
    def test_sync_blocked_when_offline(self, client):
        client.post("/edge/connectivity", json={"online": False})
        resp = client.post("/edge/sync")
        assert resp.json()["synced"] == 0
        assert "OFFLINE" in resp.json()["message"]

    def test_sync_no_packets(self, client):
        client.post("/edge/connectivity", json={"online": True})
        resp = client.post("/edge/sync")
        assert resp.json()["synced"] == 0
        assert resp.json()["failed"] == 0

    def test_sync_success(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)

        call_count = 0

        def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 201
            resp.json.return_value = {"incident_id": f"RSN-{call_count:06d}", "status": "queued"}
            resp.raise_for_status = MagicMock()
            return resp

        import app.main as main_mod
        main_mod._connectivity_state["online"] = True

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = mock_post
            MockClient.return_value = mock_client

            resp = client.post("/edge/sync")
            assert resp.json()["synced"] == 2
            assert resp.json()["failed"] == 0
            assert call_count == 2

    def test_sync_partial_failure(self, client):
        client.post("/edge/incidents", json=SAMPLE_PACKET)
        client.post("/edge/incidents", json=SAMPLE_PACKET)

        call_count = 0

        def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:
                resp.raise_for_status.side_effect = Exception("Backend error")
                return resp
            resp.status_code = 201
            resp.json.return_value = {"incident_id": f"RSN-{call_count:06d}", "status": "queued"}
            resp.raise_for_status = MagicMock()
            return resp

        import app.main as main_mod
        main_mod._connectivity_state["online"] = True

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = mock_post
            MockClient.return_value = mock_client

            resp = client.post("/edge/sync")
            assert resp.json()["synced"] == 1
            assert resp.json()["failed"] == 1
