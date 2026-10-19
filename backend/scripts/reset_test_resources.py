#!/usr/bin/env python3
"""
RescuNet — Safe Resource Reset CLI for Testing.

Safely releases rescue resources assigned to incidents during testing and
makes them available again for further test scenarios.

Usage Examples:
    # Inspect current resource statuses and assignments:
    python backend/scripts/reset_test_resources.py --inspect

    # Preview resetting all assigned test resources without modifying anything:
    python backend/scripts/reset_test_resources.py --all --dry-run

    # Safely release only orphaned, completed, or mismatched assignments:
    python backend/scripts/reset_test_resources.py --orphaned-only

    # Release resources used in synthetic [DEMO] incidents:
    python backend/scripts/reset_test_resources.py --demo-only

    # Release a specific resource by ID:
    python backend/scripts/reset_test_resources.py --resource-id RES-001

    # Release resources for a specific test incident:
    python backend/scripts/reset_test_resources.py --incident-id RSN-000001

    # Release all test resources with confirmation:
    python backend/scripts/reset_test_resources.py --all --yes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add backend directory to sys.path so app modules can be imported
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resource_reset_service import (
    backup_databases,
    inspect_resources_and_assignments,
    reset_test_resources,
)


def print_inspection(inspection: dict) -> None:
    counts = inspection["counts"]
    dbs = inspection["target_databases"]

    print("=" * 76)
    print("RescuNet Resource Status & Assignment Inspection")
    print("=" * 76)
    print(f"Resources DB: {dbs['resources_db']}")
    print(f"RescuNet DB:  {dbs['rescunet_db']}")
    print("-" * 76)
    print(
        f"Total: {counts['total']} | Available: {counts['available']} | "
        f"Deployed: {counts['deployed']} | Unavailable: {counts['unavailable']}"
    )
    print(
        f"Assignments: Orphaned/Mismatched: {counts['orphaned']} | "
        f"Demo: {counts['demo']} | Active Dispatched: {counts['active_dispatched']}"
    )
    print("-" * 76)
    print(f"{'Resource ID':<12} {'Name':<24} {'Status':<11} {'Assigned Inc':<13} {'Classification'}")
    print("-" * 76)

    for r in inspection["resources"]:
        inc_str = r["assigned_incident_id"] or "-"
        print(f"{r['resource_id']:<12} {r['name'][:23]:<24} {r['status']:<11} {inc_str:<13} {r['classification']}")

    print("=" * 76)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RescuNet Safe Resource Reset Tool for Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect current resource assignments and exit without changes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the reset and display changes without writing to database.",
    )
    parser.add_argument(
        "--mode",
        choices=["orphaned", "demo", "targeted", "all"],
        default=None,
        help="Reset mode (orphaned, demo, targeted, all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reset all deployed resources from test assignments (shortcut for --mode all).",
    )
    parser.add_argument(
        "--orphaned-only",
        action="store_true",
        help="Only release orphaned, mismatched, or completed assignments (shortcut for --mode orphaned).",
    )
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Release resources assigned to [DEMO] incidents or DEMO-* resources.",
    )
    parser.add_argument(
        "--resource-id",
        action="append",
        dest="resource_ids",
        help="Target specific resource ID(s) to release (can be repeated).",
    )
    parser.add_argument(
        "--incident-id",
        action="append",
        dest="incident_ids",
        help="Target specific incident ID(s) to release resources for (can be repeated).",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip automatic database backup before modification.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Custom directory for database backups.",
    )
    parser.add_argument(
        "--actor",
        default="test_admin",
        help="Actor identity recorded in the audit trail (default: test_admin).",
    )
    parser.add_argument(
        "--reason",
        default="Safe test resource reset",
        help="Reason recorded in the audit trail.",
    )

    args = parser.parse_args()

    # Determine mode
    if args.inspect:
        inspection = inspect_resources_and_assignments()
        print_inspection(inspection)
        return 0

    mode = args.mode
    if args.all:
        mode = "all"
    elif args.orphaned_only:
        mode = "orphaned"
    elif args.demo_only:
        mode = "demo"
    elif args.resource_ids or args.incident_ids:
        mode = "targeted"

    if not mode:
        print("No reset action specified. Showing current inspection:\n")
        inspection = inspect_resources_and_assignments()
        print_inspection(inspection)
        print("\nPlease specify one of:")
        print("  --all            : Release all test resources (returns all to 'available')")
        print("  --orphaned-only  : Release only orphaned or completed test assignments")
        print("  --demo-only      : Release only [DEMO] synthetic test resources")
        print("  --resource-id ID : Release a specific resource (e.g. RES-001)")
        print("  --incident-id ID : Release resources for an incident (e.g. RSN-000001)")
        print("Add --dry-run to preview changes without modifying databases.")
        return 0

    # Inspect first to show what would be affected
    inspection = inspect_resources_and_assignments()
    print_inspection(inspection)

    # Perform a dry-run first to show affected items
    sim = reset_test_resources(
        mode=mode,
        resource_ids=args.resource_ids,
        incident_ids=args.incident_ids,
        dry_run=True,
    )

    print("\nProposed Changes:")
    print(f"  Mode: {mode}")
    print(f"  Resources to release: {sim['released_count']}")
    for r in sim["released_resources"]:
        print(f"    - {r['resource_id']} ({r['name']}) [prev: {r['previous_assignment'] or 'none'}] -> available")

    if sim["updated_incidents"]:
        print(f"  Incidents transitioning to resolved: {', '.join(sim['updated_incidents'])}")
    if sim["updated_plans"]:
        print(f"  Response plans transitioning to completed: {', '.join(sim['updated_plans'])}")
    if sim["preserved_active_count"] > 0:
        print(f"  Preserved active assignments: {sim['preserved_active_count']}")
        for p in sim["preserved_active_resources"]:
            print(f"    - {p} (kept active)")

    if sim["released_count"] == 0:
        print("\nNo resources match the selected criteria for release.")
        return 0

    if args.dry_run:
        print("\n[DRY RUN COMPLETE] No database files were modified.")
        return 0

    # Confirmation
    if not args.yes:
        print("\n" + "!" * 76)
        print("CONFIRMATION REQUIRED:")
        print(f"Target databases: {inspection['target_databases']['resources_db']}")
        print(f"                  {inspection['target_databases']['rescunet_db']}")
        print("!" * 76)
        try:
            answer = input(f"Proceed with releasing {sim['released_count']} resource(s)? [y/N]: ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("y", "yes"):
            print("Operation aborted by user. No changes were made.")
            return 1

    # Execute reset
    print("\nExecuting safe resource reset...")
    result = reset_test_resources(
        mode=mode,
        resource_ids=args.resource_ids,
        incident_ids=args.incident_ids,
        dry_run=False,
        create_backup=not args.no_backup,
        backup_dir=args.backup_dir,
        actor=args.actor,
        reason=args.reason,
    )

    print("\n[SUCCESS] Resource reset completed successfully.")
    if result["backup_files"]:
        print("Backups created:")
        for name, path in result["backup_files"].items():
            print(f"  - {name}: {path}")

    print(f"Released {result['released_count']} resource(s):")
    for r in result["released_resources"]:
        print(f"  - {r['resource_id']} ({r['name']}) -> available")

    if result["updated_incidents"]:
        print(f"Updated incidents to resolved: {', '.join(result['updated_incidents'])}")
    if result["updated_plans"]:
        print(f"Updated response plans to completed: {', '.join(result['updated_plans'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
