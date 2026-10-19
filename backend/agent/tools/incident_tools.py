"""
RescuNet agent tools.

These are Strands @tool decorated functions that the agent uses
to gather information and make decisions. The agent calls these
tools during its reasoning loop to:

1. Retrieve incident details
2. Find available resources
3. Check resource status
4. Calculate distances
5. List active incidents
"""

import json
import math
from datetime import datetime, timezone

import httpx
from strands import tool

from agent.config import config
from agent.resource_db import get_resource_db, init_resource_db


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points using the Haversine formula.

    Args:
        lat1, lon1: Latitude and longitude of point 1 in decimal degrees
        lat2, lon2: Latitude and longitude of point 2 in decimal degrees

    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(R * c, 2)


@tool
def get_incident(incident_id: str) -> str:
    """Retrieve an existing RescuNet incident from the backend database.

    Use this tool to get full details about a specific emergency incident
    including its description, location, people affected, and current status.

    Args:
        incident_id: The incident ID (e.g., RSN-000001)

    Returns:
        JSON string with incident details, or error message if not found
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{config.backend_url}/api/incidents/{incident_id}")
            if response.status_code == 200:
                return json.dumps(response.json(), indent=2)
            elif response.status_code == 404:
                return json.dumps({"error": f"Incident '{incident_id}' not found"})
            else:
                return json.dumps({"error": f"Backend returned status {response.status_code}"})
    except httpx.ConnectError:
        return json.dumps({"error": "Cannot connect to backend server"})
    except Exception as e:
        return json.dumps({"error": f"Failed to retrieve incident: {str(e)}"})


@tool
def list_active_incidents() -> str:
    """Find all active/unresolved incidents in the system.

    Use this to understand the current emergency situation and see
    what incidents need attention. Returns incidents that are not
    yet resolved or cancelled.

    Returns:
        JSON string with list of active incidents
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{config.backend_url}/api/incidents")
            if response.status_code == 200:
                all_incidents = response.json()
                # Filter to active incidents (not resolved or cancelled)
                active = [
                    inc for inc in all_incidents
                    if inc["status"] not in ("resolved", "cancelled")
                ]
                return json.dumps(active, indent=2)
            else:
                return json.dumps({"error": f"Backend returned status {response.status_code}"})
    except httpx.ConnectError:
        return json.dumps({"error": "Cannot connect to backend server"})
    except Exception as e:
        return json.dumps({"error": f"Failed to list incidents: {str(e)}"})


@tool
def find_available_resources(incident_type: str = "any") -> str:
    """Find community responders and resources that could help with an incident.

    Returns all available resources, optionally filtered by type.
    Use this to identify potential responders for an emergency.

    Args:
        incident_type: Type of resource needed (medical, rescue, fire, supplies, shelter, or any)

    Returns:
        JSON string with list of available resources
    """
    try:
        init_resource_db()
        with get_resource_db() as conn:
            if incident_type and incident_type != "any":
                rows = conn.execute(
                    "SELECT * FROM resources WHERE status = 'available' AND type = ?",
                    (incident_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM resources WHERE status = 'available'"
                ).fetchall()

            resources = []
            for row in rows:
                resource = dict(row)
                resource["equipment"] = json.loads(resource["equipment"])
                resources.append(resource)

            return json.dumps(resources, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to find resources: {str(e)}"})


@tool
def get_resource_status(resource_id: str) -> str:
    """Check whether a specific responder/resource is currently available, dispatched, or unavailable.

    Always check availability before recommending a resource for dispatch.

    Args:
        resource_id: The resource ID (e.g., RES-001)

    Returns:
        JSON string with resource status details
    """
    try:
        init_resource_db()
        with get_resource_db() as conn:
            row = conn.execute(
                "SELECT * FROM resources WHERE resource_id = ?", (resource_id,)
            ).fetchone()
            if row:
                resource = dict(row)
                resource["equipment"] = json.loads(resource["equipment"])
                return json.dumps(resource, indent=2)
            else:
                return json.dumps({"error": f"Resource '{resource_id}' not found"})
    except Exception as e:
        return json.dumps({"error": f"Failed to get resource status: {str(e)}"})


@tool
def calculate_distance(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> str:
    """Calculate the distance between two geographic coordinates using the Haversine formula.

    Use this to determine how far a resource is from an incident location.

    Args:
        origin_latitude: Latitude of the origin point (e.g., incident location)
        origin_longitude: Longitude of the origin point
        destination_latitude: Latitude of the destination (e.g., resource location)
        destination_longitude: Longitude of the destination

    Returns:
        JSON string with distance in kilometers
    """
    try:
        distance_km = _haversine_km(
            origin_latitude, origin_longitude,
            destination_latitude, destination_longitude,
        )
        return json.dumps({
            "distance_km": distance_km,
            "origin": {"latitude": origin_latitude, "longitude": origin_longitude},
            "destination": {"latitude": destination_latitude, "longitude": destination_longitude},
        })
    except Exception as e:
        return json.dumps({"error": f"Failed to calculate distance: {str(e)}"})
