"""
Incident service layer.

Handles all database operations for incidents. This keeps route handlers
thin and business logic testable independently.
"""

from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.incident import IncidentCreate, IncidentStatus, IncidentUpdate


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_incident_id(conn) -> str:
    """Generate the next sequential incident ID (RSN-000001).

    Uses the highest existing numeric suffix rather than a row count so
    deleted rows can never cause a duplicate id.
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(incident_id, 5) AS INTEGER)), 0) AS max_id "
        "FROM incidents"
    ).fetchone()
    return f"RSN-{int(row['max_id']) + 1:06d}"


def create_incident(data: IncidentCreate) -> dict:
    """Create a new incident and return it as a dict.

    If a packet_id is provided and already exists, returns the existing
    incident instead of creating a duplicate (idempotent behavior).
    """
    with get_db() as conn:
        # Idempotency check: if packet_id already exists, return existing
        if data.packet_id:
            existing = conn.execute(
                "SELECT * FROM incidents WHERE packet_id = ?", (data.packet_id,)
            ).fetchone()
            if existing:
                return dict(existing)

        incident_id = _generate_incident_id(conn)
        now = _now_iso()

        conn.execute(
            """
            INSERT INTO incidents (incident_id, description, people_affected,
                                   latitude, longitude, status, packet_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                data.description,
                data.people_affected,
                data.latitude,
                data.longitude,
                IncidentStatus.queued.value,
                data.packet_id,
                now,
                now,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return dict(row)


def get_all_incidents() -> list[dict]:
    """Return all incidents ordered by creation time (newest first)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_incident(incident_id: str) -> Optional[dict]:
    """Return a single incident by ID, or None if not found."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ? OR packet_id = ?",
            (incident_id, incident_id),
        ).fetchone()
        return dict(row) if row else None


def update_incident_status(incident_id: str, data: IncidentUpdate) -> Optional[dict]:
    """Update an incident's status. Returns the updated incident or None."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        if not existing:
            return None

        now = _now_iso()
        conn.execute(
            "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?",
            (data.status.value, now, incident_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return dict(row)
