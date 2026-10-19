"""
Route / corridor service for RescuNet.

Routes are explicit, operator-defined corridors between two coordinates.
They are the project's representation of *known route restrictions* — this
is not real road-network or GPS routing data.

Two deterministic restriction rules:

1. Scoped restriction (`scope_resource_id` set):
   the restriction applies only to that resource — e.g. "Bridge access road
   reserved for Rescue Team Bravo". While the route is closed that resource
   cannot be assigned to any incident.

2. General corridor (`scope_resource_id` is null):
   while the route is closed, it blocks any assignment whose direct path
   from the resource to the incident crosses the corridor.

Distances are short (city scale), so the segment intersection test uses a
plain planar approximation of latitude/longitude. This is a documented
approximation for a demonstration system — it is not GIS routing.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.plans import RouteCreate, RouteInfo, RouteStatus, RouteUpdate

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Geometry ───────────────────────────────────────────────────────────────


def _orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """Signed area proxy for the orientation of triangle (a, b, c)."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> bool:
    """True when p lies on segment a-b (assumed collinear)."""
    return (
        min(ax, bx) - 1e-12 <= px <= max(ax, bx) + 1e-12
        and min(ay, by) - 1e-12 <= py <= max(ay, by) + 1e-12
    )


def segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    """Deterministic segment intersection test (x=lng, y=lat)."""
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2

    d1 = _orientation(x3, y3, x4, y4, x1, y1)
    d2 = _orientation(x3, y3, x4, y4, x2, y2)
    d3 = _orientation(x1, y1, x2, y2, x3, y3)
    d4 = _orientation(x1, y1, x2, y2, x4, y4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    # Collinear / touching cases
    if abs(d1) < 1e-15 and _on_segment(x3, y3, x4, y4, x1, y1):
        return True
    if abs(d2) < 1e-15 and _on_segment(x3, y3, x4, y4, x2, y2):
        return True
    if abs(d3) < 1e-15 and _on_segment(x1, y1, x2, y2, x3, y3):
        return True
    if abs(d4) < 1e-15 and _on_segment(x1, y1, x2, y2, x4, y4):
        return True
    return False


def assignment_blocked_by(
    route: dict,
    resource: dict,
    incident: dict,
) -> bool:
    """Decide whether a route restriction blocks a resource→incident assignment.

    Args:
        route: Route row dict
        resource: Resource row dict (needs latitude/longitude/resource_id)
        incident: Incident row dict (needs latitude/longitude)

    Returns True when the assignment must not be proposed while the route
    is closed.
    """
    if route.get("status") != RouteStatus.closed.value:
        return False

    scope = route.get("scope_resource_id")
    if scope:
        # Scoped restriction: applies to exactly one resource.
        return scope == resource.get("resource_id")

    # General corridor: blocked when the direct path crosses the corridor.
    return segments_intersect(
        (route["from_lng"], route["from_lat"]),
        (route["to_lng"], route["to_lat"]),
        (float(resource["longitude"]), float(resource["latitude"])),
        (float(incident["longitude"]), float(incident["latitude"])),
    )


def blocked_routes_for(resource: dict, incident: dict) -> list[dict]:
    """All closed routes that block this resource→incident assignment."""
    routes = list_routes(status_filter=RouteStatus.closed.value)
    return [r for r in routes if assignment_blocked_by(r, resource, incident)]


# ─── CRUD ───────────────────────────────────────────────────────────────────


def _row_to_info(row: dict) -> RouteInfo:
    return RouteInfo(
        route_id=row["route_id"],
        name=row["name"],
        status=RouteStatus(row["status"]),
        restriction_reason=row.get("restriction_reason"),
        scope_resource_id=row.get("scope_resource_id"),
        from_lat=row["from_lat"],
        from_lng=row["from_lng"],
        to_lat=row["to_lat"],
        to_lng=row["to_lng"],
        updated_at=row["updated_at"],
    )


def _generate_route_id(conn) -> str:
    """Next route id (RTE-000001), safe even if older routes were deleted."""
    row = conn.execute(
        "SELECT COALESCE(MAX(CAST(substr(route_id, 5) AS INTEGER)), 0) AS max_id "
        "FROM routes"
    ).fetchone()
    return f"RTE-{int(row['max_id']) + 1:06d}"


def list_routes(status_filter: Optional[str] = None) -> list[dict]:
    """Return all routes (optionally filtered by status)."""
    with get_db() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM routes WHERE status = ? ORDER BY route_id",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM routes ORDER BY route_id").fetchall()
        return [dict(r) for r in rows]


def get_route(route_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM routes WHERE route_id = ?", (route_id,)
        ).fetchone()
        return dict(row) if row else None


def create_route(data: RouteCreate) -> dict:
    now = _now_iso()
    with get_db() as conn:
        route_id = _generate_route_id(conn)
        conn.execute(
            """
            INSERT INTO routes (route_id, name, status, restriction_reason,
                                scope_resource_id, from_lat, from_lng,
                                to_lat, to_lng, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                route_id,
                data.name,
                data.status.value,
                data.restriction_reason,
                data.scope_resource_id,
                data.from_lat,
                data.from_lng,
                data.to_lat,
                data.to_lng,
                now,
                now,
            ),
        )
        conn.commit()
    return get_route(route_id)  # type: ignore[return-value]


def update_route(route_id: str, data: RouteUpdate) -> Optional[dict]:
    """Update a route's status/reason. Returns None when not found."""
    existing = get_route(route_id)
    if not existing:
        return None

    now = _now_iso()
    with get_db() as conn:
        conn.execute(
            "UPDATE routes SET status = ?, restriction_reason = ?, updated_at = ? "
            "WHERE route_id = ?",
            (
                data.status.value,
                data.restriction_reason if data.restriction_reason is not None
                else existing.get("restriction_reason"),
                now,
                route_id,
            ),
        )
        conn.commit()
    return get_route(route_id)
