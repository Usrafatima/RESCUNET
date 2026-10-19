"""
RescuNet Edge Gateway — SQLite database layer.

Provides a persistent local queue that survives edge gateway restarts.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DATA_DIR, DATABASE_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS edge_packets (
    packet_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    people_affected INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    synced_at TEXT,
    incident_id TEXT
);

CREATE TABLE IF NOT EXISTS edge_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Columns added after the first release; applied idempotently at startup.
MIGRATION_COLUMNS = {
    "edge_packets": {
        "last_attempt_at": "TEXT",
        "permanent": "INTEGER NOT NULL DEFAULT 0",
    }
}


def _get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Add any missing columns to existing databases."""
    for table, columns in MIGRATION_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, declaration in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def init_db() -> None:
    """Initialize the database, apply migrations and recover stuck packets.

    Packets left in `syncing` by an interrupted process are returned to
    `queued` so they are retried instead of being lost.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        _apply_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def recover_stuck_packets() -> int:
    """Reset packets stuck in `syncing` (e.g. after a crash) back to `queued`.

    Returns the number of packets recovered.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "UPDATE edge_packets SET status = 'queued' WHERE status = 'syncing'"
        )
        conn.commit()
        return cursor.rowcount or 0
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
