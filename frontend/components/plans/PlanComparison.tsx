"use client";

// Plan comparison — previous (approved) plan vs proposed revision.
// Labels are explicit: Proposed / Pending Approval / Approved / Stale / Rejected.

import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  GitBranch,
  Loader2,
  MapPin,
  Shield,
  Truck,
  Users,
  XCircle,
} from "lucide-react";
import type { RescuePlan, PlanStatusType } from "@/lib/types";
import { approvePlan, rejectPlan } from "@/lib/api";

// ─── Status badge ───────────────────────────────────────────────────────────

const STATUS_STYLES: Record<
  PlanStatusType,
  { label: string; className: string }
> = {
  proposed: {
    label: "PROPOSED",
    className: "bg-info-dim/20 text-info border-info/30",
  },
  pending_approval: {
    label: "PENDING APPROVAL",
    className: "bg-accent-dim/20 text-accent border-accent/30",
  },
  approved: {
    label: "APPROVED",
    className: "bg-success-dim/20 text-success border-success/30",
  },
  rejected: {
    label: "REJECTED",
    className: "bg-danger-dim/20 text-danger border-danger/30",
  },
  superseded: {
    label: "SUPERSEDED",
    className: "bg-muted/10 text-muted border-muted/30",
  },
  stale: {
    label: "STALE",
    className: "bg-warning-dim/20 text-warning border-warning/30",
  },
};

export function PlanStatusBadge({ status }: { status: PlanStatusType }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.proposed;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border ${style.className}`}
    >
      {style.label}
    </span>
  );
}

function TriggerBadge({ trigger }: { trigger: string }) {
  const label = trigger.replace(/_/g, " ").toUpperCase();
  const isReplan = trigger !== "initial" && trigger !== "manual";
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border ${
        isReplan
          ? "bg-warning-dim/15 text-warning border-warning/30"
          : "bg-muted/10 text-muted border-muted/30"
      }`}
    >
      <GitBranch className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}

// ─── Assignment summary ─────────────────────────────────────────────────────

