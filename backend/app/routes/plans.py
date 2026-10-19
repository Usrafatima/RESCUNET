"""
FastAPI route handlers for RescuNet Adaptive Rescue Planning.

GET  /api/plans                          — list plan proposals (filterable)
GET  /api/plans/{plan_id}                — one plan
POST /api/incidents/{id}/plan            — generate a proposal
POST /api/plans/{id}/approve             — approve a proposal (human)
POST /api/plans/{id}/reject              — reject a proposal (human)
GET  /api/incidents/{id}/plans           — plan history for an incident
GET  /api/incidents/{id}/audit           — audit trail for an incident
GET  /api/incidents/{id}/triage          — deterministic triage
POST /api/incidents/{id}/triage          — recompute triage (+AI if configured)
POST /api/replan                         — evaluate triggers, propose revisions
GET  /api/replan/changes                 — evaluate triggers without changing data
GET  /api/replan/triggers                — documented trigger definitions
GET  /api/routes                         — routes/corridors (map + constraints)
POST /api/routes                         — create a route
PATCH /api/routes/{route_id}             — open/close a route → triggers replan
PATCH /api/resources/{resource_id}/status — change availability → triggers replan

No endpoint ever dispatches anything: approvals create application-internal
assignments only, and every decision is written to the audit trail.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.models.plans import (
    PlanCreateRequest,
    PlanDecisionRequest,
    PlanListResponse,
    PlanTrigger,
    ReplanReport,
    RescuePlan,
    RouteCreate,
    RouteStatusResponse,
    RouteUpdate,
    TriageResult,
)
from app.services import (
    matching_service,
    plan_service,
    route_service,
    triage_service,
)
from app.services.plan_service import PlanConflict
from app.services.recommendation_service import _haversine_km

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["plans"])


def _conflict(exc: PlanConflict) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _require_incident(incident_id: str) -> dict:
    incident = plan_service._get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return incident


# ─── Plans ──────────────────────────────────────────────────────────────────


@router.get("/plans", response_model=PlanListResponse, summary="List rescue plans")
def list_plans_endpoint(
    incident_id: str | None = Query(default=None),
    plan_status: str | None = Query(
        default=None,
        alias="status",
        description="proposed | pending_approval | approved | rejected | superseded | stale",
    ),
):
    """List versioned rescue plans, newest version first."""
    plans = plan_service.list_plans(incident_id=incident_id, status=plan_status)
    return PlanListResponse(plans=plans, total=len(plans))


@router.get("/plans/{plan_id}", response_model=RescuePlan, summary="Get one plan")
def get_plan_endpoint(plan_id: str):
    plan = plan_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found",
        )
    return plan


@router.post(
    "/incidents/{incident_id}/plan",
    response_model=RescuePlan,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a rescue plan proposal",
)
def create_plan_endpoint(incident_id: str, request: PlanCreateRequest | None = None):
    """Generate a proposal for one incident.

    The proposal is *not* applied — it requires human approval.
    """
    _require_incident(incident_id)
    request = request or PlanCreateRequest()
    try:
        return plan_service.generate_proposal(
            incident_id,
            trigger=request.trigger or PlanTrigger.manual,
            actor=(request.actor or "operator"),
        )
    except LookupError as exc:  # pragma: no cover - guarded above
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/plans/{plan_id}/approve",
    summary="Approve a rescue plan proposal",
    response_description="Assignment created/updated after human approval",
)
def approve_plan_endpoint(plan_id: str, request: PlanDecisionRequest):
    """Approve a proposal after human review.

    - 404 when the plan does not exist
    - 409 when the proposal is stale, already decided, or the resource is gone
    - 422 when the proposal has no safe assignment (human review required)

    Approving changes application state only — no real dispatch occurs.
    """
    try:
        result = plan_service.approve_proposal(
            plan_id,
            approver=request.approver,
            decision_reason=request.decision_reason,
        )
    except PlanConflict as exc:
        raise _conflict(exc)
    return result


@router.post("/plans/{plan_id}/reject", response_model=RescuePlan, summary="Reject a proposal")
def reject_plan_endpoint(plan_id: str, request: PlanDecisionRequest):
    """Reject a proposal. Nothing is assigned and nothing is dispatched."""
    try:
        return plan_service.reject_proposal(
            plan_id,
            approver=request.approver,
            decision_reason=request.decision_reason,
        )
    except PlanConflict as exc:
        raise _conflict(exc)


@router.get(
    "/incidents/{incident_id}/plans",
    response_model=PlanListResponse,
    summary="Plan history for an incident",
)
def incident_plans_endpoint(incident_id: str):
    _require_incident(incident_id)
    plans = plan_service.list_plans(incident_id=incident_id)
    return PlanListResponse(plans=plans, total=len(plans))


@router.get(
    "/incidents/{incident_id}/audit",
    summary="Audit trail for an incident",
    response_description="Append-only list of plan/approval events",
)
def audit_endpoint(incident_id: str):
    _require_incident(incident_id)
    events = plan_service.get_audit_trail(incident_id)
    return {"incident_id": incident_id, "events": events, "total": len(events)}


# ─── Triage ─────────────────────────────────────────────────────────────────


@router.get(
    "/incidents/{incident_id}/triage",
    response_model=TriageResult,
    summary="Triage an incident",
)
def get_triage_endpoint(incident_id: str, ai: bool = Query(default=False)):
    """Deterministic triage with the documented urgency criteria.

    Set `ai=true` to also use the configured LLM for free-text interpretation
    (only when an API key is configured; the LLM can never lower the urgency
    level assigned by the rules).
    """
    incident = _require_incident(incident_id)
    return triage_service.get_triage(incident, use_ai=ai)


@router.post(
    "/incidents/{incident_id}/triage",
    response_model=TriageResult,
    summary="Recompute triage (optionally with AI interpretation)",
)
def refresh_triage_endpoint(incident_id: str, ai: bool = Query(default=False)):
    """Recompute triage. Pass `ai=true` to also request LLM interpretation."""
    incident = _require_incident(incident_id)
    return triage_service.get_triage(incident, use_ai=ai, refresh_ai=True)


# ─── Replanning ─────────────────────────────────────────────────────────────


@router.post("/replan", response_model=ReplanReport, summary="Evaluate replanning triggers")
def replan_endpoint(actor: str = Query(default="operator")):
    """Evaluate every replanning trigger and propose revised plans.

    Detected changes produce *proposals*; nothing is re-assigned or
    dispatched without a human approval.
    """
    return plan_service.evaluate_triggers(actor=actor)


@router.get(
    "/replan/changes",
    response_model=ReplanReport,
    summary="Detect changes without modifying anything",
)
def replan_changes_endpoint():
    """Dry run: report which assignments would be reassessed right now."""
    return plan_service.evaluate_triggers(actor="system", dry_run=True)


@router.get("/replan/triggers", summary="Documented replanning triggers")
def replan_triggers_endpoint():
    """The fixed, documented trigger set used by the evaluator."""
    return {
        "triggers": [
            {
                "trigger": PlanTrigger.route_closed.value,
                "description": "A road/corridor used by an assignment became unavailable.",
            },
            {
                "trigger": PlanTrigger.resource_unavailable.value,
                "description": "A responder/vehicle became unavailable or was reassigned.",
            },
            {
                "trigger": PlanTrigger.new_high_urgency.value,
                "description": "A new high-urgency incident arrived.",
            },
            {
                "trigger": PlanTrigger.incident_changed.value,
                "description": "Reported circumstances of an incident materially changed.",
            },
            {
                "trigger": PlanTrigger.resource_unsuitable.value,
                "description": "A previously assigned resource no longer satisfies capability requirements.",
            },
        ],
        "policy": (
            "Deterministic rules detect changes and generate proposals. "
            "Human approval is always required before an assignment changes."
        ),
    }


# ─── Routes / corridors ─────────────────────────────────────────────────────


@router.get("/routes", summary="List routes/corridors")
def list_routes_endpoint(status_filter: str | None = Query(default=None, alias="status")):
    """All known routes with their restriction status (used by the map)."""
    routes = route_service.list_routes(status_filter=status_filter)
    return {
        "routes": [route_service._row_to_info(r).model_dump() for r in routes],
        "total": len(routes),
    }


@router.post(
    "/routes",
    response_model=RouteStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a route/corridor",
)
def create_route_endpoint(data: RouteCreate):
    route = route_service.create_route(data)
    return RouteStatusResponse(
        route=route_service._row_to_info(route),
        message=f"Route '{route['name']}' created with status {route['status']}.",
    )


@router.patch(
    "/routes/{route_id}",
    response_model=RouteStatusResponse,
    summary="Open or close a route (triggers reassessment)",
)
def update_route_endpoint(route_id: str, data: RouteUpdate):
    """Change a route's restriction status.

    Closing a route immediately evaluates all active assignments: affected
    ones get a new *proposal* (never an automatic re-assignment).
    """
    route = route_service.update_route(route_id, data)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found",
        )

    report: ReplanReport | None = None
    if data.status.value == "closed":
        report = plan_service.evaluate_triggers(
            actor=(data.actor or "operator")
        )

    affected = [c.incident_id for c in (report.changes if report else [])]
    return RouteStatusResponse(
        route=route_service._row_to_info(route),
        message=(
            f"Route '{route['name']}' is now {route['status']}. "
            + (
                f"{len(affected)} assignment(s) affected."
                if report and affected
                else "No assignments were affected."
            )
        ),
        affected_assignments=sorted(set(affected)),
        plans_proposed=report.plans_proposed if report else [],
    )


# ─── Resource availability ──────────────────────────────────────────────────


@router.patch(
    "/resources/{resource_id}/status",
    summary="Change a responder/resource status (triggers reassessment)",
)
def update_resource_status_endpoint(
    resource_id: str,
    status_value: str = Query(..., alias="status", pattern="^(available|deployed|unavailable)$"),
    actor: str = Query(default="operator"),
    assigned_incident_id: str | None = Query(default=None),
):
    """Mark a resource available/deployed/unavailable.

    Making an assigned resource unavailable evaluates active assignments and
    proposes revisions for the ones that are now infeasible.
    """
    from agent.resource_db import get_all_resources, update_resource_status

    known = {r["resource_id"] for r in get_all_resources()}
    if resource_id not in known:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource '{resource_id}' not found",
        )

    update_resource_status(resource_id, status_value, assigned_incident_id)
    report = plan_service.evaluate_triggers(actor=actor)
    return {
        "resource_id": resource_id,
        "status": status_value,
        "replan": report,
    }
