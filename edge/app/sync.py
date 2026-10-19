"""
RescuNet Edge Gateway — Synchronization engine.

Sends queued/failed edge packets to the FastAPI backend when online.
Handles retries and idempotency via the packet_id field.
"""

import logging
import threading
from dataclasses import dataclass

import httpx

from app import config
from app.config import BACKEND_URL, SYNC_MAX_ATTEMPTS, SYNC_TIMEOUT_SECONDS
from app.models import SyncStatus
from app import queue as queue_svc

logger = logging.getLogger("rescunet.edge.sync")

# One sync run at a time: concurrent runs would risk double-submitting the
# same packet (the backend is idempotent on packet_id, but there is no reason
# to rely on that).
_sync_lock = threading.Lock()

# HTTP status codes that are worth retrying even though they are 4xx.
RETRYABLE_CLIENT_ERRORS = {408, 425, 429}


@dataclass
class SyncResult:
    """Result of a single packet sync attempt."""

    packet_id: str
    success: bool
    incident_id: str | None = None
    error: str | None = None
    skipped: bool = False


def _backoff_seconds(attempt_count: int) -> float:
    """Bounded exponential backoff for a packet that already failed N times."""
    base = config.SYNC_RETRY_BACKOFF_SECONDS
    if base <= 0:
        return 0.0
    return min(base * (2 ** max(0, attempt_count - 1)), config.SYNC_BACKOFF_MAX_SECONDS)


def _in_backoff_window(packet: dict) -> bool:
    """True when a failed packet must wait before its next attempt."""
    if not packet.get("attempt_count") or not packet.get("last_attempt_at"):
        return False
    wait = _backoff_seconds(packet["attempt_count"])
    if wait <= 0:
        return False
    try:
        from datetime import datetime, timezone

        last = datetime.fromisoformat(packet["last_attempt_at"].replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < wait
    except (ValueError, AttributeError):  # pragma: no cover - defensive
        return False


def sync_packet(packet: dict) -> SyncResult:
    """
    Attempt to sync a single packet to the backend.

    Returns a SyncResult indicating success or failure.
    """
    packet_id = packet["packet_id"]

    # Skip if already exceeded max attempts (for FAILED packets)
    if (
        packet["status"] == SyncStatus.failed.value
        and packet["attempt_count"] >= SYNC_MAX_ATTEMPTS
    ):
        logger.warning(
            "Skipping %s: max attempts (%d) reached",
            packet_id,
            SYNC_MAX_ATTEMPTS,
        )
        return SyncResult(
            packet_id=packet_id,
            success=False,
            error=f"Max attempts ({SYNC_MAX_ATTEMPTS}) reached",
        )

    # Bounded retry: do not hammer the backend for a packet that just failed.
    if _in_backoff_window(packet):
        wait = _backoff_seconds(packet["attempt_count"])
        logger.info(
            "Skipping %s for now: retry backoff (%.1fs) still active",
            packet_id,
            wait,
        )
        return SyncResult(
            packet_id=packet_id,
            success=False,
            skipped=True,
            error=f"Retry backoff active; retry in ~{wait:.0f}s",
        )

    # Mark as syncing
    queue_svc.mark_syncing(packet_id)

    # Build the payload for the backend. `packet_id` is sent every time: the
    # backend is idempotent on it, so a retried request cannot create a
    # duplicate incident.
    payload = {
        "description": packet["description"],
        "people_affected": packet["people_affected"],
        "latitude": packet["latitude"],
        "longitude": packet["longitude"],
        "packet_id": packet_id,
    }

    try:
        with httpx.Client(timeout=SYNC_TIMEOUT_SECONDS) as client:
            response = client.post(f"{BACKEND_URL}/api/incidents", json=payload)
            response.raise_for_status()

            data = response.json()
            incident_id = data.get("incident_id")
            if not incident_id:
                raise ValueError("Backend response did not include an incident_id")

            queue_svc.mark_synced(packet_id, incident_id)
            logger.info("Synced %s → %s", packet_id, incident_id)

            return SyncResult(
                packet_id=packet_id,
                success=True,
                incident_id=incident_id,
            )

    except httpx.HTTPStatusError as exc:
        # A 4xx (validation) will not fix itself: mark permanent so it is
        # surfaced instead of retried forever. 5xx and rate limits are
        # transient.
        code = exc.response.status_code
        permanent = 400 <= code < 500 and code not in RETRYABLE_CLIENT_ERRORS
        error_msg = f"Backend rejected the packet (HTTP {code})"
        queue_svc.mark_failed(packet_id, error_msg, permanent=permanent)
        logger.error(
            "Sync failed for %s: %s%s",
            packet_id,
            error_msg,
            " [permanent]" if permanent else " [will retry]",
        )
        return SyncResult(packet_id=packet_id, success=False, error=error_msg)

    except httpx.HTTPError as exc:
        # Timeouts / connection errors: the backend is unreachable or slow.
        error_msg = f"Backend unreachable: {type(exc).__name__}: {exc}"
        queue_svc.mark_failed(packet_id, error_msg)
        logger.error("Sync failed for %s: %s [will retry]", packet_id, error_msg)
        return SyncResult(packet_id=packet_id, success=False, error=error_msg)

    except Exception as exc:
        error_msg = str(exc)
        queue_svc.mark_failed(packet_id, error_msg)
        logger.error("Sync failed for %s: %s [will retry]", packet_id, error_msg)

        return SyncResult(
            packet_id=packet_id,
            success=False,
            error=error_msg,
        )


def sync_all_pending() -> list[SyncResult] | None:
    """
    Sync all pending (QUEUED or transiently FAILED) packets to the backend.

    Continues processing remaining packets even if one fails.
    Returns a list of SyncResult for each attempted packet, or None when a
    sync run is already in progress (single-flight guard).
    """
    if not _sync_lock.acquire(blocking=False):
        logger.warning("Sync already in progress — request ignored")
        return None

    try:
        packets = queue_svc.get_pending_packets()
        results: list[SyncResult] = []

        if not packets:
            logger.info("No pending packets to sync")
            return results

        logger.info("Starting sync of %d pending packet(s)", len(packets))

        for packet in packets:
            result = sync_packet(packet)
            results.append(result)

        succeeded = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        logger.info(
            "Sync complete: %d succeeded, %d failed, %d skipped out of %d total",
            succeeded,
            failed,
            skipped,
            len(results),
        )

        return results
    finally:
        _sync_lock.release()
