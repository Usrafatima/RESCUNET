"""
RescuNet Edge Gateway — Configuration.

All configurable values are read from environment variables with sensible defaults.
"""

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "edge_queue.db"

# Backend connectivity
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Edge gateway server
EDGE_PORT: int = int(os.getenv("EDGE_PORT", "8001"))

# Sync settings
SYNC_MAX_ATTEMPTS: int = int(os.getenv("SYNC_MAX_ATTEMPTS", "5"))
SYNC_TIMEOUT_SECONDS: float = float(os.getenv("SYNC_TIMEOUT_SECONDS", "10.0"))

# Bounded retry: wait at least this many seconds (doubled per attempt, capped
# at SYNC_BACKOFF_MAX_SECONDS) before retrying a packet that just failed.
# Set to 0 to retry immediately on the next sync request.
SYNC_RETRY_BACKOFF_SECONDS: float = float(os.getenv("SYNC_RETRY_BACKOFF_SECONDS", "2.0"))
SYNC_BACKOFF_MAX_SECONDS: float = float(os.getenv("SYNC_BACKOFF_MAX_SECONDS", "60.0"))

# Health probe of the central backend used by /edge/status
BACKEND_HEALTH_TIMEOUT_SECONDS: float = float(os.getenv("BACKEND_HEALTH_TIMEOUT_SECONDS", "2.0"))
