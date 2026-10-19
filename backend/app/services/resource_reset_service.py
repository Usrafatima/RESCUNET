"""
Resource Reset Service for RescuNet.

Provides safe, transactional reset operations to return rescue resources to
'available' status after local test assignments, while strictly preserving:
- Original resource attributes (IDs, names, types, equipment, capacity, coordinates).
- Incident history and audit trail records.
- Active assignments where requested.
- Unrelated application and edge data.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import agent.resource_db as resource_db_module
import app.database as database_module

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def get_rescunet_db_path() -> Path:
    """Return the active path for rescunet.db."""
    return Path(database_module.DATABASE_PATH)


def get_resources_db_path() -> Path:
    """Return the active path for resources.db."""
    return Path(resource_db_module.DATABASE_PATH)


def backup_databases(
    rescunet_path: Optional[Path] = None,
    resources_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
) -> dict[str, str]:
    """Create timestamped backups of local SQLite databases before modifying them.

    Args:
        rescunet_path: Path to rescunet.db (defaults to active path).
        resources_path: Path to resources.db (defaults to active path).
        backup_dir: Target directory for backups (defaults to <data_dir>/backups).

    Returns:
        Dict mapping database key ('rescunet', 'resources') to created backup path.
    """
    res_path = Path(resources_path or get_resources_db_path())
    resc_path = Path(rescunet_path or get_rescunet_db_path())

    target_dir = Path(backup_dir or (res_path.parent / "backups"))
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backups: dict[str, str] = {}

    if res_path.exists():
        res_backup = target_dir / f"{res_path.stem}_{timestamp}{res_path.suffix}.bak"
        shutil.copy2(str(res_path), str(res_backup))
        backups["resources"] = str(res_backup)
        logger.info("Backed up resources.db to %s", res_backup)

    if resc_path.exists():
        resc_backup = target_dir / f"{resc_path.stem}_{timestamp}{resc_path.suffix}.bak"
        shutil.copy2(str(resc_path), str(resc_backup))
        backups["rescunet"] = str(resc_backup)
        logger.info("Backed up rescunet.db to %s", resc_backup)

    return backups


def inspect_resources_and_assignments(
    rescunet_path: Optional[Path] = None,
    resources_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Inspect all resources and their assignment state across both databases.

    Categorizes each resource as:
    - 'available': Ready for matching.
    - 'orphaned_missing_incident': Resource marked deployed to an incident that does not exist.
    - 'orphaned_mismatch': Resource marked deployed to an incident whose active plan points to a different resource.
    - 'completed_or_resolved': Resource marked deployed to an incident that is already 'resolved' or 'cancelled'.
    - 'demo_assignment': Assigned to a synthetic [DEMO] incident or resource is DEMO-*.
    - 'active_dispatched': Assigned to an active dispatched test incident.

    Returns:
        Structured inspection report dictionary.
    """
    res_path = Path(resources_path or get_resources_db_path())
    resc_path = Path(rescunet_path or get_rescunet_db_path())

    if not res_path.exists():
        resource_db_module.init_resource_db()
    if not resc_path.exists():
        database_module.init_db()

    conn_res = sqlite3.connect(str(res_path))
    conn_res.row_factory = sqlite3.Row

    conn_resc = sqlite3.connect(str(resc_path))
    conn_resc.row_factory = sqlite3.Row

    try:
        resources_rows = conn_res.execute(
            "SELECT * FROM resources ORDER BY resource_id ASC"
        ).fetchall()
        resources = [dict(r) for r in resources_rows]

        incidents_rows = conn_resc.execute("SELECT * FROM incidents").fetchall()
        incidents_by_id = {r["incident_id"]: dict(r) for r in incidents_rows}

        plans_rows = conn_resc.execute("SELECT * FROM response_plans").fetchall()
        plans_by_incident = {r["incident_id"]: dict(r) for r in plans_rows}

        inspected_resources = []
        counts = {
            "total": len(resources),
            "available": 0,
            "deployed": 0,
            "unavailable": 0,
            "orphaned": 0,
            "demo": 0,
            "active_dispatched": 0,
        }

        for r in resources:
            r_id = r["resource_id"]
            status = r["status"]
            assigned_inc_id = r.get("assigned_incident_id")

            # Parse equipment JSON if string
            equipment = r.get("equipment")
            if isinstance(equipment, str):
                try:
                    equipment = json.loads(equipment)
                except Exception:
                    pass

            item = {
                "resource_id": r_id,
                "name": r["name"],
                "type": r["type"],
                "status": status,
                "assigned_incident_id": assigned_inc_id,
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "equipment": equipment,
                "max_people": r["max_people"],
                "updated_at": r["updated_at"],
                "incident": None,
                "response_plan": None,
                "classification": "available" if status == "available" else "unknown",
            }

            if status == "available":
                counts["available"] += 1
                inspected_resources.append(item)
                continue

            if status == "deployed":
                counts["deployed"] += 1
            else:
                counts["unavailable"] += 1

            if not assigned_inc_id:
                item["classification"] = "orphaned_missing_incident"
                counts["orphaned"] += 1
                inspected_resources.append(item)
                continue

            inc = incidents_by_id.get(assigned_inc_id)
            plan = plans_by_incident.get(assigned_inc_id)

            if inc:
                item["incident"] = {
                    "incident_id": inc["incident_id"],
                    "status": inc["status"],
                    "description": inc["description"],
                    "created_at": inc["created_at"],
                }
            if plan:
                item["response_plan"] = {
                    "plan_id": plan["plan_id"],
                    "status": plan["status"],
                    "resource_id": plan["resource_id"],
                    "approved_at": plan["approved_at"],
                }

            # Classify assignment
            if not inc:
                item["classification"] = "orphaned_missing_incident"
                counts["orphaned"] += 1
            elif inc["status"] in ("resolved", "cancelled"):
                item["classification"] = "completed_or_resolved"
                counts["orphaned"] += 1
            elif plan and plan["resource_id"] != r_id:
                # Mismatched/superseded assignment
                item["classification"] = "orphaned_mismatch"
                counts["orphaned"] += 1
            elif (
                (inc.get("description") or "").startswith("[DEMO]")
                or r_id.startswith("DEMO-")
            ):
                item["classification"] = "demo_assignment"
                counts["demo"] += 1
            elif inc["status"] == "dispatched":
                item["classification"] = "active_dispatched"
                counts["active_dispatched"] += 1
            else:
                item["classification"] = "active_other"

            inspected_resources.append(item)

        return {
            "counts": counts,
            "resources": inspected_resources,
            "target_databases": {
                "resources_db": str(res_path.resolve()),
                "rescunet_db": str(resc_path.resolve()),
            },
        }
    finally:
        conn_res.close()
        conn_resc.close()


