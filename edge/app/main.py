"""
RescuNet Edge Gateway — FastAPI Application Entry Point.

A lightweight local ingestion + queue + synchronization layer for
emergency incident packets. Runs on port 8001 by default.

Run with:
    uvicorn app.main:app --reload --port 8001
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app import queue as queue_svc
from app.config import EDGE_PORT
from app.database import init_db
from app.models import (
    ConnectivityResponse,
    ConnectivityUpdate,
    EdgePacketCreate,
    EdgePacketDetail,
    EdgePacketResponse,
    SyncStatus,
)
from app.sync import sync_all_pending

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("rescunet.edge")


# --- In-memory connectivity state ---
_connectivity_state: dict = {"online": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup.

    - Creates/extends the local schema.
    - Restores the persisted ONLINE/OFFLINE mode (explicit states survive a
      restart, defaulting to OFFLINE).
    - Returns packets stuck in `syncing` (interrupted process) to `queued`.
    """
    init_db()
    from app import database as db_module

    recovered = db_module.recover_stuck_packets()
    if recovered:
        logger.warning("Recovered %d packet(s) stuck in 'syncing'", recovered)

    stored = queue_svc.get_state(queue_svc.STATE_CONNECTIVITY)
    _connectivity_state["online"] = stored == "true"
    logger.info(
        "Edge gateway database initialized (mode=%s)",
        "ONLINE" if _connectivity_state["online"] else "OFFLINE",
    )
    yield


app = FastAPI(
    title="RescuNet Edge Gateway",
    description=(
        "Lightweight local emergency packet ingestion, queue management, "
        "and synchronization layer for the RescuNet edge system."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for local Next.js frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoint 1: Receive local SOS ───────────────────────────────────────────

@app.post(
    "/edge/incidents",
    response_model=EdgePacketResponse,
    status_code=201,
    tags=["edge"],
    summary="Receive a local SOS emergency packet",
)
def receive_sos(data: EdgePacketCreate):
    """
    Accept an emergency SOS packet and store it in the local queue.

    The packet persists in SQLite and will be synchronized to the
    backend when connectivity is restored.
    """
    packet = queue_svc.create_packet(data)
    logger.info(
        "Received SOS packet %s: %s (people_affected=%d)",
        packet["packet_id"],
        data.description[:50],
        data.people_affected,
    )
    return EdgePacketResponse(
        packet_id=packet["packet_id"],
        status=SyncStatus.queued,
        message="Emergency packet stored locally",
    )


# ─── Endpoint 2: View queue ──────────────────────────────────────────────────

@app.get(
    "/edge/queue",
    response_model=list[EdgePacketDetail],
    tags=["edge"],
    summary="View the local packet queue",
)
def view_queue(status: Optional[str] = Query(None, description="Filter by sync status")):
    """
    Return all queued/syncing/failed/synced packets.
    Optionally filter by status.
    """
    packets = queue_svc.list_packets(status_filter=status)
    return packets


# ─── Endpoint 3: Connectivity status ─────────────────────────────────────────

@app.get(
    "/edge/connectivity",
    response_model=ConnectivityResponse,
    tags=["edge"],
    summary="Check connectivity status",
)
def get_connectivity():
    """
    Return the current connectivity mode and number of queued packets.
    """
    mode = "ONLINE" if _connectivity_state["online"] else "OFFLINE"
    return ConnectivityResponse(
        online=_connectivity_state["online"],
        mode=mode,
        queued_packets=queue_svc.get_queued_count(),
    )


# ─── Endpoint 4: Toggle connectivity ─────────────────────────────────────────

@app.post(
    "/edge/connectivity",
    response_model=ConnectivityResponse,
    tags=["edge"],
    summary="Toggle connectivity mode",
)
def set_connectivity(data: ConnectivityUpdate):
    """
    Switch between ONLINE and OFFLINE modes.

    When set to ONLINE, returns info about pending packets that can be synced.
    """
    _connectivity_state["online"] = data.online
    # Persist the explicit mode so it survives a gateway restart.
    queue_svc.set_state(
        queue_svc.STATE_CONNECTIVITY, "true" if data.online else "false"
    )
    mode = "ONLINE" if data.online else "OFFLINE"
    logger.info("Connectivity set to %s", mode)

    return ConnectivityResponse(
        online=data.online,
        mode=mode,
        queued_packets=queue_svc.get_queued_count(),
    )


# ─── Endpoint 5: Trigger synchronization ─────────────────────────────────────

@app.post(
    "/edge/sync",
    tags=["edge"],
    summary="Trigger synchronization of queued packets",
)
def trigger_sync():
    """
    Attempt to sync all pending packets to the backend.

    Only works when connectivity is ONLINE.
    Returns results for each packet attempted.
    """
    if not _connectivity_state["online"]:
        return {
            "message": "Cannot sync: gateway is OFFLINE",
            "synced": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
        }

    results = sync_all_pending()
    if results is None:
        return {
            "message": "Sync already in progress",
            "synced": 0,
            "failed": 0,
            "skipped": 0,
            "already_running": True,
            "results": [],
        }

    synced = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)

    return {
        "message": f"Sync complete: {synced} synced, {failed} failed, {skipped} skipped",
        "synced": synced,
        "failed": failed,
        "skipped": skipped,
        "results": [
            {
                "packet_id": r.packet_id,
                "success": r.success,
                "incident_id": r.incident_id,
                "error": r.error,
                "skipped": r.skipped,
            }
            for r in results
        ],
    }


# ─── Endpoint 6: Detailed gateway status ────────────────────────────────────

_backend_health_cache: dict = {"checked_at": 0.0, "reachable": False}


@app.get(
    "/edge/status",
    tags=["edge"],
    summary="Detailed connectivity and queue status",
)
def edge_status():
    """Operational status of the gateway.

    Includes per-state packet counts, whether the central backend answers
    its health check (only probed while ONLINE, cached briefly), and when the
    last successful sync happened.
    """
    import time

    import httpx

    from app.config import BACKEND_HEALTH_TIMEOUT_SECONDS, BACKEND_URL

    counts = queue_svc.get_status_counts()
    online = _connectivity_state["online"]

    now = time.monotonic()
    if online and (now - _backend_health_cache["checked_at"] > 5.0):
        try:
            httpx.get(
                f"{BACKEND_URL}/health", timeout=BACKEND_HEALTH_TIMEOUT_SECONDS
            ).raise_for_status()
            _backend_health_cache["reachable"] = True
        except Exception as exc:
            _backend_health_cache["reachable"] = False
            logger.info("Backend health probe failed: %s", exc)
        _backend_health_cache["checked_at"] = now

    return {
        "mode": "ONLINE" if online else "OFFLINE",
        "online": online,
        "packets": counts,
        "waiting_to_sync": counts["queued"] + counts["failed_retryable"],
        "backend_url": BACKEND_URL,
        "backend_reachable": (
            _backend_health_cache["reachable"] if online else False
        ),
        "last_synced_at": queue_svc.last_synced_at(),
        "note": (
            "This gateway queues reports locally and forwards them when "
            "online. It does not provide device-to-device mesh networking."
        ),
    }


# ─── Root info ────────────────────────────────────────────────────────────────

@app.get("/", tags=["info"])
def root():
    """Basic edge gateway information."""
    return {
        "name": "RescuNet Edge Gateway",
        "version": "0.1.0",
        "description": "Local emergency packet ingestion and synchronization layer",
        "docs": "/docs",
    }


@app.get("/health", tags=["info"])
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rescunet-edge"}
