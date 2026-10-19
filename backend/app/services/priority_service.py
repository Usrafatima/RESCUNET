"""
Priority scoring service for RescuNet.

Provides deterministic priority scoring based on AI-extracted factors
and incident data. The LLM classifies incidents and extracts factors;
the final numeric score is calculated in code using configurable weights.

Scoring Formula:
    score = (severity × W_s) + (people_affected × W_p) + (urgency × W_u) + (waiting_time × W_w) + (resource_availability × W_r)

    where W_* are configurable weights that sum to 1.0.

This ensures:
- Predictable, auditable priority rankings
- No arbitrary LLM-generated numeric scores
- Easy to tune weights based on operational needs
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from agent.models import (
    IncidentType,
    Priority,
    PriorityQueueItem,
    PriorityQueueResponse,
    PriorityFactors,
    PriorityAnalysisResult,
    ResourceAvailabilityInfo,
)
from app.database import get_db

logger = logging.getLogger(__name__)

# ─── Configurable Scoring Weights ────────────────────────────────────────
# These sum to 1.0. Each weight determines how much a factor contributes
# to the final 0-100 score. Adjust based on operational requirements.

SCORING_WEIGHTS = {
    "severity": 0.30,       # How severe is the emergency?
    "people_affected": 0.25, # How many people are impacted?
    "urgency": 0.25,        # How time-sensitive is the response?
    "waiting_time": 0.10,   # How long has it been waiting?
    "resource_availability": 0.10,  # Is a suitable resource available?
}

# Waiting time scoring: incidents waiting longer get higher priority.
# Scale: 0 min → 0 points, 30+ min → 100 points (linear).
WAITING_TIME_MAX_MINUTES = 30.0

# Active statuses — incidents in these statuses appear in the priority queue.
ACTIVE_STATUSES = {"queued", "processing", "awaiting_approval", "dispatched"}

# Incident type → required resource type mapping for availability check.
INCIDENT_RESOURCE_MAP = {
    "medical": ["medical"],
    "rescue": ["rescue"],
    "fire": ["fire"],
    "supplies": ["supplies"],
    "shelter": ["shelter"],
    "infrastructure": ["rescue", "supplies"],
    "other": ["rescue", "medical", "supplies"],
}


def calculate_priority_score(
    factors: PriorityFactors,
    waiting_time_minutes: float,
    resource_available: bool,
    weights: dict[str, float] | None = None,
) -> float:
    """Calculate the deterministic priority score (0-100).

    Args:
        factors: AI-extracted priority factors (each 0-100)
        waiting_time_minutes: How long the incident has been waiting
        resource_available: Whether a suitable resource is available
        weights: Override default scoring weights

    Returns:
        Priority score from 0 to 100
    """
    w = weights or SCORING_WEIGHTS

    # Normalize waiting time to 0-100 scale
    waiting_score = min(
        100.0,
        (waiting_time_minutes / WAITING_TIME_MAX_MINUTES) * 100.0,
    )

    # Resource availability: 100 if available, 30 if not
    # (not having a resource doesn't zero out priority — the incident still needs help)
    resource_score = 100.0 if resource_available else 30.0

    score = (
        factors.severity * w["severity"]
        + factors.people_affected * w["people_affected"]
        + factors.urgency * w["urgency"]
        + waiting_score * w["waiting_time"]
        + resource_score * w["resource_availability"]
    )

    # Clamp to 0-100
    return round(max(0.0, min(100.0, score)), 1)


def _compute_waiting_time(created_at: str) -> tuple[float, str]:
    """Compute waiting time from incident creation time.

    Args:
        created_at: ISO 8601 timestamp of incident creation

    Returns:
        Tuple of (seconds, human-readable string)
    """
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.0, "0m"

    now = datetime.now(timezone.utc)
    delta = now - created
    total_seconds = delta.total_seconds()

    if total_seconds < 60:
        return total_seconds, f"{int(total_seconds)}s"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        return total_seconds, f"{minutes}m"
    else:
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        return total_seconds, f"{hours}h {minutes}m"


def _find_suitable_resource(
    incident_type: str,
) -> Optional[dict]:
    """Find the best available resource for an incident type.

    Checks the resource database for available resources matching
    the required type. Returns the first available one, or None.

    Args:
        incident_type: The classified incident type

    Returns:
        Resource dict or None if no suitable resource is available
    """
    from agent.resource_db import get_all_resources

    required_types = INCIDENT_RESOURCE_MAP.get(incident_type, ["rescue", "medical"])

    resources = get_all_resources()
    for resource in resources:
        if (
            resource["status"] == "available"
            and resource["type"] in required_types
        ):
            return resource

    return None


def _get_resource_availability_info(
    incident_type: str,
) -> ResourceAvailabilityInfo:
    """Get detailed resource availability info for a priority queue item.

    Returns info about the best suitable resource, even if it's deployed.
    """
    from agent.resource_db import get_all_resources

    required_types = INCIDENT_RESOURCE_MAP.get(incident_type, ["rescue", "medical"])
    resources = get_all_resources()

    # First, try to find an available resource
    for resource in resources:
        if (
            resource["status"] == "available"
            and resource["type"] in required_types
        ):
            return ResourceAvailabilityInfo(
                resource_id=resource["resource_id"],
                resource_name=resource["name"],
                resource_type=resource["type"],
                status=resource["status"],
                is_suitable=True,
            )

    # If none available, find a deployed one that matches
    for resource in resources:
        if resource["type"] in required_types:
            return ResourceAvailabilityInfo(
                resource_id=resource["resource_id"],
                resource_name=resource["name"],
                resource_type=resource["type"],
                status=resource["status"],
                is_suitable=True,
            )

    # No matching resource at all
    return ResourceAvailabilityInfo(
        resource_id="NONE",
        resource_name="No matching resource",
        resource_type=incident_type,
        status="unavailable",
        is_suitable=False,
    )


def _priority_label_from_score(score: float) -> str:
    """Convert numeric score to priority label."""
    if score >= 85:
        return "critical"
    elif score >= 70:
        return "high"
    elif score >= 45:
        return "medium"
    else:
        return "low"


def generate_priority_queue(
    incidents: list[dict],
    analyses: dict[str, dict],
) -> PriorityQueueResponse:
    """Generate a sorted priority queue from active incidents.

    Args:
        incidents: List of active incident dicts from the database
        analyses: Dict mapping incident_id → AI analysis result (with factors)

    Returns:
        PriorityQueueResponse with sorted queue items
    """
    items = []

    for incident in incidents:
        incident_id = incident["incident_id"]
        created_at = incident["created_at"]
        incident_type = incident.get("incident_type", "other")

        # Get AI analysis factors if available
        analysis = analyses.get(incident_id)
        if analysis and "factors" in analysis:
            factors = PriorityFactors(**analysis["factors"])
            priority_label = analysis.get("priority_label", "medium")
        else:
            # Default factors when AI hasn't analyzed yet
            # Use description heuristics
            factors = _default_factors(incident)
            priority_label = _priority_label_from_score(50.0)

        # Waiting time
        waiting_seconds, waiting_display = _compute_waiting_time(created_at)
        waiting_minutes = waiting_seconds / 60.0

        # Resource availability
        resource_info = _get_resource_availability_info(incident_type)
        resource_available = resource_info.status == "available"

        # Deterministic score
        score = calculate_priority_score(
            factors=factors,
            waiting_time_minutes=waiting_minutes,
            resource_available=resource_available,
        )

        # Override priority label with score-based label for consistency
        priority_label = _priority_label_from_score(score)

        items.append(
            PriorityQueueItem(
                rank=0,  # Will be set after sorting
                incident_id=incident_id,
                description=incident.get("description", ""),
                incident_type=incident_type,
                priority_label=priority_label,
                score=score,
                people_affected=incident.get("people_affected", 1),
                waiting_time_seconds=waiting_seconds,
                waiting_time_display=waiting_display,
                recommended_resource=resource_info,
                factors=factors,
                reason=factors.reason,
            )
        )

    # Sort by score descending (highest priority first)
    items.sort(key=lambda x: x.score, reverse=True)

    # Assign ranks
    for i, item in enumerate(items):
        item.rank = i + 1

    return PriorityQueueResponse(
        queue=items,
        total_active=len(items),
        generated_at=datetime.now(timezone.utc).isoformat(),
        scoring_weights=SCORING_WEIGHTS,
    )


def _default_factors(incident: dict) -> PriorityFactors:
    """Generate default priority factors when AI analysis is not available.

    Uses simple heuristics based on the incident data.
    """
    people = incident.get("people_affected", 1)
    description = incident.get("description", "").lower()

    # Basic severity heuristics from description
    severity = 50
    if any(w in description for w in ["critical", "emergency", "life", "trapped", "collapse"]):
        severity = 90
    elif any(w in description for w in ["fire", "injured", "urgent", "medical"]):
        severity = 75
    elif any(w in description for w in ["water", "power", "damage"]):
        severity = 60

    # People affected scaling (1 → 30, 10+ → 100)
    people_score = min(100, 30 + (people * 7))

    # Urgency defaults to high for most emergencies
    urgency = 70

    # Resource need based on incident type
    incident_type = incident.get("incident_type", "other")
    resource_need = 60 if incident_type in ("rescue", "fire", "medical") else 40

    reason = f"Emergency affecting {people} people. Assessment pending AI analysis."

    return PriorityFactors(
        severity=severity,
        people_affected=people_score,
        urgency=urgency,
        resource_need=resource_need,
        reason=reason,
    )


def get_incidents_for_priority_queue() -> list[dict]:
    """Fetch all active incidents from the database for priority evaluation.

    Returns incidents in active statuses, ordered by creation time.
    """
    with get_db() as conn:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        rows = conn.execute(
            f"""SELECT * FROM incidents
                WHERE status IN ({placeholders})
                ORDER BY created_at ASC""",
            tuple(ACTIVE_STATUSES),
        ).fetchall()
        return [dict(row) for row in rows]


def get_priority_analyses() -> dict[str, dict]:
    """Retrieve any stored priority analyses from the incidents table.

    For now, analyses are generated on-the-fly. This function
    provides a hook for caching in the future.
    """
    # Currently returns empty — analyses are generated each request
    # This is the extension point for caching AI results
    return {}
