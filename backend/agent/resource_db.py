"""
Community resources database for RescuNet.

Stores available responders/resources that the agent can match
to incidents. Uses local SQLite persistence for resource tracking.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Database path: data/resources.db relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATABASE_DIR / "resources.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    assigned_incident_id TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    equipment TEXT NOT NULL DEFAULT '[]',
    max_people INTEGER NOT NULL DEFAULT 10,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Seed data: community responders for demo
SEED_RESOURCES = [
    {
        "resource_id": "RES-001",
        "name": "Medical Team Alpha",
        "type": "medical",
        "status": "available",
        "latitude": 24.8615,
        "longitude": 67.0020,
        "equipment": ["oxygen", "first_aid", "insulin", "defibrillator"],
        "max_people": 5,
    },
    {
        "resource_id": "RES-002",
        "name": "Rescue Team Bravo",
        "type": "rescue",
        "status": "available",
        "latitude": 24.8590,
        "longitude": 67.0035,
        "equipment": ["extraction_gear", "ropes", "flashlights", "stretchers"],
        "max_people": 8,
    },
    {
        "resource_id": "RES-003",
        "name": "Supply Team Charlie",
        "type": "supplies",
        "status": "available",
        "latitude": 24.8625,
        "longitude": 67.0005,
        "equipment": ["water", "food", "blankets", "tarps"],
        "max_people": 20,
    },
    {
        "resource_id": "RES-004",
        "name": "Fire Response Delta",
        "type": "fire",
        "status": "available",
        "latitude": 24.8580,
        "longitude": 67.0050,
        "equipment": ["extinguishers", "hoses", "protective_gear"],
        "max_people": 6,
    },
    {
        "resource_id": "RES-005",
        "name": "Shelter Team Echo",
        "type": "shelter",
        "status": "available",
        "latitude": 24.8635,
        "longitude": 67.0025,
        "equipment": ["tents", "mattresses", "hygiene_kits"],
        "max_people": 50,
    },
]


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row factory."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_resource_db() -> None:
    """Initialize the resources database and seed if empty."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        conn.executescript(SCHEMA_SQL)

        # Migration: add assigned_incident_id column if missing
        cols = [row[1] for row in conn.execute("PRAGMA table_info(resources)").fetchall()]
        if "assigned_incident_id" not in cols:
            conn.execute("ALTER TABLE resources ADD COLUMN assigned_incident_id TEXT")
            conn.commit()

        # Seed if empty
        count = conn.execute("SELECT COUNT(*) as count FROM resources").fetchone()["count"]
        if count == 0:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            for resource in SEED_RESOURCES:
                conn.execute(
                    """
                    INSERT INTO resources (resource_id, name, type, status,
                                          latitude, longitude, equipment, max_people,
                                          created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resource["resource_id"],
                        resource["name"],
                        resource["type"],
                        resource["status"],
                        resource["latitude"],
                        resource["longitude"],
                        json.dumps(resource["equipment"]),
                        resource["max_people"],
                        now,
                        now,
                    ),
                )
            conn.commit()
    finally:
        conn.close()


@contextmanager
def get_resource_db():
    """Context manager for resource database connection."""
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()


def update_resource_status(
    resource_id: str, status: str, assigned_incident_id: str | None = None
) -> bool:
    """Update a resource's status and optionally assign it to an incident.

    Args:
        resource_id: The resource to update (e.g. RES-001)
        status: New status (available, deployed, unavailable)
        assigned_incident_id: If deploying, the incident this resource is assigned to

    Returns:
        True if the resource was updated, False if not found
    """
    from datetime import datetime, timezone

    conn = _get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE resources SET status = ?, assigned_incident_id = ?, updated_at = ? WHERE resource_id = ?",
            (status, assigned_incident_id, now, resource_id),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_all_resources() -> list[dict]:
    """Return all resources with their current status."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM resources ORDER BY resource_id").fetchall()
        resources = []
        for row in rows:
            resource = dict(row)
            resource["equipment"] = json.loads(resource["equipment"])
            resources.append(resource)
        return resources
    finally:
        conn.close()

