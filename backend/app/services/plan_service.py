"""
Adaptive rescue planning service for RescuNet.

Responsibilities
----------------
1. Generate a *proposal* (versioned rescue plan) for an incident from triage
   + deterministic resource matching.
2. Snapshot the conditions the proposal was based on, then detect when those
   conditions change (route closed, resource unavailable, urgency rose,
   incident changed, capability lost) — that is the replanning trigger set.
3. Approve / reject proposals with an audit trail and a stale-proposal guard
   so an older recommendation can never silently overwrite a newer decision.

Safety properties
-----------------
- Nothing is ever dispatched automatically: an approved plan is required to
  create or change an assignment.
- Proposals are never applied to real assignments on their own.
- When matching cannot produce a safe assignment the proposal is marked
  `requires_human_review` with explicit shortages instead of inventing one.
- Every state change writes an `audit_events` row.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.plans import (
    DetectedChange,
    MatchResult,
    PlanAssignmentView,
    PlanStatus,
    PlanTrigger,
    ReplanReport,
    RescuePlan,
    TriageResult,
)
from app.services import matching_service, route_service, triage_service

logger = logging.getLogger(__name__)

# Incident statuses considered active for planning purposes.
ACTIVE_INCIDENT_STATUSES = ("queued", "processing", "awaiting_approval", "dispatched")

# Plan statuses that are still open for a decision.
OPEN_PLAN_STATUSES = (PlanStatus.proposed.value, PlanStatus.pending_approval.value)

# Fields in the stored context that, when changed, trigger a reassessment.
CONTEXT_TRIGGERS = {
    "resource_status": PlanTrigger.resource_unavailable,
    "resource_assignment": PlanTrigger.resource_unavailable,
    "blocked_route_ids": PlanTrigger.route_closed,
    "urgency_level": PlanTrigger.incident_changed,
    "people_affected": PlanTrigger.incident_changed,
    "incident_status": PlanTrigger.incident_changed,
    "capability_ok": PlanTrigger.resource_unsuitable,
}

# Human-readable change descriptions.
CONTEXT_LABELS = {
    "resource_status": "Assigned resource status changed",
    "resource_assignment": "Assigned resource is now committed elsewhere",
    "blocked_route_ids": "A route restriction now blocks the assignment",
    "urgency_level": "Reported urgency changed",
    "people_affected": "Reported number of people affected changed",
    "incident_status": "Incident status changed",
    "capability_ok": "Assigned resource no longer satisfies the capability requirement",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Audit trail ────────────────────────────────────────────────────────────


def record_audit(
    conn,
    incident_id: Optional[str],
    plan_id: Optional[str],
    event_type: str,
    detail: dict | str,
    actor: Optional[str] = None,
) -> None:
    """Append one immutable audit event (uses the caller's connection)."""
    conn.execute(
        """
        INSERT INTO audit_events (incident_id, plan_id, event_type, detail, actor, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            plan_id,
            event_type,
            json.dumps(detail) if not isinstance(detail, str) else detail,
            actor,
            _now_iso(),
        ),
    )


def get_audit_trail(incident_id: str) -> list[dict]:
    """Audit events for an incident, oldest first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE incident_id = ? ORDER BY event_id ASC",
            (incident_id,),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["detail"] = json.loads(item["detail"])
            except (TypeError, ValueError):
                pass
            out.append(item)
        return out


# ─── Small helpers ──────────────────────────────────────────────────────────


def _get_incident(incident_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None


def _get_resource(resource_id: str) -> Optional[dict]:
    from agent.resource_db import get_all_resources

    for resource in get_all_resources():
        if resource["resource_id"] == resource_id:
            return resource
    return None


def _next_version(conn, incident_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM rescue_plans WHERE incident_id = ?",
        (incident_id,),
    ).fetchone()
    return int(row["v"]) + 1


def _next_plan_id(conn) -> str:
    """Next plan id (RPL-000001), safe even if older plans were deleted."""
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(plan_id, 5) AS INTEGER)), 0) AS max_id "
        "FROM rescue_plans"
    ).fetchone()
    return f"RPL-{int(row['max_id']) + 1:06d}"


def _capability_ok(resource: dict, incident_type: str) -> bool:
    required = matching_service.required_capabilities(incident_type)
    ok, _ = matching_service._capability_match(required, resource.get("equipment") or [])
    return ok