function AssignmentBlock({
  plan,
  tone,
}: {
  plan: RescuePlan | null;
  tone: "previous" | "proposed";
}) {
  if (!plan || !plan.assignment.resource_id) {
    return (
      <div className="p-3 rounded border border-dashed border-card-border bg-surface/50">
        <div className="text-[9px] tracking-widest text-muted mb-1">
          {tone === "previous" ? "PREVIOUS ASSIGNMENT" : "PROPOSED ASSIGNMENT"}
        </div>
        <div className="flex items-center gap-2 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" />
          No safe automatic assignment
        </div>
        {plan && plan.shortages.length > 0 && (
          <ul className="mt-2 space-y-1">
            {plan.shortages.map((s) => (
              <li key={s} className="text-[10px] text-muted leading-relaxed">
                • {s}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  const isProposed = tone === "proposed";
  return (
    <div
      className={`p-3 rounded border ${
        isProposed
          ? "border-accent/30 bg-accent-dim/10"
          : "border-success/30 bg-success-dim/10"
      }`}
    >
      <div className="text-[9px] tracking-widest text-muted mb-1">
        {isProposed ? "PROPOSED ASSIGNMENT" : "PREVIOUS ASSIGNMENT"}
      </div>
      <div className="flex items-center gap-2">
        {isProposed ? (
          <Truck className="h-3.5 w-3.5 text-accent" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 text-success" />
        )}
        <span
          className={`text-sm font-bold ${
            isProposed ? "text-accent" : "text-success"
          }`}
        >
          {plan.assignment.resource_name}
        </span>
      </div>
      <div className="text-[10px] font-mono text-muted mt-0.5">
        {plan.assignment.resource_id} ·{" "}
        {(plan.assignment.resource_type ?? "").toUpperCase()}
      </div>
      <div className="flex items-center gap-3 mt-2 text-[10px] text-muted">
        {plan.assignment.distance_km !== null && (
          <span className="flex items-center gap-1">
            <MapPin className="h-2.5 w-2.5" />
            {plan.assignment.distance_km.toFixed(2)} km
          </span>
        )}
        {plan.assignment.match_score !== null && (
          <span className="flex items-center gap-1">
            <Shield className="h-2.5 w-2.5" />
            {plan.assignment.match_score.toFixed(0)}/100
          </span>
        )}
        <span className="flex items-center gap-1">
          <Clock className="h-2.5 w-2.5" />
          v{plan.version}
        </span>
      </div>
    </div>
  );
}

// ─── Main comparison component ──────────────────────────────────────────────

interface PlanComparisonProps {
  /** Full plan history for the incident, newest version first. */
  plans: RescuePlan[];
  /** Called after a decision so the parent can refresh. */
  onChanged?: () => void;
  /** Show the compact history list (default true). */
  showHistory?: boolean;
}

export function PlanComparison({
  plans,
  onChanged,
  showHistory = true,
}: PlanComparisonProps) {
  const [approver, setApprover] = useState("Operator");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<
    { planId: string; outcome: "approved" | "rejected"; message: string } | null
  >(null);

  const ordered = [...plans].sort((a, b) => b.version - a.version);
  const pending =
    ordered.find((p) => p.status === "pending_approval" || p.status === "proposed") ??
    null;
  const approved = ordered.find((p) => p.status === "approved") ?? null;
  const previous = pending?.previous_plan_id
    ? ordered.find((p) => p.plan_id === pending.previous_plan_id) ?? approved
    : approved;

  if (plans.length === 0) return null;

  const handleApprove = async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      const result = await approvePlan(pending.plan_id, {
        approver,
        decision_reason: "Approved from plan comparison view",
      });
      setDecision({
        planId: pending.plan_id,
        outcome: "approved",
        message: result.message,
      });
      onChanged?.();
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await rejectPlan(pending.plan_id, {
        approver,
        decision_reason: "Rejected from plan comparison view",
      });
      setDecision({
        planId: pending.plan_id,
        outcome: "rejected",
        message: "Proposal rejected — no assignment was changed.",
      });
      onChanged?.();
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* ── Active comparison ── */}
      {pending ? (
        <div className="bg-card border border-accent/30 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-card-border flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-accent" />
              <span className="text-xs font-bold tracking-wider text-accent">
                PLAN v{pending.version} — CHANGE PROPOSED
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <TriggerBadge trigger={pending.trigger} />
              <PlanStatusBadge status={pending.status} />
            </div>
          </div>

          {/* What changed */}
          <div className="px-4 py-3 border-b border-card-border">
            <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
              WHAT CHANGED
            </div>
            <p className="text-xs text-foreground/85 leading-relaxed">
              {pending.trigger_detail || pending.rationale}
            </p>
            <div className="mt-2 flex items-start gap-2 text-[10px] text-muted">
              <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0 text-warning" />
              <span>
                Human approval is required before any assignment changes.
                Nothing has been dispatched.
              </span>
            </div>
          </div>

          {/* Side-by-side comparison */}
          <div className="px-4 py-3 grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-2 items-stretch">
            <AssignmentBlock plan={previous} tone="previous" />
            <div className="flex items-center justify-center">
              <ArrowRight className="h-4 w-4 text-muted rotate-90 sm:rotate-0" />
            </div>
            <AssignmentBlock plan={pending} tone="proposed" />
          </div>

          {/* Rationale */}
          <div className="px-4 pb-3">
            <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
              WHY THIS RECOMMENDATION
            </div>
            <p className="text-[11px] text-foreground/75 leading-relaxed">
              {pending.rationale}
            </p>
          </div>

          {/* Alternatives + shortages */}
          {(pending.alternatives.length > 0 ||
            pending.shortages.length > 0 ||
            pending.review_reasons.length > 0) && (
            <div className="px-4 pb-3 space-y-2">
              {pending.alternatives.length > 0 && (
                <div>
                  <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
                    ALTERNATIVE ASSIGNMENTS CONSIDERED
                  </div>
                  <div className="space-y-1">
                    {pending.alternatives.map((alt) => (
                      <div
                        key={alt.resource_id}
                        className="flex items-center justify-between text-[10px] px-2 py-1 rounded bg-surface border border-card-border"
                      >
                        <span className="text-foreground/80">
                          {alt.name}{" "}
                          <span className="font-mono text-muted">
                            ({alt.resource_id})
                          </span>
                        </span>
                        <span className="text-muted">
                          {alt.distance_km.toFixed(1)} km ·{" "}
                          {alt.match_score.toFixed(0)}/100
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {pending.shortages.length > 0 && (
                <div className="rounded border border-warning/30 bg-warning-dim/10 px-3 py-2">
                  <div className="text-[9px] tracking-widest text-warning font-bold mb-1">
                    RESOURCE SHORTAGES
                  </div>
                  {pending.shortages.map((s) => (
                    <p key={s} className="text-[10px] text-muted leading-relaxed">
                      • {s}
                    </p>
                  ))}
                </div>
              )}

              {pending.review_reasons.length > 0 && (
                <div className="rounded border border-info/30 bg-info-dim/10 px-3 py-2">
                  <div className="text-[9px] tracking-widest text-info font-bold mb-1">
                    HUMAN REVIEW REQUESTED
                  </div>
                  {pending.review_reasons.map((r) => (
                    <p key={r} className="text-[10px] text-muted leading-relaxed">
                      • {r}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Decision controls */}
          {decision && decision.planId === pending.plan_id ? (
            <div
              className={`px-4 py-3 border-t border-card-border ${
                decision.outcome === "approved"
                  ? "bg-success-dim/10"
                  : "bg-danger-dim/10"
              }`}
            >
              <div
                className={`flex items-center gap-2 text-xs font-bold tracking-wider ${
                  decision.outcome === "approved" ? "text-success" : "text-danger"
                }`}
              >
                {decision.outcome === "approved" ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <XCircle className="h-3.5 w-3.5" />
                )}
                PLAN v{pending.version} {decision.outcome.toUpperCase()}
              </div>
              <p className="text-[10px] text-muted mt-1">{decision.message}</p>
              {decision.outcome === "approved" && (
                <p className="text-[10px] text-warning mt-1">
                  ✦ No real-world dispatch was performed — this is an
                  application-internal assignment only.
                </p>
              )}
            </div>
          ) : (
            <div className="px-4 py-3 border-t border-card-border space-y-2">
              <label className="block">
                <span className="text-[9px] tracking-widest text-muted font-medium">
                  APPROVING COORDINATOR (RECORDED IN AUDIT TRAIL)
                </span>
                <input
                  value={approver}
                  onChange={(e) => setApprover(e.target.value)}
                  maxLength={80}
                  className="mt-1 w-full bg-surface border border-card-border rounded px-2 py-1.5 text-xs text-foreground focus:outline-none focus:border-accent/50"
                  placeholder="Name of the authorized person"
                />
              </label>
              {error && (
                <div className="flex items-center gap-2 text-[10px] text-danger">
                  <XCircle className="h-3 w-3" />
                  {error}
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={handleApprove}
                  disabled={busy || !approver.trim()}
                  className="flex items-center gap-2 px-3 py-1.5 bg-success text-white text-[10px] font-bold tracking-wider rounded hover:bg-success/90 transition-colors disabled:opacity-50"
                >
                  {busy ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3" />
                  )}
                  APPROVE REVISED PLAN
                </button>
                <button
                  onClick={handleReject}
                  disabled={busy}
                  className="flex items-center gap-2 px-3 py-1.5 border border-danger/30 text-danger text-[10px] font-bold tracking-wider rounded hover:bg-danger-dim/20 transition-colors disabled:opacity-50"
                >
                  <XCircle className="h-3 w-3" />
                  REJECT
                </button>
              </div>
            </div>
          )}
        </div>
      ) : approved ? (
        /* ── Approved, nothing pending ── */
        <div className="bg-card border border-success/30 rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-card-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <span className="text-xs font-bold tracking-wider text-success">
                PLAN v{approved.version} APPROVED
              </span>
            </div>
            <PlanStatusBadge status="approved" />
          </div>
          <div className="px-4 py-3">
            <AssignmentBlock plan={approved} tone="previous" />
            <div className="mt-2 text-[10px] text-muted flex items-center gap-2">
              <Users className="h-3 w-3" />
              Approved by {approved.decided_by ?? "unknown"} ·{" "}
              {approved.decided_at
                ? new Date(approved.decided_at).toLocaleString("en-US", {
                    month: "short",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                  })
                : "—"}
            </div>
            {approved.decision_reason && (
              <p className="mt-1 text-[10px] text-foreground/70">
                “{approved.decision_reason}”
              </p>
            )}
            <p className="mt-2 text-[10px] text-warning">
              ✦ Application-internal assignment only — no real dispatch occurs.
            </p>
          </div>
        </div>
      ) : null}

      {/* ── History ── */}
      {showHistory && (
        <div className="bg-card border border-card-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-card-border">
            <span className="text-[10px] tracking-widest text-muted font-medium">
              PLAN HISTORY ({ordered.length})
            </span>
          </div>
          <div className="divide-y divide-card-border/50">
            {ordered.map((plan) => (
              <div
                key={plan.plan_id}
                className="px-4 py-2 flex items-center gap-2 text-[10px]"
              >
                <span className="font-mono text-muted w-8">v{plan.version}</span>
                <TriggerBadge trigger={plan.trigger} />
                <span className="text-foreground/70 truncate flex-1">
                  {plan.assignment.resource_name ?? "no safe assignment"}
                </span>
                <span className="text-muted hidden sm:inline">
                  {new Date(plan.created_at).toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: false,
                  })}
                </span>
                <PlanStatusBadge status={plan.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