def get_configured_capacities() -> dict[str, int]:
    """Retrieve original configured capacities from seed data and demo fixtures.

    Returns a dict mapping resource_id -> configured maximum capacity.
    """
    capacities: dict[str, int] = {}

    # 1. From SEED_RESOURCES
    for r in getattr(resource_db_module, "SEED_RESOURCES", []):
        if "resource_id" in r and "max_people" in r:
            capacities[r["resource_id"]] = int(r["max_people"])

    # 2. From demo fixtures if present
    fixtures_path = resource_db_module.PROJECT_ROOT / "demo" / "fixtures.json"
    if fixtures_path.exists():
        try:
            with open(fixtures_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for r in data.get("resources", []):
                    if "resource_id" in r and "max_people" in r:
                        capacities[r["resource_id"]] = int(r["max_people"])
        except Exception as exc:
            logger.warning("Could not read fixtures.json for configured capacities: %s", exc)

    return capacities


def reset_test_resources(
    mode: str = "orphaned",
    resource_ids: Optional[list[str]] = None,
    incident_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    create_backup: bool = True,
    actor: str = "test_admin",
    reason: str = "Safe test resource reset",
    rescunet_path: Optional[Path] = None,
    resources_path: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Safely reset assigned test resources to 'available'.

    Args:
        mode:
            - 'orphaned': Only release resources with missing/resolved incidents or mismatched plans.
            - 'demo': Release resources assigned to [DEMO] incidents or DEMO-* resources.
            - 'targeted': Release specific resources or incidents specified in resource_ids / incident_ids.
            - 'all': Release all deployed/unavailable resources from test assignments and restore capacities.
        resource_ids: List of specific resource IDs to release (for mode='targeted').
        incident_ids: List of specific incident IDs to release resources for (for mode='targeted').
        dry_run: If True, simulate changes without writing to database files.
        create_backup: If True and not dry_run, create timestamped backups prior to modification.
        actor: Identity recorded in the audit trail.
        reason: Explanation recorded in the audit trail.
        rescunet_path: Path to rescunet.db override.
        resources_path: Path to resources.db override.
        backup_dir: Directory for database backups.

    Returns:
        Summary dict containing counts, affected items, and backup paths.
    """
    valid_modes = ("orphaned", "demo", "targeted", "all")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {valid_modes}")

    inspection = inspect_resources_and_assignments(
        rescunet_path=rescunet_path, resources_path=resources_path
    )
    all_resources = inspection["resources"]
    configured_caps = get_configured_capacities()

    # Filter resources to release based on mode
    target_items = []
    skipped_active_items = []

    req_res_ids = set(resource_ids or [])
    req_inc_ids = set(incident_ids or [])

    for item in all_resources:
        r_id = item["resource_id"]
        inc_id = item["assigned_incident_id"]
        classification = item["classification"]
        status = item["status"]
        current_cap = item.get("max_people")
        conf_cap = configured_caps.get(r_id)

        # In 'all' mode: reset all resources that are deployed, unavailable, have an assignment,
        # or whose capacity does not match their configured maximum.
        if mode == "all":
            needs_reset = (
                status != "available"
                or inc_id is not None
                or (conf_cap is not None and current_cap != conf_cap)
            )
            if needs_reset:
                target_items.append(item)
            continue

        if status != "deployed":
            continue

        should_release = False

        if mode == "orphaned":
            if classification in (
                "orphaned_missing_incident",
                "orphaned_mismatch",
                "completed_or_resolved",
            ):
                should_release = True
            else:
                skipped_active_items.append(item)

        elif mode == "demo":
            if classification in (
                "demo_assignment",
                "orphaned_missing_incident",
                "orphaned_mismatch",
                "completed_or_resolved",
            ):
                should_release = True
            else:
                skipped_active_items.append(item)

        elif mode == "targeted":
            match_res = r_id in req_res_ids
            match_inc = inc_id and inc_id in req_inc_ids
            if match_res or match_inc:
                should_release = True
            else:
                skipped_active_items.append(item)

        if should_release:
            target_items.append(item)

    # Determine capacity restoration and limitations per Requirement 8
    restored_capacities: dict[str, int] = {}
    limitations: list[str] = []

    for item in target_items:
        r_id = item["resource_id"]
        current_cap = item.get("max_people")
        if r_id in configured_caps:
            target_cap = configured_caps[r_id]
            restored_capacities[r_id] = target_cap
        else:
            if current_cap is not None:
                target_cap = current_cap
                limitations.append(
                    f"Original capacity for resource '{r_id}' cannot be determined safely from configured definitions; preserved existing schema capacity ({current_cap})."
                )
                restored_capacities[r_id] = target_cap
            else:
                limitations.append(
                    f"Original capacity for resource '{r_id}' is undefined and cannot be determined safely."
                )

    backup_info = {}
    if not dry_run and create_backup and target_items:
        backup_info = backup_databases(
            rescunet_path=rescunet_path,
            resources_path=resources_path,
            backup_dir=backup_dir,
        )

    released_resources = []
    updated_incidents = set()
    updated_plans = set()

    if not dry_run and target_items:
        res_path = Path(resources_path or get_resources_db_path())
        resc_path = Path(rescunet_path or get_rescunet_db_path())

        now = _now_iso()

        conn_res = sqlite3.connect(str(res_path))
        conn_res.row_factory = sqlite3.Row
        conn_resc = sqlite3.connect(str(resc_path))
        conn_resc.row_factory = sqlite3.Row
        conn_resc.execute("PRAGMA foreign_keys=ON")

        try:
            # 1. Update resources in resources.db: reset availability and restore capacity
            for item in target_items:
                r_id = item["resource_id"]
                target_cap = restored_capacities.get(r_id, item.get("max_people"))
                conn_res.execute(
                    """
                    UPDATE resources
                    SET status = 'available',
                        assigned_incident_id = NULL,
                        max_people = ?,
                        updated_at = ?
                    WHERE resource_id = ?
                    """,
                    (target_cap, now, r_id),
                )
                released_resources.append({
                    "resource_id": r_id,
                    "name": item["name"],
                    "type": item["type"],
                    "previous_status": item["status"],
                    "previous_assignment": item["assigned_incident_id"],
                    "restored_capacity": target_cap,
                    "classification": item["classification"],
                })

            # 2. Append audit event to preserve history without modifying incidents or plan assignments
            audit_detail = {
                "action": "test_resource_reset",
                "mode": mode,
                "actor": actor,
                "reason": reason,
                "released_count": len(released_resources),
                "released_resources": [r["resource_id"] for r in released_resources],
                "restored_capacities": restored_capacities,
                "limitations": limitations,
            }
            conn_resc.execute(
                """
                INSERT INTO audit_events (incident_id, plan_id, event_type, detail, actor, created_at)
                VALUES (NULL, NULL, 'test_resource_reset', ?, ?, ?)
                """,
                (json.dumps(audit_detail), actor, now),
            )

            conn_res.commit()
            conn_resc.commit()
        except Exception as exc:
            conn_res.rollback()
            conn_resc.rollback()
            logger.error("Transaction failed during resource reset: %s", exc)
            raise
        finally:
            conn_res.close()
            conn_resc.close()
    else:
        # Simulation for dry_run
        for item in target_items:
            r_id = item["resource_id"]
            target_cap = restored_capacities.get(r_id, item.get("max_people"))
            released_resources.append({
                "resource_id": r_id,
                "name": item["name"],
                "type": item["type"],
                "previous_status": item["status"],
                "previous_assignment": item["assigned_incident_id"],
                "restored_capacity": target_cap,
                "classification": item["classification"],
            })

    return {
        "status": "success",
        "dry_run": dry_run,
        "mode": mode,
        "backup_files": backup_info,
        "released_count": len(released_resources),
        "released_resources": released_resources,
        "restored_capacities": restored_capacities,
        "limitations": limitations,
        "updated_incidents": sorted(updated_incidents),
        "updated_plans": sorted(updated_plans),
        "preserved_active_count": len(skipped_active_items),
        "preserved_active_resources": [
            f"{i['resource_id']} ({i.get('assigned_incident_id')})"
            for i in skipped_active_items
        ],
        "target_databases": inspection["target_databases"],
        "message": f"Successfully reset {len(released_resources)} resource(s) to available.",
    }
