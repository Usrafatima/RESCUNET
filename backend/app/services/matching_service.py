"""
Resource matching service for RescuNet Adaptive Rescue Planning.

Matches an incident to responder/resource records using HARD constraints
evaluated deterministically:

  H1  Availability  — only resources with status == 'available' can be assigned.
  H2  Capability    — the resource must carry at least one capability required
                      for the incident type (documented capability map).
  H3  Capacity      — the resource must be able to serve the reported number
                      of people (max_people >= people_affected).
  H4  Route limits  — the assignment must not be blocked by a known route
                      restriction (closed corridor / scoped access route).

Every candidate carries plain-language `reasons` (why it is suitable) or
`blockers` (which hard constraint it violated), so a human can audit the
decision. When no safe automatic assignment exists the result is marked
`requires_human_review` with explicit shortage reasons — the service never
invents an assignment.
"""

import logging
from datetime import datetime, timezone

from app.models.plans import MatchCandidate, MatchResult
from app.services import route_service
from app.services.recommendation_service import (
    INCIDENT_CAPABILITY_MAP,
    _calculate_match_score,
    _haversine_km,
    _infer_incident_type,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def required_capabilities(incident_type: str) -> list[str]:
    """Documented capability requirements for an incident type."""
    return list(INCIDENT_CAPABILITY_MAP.get(incident_type, []))


def _capability_match(required: list[str], equipment: list[str]) -> tuple[bool, list[str]]:
    """Return (satisfied, matched_capabilities) using the documented map."""
    if not required:
        return True, []
    equipment_lower = [str(e).lower().replace(" ", "_") for e in equipment]
    matched = [cap for cap in required if any(cap in eq for eq in equipment_lower)]
    return bool(matched), matched


def evaluate_candidate(
    incident: dict,
    resource: dict,
    incident_type: str,
) -> MatchCandidate:
    """Evaluate all hard constraints for one resource against one incident."""
    required = required_capabilities(incident_type)
    equipment = resource.get("equipment") or []
    distance = _haversine_km(
        float(incident["latitude"]),
        float(incident["longitude"]),
        float(resource["latitude"]),
        float(resource["longitude"]),
    )
    score = _calculate_match_score(incident_type, equipment, distance)

    reasons: list[str] = []
    blockers: list[str] = []

    # H1 — availability
    if resource.get("status") == "available":
        reasons.append("Status is 'available' — not currently deployed elsewhere.")
    else:
        blockers.append(
            f"Status is '{resource.get('status')}' — unavailable resources are "
            "never assigned."
        )

    # H2 — capability
    satisfied, matched = _capability_match(required, equipment)
    if required:
        if satisfied:
            reasons.append(
                "Carries required capability for "
                f"{incident_type}: {', '.join(matched)}."
            )
        else:
            blockers.append(
                f"Does not carry any capability required for {incident_type} "
                f"(needs one of: {', '.join(required)}; carries: "
                f"{', '.join(map(str, equipment)) or 'nothing'})."
            )
    else:
        reasons.append(
            "Incident type has no documented capability requirement — "
            "capability match cannot be verified from the report."
        )

    # H3 — capacity
    people = int(incident.get("people_affected") or 1)
    max_people = int(resource.get("max_people") or 0)
    if max_people >= people:
        reasons.append(f"Capacity {max_people} covers the {people} reported people.")
    else:
        blockers.append(
            f"Capacity {max_people} is less than the {people} reported people."
        )

    # H4 — route restrictions
    blocked_routes = route_service.blocked_routes_for(resource, incident)
    if blocked_routes:
        for route in blocked_routes:
            reason = route.get("restriction_reason") or "no reason recorded"
            scope = route.get("scope_resource_id")
            if scope and scope == resource.get("resource_id"):
                blockers.append(
                    f"Access route {route['route_id']} '{route['name']}' is closed "
                    f"({reason}) — it applies specifically to this resource."
                )
            else:
                blockers.append(
                    f"Closed corridor {route['route_id']} '{route['name']}' "
                    f"({reason}) crosses the direct path to this incident."
                )
    else:
        reasons.append("No closed route blocks the direct path to the incident.")

    reasons.append(f"Distance {distance:.2f} km; match score {score:.1f}/100.")

    return MatchCandidate(
        resource_id=resource["resource_id"],
        name=resource.get("name", resource["resource_id"]),
        type=resource.get("type", "other"),
        status=resource.get("status", "unknown"),
        distance_km=round(distance, 2),
        match_score=score,
        feasible=not blockers,
        reasons=reasons,
        blockers=blockers,
        max_people=max_people,
        assigned_incident_id=resource.get("assigned_incident_id"),
    )


def match_resources(incident: dict, incident_type: str | None = None) -> MatchResult:
    """Match an incident against every known resource.

    Args:
        incident: incident row dict
        incident_type: optional pre-computed type (e.g. from triage)

    Returns a MatchResult with feasible candidates ordered best-first,
    rejected candidates with their blockers, shortage notes and — when no
    safe assignment exists — `requires_human_review=True`.
    """
    from agent.resource_db import get_all_resources

    incident_type = incident_type or _infer_incident_type(
        incident.get("description", "")
    )
    required = required_capabilities(incident_type)
    resources = get_all_resources()

    candidates = [
        evaluate_candidate(incident, resource, incident_type)
        for resource in resources
    ]

    feasible = [c for c in candidates if c.feasible]
    infeasible = [c for c in candidates if not c.feasible]
    feasible.sort(key=lambda c: (-c.match_score, c.distance_km, c.resource_id))
    infeasible.sort(key=lambda c: (-c.match_score, c.distance_km, c.resource_id))
    # Candidates are returned best-first: feasible first, then rejected ones.
    candidates = feasible + infeasible

    # Shortage / blocking statistics for transparency
    shortages: list[str] = []
    review_reasons: list[str] = []

    if required:
        capable_and_available = [
            r
            for r in resources
            if r.get("status") == "available"
            and _capability_match(required, r.get("equipment") or [])[0]
        ]
        if not feasible:
            shortages.append(
                f"No resource satisfies all hard constraints for {incident_type} "
                f"({len(infeasible)} of {len(resources)} rejected)."
            )
        deployed_capable = sum(
            1 for r in resources
            if r.get("status") != "available"
            and _capability_match(required, r.get("equipment") or [])[0]
        )
        if deployed_capable:
            shortages.append(
                f"{deployed_capable} capable resource(s) are already deployed "
                "or unavailable."
            )
        route_blocked = sum(
            1 for c in infeasible
            if any("closed" in b.lower() or "route" in b.lower() for b in c.blockers)
        )
        if route_blocked:
            shortages.append(
                f"{route_blocked} candidate(s) rejected because of route restrictions."
            )
        if feasible and not capable_and_available:  # pragma: no cover - defensive
            review_reasons.append(
                "No feasible candidate demonstrably carries a required capability."
            )

    best = feasible[0] if feasible else None

    if best is None:
        review_reasons.append(
            "No safe automatic assignment exists — every candidate violated at "
            "least one hard constraint (availability, capability, capacity or "
            "route restriction)."
        )
    elif incident_type == "other":
        review_reasons.append(
            "Incident type could not be determined from the report, so the "
            "capability match cannot be verified — a human should confirm this "
            "assignment."
        )

    return MatchResult(
        incident_id=incident["incident_id"],
        incident_type=incident_type,
        required_capabilities=required,
        candidates=candidates,
        best=best,
        requires_human_review=bool(review_reasons),
        review_reasons=review_reasons,
        shortages=shortages,
        generated_at=_now_iso(),
    )