def build_context(
    incident: dict,
    triage: TriageResult,
    resource_id: Optional[str],
) -> dict:
    """Snapshot the conditions a plan/proposal is based on.

    This snapshot is later diffed against current reality to detect that a
    reassessment is required.
    """
    resource = _get_resource(resource_id) if resource_id else None
    blocked_route_ids: list[str] = []
    resource_status = "missing"
    resource_assignment: Optional[str] = None
    capability_ok = False

    if resource:
        resource_status = resource.get("status", "missing")
        resource_assignment = resource.get("assigned_incident_id")
        capability_ok = _capability_ok(resource, triage.incident_type)
        blocked_route_ids = [
            r["route_id"] for r in route_service.blocked_routes_for(resource, incident)
        ]

    return {
        "incident_id": incident.get("incident_id"),
        "incident_status": incident.get("status"),
        "incident_type": triage.incident_type,
        "urgency_level": triage.urgency_level,
        "people_affected": incident.get("people_affected"),
        "resource_id": resource_id,
        "resource_status": resource_status,
        "resource_assignment": resource_assignment,
        "capability_ok": capability_ok,
        "blocked_route_ids": blocked_route_ids,
    }


def diff_context(previous: dict, current: dict) -> list[dict]:
    """Return the changes between a stored context and current reality."""
    changes: list[dict] = []
    for field, trigger in CONTEXT_TRIGGERS.items():
        before = previous.get(field)
        after = current.get(field)
        if field == "blocked_route_ids":
            before = sorted(before or [])
            after = sorted(after or [])
        if before == after:
            continue

        # A resource still being deployed for *this* incident is not a change.
        if field == "resource_status" and before == "available" and after == "deployed":
            continue
        if (
            field == "resource_assignment"
            and before in (None, current.get("incident_id"))
            and after in (None, current.get("incident_id"))
        ):
            continue

        changes.append(
            {
                "field": field,
                "trigger": trigger,
                "previous": before,
                "current": after,
                "detail": (
                    f"{CONTEXT_LABELS[field]}: "
                    f"{_fmt(before)} → {_fmt(after)}"
                ),
            }
        )
    return changes


