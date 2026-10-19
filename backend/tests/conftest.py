"""
Pytest configuration and shared fixtures for RescuNet backend tests.

Uses an in-memory SQLite database to keep tests isolated and fast.
"""

import pytest
from fastapi.testclient import TestClient

import app.database as db_module
from app.main import app


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """
    Point the database to a temporary file per test so each test
    starts with a clean schema and no data leaks between tests.
    """
    test_db_path = tmp_path / "test_rescunet.db"
    monkeypatch.setattr(db_module, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(db_module, "DATABASE_DIR", tmp_path)
    db_module.init_db()
    yield


@pytest.fixture()
def client():
    """Return a FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture()
def isolated_resources(tmp_path, monkeypatch):
    """Point the resource database at a temp file seeded with the defaults.

    Tests that exercise matching/planning must not depend on the mutable
    shared resource database in data/resources.db.
    """
    import agent.resource_db as resource_db

    monkeypatch.setattr(resource_db, "DATABASE_PATH", tmp_path / "resources.db")
    monkeypatch.setattr(resource_db, "DATABASE_DIR", tmp_path)
    resource_db.init_resource_db()
    return resource_db
