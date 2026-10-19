"""
Tests for edge queue management.
"""

from app.database import init_db, get_db
from app.models import EdgePacketCreate, SyncStatus
from app import queue as queue_svc


class TestCreatePacket:
    def test_creates_packet_with_queued_status(self):
        data = EdgePacketCreate(
            description="Urgent medical emergency",
            people_affected=3,
            latitude=25.0,
            longitude=67.0,
        )
        packet = queue_svc.create_packet(data)
        assert packet["packet_id"].startswith("EDGE-")
        assert packet["status"] == SyncStatus.queued.value
        assert packet["description"] == "Urgent medical emergency"
        assert packet["people_affected"] == 3
        assert packet["attempt_count"] == 0

    def test_sequential_packet_ids(self):
        data = EdgePacketCreate(
            description="Fire", people_affected=1, latitude=24.0, longitude=67.0
        )
        p1 = queue_svc.create_packet(data)
        p2 = queue_svc.create_packet(data)
        assert p1["packet_id"] == "EDGE-000001"
        assert p2["packet_id"] == "EDGE-000002"

    def test_packet_persists_in_sqlite(self):
        data = EdgePacketCreate(
            description="Flood warning", people_affected=5, latitude=24.5, longitude=67.5
        )
        packet = queue_svc.create_packet(data)
        # Re-read from DB
        retrieved = queue_svc.get_packet(packet["packet_id"])
        assert retrieved is not None
        assert retrieved["description"] == "Flood warning"


class TestListPackets:
    def test_empty_list(self):
        assert queue_svc.list_packets() == []

    def test_returns_all(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        queue_svc.create_packet(data)
        queue_svc.create_packet(data)
        packets = queue_svc.list_packets()
        assert len(packets) == 2

    def test_filter_by_status(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        p = queue_svc.create_packet(data)
        queue_svc.mark_synced(p["packet_id"], "RSN-000001")

        queued = queue_svc.list_packets(status_filter="queued")
        assert len(queued) == 0
        synced = queue_svc.list_packets(status_filter="synced")
        assert len(synced) == 1


class TestStatusChanges:
    def test_mark_syncing(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        p = queue_svc.create_packet(data)
        queue_svc.mark_syncing(p["packet_id"])
        updated = queue_svc.get_packet(p["packet_id"])
        assert updated["status"] == SyncStatus.syncing.value

    def test_mark_synced_records_incident_id(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        p = queue_svc.create_packet(data)
        queue_svc.mark_synced(p["packet_id"], "RSN-000001")
        updated = queue_svc.get_packet(p["packet_id"])
        assert updated["status"] == SyncStatus.synced.value
        assert updated["incident_id"] == "RSN-000001"
        assert updated["synced_at"] is not None

    def test_mark_failed_increments_attempt_count(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        p = queue_svc.create_packet(data)
        queue_svc.mark_failed(p["packet_id"], "Connection refused")
        updated = queue_svc.get_packet(p["packet_id"])
        assert updated["status"] == SyncStatus.failed.value
        assert updated["attempt_count"] == 1
        assert updated["last_error"] == "Connection refused"

    def test_pending_packets_include_queued_and_failed(self):
        data = EdgePacketCreate(
            description="Test", people_affected=1, latitude=24.0, longitude=67.0
        )
        p1 = queue_svc.create_packet(data)  # queued
        p2 = queue_svc.create_packet(data)
        queue_svc.mark_failed(p2["packet_id"], "error")  # failed
        p3 = queue_svc.create_packet(data)
        queue_svc.mark_synced(p3["packet_id"], "RSN-1")  # synced — should be excluded

        pending = queue_svc.get_pending_packets()
        pending_ids = [p["packet_id"] for p in pending]
        assert p1["packet_id"] in pending_ids
        assert p2["packet_id"] in pending_ids
        assert p3["packet_id"] not in pending_ids


class TestPersistence:
    def test_packets_survive_db_reopen(self, tmp_path):
        """Simulate restart by reinitializing the DB connection."""
        from app import config
        import app.database as db_mod

        db_path = tmp_path / "persist_test.db"
        db_mod.DATABASE_PATH = db_path
        db_mod.DATA_DIR = tmp_path
        db_mod.init_db()

        data = EdgePacketCreate(
            description="Critical", people_affected=10, latitude=24.0, longitude=67.0
        )
        p = queue_svc.create_packet(data)

        # Simulate restart: re-init DB (same file)
        db_mod.init_db()
        retrieved = queue_svc.get_packet(p["packet_id"])
        assert retrieved is not None
        assert retrieved["description"] == "Critical"

        # Cleanup
        db_mod.DATABASE_PATH = config.DATABASE_PATH
        db_mod.DATA_DIR = config.DATA_DIR