def _fmt(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "none"
    if value is None:
        return "none"
    return str(value)


def _describe_routes(route_ids: list[str]) -> str:
    """Human-readable route references (id + name + reason when closed)."""
    from app.services import route_service as _routes

    parts: list[str] = []
    for route_id in route_ids:
        route = _routes.get_route(route_id)
        if route:
            reason = route.get("restriction_reason")
            suffix = f" ({reason})" if reason else ""
            parts.append(f"{route_id} '{route['name']}'{suffix}")
        else:  # pragma: no cover - defensive
            parts.append(route_id)
    return ", ".join(parts)


# ─── Rationale text ─────────────────────────────────────────────────────────


def _build_rationale(
    trigger: PlanTrigger,
    trigger_detail: Optional[str],
    match: MatchResult,
    triage: TriageResult,
    previous: Optional[dict],
) -> str:
    best = match.best
    parts: list[str] = []

    if trigger == PlanTrigger.initial or trigger == PlanTrigger.manual:
        parts.append(
            f"New plan for a {triage.urgency_level}-urgency "
            f"{triage.incident_type} incident (urgency rules {triage.criteria_version})."
        )
    else:
        parts.append(f"Reassessment triggered by: {trigger_detail or trigger.value}.")

    if previous and previous.get("resource_id"):
        if best and previous.get("resource_id") != best.resource_id:
            parts.append(
                f"The previous assignment ({previous.get('resource_name') or previous.get('resource_id')}) "
                "is no longer feasible, so a different resource is proposed."
            )
        elif not best:
            parts.append(
                f"The previous assignment ({previous.get('resource_name') or previous.get('resource_id')}) "
                "can no longer be made safely."
            )

    if best:
        parts.append(
            f"Proposed: {best.name} ({best.resource_id}, {best.type}) — "
            f"{best.distance_km:.2f} km, match score {best.match_score:.1f}/100. "
            + " ".join(best.reasons[:3])
        )
        if len(match.candidates) > 1:
            alts = [c for c in match.candidates if c.feasible and c.resource_id != best.resource_id]
            if alts:
                parts.append(
                    "Alternative feasible option(s): "
                    + "; ".join(f"{c.name} ({c.resource_id})" for c in alts[:3])
                    + "."
                )
    else:
        parts.append(
            "No resource satisfies every hard constraint, so no automatic "
            "assignment is proposed."
        )
        parts.extend(match.shortages)

    if match.requires_human_review:
        parts.extend(match.review_reasons)

    parts.append("Human approval is required before any dispatch or re-assignment.")
    return " ".join(parts)


# ─── Proposal generation ────────────────────────────────────────────────────


def _insert_plan(
    conn,
    incident: dict,
    triage: TriageResult,
    match: MatchResult,
    trigger: PlanTrigger,
    trigger_detail: Optional[str],
    previous_plan: Optional[dict],
    actor: str,
) -> dict:
    version = _next_version(conn, incident["incident_id"])
    plan_id = _next_plan_id(conn)

    best = match.best
    resource = _get_resource(best.resource_id) if best else None
    # The context records the conditions of THIS plan's own assignment, so
    # later evaluations can tell whether the plan is still applicable.
    context = build_context(
        incident, triage, resource["resource_id"] if resource else None
    )

    rationale = _build_rationale(
        trigger, trigger_detail, match, triage, previous_plan
    )

    assignment = PlanAssignmentView(
        resource_id=best.resource_id if best else None,
        resource_name=best.name if best else None,
        resource_type=best.type if best else None,
        distance_km=best.distance_km if best else None,
        match_score=best.match_score if best else None,
        requires_human_review=match.requires_human_review,
    )

    now = _now_iso()
    conn.execute(
        """
        INSERT INTO rescue_plans
            (plan_id, incident_id, version, status, trigger, trigger_detail,
             previous_plan_id, resource_id, resource_name, resource_type,
             distance_km, requires_human_review, assignment_json, triage_json,
             context_json, rationale, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            plan_id,
            incident["incident_id"],
            version,
            PlanStatus.pending_approval.value,
            trigger.value,
            trigger_detail,
            previous_plan["plan_id"] if previous_plan else None,
            best.resource_id if best else None,
            best.name if best else None,
            best.type if best else None,
            best.distance_km if best else None,
            1 if match.requires_human_review else 0,
            match.model_dump_json(),
            triage.model_dump_json(),
            json.dumps(context),
            rationale,
            actor,
            now,
        ),
    )

    # Move the incident into the approval step of its lifecycle.
    if incident.get("status") in ("queued", "processing"):
        conn.execute(
            "UPDATE incidents SET status = 'awaiting_approval', updated_at = ? "
            "WHERE incident_id = ?",
            (now, incident["incident_id"]),
        )

    record_audit(
        conn,
        incident["incident_id"],
        plan_id,
        "plan_proposed",
        {
            "version": version,
            "trigger": trigger.value,
            "trigger_detail": trigger_detail,
            "resource_id": best.resource_id if best else None,
            "requires_human_review": match.requires_human_review,
            "rationale": rationale,
        },
        actor,
    )
    return {"plan_id": plan_id, "version": version}


def generate_proposal(
    incident_id: str,
    trigger: PlanTrigger = PlanTrigger.manual,
    trigger_detail: Optional[str] = None,
    actor: str = "system",
) -> RescuePlan:
    """Create a new plan proposal for one incident."""
    incident = _get_incident(incident_id)
    if incident is None:
        raise LookupError(f"incident '{incident_id}' not found")

    triage = triage_service.get_triage(incident)
    match = matching_service.match_resources(incident, triage.incident_type)

    with get_db() as conn:
        previous = conn.execute(
            """
            SELECT * FROM rescue_plans WHERE incident_id = ?
            ORDER BY version DESC LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
        previous_plan = dict(previous) if previous else None

        created = _insert_plan(
            conn, incident, triage, match, trigger, trigger_detail, previous_plan, actor
        )
        conn.commit()

    plan = get_plan(created["plan_id"])
    if plan is None:  # pragma: no cover - defensive
        raise LookupError(f"plan '{created['plan_id']}' could not be reloaded")
    return plan


def get_plan(plan_id: str) -> Optional[RescuePlan]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rescue_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        return _row_to_plan(dict(row)) if row else None


def list_plans(
    incident_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[RescuePlan]:
    query = "SELECT * FROM rescue_plans"
    clauses: list[str] = []
    params: list = []
    if incident_id:
        clauses.append("incident_id = ?")
        params.append(incident_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY incident_id ASC, version DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
        return [_row_to_plan(dict(r)) for r in rows]


def _row_to_plan(row: dict) -> RescuePlan:
    match = MatchResult(**json.loads(row["assignment_json"]))
    triage = (
        TriageResult(**json.loads(row["triage_json"])) if row.get("triage_json") else None
    )
    best = match.best
    alternatives = [
        c for c in match.candidates if c.feasible and (not best or c.resource_id != best.resource_id)
    ][:3]
    return RescuePlan(
        plan_id=row["plan_id"],
        incident_id=row["incident_id"],
        version=row["version"],
        status=PlanStatus(row["status"]),
        trigger=PlanTrigger(row["trigger"]),
        trigger_detail=row.get("trigger_detail"),
        previous_plan_id=row.get("previous_plan_id"),
        assignment=PlanAssignmentView(
            resource_id=row.get("resource_id"),
            resource_name=row.get("resource_name"),
            resource_type=row.get("resource_type"),
            distance_km=row.get("distance_km"),
            match_score=best.match_score if best and best.resource_id == row.get("resource_id") else None,
            requires_human_review=bool(row.get("requires_human_review")),
        ),
        rationale=row.get("rationale", ""),
        alternatives=alternatives,
        shortages=match.shortages,
        review_reasons=match.review_reasons,
        triage=triage,
        match=match,
        created_by=row.get("created_by", "system"),
        created_at=row.get("created_at", ""),
        decided_at=row.get("decided_at"),
        decided_by=row.get("decided_by"),
        decision_reason=row.get("decision_reason"),
    )


# ─── Decision: approve / reject ─────────────────────────────────────────────


class PlanConflict(Exception):
    """Raised when a plan decision violates a workflow constraint."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def approve_proposal(
    plan_id: str,
    approver: str,
    decision_reason: Optional[str] = None,
) -> dict:
    """Approve a proposal and create/update the assignment for its incident.

    Returns the same payload shape as the legacy approval endpoint so the
    existing frontend contract keeps working.

    Raises PlanConflict when the proposal is stale, already decided, or the
    target resource is no longer available.
    """
    if not approver or not approver.strip():
        raise PlanConflict("approver must be a non-empty name", status_code=422)

    released: Optional[str] = None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rescue_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise PlanConflict(f"plan '{plan_id}' not found", status_code=404)
        plan = dict(row)

        if plan["status"] not in OPEN_PLAN_STATUSES:
            raise PlanConflict(
                f"plan {plan_id} is '{plan['status']}' — only open proposals "
                "can be approved"
            )

        # Stale guard: an older proposal must never overwrite a newer decision.
        latest = _next_version(conn, plan["incident_id"]) - 1
        if plan["version"] != latest:
            raise PlanConflict(
                f"stale recommendation: plan {plan_id} is version {plan['version']} "
                f"but version {latest} is current. Regenerate the plan."
            )

        if not plan["resource_id"]:
            raise PlanConflict(
                "this proposal has no safe assignment — human review required "
                "before it can be approved",
                status_code=422,
            )

        resource = _get_resource(plan["resource_id"])
        if not resource:
            raise PlanConflict(
                f"resource '{plan['resource_id']}' no longer exists", status_code=409
            )
        if resource["status"] not in ("available",):
            # Deployed *for this same incident* is idempotent; anything else blocks.
            if not (
                resource["status"] == "deployed"
                and resource.get("assigned_incident_id") == plan["incident_id"]
            ):
                raise PlanConflict(
                    f"resource '{plan['resource_id']}' is "
                    f"'{resource['status']}' — it cannot be assigned"
                )

        incident = _get_incident(plan["incident_id"])
        if not incident:
            raise PlanConflict(f"incident '{plan['incident_id']}' not found", 404)

        now = _now_iso()

        # ── Update or create the response plan (one active assignment per incident)
        existing = conn.execute(
            "SELECT * FROM response_plans WHERE incident_id = ?",
            (plan["incident_id"],),
        ).fetchone()
        previous_resource_id = None
        if existing:
            existing = dict(existing)
            previous_resource_id = existing["resource_id"]
            if previous_resource_id != plan["resource_id"]:
                conn.execute(
                    """
                    UPDATE response_plans
                    SET resource_id = ?, resource_name = ?, resource_type = ?,
                        distance_km = ?, reason = ?, status = 'dispatched',
                        approved_at = ?
                    WHERE incident_id = ?
                    """,
                    (
                        plan["resource_id"],
                        plan["resource_name"],
                        plan["resource_type"],
                        plan["distance_km"] or 0.0,
                        plan["rationale"],
                        now,
                        plan["incident_id"],
                    ),
                )
            else:
                conn.execute(
                    "UPDATE response_plans SET approved_at = ?, reason = ? "
                    "WHERE incident_id = ?",
                    (now, plan["rationale"], plan["incident_id"]),
                )
        else:
            plan_row = conn.execute(
                "SELECT COALESCE(MAX(CAST(substr(plan_id, 5) AS INTEGER)), 0) AS max_id "
                "FROM response_plans"
            ).fetchone()
            conn.execute(
                """
                INSERT INTO response_plans
                    (plan_id, incident_id, resource_id, resource_name, resource_type,
                     distance_km, reason, status, approved_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'dispatched', ?, ?)
                """,
                (
                    f"PLN-{int(plan_row['max_id']) + 1:06d}",
                    plan["incident_id"],
                    plan["resource_id"],
                    plan["resource_name"],
                    plan["resource_type"],
                    plan["distance_km"] or 0.0,
                    plan["rationale"],
                    now,
                    now,
                ),
            )

        # ── Incident lifecycle
        conn.execute(
            "UPDATE incidents SET status = 'dispatched', updated_at = ? "
            "WHERE incident_id = ?",
            (now, plan["incident_id"]),
        )

        # ── Plan bookkeeping
        conn.execute(
            """
            UPDATE rescue_plans
            SET status = 'approved', decided_at = ?, decided_by = ?,
                decision_reason = ?, context_json = ?
            WHERE plan_id = ?
            """,
            (
                now,
                approver,
                decision_reason,
                json.dumps(
                    build_context(incident, _triage_from_row(plan), plan["resource_id"])
                ),
                plan_id,
            ),
        )
        conn.execute(
            """
            UPDATE rescue_plans SET status = 'superseded'
            WHERE incident_id = ? AND plan_id != ? AND status IN (?, ?)
            """,
            (
                plan["incident_id"],
                plan_id,
                PlanStatus.proposed.value,
                PlanStatus.pending_approval.value,
            ),
        )

        # ── Release a previously assigned resource (re-assignment case)
        if previous_resource_id and previous_resource_id != plan["resource_id"]:
            from agent.resource_db import update_resource_status

            update_resource_status(previous_resource_id, "available", None)
            released = previous_resource_id

        record_audit(
            conn,
            plan["incident_id"],
            plan_id,
            "plan_approved",
            {
                "version": plan["version"],
                "approver": approver,
                "decision_reason": decision_reason,
                "resource_id": plan["resource_id"],
                "previous_resource_id": previous_resource_id,
                "reassigned": bool(
                    previous_resource_id and previous_resource_id != plan["resource_id"]
                ),
                "real_world_dispatch": False,
            },
            approver,
        )
        conn.commit()

    # ── Deploy the assigned resource (outside the incident transaction)
    from agent.resource_db import update_resource_status

    update_resource_status(plan["resource_id"], "deployed", plan["incident_id"])

    logger.info(
        "Plan %s v%s approved by %s → resource %s deployed for %s",
        plan_id,
        plan["version"],
        approver,
        plan["resource_id"],
        plan["incident_id"],
    )

    return {
        "incident_id": plan["incident_id"],
        "status": "dispatched",
        "resource": {
            "id": plan["resource_id"],
            "name": plan["resource_name"],
            "type": plan["resource_type"],
            "status": "deployed",
        },
        "distance_km": plan["distance_km"] or 0.0,
        "message": (
            f"Plan {plan_id} v{plan['version']} approved by {approver}. "
            "Response approved and dispatch initiated. No real-world dispatch "
            "was performed."
        ),
        "real_world_dispatch": False,
        "plan_id": plan_id,
        "version": plan["version"],
        "released_resource_id": released,
    }


def _triage_from_row(plan_row: dict) -> TriageResult:
    if plan_row.get("triage_json"):
        return TriageResult(**json.loads(plan_row["triage_json"]))
    incident = _get_incident(plan_row["incident_id"])
    return triage_service.build_triage(incident or {"incident_id": plan_row["incident_id"], "description": "", "people_affected": 1, "latitude": 0, "longitude": 0})


def reject_proposal(
    plan_id: str,
    approver: str,
    decision_reason: Optional[str] = None,
) -> RescuePlan:
    """Reject a proposal. No assignment changes; nothing is dispatched."""
    if not approver or not approver.strip():
        raise PlanConflict("approver must be a non-empty name", status_code=422)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rescue_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise PlanConflict(f"plan '{plan_id}' not found", status_code=404)
        plan = dict(row)
        if plan["status"] not in OPEN_PLAN_STATUSES:
            raise PlanConflict(f"plan {plan_id} is '{plan['status']}' — not open")

        now = _now_iso()
        conn.execute(
            """
            UPDATE rescue_plans
            SET status = 'rejected', decided_at = ?, decided_by = ?, decision_reason = ?
            WHERE plan_id = ?
            """,
            (now, approver, decision_reason, plan_id),
        )
        record_audit(
            conn,
            plan["incident_id"],
            plan_id,
            "plan_rejected",
            {"version": plan["version"], "approver": approver, "reason": decision_reason},
            approver,
        )
        conn.commit()

    result = get_plan(plan_id)
    assert result is not None
    return result


# ─── Trigger evaluation / replanning ────────────────────────────────────────


def evaluate_triggers(actor: str = "system", dry_run: bool = False) -> ReplanReport:
    """Evaluate all replanning triggers and act on them.

    For every active assignment (approved plan) the stored context is diffed
    against current reality. A detected change produces a *new proposal* —
    never an automatic re-assignment. Open proposals whose own context no
    longer matches reality are marked `stale` so they cannot be approved.

    High-urgency incidents that have never been planned are picked up here
    as trigger `new_high_urgency`.

    With `dry_run=True` nothing is written: the report only describes what
    would happen.
    """
    changes: list[DetectedChange] = []
    proposed: list[str] = []
    stale: list[str] = []
    evaluated = 0

    with get_db() as conn:
        incident_rows = conn.execute(
            "SELECT * FROM incidents WHERE status IN ({})".format(
                ",".join("?" for _ in ACTIVE_INCIDENT_STATUSES)
            ),
            ACTIVE_INCIDENT_STATUSES,
        ).fetchall()
        incidents = [dict(r) for r in incident_rows]

        plan_rows = conn.execute("SELECT * FROM rescue_plans").fetchall()
        plans = [dict(r) for r in plan_rows]

    by_incident: dict[str, list[dict]] = {}
    for plan in plans:
        by_incident.setdefault(plan["incident_id"], []).append(plan)

    for incident in incidents:
        incident_id = incident["incident_id"]
        incident_plans = sorted(
            by_incident.get(incident_id, []), key=lambda p: p["version"]
        )
        triage = triage_service.get_triage(incident)

        approved = [p for p in incident_plans if p["status"] == PlanStatus.approved.value]
        open_plans = [p for p in incident_plans if p["status"] in OPEN_PLAN_STATUSES]
        latest_approved = approved[-1] if approved else None

        if latest_approved:
            evaluated += 1
            stored_context = json.loads(latest_approved.get("context_json") or "{}")
            current_context = build_context(
                incident, triage, stored_context.get("resource_id")
            )
            diff = diff_context(stored_context, current_context)
            if diff:
                # First: stale-check open proposals against their OWN resource.
                still_open: list[dict] = []
                for open_plan in open_plans:
                    open_ctx = json.loads(open_plan.get("context_json") or "{}")
                    open_current = build_context(
                        incident, triage, open_ctx.get("resource_id")
                    )
                    if diff_context(open_ctx, open_current):
                        if not dry_run:
                            _mark_stale(open_plan, actor, "conditions changed")
                        stale.append(open_plan["plan_id"])
                    else:
                        still_open.append(open_plan)

                # Only propose when no still-open proposal already covers this
                # revision — repeated evaluations must not stack proposals.
                covered = any(
                    p["version"] > latest_approved["version"] for p in still_open
                )
                if not covered:
                    change_details: list[str] = []
                    for d in diff:
                        detail_text = d["detail"]
                        if d["field"] == "blocked_route_ids":
                            added = sorted(set(d["current"]) - set(d["previous"]))
                            removed = sorted(set(d["previous"]) - set(d["current"]))
                            parts: list[str] = []
                            if added:
                                parts.append(
                                    "closed route(s) now block the assignment: "
                                    + _describe_routes(added)
                                )
                            if removed:
                                parts.append(
                                    "no longer blocked by: " + _describe_routes(removed)
                                )
                            detail_text = "Route restrictions changed: " + "; ".join(parts)
                        change_details.append(detail_text)
                        changes.append(
                            DetectedChange(
                                incident_id=incident_id,
                                plan_id=latest_approved["plan_id"],
                                trigger=d["trigger"],
                                field=d["field"],
                                previous=_fmt(d["previous"]),
                                current=_fmt(d["current"]),
                                detail=detail_text,
                            )
                        )
                    trigger = diff[0]["trigger"]
                    detail = "; ".join(change_details)
                    if not dry_run:
                        created = _generate_proposal_row(
                            incident, triage, trigger, detail, latest_approved, actor
                        )
                        proposed.append(created)

        elif not incident_plans:
            # No plan at all: pick it up when it is high urgency.
            if triage.urgency_level in ("critical", "high"):
                if incident.get("status") not in ("resolved", "cancelled"):
                    evaluated += 1
                    changes.append(
                        DetectedChange(
                            incident_id=incident_id,
                            plan_id="",
                            trigger=PlanTrigger.new_high_urgency,
                            field="urgency_level",
                            previous="",
                            current=triage.urgency_level,
                            detail=(
                                f"New high-urgency incident ({triage.urgency_level}) "
                                f"with no response plan yet."
                            ),
                        )
                    )
                    if not dry_run:
                        created = _generate_proposal_row(
                            incident,
                            triage,
                            PlanTrigger.new_high_urgency,
                            f"Urgency {triage.urgency_level} on arrival",
                            None,
                            actor,
                        )
                        proposed.append(created)

        else:
            # Open proposals (no approved assignment): stale-check them.
            current_context = build_context(
                incident, triage, incident_plans[-1].get("resource_id")
            )
            for open_plan in open_plans:
                open_ctx = json.loads(open_plan.get("context_json") or "{}")
                if diff_context(open_ctx, current_context):
                    if not dry_run:
                        _mark_stale(open_plan, actor, "conditions changed")
                    stale.append(open_plan["plan_id"])
                    if not dry_run:
                        created = _generate_proposal_row(
                            incident,
                            triage,
                            PlanTrigger.incident_changed,
                            "Conditions changed while the proposal was pending review",
                            open_plan,
                            actor,
                        )
                        proposed.append(created)

    # Unresolved incidents: active, no approved assignment, no safe candidate.
    unresolved: list[str] = []
    for incident in incidents:
        incident_id = incident["incident_id"]
        incident_plans = by_incident.get(incident_id, [])
        has_approved = any(
            p["status"] == PlanStatus.approved.value for p in incident_plans
        )
        if has_approved:
            continue
        triage = triage_service.get_triage(incident)
        match = matching_service.match_resources(incident, triage.incident_type)
        open_plans = [p for p in incident_plans if p["status"] in OPEN_PLAN_STATUSES]
        covers = any(
            p.get("resource_id") for p in open_plans
        ) and not any(
            p.get("requires_human_review") for p in open_plans
        )
        if match.best is None or not covers:
            unresolved.append(incident_id)

    if proposed:
        message = (
            f"Detected {len(changes)} change(s); proposed {len(proposed)} revised "
            f"plan(s); marked {len(stale)} stale; {len(unresolved)} unresolved."
        )
    elif changes:
        message = f"Detected {len(changes)} change(s); no new proposal needed."
    else:
        message = "No replanning triggers detected."

    return ReplanReport(
        changes=changes,
        plans_proposed=proposed,
        stale_plans=stale,
        unresolved_incidents=unresolved,
        evaluated_assignments=evaluated,
        message=message,
        generated_at=_now_iso(),
    )


def _mark_stale(plan: dict, actor: str, reason: str) -> None:
    """Mark an open proposal stale so it can no longer be approved."""
    with get_db() as conn:
        conn.execute(
            "UPDATE rescue_plans SET status = 'stale' WHERE plan_id = ?",
            (plan["plan_id"],),
        )
        record_audit(
            conn,
            plan["incident_id"],
            plan["plan_id"],
            "plan_stale",
            {"reason": reason, "version": plan["version"]},
            actor,
        )
        conn.commit()


def _generate_proposal_row(
    incident: dict,
    triage: TriageResult,
    trigger: PlanTrigger,
    trigger_detail: Optional[str],
    previous_plan: Optional[dict],
    actor: str,
) -> str:
    """Create a proposal on its own connection (used by trigger evaluation)."""
    with get_db() as conn:
        match = matching_service.match_resources(incident, triage.incident_type)
        created = _insert_plan(
            conn, incident, triage, match, trigger, trigger_detail, previous_plan, actor
        )
        conn.commit()
    return created["plan_id"]


# ─── Reacting to route / resource changes ───────────────────────────────────


def on_new_incident(incident: dict, actor: str = "system") -> Optional[str]:
    """Handle a newly arrived incident.

    Generates a proposal only when the reported urgency is high or critical —
    a new high-urgency incident is one of the documented replanning triggers.
    Returns the proposal id, or None.
    """
    triage = triage_service.get_triage(incident)
    if triage.urgency_level not in ("critical", "high"):
        return None
    plan = generate_proposal(
        incident["incident_id"],
        trigger=PlanTrigger.new_high_urgency,
        trigger_detail=f"Urgency {triage.urgency_level} on arrival",
        actor=actor,
    )
    return plan.plan_id


def record_approved_assignment(
    incident_id: str,
    resource: dict,
    distance_km: float,
    reason: str,
    approver: str,
    trigger: PlanTrigger = PlanTrigger.initial,
) -> Optional[str]:
    """Record a human-approved assignment as a versioned rescue plan.

    Used by the legacy approval endpoint so every assignment — whichever
    endpoint created it — is tracked in the plan history and audit trail.

    Must be called AFTER the caller has committed its own writes (it opens
    its own connection).
    """
    incident = _get_incident(incident_id)
    if incident is None:  # pragma: no cover - defensive
        return None

    triage = triage_service.get_triage(incident)
    match = matching_service.match_resources(incident, triage.incident_type)

    with get_db() as conn:
        previous = conn.execute(
            "SELECT plan_id FROM rescue_plans WHERE incident_id = ? "
            "ORDER BY version DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        version = _next_version(conn, incident_id)
        plan_id = _next_plan_id(conn)

        context = build_context(incident, triage, resource["resource_id"])
        # The caller deploys the resource immediately after this returns.
        context["resource_status"] = "deployed"
        context["resource_assignment"] = incident_id
        context["incident_status"] = "dispatched"

        best_view = PlanAssignmentView(
            resource_id=resource["resource_id"],
            resource_name=resource.get("name"),
            resource_type=resource.get("type"),
            distance_km=round(distance_km, 2),
            match_score=match.best.match_score if match.best else None,
            requires_human_review=False,
        )
        rationale = (
            f"{reason} Assignment approved by {approver} via the approval workflow. "
            "Human approval received; no real-world dispatch was performed."
        )
        now = _now_iso()

        conn.execute(
            """
            INSERT INTO rescue_plans
                (plan_id, incident_id, version, status, trigger, trigger_detail,
                 previous_plan_id, resource_id, resource_name, resource_type,
                 distance_km, requires_human_review, assignment_json, triage_json,
                 context_json, rationale, created_by, created_at,
                 decided_at, decided_by, decision_reason)
            VALUES (?, ?, ?, 'approved', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                incident_id,
                version,
                trigger.value,
                "Approved through the existing approval workflow",
                previous["plan_id"] if previous else None,
                resource["resource_id"],
                resource.get("name"),
                resource.get("type"),
                round(distance_km, 2),
                match.model_dump_json(),
                triage.model_dump_json(),
                json.dumps(context),
                rationale,
                approver,
                now,
                now,
                approver,
                reason,
            ),
        )
        record_audit(
            conn,
            incident_id,
            plan_id,
            "legacy_approval",
            {
                "version": version,
                "resource_id": resource["resource_id"],
                "reason": reason,
                "approver": approver,
                "real_world_dispatch": False,
            },
            approver,
        )
        conn.commit()

    return plan_id
