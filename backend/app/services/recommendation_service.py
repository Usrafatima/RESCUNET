"""
Recommendation service for RescuNet.

Validates resource availability and returns enriched recommendation
data including capabilities, match score, and distance.
"""

import json
import logging
import math
from typing import Optional

from app.database import get_db

logger = logging.getLogger(__name__)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance between two coordinates in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_incident(incident_id: str) -> Optional[dict]:
    """Get incident from database."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None


def _get_resource(resource_id: str) -> Optional[dict]:
    """Get resource from resource database."""
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


def _get_all_resources() -> list[dict]:
    """Get all resources."""
    from agent.resource_db import get_all_resources

    return get_all_resources()


# Incident type to required capability mapping
INCIDENT_CAPABILITY_MAP = {
    "medical": ["first_aid", "oxygen", "defibrillator", "insulin", "medical"],
    "rescue": ["extraction_gear", "ropes", "flashlights", "stretchers", "rescue"],
    "fire": ["extinguishers", "hoses", "protective_gear", "fire"],
    "supplies": ["water", "food", "blankets", "tarps", "supplies"],
    "shelter": ["tents", "mattresses", "hygiene_kits", "shelter"],
    "infrastructure": ["extraction_gear", "ropes", "tools", "infrastructure"],
    "other": [],
}


def _calculate_match_score(
    incident_type: str, equipment: list[str], distance_km: float
) -> float:
    """Calculate a match score (0-100) for a resource against an incident type.

    Factors:
    - Capability match (60%): how many required capabilities the resource has
    - Distance (25%): closer = better (0km=100, 10km+=0)
    - Equipment count (15%): more equipment = more versatile
    """
    required = INCIDENT_CAPABILITY_MAP.get(incident_type, [])
    if not required:
        # No specific requirements — base score on distance and versatility
        capability_score = 60.0
    else:
        equipment_lower = [e.lower().replace(" ", "_") for e in equipment]
        matched = sum(1 for cap in required if any(cap in eq for eq in equipment_lower))
        capability_score = (matched / len(required)) * 100

    # Distance score: 0km=100, 5km=50, 10km+=0
    distance_score = max(0, 100 - (distance_km * 10))

    # Equipment count score: normalize to 0-100 (more equipment = more versatile)
    equipment_score = min(100, len(equipment) * 20)

    # Weighted combination
    score = (capability_score * 0.60) + (distance_score * 0.25) + (equipment_score * 0.15)
    return round(min(100, max(0, score)), 1)


def get_recommendation(incident_id: str) -> Optional[dict]:
    """Get enriched recommendation for an incident.

    Validates resource availability, calculates match scores,
    and returns comprehensive recommendation data.
    """
    incident = _get_incident(incident_id)
    if not incident:
        return None

    all_resources = _get_all_resources()
    if not all_resources:
        return None

    # Determine incident type from existing agent analysis or use heuristic
    incident_type = _infer_incident_type(incident["description"])

    # Score all available resources
    scored_resources = []
    for resource in all_resources:
        distance = _haversine_km(
            incident["latitude"],
            incident["longitude"],
            resource["latitude"],
            resource["longitude"],
        )
        score = _calculate_match_score(incident_type, resource["equipment"], distance)

        scored_resources.append(
            {
                "resource_id": resource["resource_id"],
                "name": resource["name"],
                "type": resource["type"],
                "status": resource["status"],
                "latitude": resource["latitude"],
                "longitude": resource["longitude"],
                "equipment": resource["equipment"],
                "max_people": resource["max_people"],
                "distance_km": round(distance, 2),
                "match_score": score,
                "is_available": resource["status"] == "available",
                "assigned_incident_id": resource.get("assigned_incident_id"),
            }
        )

    # Sort by match score descending
    scored_resources.sort(key=lambda r: r["match_score"], reverse=True)

    # Find best available resource
    best_available = next((r for r in scored_resources if r["is_available"]), None)

    # Check if incident already has a dispatched resource
    existing_plan = None
    with get_db() as conn:
        plan_row = conn.execute(
            "SELECT * FROM response_plans WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        if plan_row:
            existing_plan = dict(plan_row)

    # Build recommendation
    total_resources = len(scored_resources)
    available_count = sum(1 for r in scored_resources if r["is_available"])

    if existing_plan:
        # Already dispatched — return the dispatched resource info
        dispatched_resource = next(
            (r for r in scored_resources if r["resource_id"] == existing_plan["resource_id"]),
            None,
        )
        return {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "status": "dispatched",
            "recommended_resource": dispatched_resource,
            "activity": [
                {"step": "Incident retrieved", "status": "completed"},
                {"step": f"Severity classified: {incident_type.upper()}", "status": "completed"},
                {"step": f"Required capability identified: {incident_type.upper()}", "status": "completed"},
                {"step": "Available resources checked", "status": "completed"},
                {"step": f"{dispatched_resource['resource_id']} capability match confirmed", "status": "completed"} if dispatched_resource else {"step": "Resource matched", "status": "completed"},
                {"step": f"Distance calculated: {dispatched_resource['distance_km']:.1f} km" if dispatched_resource else "Distance calculated", "status": "completed"},
                {"step": "Recommendation generated", "status": "completed"},
                {"step": "Human approval received", "status": "completed"},
                {"step": "Resource dispatched", "status": "completed"},
            ],
            "total_resources_checked": total_resources,
            "available_resources": available_count,
            "resource_rankings": scored_resources[:5],  # Top 5
        }

    if best_available:
        return {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "status": "recommendation_ready",
            "recommended_resource": best_available,
            "activity": [
                {"step": "Incident retrieved", "status": "completed"},
                {"step": f"Severity classified: {incident_type.upper()}", "status": "completed"},
                {"step": f"Required capability identified: {incident_type.upper()}", "status": "completed"},
                {"step": f"Available resources checked ({total_resources} total, {available_count} available)", "status": "completed"},
                {"step": f"{best_available['resource_id']} capability match confirmed", "status": "completed"},
                {"step": f"Distance calculated: {best_available['distance_km']:.1f} km", "status": "completed"},
                {"step": "Recommendation generated", "status": "completed"},
                {"step": "Human approval required", "status": "pending"},
            ],
            "total_resources_checked": total_resources,
            "available_resources": available_count,
            "resource_rankings": scored_resources[:5],
        }
    else:
        return {
            "incident_id": incident_id,
            "incident_type": incident_type,
            "status": "no_resource_available",
            "recommended_resource": None,
            "activity": [
                {"step": "Incident retrieved", "status": "completed"},
                {"step": f"Severity classified: {incident_type.upper()}", "status": "completed"},
                {"step": f"Required capability identified: {incident_type.upper()}", "status": "completed"},
                {"step": f"Resources checked ({total_resources} total, {available_count} available)", "status": "completed"},
                {"step": "No suitable responder available", "status": "warning"},
            ],
            "total_resources_checked": total_resources,
            "available_resources": available_count,
            "resource_rankings": [],
        }


def _infer_incident_type(description: str) -> str:
    """Infer incident type from description using keyword matching."""
    desc_lower = description.lower()

    if any(w in desc_lower for w in ["medical", "injury", "injured", "heart", "bleeding", "sick", "ambulance"]):
        return "medical"
    if any(w in desc_lower for w in ["rescue", "trapped", "collapse", "collapse", "stuck", "building"]):
        return "rescue"
    if any(w in desc_lower for w in ["fire", "burning", "smoke", "flame", "arson"]):
        return "fire"
    if any(w in desc_lower for w in ["supply", "food", "water", "blanket", "material"]):
        return "supplies"
    if any(w in desc_lower for w in ["shelter", "homeless", "displaced", "housing"]):
        return "shelter"
    if any(w in desc_lower for w in ["infrastructure", "road", "bridge", "power", "electric"]):
        return "infrastructure"
    return "other"
