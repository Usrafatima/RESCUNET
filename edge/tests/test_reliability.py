"""
Tests for Edge Gateway reliability improvements.

Focus:
- ONLINE/OFFLINE mode and queued packets survive a gateway restart
- packets stuck in `syncing` after a crash are recovered on startup
- transient failures are retried within a bounded budget; permanent
  rejections (4xx) are not retried forever
- single-flight sync guard prevents concurrent runs
- repeated synchronization cannot create duplicate incidents
- /edge/status reports useful operational information
"""

import asyncio
from unittest.mock import MagicMock, patch

import httpx

from app import config, database as db_module, queue as queue_svc
from app.main import _connectivity_state, app, lifespan
from app.models import EdgePacketCreate
from app.sync import sync_all_pending, sync_packet


SAMPLE = {
    "description": "[DEMO] Test emergency for reliability checks",
    "people_affected": 3,
    "latitude": 24.86,
    "longitude": 67.0,
}


def _run_lifespan():
    """Execute the gateway's real startup/shutdown code (simulates a restart)."""
    async def _run():
        async with lifespan(app):
            return None

    return asyncio.run(_run())


def _mock_client(post):
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.side_effect = post
    return client


def _ok_response(incident_id="RSN-000001"):
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"incident_id": incident_id, "status": "queued"}
    response.raise_for_status = MagicMock()
    return response


def _error_response(code: int):
    request = httpx.Request("POST", "http://127.0.0.1:8000/api/incidents")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"HTTP {code}", request=request, response=response)


def _raising_client(exc):
    """Mock HTTP client whose post() raises the given exception."""

    def _post(url, json=None):
        raise exc

    return _mock_client(_post)


