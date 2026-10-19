"""
Pytest configuration and shared fixtures for edge gateway tests.

Uses a temporary SQLite database and a controllable connectivity state.
"""

import pytest
from fastapi.testclient import TestClient

import app.database as db_module
from app.main import app, _connectivity_state


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the edge database to a temporary file per test."""
    test_db_path = tmp_path / "test_edge_queue.db"
    monkeypatch.setattr(db_module, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(db_module, "DATA_DIR", tmp_path)
    db_module.init_db()
    yield


@pytest.fixture(autouse=True)
def _reset_connectivity():
    """Reset connectivity to OFFLINE before each test."""
    _connectivity_state["online"] = False
    yield


@pytest.fixture()
def client():
    """Return a FastAPI TestClient for the edge gateway."""
    return TestClient(app)


@pytest.fixture()
def sample_packet():
    """Return a valid SOS packet payload."""
    return {
        "description": "Building fire on 5th floor, people trapped",
        "people_affected": 8,
        "latitude": 24.8607,
        "longitude": 67.0011,
    }
