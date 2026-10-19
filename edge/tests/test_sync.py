"""
Tests for the edge synchronization engine.
"""

from unittest.mock import MagicMock, patch

from app import queue as queue_svc
from app.models import EdgePacketCreate, SyncStatus
from app.sync import sync_packet, sync_all_pending


def _make_packet(**overrides) -> dict:
    """Helper to create a packet dict for testing sync functions."""
    defaults = {
        "packet_id": "EDGE-000001",
        "description": "Test emergency",
        "people_affected": 2,
        "latitude": 24.0,
        "longitude": 67.0,
        "created_at": "2026-08-29T00:00:00+00:00",
        "status": SyncStatus.queued.value,
        "attempt_count": 0,
        "last_error": None,
        "synced_at": None,
        "incident_id": None,
    }
    defaults.update(overrides)
    return defaults


class TestSyncPacket:
    def test_successful_sync(self):
        """Packet should be marked SYNCED with the backend incident_id."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"incident_id": "RSN-000001", "status": "queued"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            MockClient.return_value = mock_client

            packet = _make_packet()
            result = sync_packet(packet)

            assert result.success is True
            assert result.incident_id == "RSN-000001"
            assert result.error is None

    def test_failed_sync_marks_packet(self):
        """Failed sync should mark the packet as FAILED."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Server error 500")

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            MockClient.return_value = mock_client

            packet = _make_packet()
            result = sync_packet(packet)

            assert result.success is False
            assert result.error is not None

    def test_sync_skips_max_attempts(self):
        """Packet at max attempts should be skipped."""
        packet = _make_packet(
            status=SyncStatus.failed.value,
            attempt_count=5,  # default SYNC_MAX_ATTEMPTS
        )
        result = sync_packet(packet)
        assert result.success is False
        assert "Max attempts" in result.error


class TestSyncAllPending:
    def test_syncs_multiple_packets(self):
        """All queued packets should be synced successfully."""
        data = EdgePacketCreate(
            description="Emergency 1", people_affected=1, latitude=24.0, longitude=67.0
        )
        p1 = queue_svc.create_packet(data)
        p2 = queue_svc.create_packet(data)

        call_count = 0

        def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 201
            resp.json.return_value = {"incident_id": f"RSN-{call_count:06d}", "status": "queued"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = mock_post
            MockClient.return_value = mock_client

            results = sync_all_pending()
            assert len(results) == 2
            assert all(r.success for r in results)
            assert call_count == 2

    def test_one_failure_does_not_block_others(self):
        """If one packet fails, others should still be processed."""
        data = EdgePacketCreate(
            description="Emergency", people_affected=1, latitude=24.0, longitude=67.0
        )
        p1 = queue_svc.create_packet(data)
        p2 = queue_svc.create_packet(data)

        call_count = 0

        def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if call_count == 1:
                resp.raise_for_status.side_effect = Exception("Server error")
                return resp
            resp.status_code = 201
            resp.json.return_value = {"incident_id": f"RSN-{call_count:06d}", "status": "queued"}
            resp.raise_for_status = MagicMock()
            return resp

        with patch("app.sync.httpx.Client") as MockClient:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = mock_post
            MockClient.return_value = mock_client

            results = sync_all_pending()
            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]
            assert len(successes) == 1
            assert len(failures) == 1

    def test_empty_queue_returns_no_results(self):
        """No pending packets should return an empty results list."""
        results = sync_all_pending()
        assert results == []
