"""
Approval service for RescuNet response plans.

Handles the human approval workflow:
1. Validate incident exists and is analyzable
2. Validate resource exists and is available
3. Create response plan
4. Assign resource
5. Update incident status

This service does NOT perform real dispatch.
All actions are application-internal.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.response_plan import (
    ApprovalRequest,
    ApprovalResponse,
    ResponsePlanResource,
    ResponsePlanStatus,
)

logger = logging.getLogger(__name__)


class StaleRecommendationError(Exception):
    """Raised when approval is attempted against a superseded recommendation.

    The plan module maintains versioned proposals; approving the legacy
    recommendation while a newer proposal is open would silently overwrite
    the newer decision, so it is refused with 409 instead.
    """

    def __init__(self, plan_id: str, version: int):
        super().__init__(
            f"A newer recommendation (plan {plan_id}, version {version}) is "
            "pending review. Approve that proposal instead of the older "
            "recommendation."
        )
        self.plan_id = plan_id
        self.version = version


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_plan_id(conn) -> str:
    """Generate the next sequential plan ID (PLN-000001).

    Uses the highest existing suffix rather than a row count so deleted rows
    can never cause a duplicate id.
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(plan_id, 5) AS INTEGER)), 0) AS max_id "
        "FROM response_plans"
    ).fetchone()
    return f"PLN-{int(row['max_id']) + 1:06d}"


def approve_recommendation(
    incident_id: str, request: ApprovalRequest
) -> Optional[ApprovalResponse]:
    """Approve an AI recommendation and create a response plan.

    This is the core approval workflow. It validates all preconditions,
    creates a response plan, assigns the resource (simulated dispatch),
    and updates the incident to DISPATCHED.

    Args:
        incident_id: The incident to approve a response for
        request: The approval request with resource_id, distance, reason

    Returns:
        ApprovalResponse on success, or None if validation fails
    """
    with get_db() as conn:
        # 1. Verify incident exists
        incident = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        if not incident:
            logger.warning("Approval failed: incident %s not found", incident_id)
            return None

        # Stale guard: never let an older recommendation overwrite a newer proposal
        open_plan = conn.execute(
            """
            SELECT plan_id, version FROM rescue_plans
            WHERE incident_id = ? AND status IN ('proposed', 'pending_approval')
            ORDER BY version DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        if open_plan:
            logger.warning(
                "Approval blocked for %s: newer proposal %s v%s is pending",
                incident_id,
                open_plan["plan_id"],
                open_plan["version"],
            )
            raise StaleRecommendationError(open_plan["plan_id"], open_plan["version"])

        # 2. Check if a response plan already exists (idempotent)
        existing_plan = conn.execute(
            "SELECT * FROM response_plans WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        if existing_plan:
            # Return existing plan (idempotent behavior)
            return ApprovalResponse(
                incident_id=incident_id,
                status=ResponsePlanStatus.dispatched.value,
                resource=ResponsePlanResource(
                    id=existing_plan["resource_id"],
                    name=existing_plan["resource_name"],
                    type=existing_plan["resource_type"],
                    status="deployed",
                ),
                distance_km=existing_plan["distance_km"],
                message="Response already dispatched for this incident.",
                real_world_dispatch=False,
            )

        # 3. Verify resource exists in the resource database
        resource = _get_resource(request.resource_id)
        if not resource:
            logger.warning(
                "Approval failed: resource %s not found", request.resource_id
            )
            return None

        # 4. Verify resource is available
        if resource["status"] != "available":
            logger.warning(
                "Approval failed: resource %s is %s",
                request.resource_id,
                resource["status"],
            )
            return None

        # 5. Create response plan (status: dispatched — the plan is active)
        now = _now_iso()
        plan_id = _generate_plan_id(conn)

        conn.execute(
            """
            INSERT INTO response_plans
                (plan_id, incident_id, resource_id, resource_name, resource_type,
                 distance_km, reason, status, approved_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                incident_id,
                resource["resource_id"],
                resource["name"],
                resource["type"],
                request.distance_km,
                request.reason,
                ResponsePlanStatus.dispatched.value,
                now,
                now,
            ),
        )

        # 6. Update incident status to DISPATCHED
        conn.execute(
            "UPDATE incidents SET status = 'dispatched', updated_at = ? WHERE incident_id = ?",
            (now, incident_id),
        )

        # 7. Deploy the resource — change status to 'deployed' and assign incident
        from agent.resource_db import update_resource_status

        conn.commit()  # commit incident + plan first
        update_resource_status(
            request.resource_id, "deployed", assigned_incident_id=incident_id
        )

        # Record the approved assignment in the versioned plan history + audit
        # trail (opened on its own connection, after our writes are committed).
        from app.services.plan_service import record_approved_assignment

        plan_id = record_approved_assignment(
            incident_id=incident_id,
            resource=resource,
            distance_km=request.distance_km,
            reason=request.reason,
            approver=(request.approver or "operator").strip() or "operator",
        )

        logger.info(
            "Response plan %s created for incident %s, resource %s deployed",
            plan_id,
            incident_id,
            resource["resource_id"],
        )

        return ApprovalResponse(
            incident_id=incident_id,
            status=ResponsePlanStatus.dispatched.value,
            resource=ResponsePlanResource(
                id=resource["resource_id"],
                name=resource["name"],
                type=resource["type"],
                status="deployed",
            ),
            distance_km=request.distance_km,
            message="Response approved and dispatch initiated. No real-world dispatch was performed.",
            real_world_dispatch=False,
        )


def get_response_plan(incident_id: str) -> Optional[dict]:
    """Retrieve the response plan for an incident, if one exists."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM response_plans WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None


def _get_resource(resource_id: str) -> Optional[dict]:
    """Retrieve a resource from the resource database."""
    from agent.resource_db import get_resource_db, init_resource_db

    init_resource_db()
    with get_resource_db() as conn:
        row = conn.execute(
            "SELECT * FROM resources WHERE resource_id = ?", (resource_id,)
        ).fetchone()
        if row:
            resource = dict(row)
            resource["equipment"] = json.loads(resource["equipment"])
            return resource
        return None
