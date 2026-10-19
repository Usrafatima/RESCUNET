"use client";

// Compact dashboard card: rescue plans waiting for a human decision.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Loader2,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import type { RescuePlan } from "@/lib/types";
import { approvePlan, getPlans, rejectPlan } from "@/lib/api";

const TRIGGER_LABEL: Record<string, string> = {
  initial: "initial plan",
  manual: "manual request",
  route_closed: "route closed",
  resource_unavailable: "resource unavailable",
  resource_unsuitable: "resource unsuitable",
  new_high_urgency: "high-urgency arrival",
  incident_changed: "incident changed",
};

export function PendingApprovals() {
  const [plans, setPlans] = useState<RescuePlan[]>([]);
  const [error, setError] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [approver, setApprover] = useState("Operator");

  const loadRef = useRef<() => void>(() => {});

  useEffect(() => {
    const load = () => {
      getPlans(undefined, "pending_approval")
        .then((res) => {
          setPlans(res.plans.filter((p) => p.status === "pending_approval"));
          setError(false);
        })
        .catch(() => setError(true));
    };
    loadRef.current = load;

    load();
    const interval = setInterval(() => loadRef.current(), 6000);
    const handler = () => loadRef.current();
    window.addEventListener("rescunet:refresh", handler);
    return () => {
      clearInterval(interval);
      window.removeEventListener("rescunet:refresh", handler);
    };
  }, []);

  const decide = async (plan: RescuePlan, approve: boolean) => {
    setBusyId(plan.plan_id);
    try {
      if (approve) {
        await approvePlan(plan.plan_id, {
          approver,
          decision_reason: "Approved from the command center",
        });
      } else {
        await rejectPlan(plan.plan_id, {
          approver,
          decision_reason: "Rejected from the command center",
        });
      }
      loadRef.current();
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));
    } catch (err) {
      setError(true);
      console.error("Plan decision failed", err);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="border-b border-card-border">
      <div className="px-4 py-2 border-b border-card-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert
            className={`h-3.5 w-3.5 ${plans.length > 0 ? "text-info" : "text-muted"}`}
          />
          <h3 className="text-[11px] font-semibold text-foreground">
            Pending Approvals
          </h3>
          {plans.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-tangerine/15 text-info border border-tangerine/40 font-mono font-bold">
              {plans.length}
            </span>
          )}
        </div>
        <button
          onClick={() => loadRef.current()}
          className="p-1 text-muted hover:text-foreground transition-colors"
          title="Refresh"
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>

      {error && (
        <div className="px-4 py-2 text-[10px] text-danger">
          Backend unreachable — approvals unavailable
        </div>
      )}

      {!error && plans.length === 0 && (
        <div className="px-4 py-2.5 text-[11px] text-muted">
          No proposals waiting for review.
        </div>
      )}

      <div className="divide-y divide-card-border/50">
        {plans.slice(0, 4).map((plan) => (
          <div key={plan.plan_id} className="px-4 py-2">
            <div className="flex items-center gap-2 mb-1">
              <GitBranch className="h-2.5 w-2.5 text-info shrink-0" />
              <Link
                href={`/incidents/${plan.incident_id}`}
                className="text-[11px] font-mono text-accent hover:underline"
              >
                {plan.incident_id}
              </Link>
              <span className="text-[9px] text-muted">
                v{plan.version} · {TRIGGER_LABEL[plan.trigger] ?? plan.trigger}
              </span>
            </div>

            {plan.assignment.resource_id ? (
              <p className="text-[10px] text-muted mb-1">
                → {plan.assignment.resource_name}{" "}
                <span className="font-mono">
                  ({plan.assignment.distance_km?.toFixed(1)} km)
                </span>
              </p>
            ) : (
              <p className="flex items-center gap-1 text-[10px] text-warning-ink mb-1">
                <AlertTriangle className="h-2.5 w-2.5" />
                No safe assignment — human review requested
              </p>
            )}

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => decide(plan, true)}
                disabled={busyId !== null || !plan.assignment.resource_id}
                className="flex items-center gap-1 px-2 py-1 bg-success text-white text-[9px] font-semibold rounded hover:bg-success-dim transition-colors disabled:opacity-40"
              >
                {busyId === plan.plan_id ? (
                  <Loader2 className="h-2.5 w-2.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-2.5 w-2.5" />
                )}
                APPROVE
              </button>
              <button
                onClick={() => decide(plan, false)}
                disabled={busyId !== null}
                className="flex items-center gap-1 px-2 py-1 border border-danger/30 text-danger text-[9px] font-semibold rounded hover:bg-danger/10 transition-colors disabled:opacity-40"
              >
                <XCircle className="h-2.5 w-2.5" />
                REJECT
              </button>
              <Link
                href={`/plans?incident=${plan.incident_id}`}
                className="ml-auto text-[9px] text-muted hover:text-foreground flex items-center"
              >
                Compare <ChevronRight className="h-2.5 w-2.5" />
              </Link>
            </div>
          </div>
        ))}
      </div>

      {plans.length > 0 && (
        <div className="px-4 py-2 border-t border-card-border">
          <label className="block">
            <span className="text-[9px] text-muted">
              COORDINATOR NAME (AUDIT)
            </span>
            <input
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              maxLength={80}
              className="mt-1 w-full bg-card border border-card-border rounded px-2 py-1 text-[11px] text-foreground focus:border-accent focus:ring-1 focus:ring-accent/30 outline-none"
            />
          </label>
        </div>
      )}
    </div>
  );
}