class TestRestartPersistence:
    def test_mode_survives_restart(self, client):
        client.post("/edge/connectivity", json={"online": True})
        assert _connectivity_state["online"] is True

        _connectivity_state["online"] = False  # simulate process restart
        _run_lifespan()

        assert _connectivity_state["online"] is True
        assert client.get("/edge/connectivity").json()["mode"] == "ONLINE"

    def test_offline_mode_survives_restart(self, client):
        client.post("/edge/connectivity", json={"online": False})
        _connectivity_state["online"] = True  # simulate restart default
        _run_lifespan()
        assert _connectivity_state["online"] is False

    def test_queued_packets_survive_restart(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        client.post("/edge/incidents", json=SAMPLE)

        _run_lifespan()

        queue = client.get("/edge/queue").json()
        assert len(queue) == 2
        assert all(p["status"] == "queued" for p in queue)

    def test_stuck_syncing_packet_is_recovered_on_restart(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        packet = queue_svc.list_packets()[0]
        queue_svc.mark_syncing(packet["packet_id"])
        assert queue_svc.get_packet(packet["packet_id"])["status"] == "syncing"

        _run_lifespan()

        assert queue_svc.get_packet(packet["packet_id"])["status"] == "queued"


class TestRetryPolicy:
    def test_transient_failure_is_retried(self, client, monkeypatch):
        monkeypatch.setattr(config, "SYNC_RETRY_BACKOFF_SECONDS", 0.0)
        client.post("/edge/incidents", json=SAMPLE)

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _raising_client(_error_response(503))
            first = sync_all_pending()

        assert first[0].success is False
        packet = queue_svc.list_packets()[0]
        assert packet["status"] == "failed"
        assert packet["permanent"] == 0
        assert packet["attempt_count"] == 1
        assert queue_svc.get_pending_packets(), "transient failure must stay pending"

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _mock_client(
                lambda url, json=None: _ok_response("RSN-000001")
            )
            second = sync_all_pending()

        assert second[0].success is True
        assert queue_svc.get_packet(packet["packet_id"])["status"] == "synced"

    def test_permanent_rejection_is_not_retried(self, client):
        client.post("/edge/incidents", json=SAMPLE)

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _raising_client(_error_response(422))
            sync_all_pending()

        packet = queue_svc.list_packets()[0]
        assert packet["status"] == "failed"
        assert packet["permanent"] == 1
        assert queue_svc.get_pending_packets() == []

        # A later sync must not spend another attempt on invalid data.
        with patch("app.sync.httpx.Client") as MockClient:
            mock = _mock_client(lambda url, json=None: _ok_response())
            MockClient.return_value = mock
            results = sync_all_pending()
        assert results == []
        assert mock.post.call_count == 0

    def test_backoff_skips_a_just_failed_packet(self, client, monkeypatch):
        monkeypatch.setattr(config, "SYNC_RETRY_BACKOFF_SECONDS", 60.0)
        client.post("/edge/incidents", json=SAMPLE)

        with patch("app.sync.httpx.Client") as MockClient:
            mock = _raising_client(_error_response(500))
            MockClient.return_value = mock
            sync_all_pending()
            assert mock.post.call_count == 1

            # Immediately afterwards: skipped, backend not contacted again.
            results = sync_all_pending()
            assert results[0].skipped is True
            assert mock.post.call_count == 1

    def test_max_attempts_still_bounds_retries(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        packet = queue_svc.list_packets()[0]
        queue_svc.mark_failed(packet["packet_id"], "boom")
        queue_svc.mark_failed(packet["packet_id"], "boom")
        queue_svc.mark_failed(packet["packet_id"], "boom")
        queue_svc.mark_failed(packet["packet_id"], "boom")
        queue_svc.mark_failed(packet["packet_id"], "boom")

        result = sync_packet(queue_svc.get_packet(packet["packet_id"]))
        assert result.success is False
        assert "Max attempts" in result.error


class TestSyncSafety:
    def test_single_flight_guard(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        from app.sync import _sync_lock

        assert _sync_lock.acquire(blocking=False)
        try:
            assert sync_all_pending() is None
        finally:
            _sync_lock.release()

    def test_repeated_sync_does_not_duplicate_incidents(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        submitted_payloads = []

        def post(url, json=None):
            submitted_payloads.append(json)
            # The backend is idempotent on packet_id: a retried submission
            # returns the same incident.
            return _ok_response("RSN-000001")

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _mock_client(post)
            first = sync_all_pending()
            second = sync_all_pending()

        assert first[0].incident_id == "RSN-000001"
        assert second == []  # already synced — nothing pending
        assert len(submitted_payloads) == 1
        assert submitted_payloads[0]["packet_id"] == first[0].packet_id

    def test_packet_id_is_sent_on_every_attempt(self, client, monkeypatch):
        monkeypatch.setattr(config, "SYNC_RETRY_BACKOFF_SECONDS", 0.0)
        client.post("/edge/incidents", json=SAMPLE)
        payloads = []

        def post(url, json=None):
            payloads.append(json)
            if len(payloads) == 1:
                raise _error_response(503)
            return _ok_response("RSN-000042")

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _mock_client(post)
            sync_all_pending()

        with patch("app.sync.httpx.Client") as MockClient:
            MockClient.return_value = _mock_client(post)
            results = sync_all_pending()

        assert results[0].success is True
        assert results[0].incident_id == "RSN-000042"
        assert payloads[0]["packet_id"] == payloads[1]["packet_id"]


class TestStatusEndpoint:
    def test_status_reports_counts_and_limits(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        client.post("/edge/incidents", json=SAMPLE)

        body = client.get("/edge/status").json()
        assert body["mode"] == "OFFLINE"
        assert body["packets"]["queued"] == 2
        assert body["waiting_to_sync"] == 2
        assert body["backend_reachable"] is False
        assert "mesh" in body["note"].lower() or "device-to-device" in body["note"].lower()

    def test_status_counts_failures_by_kind(self, client):
        client.post("/edge/incidents", json=SAMPLE)
        packet = queue_svc.list_packets()[0]
        queue_svc.mark_failed(packet["packet_id"], "invalid", permanent=True)

        body = client.get("/edge/status").json()
        assert body["packets"]["failed_permanent"] == 1
        assert body["packets"]["failed_retryable"] == 0
        assert body["waiting_to_sync"] == 0
