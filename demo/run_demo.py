#!/usr/bin/env python3
"""
RescuNet — Adaptive Rescue Planning demo (synthetic data only).

Runs the full scenario end-to-end over HTTP:

  1. Several SOS reports arrive (labelled [DEMO]).
  2. One report is classified HIGH urgency from its supplied evidence.
  3. The system proposes responder assignments (human approval required).
  4. The Edge Gateway is switched to OFFLINE.
  5. A new SOS is queued locally on the gateway.
  6. The gateway restarts — the queued SOS is still stored.
  7. Connectivity is restored and the queued SOS is synchronized
     (running the sync twice proves no duplicate incident is created).
  8. A previously usable route becomes unavailable.
  9. The system identifies the affected assignment and proposes a revised plan.
 10. An authorized user reviews and approves the proposed change.

Everything is deterministic (fixed fixtures in fixtures.json). Nothing here
dispatches real responders, uses a real road network, or creates a physical
offline/mesh network — the Edge Gateway queues locally and forwards later.

Usage (from the repo root, with backend :8000 and edge :8001 running):

    python demo/run_demo.py                 # run the whole scenario
    python demo/run_demo.py --no-restart-edge
    python demo/run_demo.py --cleanup       # remove [DEMO] data afterwards

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = ROOT / "demo"
EDGE_DIR = ROOT / "edge"
RESOURCE_DB = ROOT / "data" / "resources.db"
EDGE_LOG = ROOT / "edge-demo.log"

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
EDGE_URL = os.getenv("EDGE_URL", "http://127.0.0.1:8001")

PASS = "PASS"
FAIL = "FAIL"
RESULTS: list[tuple[str, str, str]] = []

# Windows consoles often default to cp1252; keep output UTF-8-safe.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - older Python
    pass


# ─── Tiny HTTP client (stdlib only) ─────────────────────────────────────────


def call(method: str, url: str, payload: dict | None = None) -> tuple[int, dict | list | str]:
    url = urllib.parse.quote(url, safe=":/?&=%")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason)}


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((PASS if ok else FAIL, name, detail))
    printable = detail.replace("→", "->") if isinstance(detail, str) else detail
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" - {printable}" if printable else ""))
    return ok


def step(number: int, title: str) -> None:
    print(f"\nStep {number}: {title}")


# ─── Edge gateway restart helper ────────────────────────────────────────────


def _listening_pid(port: int) -> str | None:
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                return line.split()[-1]
    else:
        for cmd in (["lsof", "-ti", f"tcp:{port}"], ["ss", "-lptn", f"sport = :{port}"]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True).stdout
            except FileNotFoundError:
                continue
            for token in out.replace("=", " ").split():
                if token.isdigit():
                    return token
    return None


def restart_edge() -> bool:
    """Kill the process listening on the edge port and start it again."""
    pid = _listening_pid(8001)
    if not pid:
        print("  (no process found on port 8001 — is the gateway running?)")
        return False

    print(f"  Stopping edge gateway (PID {pid})…")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    else:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
    time.sleep(1.5)

    print("  Starting edge gateway again…")
    log = open(EDGE_LOG, "ab")
    kwargs = {"cwd": str(EDGE_DIR), "stdout": log, "stderr": log}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        **kwargs,
    )

    for _ in range(30):
        status, _ = call("GET", f"{EDGE_URL}/health")
        if status == 200:
            return True
        time.sleep(0.5)
    return False


# ─── Demo data helpers ──────────────────────────────────────────────────────


def seed_resources(fixtures: dict) -> None:
    """Insert the two clearly-labelled DEMO responder units (idempotent)."""
    conn = sqlite3.connect(str(RESOURCE_DB))
    try:
        now = "2026-01-01T00:00:00+00:00"
        for res in fixtures["resources"]:
            conn.execute(
                """
                INSERT OR IGNORE INTO resources
                    (resource_id, name, type, status, latitude, longitude,
                     equipment, max_people, created_at, updated_at)
                VALUES (?, ?, ?, 'available', ?, ?, ?, ?, ?, ?)
                """,
                (
                    res["resource_id"],
                    res["name"],
                    res["type"],
                    res["latitude"],
                    res["longitude"],
                    json.dumps(res["equipment"]),
                    res["max_people"],
                    now,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def all_incidents() -> list[dict]:
    status, body = call("GET", f"{BACKEND_URL}/api/incidents")
    return body if status == 200 else []


def find_incident(description: str) -> dict | None:
    return next((i for i in all_incidents() if i["description"] == description), None)


def find_or_create_incident(spec: dict) -> dict:
    existing = find_incident(spec["description"])
    if existing:
        return existing
    status, body = call(
        "POST",
        f"{BACKEND_URL}/api/incidents",
        {
            "description": spec["description"],
            "people_affected": spec["people_affected"],
            "latitude": spec["latitude"],
            "longitude": spec["longitude"],
            "auto_plan": spec.get("auto_plan", False),
        },
    )
    if status != 201:
        raise RuntimeError(f"Could not create incident: {status} {body}")
    return body


def plans_for(incident_id: str) -> list[dict]:
    status, body = call("GET", f"{BACKEND_URL}/api/incidents/{incident_id}/plans")
    return body.get("plans", []) if status == 200 else []


def triage_for(incident_id: str) -> dict:
    status, body = call("GET", f"{BACKEND_URL}/api/incidents/{incident_id}/triage")
    if status != 200:
        raise RuntimeError(f"Triage failed: {status} {body}")
    return body


def ensure_plan(incident_id: str) -> dict:
    """Return the newest open proposal, creating one if none exists."""
    plans = sorted(plans_for(incident_id), key=lambda p: p["version"])
    open_plans = [p for p in plans if p["status"] in ("proposed", "pending_approval")]
    if open_plans:
        return open_plans[-1]
    status, body = call(
        "POST", f"{BACKEND_URL}/api/incidents/{incident_id}/plan", {"trigger": "manual"}
    )
    if status != 201:
        raise RuntimeError(f"Plan generation failed: {status} {body}")
    return body


def latest_plan(incident_id: str) -> dict | None:
    plans = sorted(plans_for(incident_id), key=lambda p: p["version"])
    return plans[-1] if plans else None


def approve(plan_id: str, approver: str, reason: str) -> tuple[int, dict]:
    return call(
        "POST",
        f"{BACKEND_URL}/api/plans/{plan_id}/approve",
        {"approver": approver, "decision_reason": reason},
    )


def resource_status(resource_id: str) -> str | None:
    status, body = call("GET", f"{BACKEND_URL}/api/resources")
    if status != 200:
        return None
    match = next((r for r in body if r["resource_id"] == resource_id), None)
    return match["status"] if match else None


def find_route(name: str) -> dict | None:
    status, body = call("GET", f"{BACKEND_URL}/api/routes")
    if status != 200:
        return None
    return next((r for r in body.get("routes", []) if r["name"] == name), None)


# ─── The scenario ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="RescuNet adaptive rescue planning demo")
    parser.add_argument("--no-restart-edge", action="store_true",
                        help="Do not restart the Edge Gateway during the run")
    parser.add_argument("--cleanup", action="store_true",
                        help="Remove all [DEMO] data after the run")
    args = parser.parse_args()

    fixtures = json.loads((DEMO_DIR / "fixtures.json").read_text(encoding="utf-8"))
    approver = fixtures["approver"]

    if args.cleanup:
        cleaned = {"done": False}

        def _cleanup_once() -> None:
            if cleaned["done"]:
                return
            cleaned["done"] = True
            cleanup(fixtures)
            print("\nDemo data removed (--cleanup).")

        atexit.register(_cleanup_once)

    print("=" * 72)
    print("RescuNet — Adaptive Rescue Planning demonstration")
    print("All data created by this script is labelled [DEMO] / DEMO-.")
    print("=" * 72)

    # ── Preflight
    step(0, "Preflight — services reachable")
    status, _ = call("GET", f"{BACKEND_URL}/health")
    if not check("Backend reachable", status == 200, BACKEND_URL):
        print("\nStart it first:  cd backend; python -m uvicorn app.main:app --port 8000")
        return 1
    status, _ = call("GET", f"{EDGE_URL}/health")
    if not check("Edge gateway reachable", status == 200, EDGE_URL):
        print("\nStart it first:  cd edge; python -m uvicorn app.main:app --port 8001")
        return 1

    # ── Seed
    step(1, "Seed labelled demo responder units")
    seed_resources(fixtures)
    check("Demo resources available",
          resource_status("DEMO-RES-02") == "available", "DEMO-RES-01, DEMO-RES-02")

    # ── SOS reports arrive
    step(2, "Several SOS reports arrive (synthetic, labelled [DEMO])")
    incidents: dict[str, dict] = {}
    for spec in fixtures["incidents"]:
        incidents[spec["key"]] = find_or_create_incident(spec)
        print(f"  {incidents[spec['key']]['incident_id']}: {spec['description'][:66]}")
    check("3 demo incidents present", len(incidents) == 3)

    # ── Triage
    step(3, "Triage — one report classified high urgency from its evidence")
    triage = {key: triage_for(inc["incident_id"]) for key, inc in incidents.items()}
    for spec in fixtures["incidents"]:
        got = triage[spec["key"]]["urgency_level"]
        check(f"'{spec['key']}' urgency == {spec['expected_urgency']}",
              got == spec["expected_urgency"], f"got {got}")
    critical = triage["medical"]
    evidence = [e for c in critical["criteria"] if c["matched"] for e in c["evidence"]]
    check("Urgency is evidence-based", bool(evidence), "; ".join(evidence)[:70])

    # ── Proposed assignments
    step(4, "System proposes responder assignments (no dispatch yet)")
    proposals: dict[str, dict] = {}
    for key in ("medical", "rescue"):
        incident_id = incidents[key]["incident_id"]
        proposals[key] = ensure_plan(incident_id)
        assigned = proposals[key]["assignment"]["resource_name"]
        check(f"'{key}' proposal pending approval",
              proposals[key]["status"] in ("proposed", "pending_approval"),
              f"v{proposals[key]['version']} → {assigned}")
    check("Nothing dispatched before approval",
          resource_status(proposals["medical"]["assignment"]["resource_id"]) != "deployed"
          or latest_plan(incidents["medical"]["incident_id"])["status"] == "approved")

    # ── Human approval of the two initial plans
    step(5, f"Authorized user ({approver}) approves the initial plans")
    for key in ("medical", "rescue"):
        plan = proposals[key]
        if plan["status"] == "approved":
            print(f"  ({key} plan already approved)")
            continue
        status, body = approve(plan["plan_id"], approver, "Reviewed evidence in the demo")
        if check(f"{key} plan approved",
                 status == 200 and body.get("real_world_dispatch") is False,
                 str(body.get("message", ""))[:60]):
            print(f"    → {body['resource']['name']} deployed (application-internal only)")

    # ── Edge OFFLINE
    step(6, "Edge Gateway goes OFFLINE")
    status, body = call("POST", f"{EDGE_URL}/edge/connectivity", {"online": False})
    check("Gateway reports OFFLINE", status == 200 and body.get("mode") == "OFFLINE")

    # ── Queue a new SOS locally
    step(7, "New SOS is queued locally while offline")
    sos = fixtures["offline_sos"]
    status, body = call("POST", f"{EDGE_URL}/edge/incidents", {
        "description": sos["description"],
        "people_affected": sos["people_affected"],
        "latitude": sos["latitude"],
        "longitude": sos["longitude"],
    })
    packet_id = body.get("packet_id") if status == 201 else None
    check("Packet queued on the gateway", status == 201 and packet_id is not None,
          packet_id or str(body))

    status, body = call("GET", f"{EDGE_URL}/edge/queue?status=queued")
    check("Packet is stored in the local SQLite queue",
          any(p["packet_id"] == packet_id for p in body) if status == 200 else False)

    # ── Restart the gateway
    step(8, "Gateway restart — the queued SOS must survive")
    if args.no_restart_edge:
        print("  (--no-restart-edge: skipping the restart, verifying persistence only)")
    elif not restart_edge():
        check("Gateway restarted", False, "could not restart — is port 8001 owned by another user?")
    status, queue = call("GET", f"{EDGE_URL}/edge/queue")
    survived = any(p["packet_id"] == packet_id and p["status"] == "queued"
                   for p in queue) if status == 200 else False
    check("Queued SOS survived the restart", survived, packet_id or "")

    # ── Back online and sync
    step(9, "Connectivity restored — queued SOS synchronized (no duplicates)")
    call("POST", f"{EDGE_URL}/edge/connectivity", {"online": True})
    status, body = call("POST", f"{EDGE_URL}/edge/sync")
    results = body.get("results", []) if status == 200 else []
    synced = [r for r in results if r.get("success") and r["packet_id"] == packet_id]
    incident_id = synced[0].get("incident_id") if synced else None
    check("Packet synchronized to the backend", bool(incident_id), incident_id or str(body)[:80])

    before = len([
        i for i in all_incidents() if i.get("packet_id") == packet_id
    ])
    call("POST", f"{EDGE_URL}/edge/sync")  # second run must be a no-op
    after = len([
        i for i in all_incidents() if i.get("packet_id") == packet_id
    ])
    check("Repeated sync creates no duplicate incident", before == 1 and after == 1,
          f"{after} incident for packet {packet_id}")

    # The synced incident was ingested while the system was busy: pick it up now.
    status, report = call("POST", f"{BACKEND_URL}/api/replan?actor={approver}")
    report_dict = report if isinstance(report, dict) else {}
    picked_up = incident_id in (report_dict.get("plans_proposed") or []) or any(
        p["incident_id"] == incident_id for p in plans_for(incident_id)
    ) if incident_id and status == 200 else False
    synced_plan = latest_plan(incident_id) if incident_id else None
    check("Synced high-urgency SOS picked up for planning",
          bool(synced_plan) and synced_plan["status"] == "pending_approval",
          f"{synced_plan['trigger'] if synced_plan else 'no plan'}")

    # ── Route becomes unavailable
    step(10, "A previously usable route becomes unavailable")
    route_spec = fixtures["route"]
    route = find_route(route_spec["name"])
    if route is None:
        status, body = call("POST", f"{BACKEND_URL}/api/routes", {
            "name": route_spec["name"],
            "from_lat": route_spec["from_lat"], "from_lng": route_spec["from_lng"],
            "to_lat": route_spec["to_lat"], "to_lng": route_spec["to_lng"],
            "status": "open",
        })
        route = body["route"] if status == 201 else None
    check("Corridor exists and is open", route is not None and route["status"] == "open",
          route_spec["name"])

    rescue_incident = incidents["rescue"]["incident_id"]
    status, report = call("POST", f"{BACKEND_URL}/api/replan?actor={approver}")
    report_dict = report if isinstance(report, dict) else {}
    if status != 200:
        check("Replan endpoint responds", False, str(report)[:80])
    check("Open corridor affects no assignment",
          rescue_incident not in report_dict.get("affected_assignments", [])
          if status == 200 else False,
          str(report_dict.get("message", str(report)))[:60])

    status, body = call("PATCH", f"{BACKEND_URL}/api/routes/{route['route_id']}", {
        "status": "closed",
        "restriction_reason": route_spec["reason"],
        "actor": approver,
    })
    affected = body.get("affected_assignments", []) if status == 200 else []
    proposed = body.get("plans_proposed", []) if status == 200 else []
    check("Closing the corridor flags the affected assignment",
          rescue_incident in affected, ", ".join(affected) or "none")
    check("A revised plan was proposed (not applied)", len(proposed) == 1,
          ", ".join(proposed))

    plans = sorted(plans_for(rescue_incident), key=lambda p: p["version"])
    revised = plans[-1] if plans else None
    if revised and revised["version"] > 1:
        check("Revised plan explains what changed",
              revised["trigger"] == "route_closed" and bool(revised["rationale"]),
              f"v{revised['version']} trigger={revised['trigger']}")
        check("Revised plan proposes a different feasible resource",
              revised["assignment"]["resource_id"] not in (None, "RES-002"),
              str(revised["assignment"]["resource_name"]))
    else:
        check("Revised plan exists", False, "no version > 1 found")

    # ── Approve the revision
    step(11, "Authorized user reviews and approves the revised plan")
    if revised and revised["status"] in ("proposed", "pending_approval"):
        status, body = approve(revised["plan_id"], approver, "Route blocked — rerouted")
        check("Revised plan approved",
              status == 200 and body.get("released_resource_id") == "RES-002",
              f"now {body.get('resource', {}).get('name') if status == 200 else body}")
    else:
        print(f"  (revised plan status: {revised['status'] if revised else 'missing'})")

    check("New resource deployed, old one released",
          resource_status("DEMO-RES-02") == "deployed"
          and resource_status("RES-002") == "available")

    status, trail = call("GET", f"{BACKEND_URL}/api/incidents/{rescue_incident}/audit")
    events = [e["event_type"] for e in trail.get("events", [])] if status == 200 else []
    check("Audit trail records the whole decision chain",
          "plan_proposed" in events and "plan_approved" in events, " → ".join(events[:6]))

    # ── Summary
    print("\n" + "=" * 72)
    failed = [r for r in RESULTS if r[0] == FAIL]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    print("\nOpen the UI to explore the result:")
    print(f"  Dashboard   http://localhost:3000/")
    print(f"  Plans       http://localhost:3000/plans")
    print(f"  Incident    http://localhost:3000/incidents/{rescue_incident}")
    print("\nRemember: this is a simulation. Approving a plan only changes")
    print("application state — no real responders are dispatched.")
    print("=" * 72)

    return 1 if failed else 0


def cleanup(fixtures: dict) -> None:
    """Remove every [DEMO] incident and DEMO- resource."""
    demo_descriptions = {
        spec["description"] for spec in fixtures["incidents"]
    } | {fixtures["offline_sos"]["description"]}

    conn = sqlite3.connect(str(ROOT / "data" / "rescunet.db"))
    try:
        ids = [
            row[0] for row in conn.execute(
                "SELECT incident_id FROM incidents WHERE description LIKE '[DEMO]%'"
            ).fetchall()
        ]
        for incident_id in ids:
            conn.execute("DELETE FROM audit_events WHERE incident_id = ?", (incident_id,))
            conn.execute("DELETE FROM rescue_plans WHERE incident_id = ?", (incident_id,))
            conn.execute("DELETE FROM incident_triage WHERE incident_id = ?", (incident_id,))
            conn.execute("DELETE FROM response_plans WHERE incident_id = ?", (incident_id,))
            conn.execute("DELETE FROM incidents WHERE incident_id = ?", (incident_id,))
        conn.execute("DELETE FROM routes WHERE name LIKE '[DEMO]%'")
        conn.commit()
    finally:
        conn.close()

    res_conn = sqlite3.connect(str(RESOURCE_DB))
    try:
        res_conn.execute("DELETE FROM resources WHERE resource_id LIKE 'DEMO-%'")
        res_conn.commit()
    finally:
        res_conn.close()

    edge_conn = sqlite3.connect(str(ROOT / "edge" / "data" / "edge_queue.db"))
    try:
        edge_conn.execute("DELETE FROM edge_packets WHERE description LIKE '[DEMO]%'")
        edge_conn.commit()
    finally:
        edge_conn.close()


if __name__ == "__main__":
    sys.exit(main())
