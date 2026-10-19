"use client";

// Rescue plan review page — pending proposals, previous-vs-proposed
// comparison and the replanning trigger evaluation.

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  GitBranch,
  ListChecks,
  Loader2,
  MapPin,
  RefreshCw,
  XCircle,
} from "lucide-react";
import type { DetectedChange, RescuePlan } from "@/lib/types";
import { getPlans, getReplanChanges, replan } from "@/lib/api";
import { PlanComparison, PlanStatusBadge } from "@/components/plans/PlanComparison";

const TRIGGER_LABEL: Record<string, string> = {
  initial: "INITIAL",
  manual: "MANUAL",
  route_closed: "ROUTE CLOSED",
  resource_unavailable: "RESOURCE UNAVAILABLE",
  resource_unsuitable: "RESOURCE UNSUITABLE",
  new_high_urgency: "HIGH-URGENCY ARRIVAL",
  incident_changed: "INCIDENT CHANGED",
};

function ChangeRow({ change }: { change: DetectedChange }) {
  return (      <div className="px-3 py-1.5 border-b border-card-border/50 last:border-b-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-warning/15 text-warning-ink border border-warning/40 font-bold">
            {TRIGGER_LABEL[change.trigger] ?? change.trigger}
          </span>
          <Link
            href={`/incidents/${change.incident_id}`}
            className="text-[10px] font-mono text-accent hover:underline"
          >
            {change.incident_id}
          </Link>
        </div>
        <p className="text-[11px] text-muted leading-relaxed">
          {change.detail}
        </p>
      </div>
  );
}

