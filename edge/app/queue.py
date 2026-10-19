"""
RescuNet Edge Gateway — Queue management.

Handles all local database operations for edge packets.
"""

from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models import EdgePacketCreate, SyncStatus


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_packet_id(conn) -> str:
    """Generate the next sequential edge packet ID (EDGE-000001).

    Uses the highest existing suffix rather than a row count so deleted
    (or cleaned-up) packets can never cause a duplicate id.
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(packet_id, 6) AS INTEGER)), 0) AS max_id "
        "FROM edge_packets"
    ).fetchone()
    return f"EDGE-{int(row['max_id']) + 1:06d}"


def create_packet(data: EdgePacketCreate) -> dict:
    """Create a new edge packet with status QUEUED and return it."""
    with get_db() as conn:
        packet_id = _generate_packet_id(conn)
        now = _now_iso()

        conn.execute(
            """
            INSERT INTO edge_packets
                (packet_id, description, people_affected, latitude, longitude,
                 created_at, status, attempt_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet_id,
                data.description,
                data.people_affected,
                data.latitude,
                data.longitude,
                now,
                SyncStatus.queued.value,
                0,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM edge_packets WHERE packet_id = ?", (packet_id,)
        ).fetchone()
        return dict(row)


def get_packet(packet_id: str) -> Optional[dict]:
    """Return a single packet by ID, or None if not found."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM edge_packets WHERE packet_id = ?", (packet_id,)
        ).fetchone()
        return dict(row) if row else None


def list_packets(status_filter: Optional[str] = None) -> list[dict]:
    """Return all packets, optionally filtered by status."""
    with get_db() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM edge_packets WHERE status = ? ORDER BY created_at ASC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM edge_packets ORDER BY created_at ASC"
            ).fetchall()
        return [dict(row) for row in rows]


def get_queued_count() -> int:
    """Return the number of packets with status QUEUED."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM edge_packets WHERE status = ?",
            (SyncStatus.queued.value,),
        ).fetchone()
        return row["count"]


def get_status_counts() -> dict[str, int]:
    """Return packet counts per sync state (queued/syncing/synced/failed)."""
    counts = {status.value: 0 for status in SyncStatus}
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM edge_packets GROUP BY status"
        ).fetchall()
        for row in rows:
            counts[row["status"]] = row["c"]
        retryable = conn.execute(
            """
            SELECT COUNT(*) AS c FROM edge_packets
            WHERE status = ? AND COALESCE(permanent, 0) = 0
            """,
            (SyncStatus.failed.value,),
        ).fetchone()["c"]
        permanent = conn.execute(
            """
            SELECT COUNT(*) AS c FROM edge_packets
            WHERE status = ? AND COALESCE(permanent, 0) = 1
            """,
            (SyncStatus.failed.value,),
        ).fetchone()["c"]
    counts["failed_retryable"] = retryable
    counts["failed_permanent"] = permanent
    return counts


def get_pending_packets() -> list[dict]:
    """Return packets that still need syncing.

    Includes QUEUED packets and *transiently* failed ones (under the retry
    budget). Permanently rejected packets are excluded — retrying them would
    never succeed and would mask the validation error.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM edge_packets
            WHERE status IN (?, ?) AND COALESCE(permanent, 0) = 0
            ORDER BY created_at ASC
            """,
            (SyncStatus.queued.value, SyncStatus.failed.value),
        ).fetchall()
        return [dict(row) for row in rows]


def mark_syncing(packet_id: str) -> None:
    """Mark a packet as currently being synced."""
    with get_db() as conn:
        conn.execute(
            "UPDATE edge_packets SET status = ?, last_attempt_at = ? WHERE packet_id = ?",
            (SyncStatus.syncing.value, _now_iso(), packet_id),
        )
        conn.commit()


def mark_synced(packet_id: str, incident_id: str) -> None:
    """Mark a packet as successfully synced to the backend."""
    now = _now_iso()
    with get_db() as conn:
        conn.execute(
            """
            UPDATE edge_packets
            SET status = ?, synced_at = ?, incident_id = ?
            WHERE packet_id = ?
            """,
            (SyncStatus.synced.value, now, incident_id, packet_id),
        )
        conn.commit()


def mark_failed(packet_id: str, error: str, permanent: bool = False) -> None:
    """Mark a packet as failed and record the error.

    Args:
        packet_id: The packet that failed
        error: Human-readable failure reason
        permanent: True when the backend rejected the packet in a way that
                   retrying cannot fix (e.g. validation error). Permanent
                   failures are surfaced for manual handling instead of being
                   retried forever.
    """
    with get_db() as conn:
        conn.execute(
            """
            UPDATE edge_packets
            SET status = ?, attempt_count = attempt_count + 1, last_error = ?,
                last_attempt_at = ?, permanent = ?
            WHERE packet_id = ?
            """,
            (
                SyncStatus.failed.value,
                error,
                _now_iso(),
                1 if permanent else 0,
                packet_id,
            ),
        )
        conn.commit()


def last_synced_at() -> str | None:
    """Timestamp of the most recent successful synchronization, if any."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(synced_at) AS ts FROM edge_packets"
        ).fetchone()
        return row["ts"]


# ─── Gateway state (connectivity mode survives restarts) ───────────────────

STATE_CONNECTIVITY = "connectivity_online"


def get_state(key: str, default: str | None = None) -> str | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM edge_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_state(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO edge_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()
