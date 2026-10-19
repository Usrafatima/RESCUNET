"""
RescuNet SQLite database layer.

Uses Python's built-in sqlite3 module — no external database required.
The database file is stored at data/rescunet.db relative to the project root.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Resolve the database path: data/rescunet.db relative to the project root
# (two levels up from backend/app/database.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATABASE_DIR / "rescunet.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    people_affected INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    packet_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS response_plans (
    plan_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL UNIQUE,
    resource_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    distance_km REAL NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    approved_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    restriction_reason TEXT,
    scope_resource_id TEXT,
    from_lat REAL NOT NULL,
    from_lng REAL NOT NULL,
    to_lat REAL NOT NULL,
    to_lng REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_triage (
    incident_id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'rules',
    triage_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS rescue_plans (
    plan_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    trigger TEXT NOT NULL DEFAULT 'initial',
    trigger_detail TEXT,
    previous_plan_id TEXT,
    resource_id TEXT,
    resource_name TEXT,
    resource_type TEXT,
    distance_km REAL,
    requires_human_review INTEGER NOT NULL DEFAULT 0,
    assignment_json TEXT NOT NULL,
    triage_json TEXT,
    context_json TEXT,
    rationale TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_reason TEXT,
    UNIQUE (incident_id, version),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT,
    plan_id TEXT,
    event_type TEXT NOT NULL,
    detail TEXT,
    actor TEXT,
    created_at TEXT NOT NULL
);
"""


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db():
    """Context manager that yields a database connection and ensures cleanup."""
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()