function PlansContent() {
  const searchParams = useSearchParams();
  const focusIncident = searchParams.get("incident");

  const [plans, setPlans] = useState<RescuePlan[]>([]);
  const [changes, setChanges] = useState<DetectedChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(
    focusIncident ?? null,
  );

  const loadRef = useRef<() => void>(() => {});

  useEffect(() => {
    const load = () => {
      Promise.allSettled([getPlans(), getReplanChanges()])
        .then(([plansRes, changesRes]) => {
          if (plansRes.status === "fulfilled") {
            setPlans(plansRes.value.plans);
            setError(null);
          } else {
            setError("Rescue planning API unreachable — is the backend running?");
          }
          if (changesRes.status === "fulfilled") setChanges(changesRes.value.changes);
          setLoading(false);
        })
        .catch(() =>
          setError("Rescue planning API unreachable — is the backend running?"),
        );
    };
    loadRef.current = load;

    load();
    const handler = () => loadRef.current();
    window.addEventListener("rescunet:refresh", handler);
    return () => window.removeEventListener("rescunet:refresh", handler);
  }, []);

  const handleEvaluate = async () => {
    setEvaluating(true);
    setReport(null);
    try {
      const result = await replan();
      setReport(result.message);
      loadRef.current();
    } catch (err) {
      setReport(err instanceof Error ? err.message : "Evaluation failed");
    } finally {
      setEvaluating(false);
    }
  };

  const openPlans = plans.filter(
    (p) => p.status === "pending_approval" || p.status === "proposed",
  );
  const incidentIds = Array.from(
    new Set(openPlans.map((p) => p.incident_id)),
  );
  const activeIncident = selected ?? incidentIds[0] ?? null;
  const incidentPlans = activeIncident
    ? plans.filter((p) => p.incident_id === activeIncident)
    : [];

  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-2.5 border-b border-card-border bg-surface sticky top-0 z-10">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/"
            className="p-1 text-muted hover:text-accent transition-colors"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-base font-semibold tracking-wide">
              Rescue Plans
            </h1>
            <p className="text-[11px] text-muted truncate">
              Proposed assignments awaiting human decision
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadRef.current()}
            className="p-1.5 text-muted hover:text-accent transition-colors"
            title="Refresh"
            aria-label="Refresh plans"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={handleEvaluate}
            disabled={evaluating}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-semibold rounded-md hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {evaluating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <ListChecks className="h-3.5 w-3.5" />
            )}
            EVALUATE TRIGGERS
          </button>
        </div>
      </div>

      {/* Simulation notice */}
      <div className="px-4 md:px-6 py-1.5 border-b border-card-border bg-tangerine/10 flex items-center gap-2">
        <AlertTriangle className="h-3.5 w-3.5 text-info shrink-0" />
        <p className="text-[11px] text-muted">
          Plans are recommendations only. Approving changes application state
          (an internal assignment record) — it never dispatches real
          responders. Incidents created by the demo script are labelled
          <span className="font-mono text-foreground"> [DEMO]</span> in their
          description.
        </p>
      </div>

      {error && (
        <div className="px-6 py-3 text-xs text-danger flex items-center gap-2">
          <XCircle className="h-4 w-4" />
          {error}
        </div>
      )}
      {report && (
        <div className="px-6 py-2 text-xs text-info flex items-center gap-2">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {report}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 text-muted animate-spin" />
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] min-h-0">
          {/* Left: incident list + detected changes */}
          <div className="border-b lg:border-b-0 lg:border-r border-card-border overflow-y-auto">
            <div className="px-4 py-2 border-b border-card-border bg-surface">
              <span className="text-[11px] font-semibold text-foreground">
                Awaiting decision ({incidentIds.length})
              </span>
            </div>
            {incidentIds.length === 0 && (
              <div className="px-4 py-3 text-[11px] text-muted">
                No proposals are waiting for review.
              </div>
            )}
            {incidentIds.map((id) => {
              const latest = plans.find(
                (p) => p.incident_id === id && p.status === "pending_approval",
              );
              return (
                <button
                  key={id}
                  onClick={() => setSelected(id)}
                  className={`w-full text-left px-4 py-2 border-b border-card-border/50 transition-colors ${
                    activeIncident === id
                      ? "bg-card border-l-2 border-l-accent"
                      : "hover:bg-card border-l-2 border-l-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <GitBranch className="h-3 w-3 text-info shrink-0" />
                    <span className="text-xs font-mono text-accent">{id}</span>
                    <span className="ml-auto text-[9px] text-muted">
                      v{latest?.version}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="text-[9px] text-muted">
                      {TRIGGER_LABEL[latest?.trigger ?? "initial"]}
                    </span>
                    {latest?.assignment.resource_id ? (
                      <span className="text-[10px] text-muted truncate">
                        → {latest.assignment.resource_name}
                      </span>
                    ) : (
                      <span className="text-[10px] text-warning-ink flex items-center gap-1">
                        <AlertTriangle className="h-2.5 w-2.5" />
                        review required
                      </span>
                    )}
                  </div>
                </button>
              );
            })}

            <div className="px-4 py-2 border-b border-card-border bg-surface mt-2">
              <span className="text-[11px] font-semibold text-foreground">
                Detected changes
              </span>
            </div>
            {changes.length === 0 ? (
              <div className="px-4 py-3 text-[11px] text-muted">
                No assignment changes detected right now.
              </div>
            ) : (
              changes.map((change, i) => (
                <ChangeRow
                  key={`${change.incident_id}-${change.field}-${i}`}
                  change={change}
                />
              ))
            )}
          </div>

          {/* Right: comparison */}
          <div className="p-4 overflow-y-auto">
            {activeIncident ? (
              <>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-mono text-accent">
                    {activeIncident}
                  </span>
                  <Link
                    href={`/incidents/${activeIncident}`}
                    className="text-[10px] text-muted hover:text-foreground"
                  >
                    open incident →
                  </Link>
                </div>
                <PlanComparison plans={incidentPlans} onChanged={() => loadRef.current()} />
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <GitBranch className="h-8 w-8 text-muted/30 mb-3" />
                <p className="text-sm text-muted mb-1">Nothing to review</p>
                <p className="text-xs text-muted/70 max-w-sm">
                  When the system proposes a plan — on arrival of a high-urgency
                  report, or after a route/responder change — it appears here
                  with a previous-vs-proposed comparison.
                </p>
              </div>
            )}

            {/* All plans overview */}
            {plans.length > 0 && (
              <div className="mt-4 bg-card border border-card-border rounded-md overflow-hidden">
                <div className="px-4 py-2 border-b border-card-border bg-surface">
                  <span className="text-[11px] font-semibold text-foreground">
                    All plans ({plans.length})
                  </span>
                </div>
                <div className="divide-y divide-card-border/50">
                  {plans.map((plan) => (
                    <button
                      key={plan.plan_id}
                      onClick={() => setSelected(plan.incident_id)}
                      className="w-full text-left px-4 py-2 flex items-center gap-2 text-[10px] hover:bg-surface transition-colors"
                    >
                      <span className="font-mono text-accent">
                        {plan.incident_id}
                      </span>
                      <span className="font-mono text-muted">v{plan.version}</span>
                      <span className="text-muted truncate flex-1 flex items-center gap-1">
                        <MapPin className="h-2.5 w-2.5 text-muted" />
                        {plan.assignment.resource_name ?? "no safe assignment"}
                      </span>
                      <PlanStatusBadge status={plan.status} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PlansPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-6 w-6 text-muted animate-spin" />
        </div>
      }
    >
      <PlansContent />
    </Suspense>
  );
}
