"""
FastAPI route handlers for RescuNet incident endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.services import incident_service
from app.services.priority_service import (
    PriorityQueueResponse,
    generate_priority_queue,
    get_incidents_for_priority_queue,
    get_priority_analyses,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new emergency incident",
)
def create_incident(data: IncidentCreate):
    """Submit a new SOS incident report.

    With `auto_plan=true`, a high-urgency report additionally produces a
    rescue-plan proposal (trigger `new_high_urgency`). The proposal is only
    stored for human review — nothing is assigned or dispatched.
    """
    incident = incident_service.create_incident(data)

    if data.auto_plan:
        from app.services import plan_service

        try:
            plan_id = plan_service.on_new_incident(incident, actor="system")
            if plan_id:
                logger.info(
                    "High-urgency incident %s produced proposal %s on arrival",
                    incident["incident_id"],
                    plan_id,
                )
                refreshed = incident_service.get_incident(incident["incident_id"])
                if refreshed:
                    incident = refreshed
        except Exception as exc:  # pragma: no cover - never block SOS ingestion
            logger.error("Auto planning failed for %s: %s", incident["incident_id"], exc)

    return incident


@router.get(
    "",
    response_model=list[IncidentResponse],
    summary="List all incidents",
)
def list_incidents():
    """Retrieve all submitted incidents, ordered by creation time (newest first)."""
    return incident_service.get_all_incidents()


@router.get(
    "/priority-queue",
    response_model=PriorityQueueResponse,
    summary="AI-powered priority queue of active incidents",
    description="Returns all active incidents ranked by a deterministic priority score."
                 " Factors are AI-extracted; the final score uses configurable weights.",
)
def get_priority_queue():
    """Generate a prioritized queue of active emergencies.

    The system:
    1. Fetches all active incidents (queued, processing, awaiting_approval, dispatched)
    2. Uses AI-extracted priority factors when available
    3. Applies configurable scoring weights deterministically
    4. Ranks incidents by final score (highest first)
    5. Checks resource availability for each incident type

    This endpoint does NOT call the LLM on each request.
    AI analyses are generated on-demand via POST /api/agent/analyze-priority/{id}
    and cached for future requests.
    """
    try:
        incidents = get_incidents_for_priority_queue()
        analyses = get_priority_analyses()
        return generate_priority_queue(incidents, analyses)
    except Exception as e:
        logger.error(f"Failed to generate priority queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate priority queue",
        )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get a specific incident",
)
def get_incident(incident_id: str):
    """Retrieve a single incident by its ID. Returns 404 if not found."""
    incident = incident_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return incident


@router.patch(
    "/{incident_id}/status",
    response_model=IncidentResponse,
    summary="Update incident status",
)
def update_incident_status(incident_id: str, data: IncidentUpdate):
    """Update the status of an existing incident. Returns 404 if not found."""
    incident = incident_service.update_incident_status(incident_id, data)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return incident
