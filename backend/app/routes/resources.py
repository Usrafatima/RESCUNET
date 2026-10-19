"""
FastAPI route handler for RescuNet resource endpoints.

GET /api/resources — list all community resources with live status
"""

import logging

from fastapi import APIRouter

from agent.resource_db import get_all_resources, init_resource_db

router = APIRouter(prefix="/api", tags=["resources"])


@router.get(
    "/resources",
    summary="List all community resources",
    response_description="Resources with current deployment status",
)
def list_resources():
    """Return all community resources with their current status.

    Resources reflect real application state — a resource that was
    deployed for an incident will show status='deployed' here.
    """
    init_resource_db()
    return get_all_resources()


@router.post(
    "/resources/reset",
    summary="Reset resources to available for testing",
    response_description="Summary of released resources and restored capacity",
)
@router.post(
    "/resources/reset-test",
    summary="Reset test resources to available (development/testing only)",
    response_description="Summary of released resources and updated assignments",
)
def reset_test_resources_endpoint(
    mode: str = "orphaned",
    resource_id: str | None = None,
    incident_id: str | None = None,
    dry_run: bool = False,
    confirm: bool = False,
    body: dict | None = None,
):
    """Safely reset assigned test resources to 'available'.

    Guarded for local testing/development environments.
    Modes:
      - 'orphaned': Release only orphaned, missing, or mismatched assignments.
      - 'demo': Release [DEMO] incidents and DEMO-* resources.
      - 'targeted': Release specific resource_id or incident_id.
      - 'all': Release all test assignments and restore capacities (requires confirm=True).
    """
    import os
    from fastapi import HTTPException, status
    from app.services.resource_reset_service import reset_test_resources

    # Support optional JSON body override
    if body and isinstance(body, dict):
        if "mode" in body:
            mode = body["mode"]
        if "resource_id" in body:
            resource_id = body["resource_id"]
        if "incident_id" in body:
            incident_id = body["incident_id"]
        if "dry_run" in body:
            dry_run = bool(body["dry_run"])
        if "confirm" in body:
            confirm = bool(body["confirm"])

    # Guard: prevent execution in production unless explicitly enabled
    env = os.getenv("ENVIRONMENT", "development").lower()
    allow_reset = os.getenv("ALLOW_TEST_RESET", "false").lower() == "true"
    if env in ("production", "prod") and not allow_reset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test resource reset endpoint is disabled in production environments.",
        )

    if mode == "all" and not confirm and not dry_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resetting all test resources requires 'confirm=true'.",
        )

    try:
        result = reset_test_resources(
            mode=mode,
            resource_ids=[resource_id] if resource_id else None,
            incident_ids=[incident_id] if incident_id else None,
            dry_run=dry_run,
            actor="test_api_client",
            reason="Reset requested via testing API endpoint",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

