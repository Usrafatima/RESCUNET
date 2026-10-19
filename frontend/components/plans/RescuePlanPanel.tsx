"use client";

// Rescue plan panel — triage, plan comparison and audit trail for one incident.

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  FileText,
  GitBranch,
  Loader2,
  ListChecks,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import type {
  AuditEvent,
  RescuePlan,
  TriageResult,
} from "@/lib/types";
import {
  createPlan,
  getAuditTrail,
  getIncidentPlans,
  getTriage,
  refreshTriage,
  replan,
} from "@/lib/api";
import { PlanComparison } from "./PlanComparison";

// ─── Urgency badge ──────────────────────────────────────────────────────────

function UrgencyBadge({ level }: { level: string }) {
  const color =
    level === "critical"
      ? "bg-danger/20 text-danger border-danger/30"
      : level === "high"
        ? "bg-accent/20 text-accent border-accent/30"
        : level === "medium"
          ? "bg-info/20 text-info border-info/30"
          : "bg-muted/20 text-muted border-muted/30";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border ${color}`}
    >
      {level.toUpperCase()}
    </span>
  );
}

// ─── Triage card ────────────────────────────────────────────────────────────

function TriageCard({
  triage,
  onRefreshAi,
  aiBusy,
}: {
  triage: TriageResult;
  onRefreshAi: () => void;
  aiBusy: boolean;
}) {
  const matched = triage.criteria.filter((c) => c.matched);
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      <div className="px-4 py-3 bg-info-dim/10 border-b border-card-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-info" />
          <span className="text-xs font-bold tracking-wider text-info">
            EMERGENCY TRIAGE
          </span>
        </div>
        <button
          onClick={onRefreshAi}
          disabled={aiBusy}
          className="flex items-center gap-1.5 px-2 py-1 text-[9px] tracking-wider font-bold text-muted border border-card-border rounded hover:text-foreground transition-colors disabled:opacity-50"
          title="Re-run triage with AI interpretation of the report text"
        >
          {aiBusy ? (
            <Loader2 className="h-2.5 w-2.5 animate-spin" />
          ) : (
            <Sparkles className="h-2.5 w-2.5" />
          )}
          AI INTERPRET
        </button>
      </div>

      <div className="p-4 space-y-3">
        {/* Level + type */}
        <div className="flex flex-wrap items-center gap-2">
          <UrgencyBadge level={triage.urgency_level} />
          <span className="inline-flex items-center px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border bg-muted/10 text-muted border-muted/30">
            {triage.incident_type.toUpperCase()}
          </span>
          <span className="text-[10px] font-mono text-muted">
            urgency {triage.urgency_score}/100 · {triage.criteria_version}
          </span>
        </div>

        {triage.insufficient_evidence && (
          <div className="flex items-start gap-2 rounded border border-warning/30 bg-warning-dim/10 px-3 py-2">
            <AlertTriangle className="h-3 w-3 mt-0.5 text-warning shrink-0" />
            <p className="text-[10px] text-muted leading-relaxed">
              Report contains little evidence. The conservative urgency level
              was applied — missing information never lowers urgency.
            </p>
          </div>
        )}

        {/* Criteria that fired */}
        <div>
          <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
            URGENCY CRITERIA (DOCUMENTED)
          </div>
          <div className="space-y-1">
            {matched.length === 0 && (
              <p className="text-[10px] text-muted">
                No criterion matched — conservative default applied.
              </p>
            )}
            {matched.map((c) => (
              <div
                key={c.rule_id}
                className="rounded border border-card-border bg-surface px-2.5 py-1.5"
              >
                <div className="flex items-center gap-2 text-[10px]">
                  <CheckCircle2 className="h-2.5 w-2.5 text-success" />
                  <span className="font-bold text-foreground">
                    {c.rule_id}
                  </span>
                  <span className="text-muted flex-1">{c.description}</span>
                </div>
                {c.evidence.length > 0 && (
                  <p className="text-[9px] font-mono text-info mt-1 pl-4.5">
                    evidence: {c.evidence.join(" · ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Extracted facts */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
              HAZARDS
            </div>
            {triage.hazards.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {triage.hazards.map((h) => (
                  <span
                    key={h}
                    className="px-1.5 py-0.5 text-[9px] tracking-wider rounded bg-danger-dim/20 text-danger border border-danger/20"
                  >
                    {h.toUpperCase()}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted">None detected</p>
            )}
          </div>
          <div>
            <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
              REQUESTED ASSISTANCE
            </div>
            {triage.requested_assistance.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {triage.requested_assistance.map((a) => (
                  <span
                    key={a}
                    className="px-1.5 py-0.5 text-[9px] tracking-wider rounded bg-info-dim/20 text-info border border-info/20"
                  >
                    {a.toUpperCase()}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-muted">Not stated</p>
            )}
          </div>
        </div>

        {/* Missing / uncertain */}
        {(triage.missing_info.length > 0 || triage.uncertain.length > 0) && (
          <div className="rounded border border-card-border bg-surface px-3 py-2 space-y-1">
            {triage.missing_info.length > 0 && (
              <>
                <div className="text-[9px] tracking-widest text-muted font-medium">
                  MISSING INFORMATION
                </div>
                {triage.missing_info.map((m) => (
                  <p key={m} className="text-[10px] text-muted leading-relaxed">
                    • {m}
                  </p>
                ))}
              </>
            )}
            {triage.uncertain.length > 0 && (
              <>
                <div className="text-[9px] tracking-widest text-warning font-medium pt-1">
                  UNCERTAIN / CONFLICTING
                </div>
                {triage.uncertain.map((u) => (
                  <p key={u} className="text-[10px] text-muted leading-relaxed">
                    • {u}
                  </p>
                ))}
              </>
            )}
          </div>
        )}

        {/* AI interpretation (advisory only) */}
        {triage.ai_summary && (
          <div className="rounded border border-info/25 bg-info-dim/5 px-3 py-2">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="h-3 w-3 text-info" />
              <span className="text-[9px] tracking-widest text-info font-bold">
                AI INTERPRETATION (ADVISORY)
              </span>
            </div>
            <p className="text-[10px] text-foreground/75 leading-relaxed">
              {triage.ai_summary}
            </p>
            <p className="text-[9px] text-muted mt-1">
              The urgency level above comes from documented rules; AI text can
              add context but never lowers a rule-derived level.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Audit trail ────────────────────────────────────────────────────────────

function AuditTrail({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return null;
  const label: Record<string, string> = {
    plan_proposed: "Plan proposed",
    plan_approved: "Plan approved by a human",
    plan_rejected: "Plan rejected",
    plan_stale: "Plan marked stale (conditions changed)",
    legacy_approval: "Approved via the classic approval workflow",
  };
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mt-4">
      <div className="px-4 py-2 border-b border-card-border flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 text-muted" />
        <span className="text-[10px] tracking-widest text-muted font-medium">
          AUDIT TRAIL ({events.length})
        </span>
      </div>
      <div className="p-3 space-y-1.5 max-h-56 overflow-y-auto">
        {events.map((event) => (
          <div key={event.event_id} className="flex items-start gap-2 text-[10px]">
            <span className="font-mono text-muted w-14 shrink-0">
              {new Date(event.created_at).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
              })}
            </span>
            <span className="text-foreground/80 flex-1">
              {label[event.event_type] ?? event.event_type}
              {typeof event.detail === "object" &&
                event.detail !== null &&
                "version" in event.detail && (
                  <span className="text-muted"> (v{String(event.detail.version)})</span>
                )}
              {event.actor && (
                <span className="text-muted"> — {event.actor}</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main panel ─────────────────────────────────────────────────────────────

interface RescuePlanPanelProps {
  incidentId: string;
  onChanged?: () => void;
}

export function RescuePlanPanel({ incidentId, onChanged }: RescuePlanPanelProps) {
  const [plans, setPlans] = useState<RescuePlan[]>([]);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const loadRef = useRef<() => void>(() => {});

  useEffect(() => {
    const load = () => {
      Promise.allSettled([
        getIncidentPlans(incidentId),
        getTriage(incidentId),
        getAuditTrail(incidentId),
      ])
        .then(([plansRes, triageRes, auditRes]) => {
          if (plansRes.status === "fulfilled") setPlans(plansRes.value.plans);
          if (triageRes.status === "fulfilled") setTriage(triageRes.value);
          if (auditRes.status === "fulfilled") setEvents(auditRes.value.events);
          if (
            plansRes.status === "rejected" &&
            triageRes.status === "rejected" &&
            auditRes.status === "rejected"
          ) {
            setError("Rescue planning API unreachable");
          } else {
            setError(null);
          }
          setLoading(false);
        })
        .catch(() => setError("Rescue planning API unreachable"));
    };
    loadRef.current = load;

    load();
    const handler = () => loadRef.current();
    window.addEventListener("rescunet:refresh", handler);
    return () => window.removeEventListener("rescunet:refresh", handler);
  }, [incidentId]);

  const handleGenerate = async () => {
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      const plan = await createPlan(incidentId);
      setNotice(
        `Plan v${plan.version} proposed — waiting for human approval. Nothing was dispatched.`,
      );
      loadRef.current();
      onChanged?.();
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a plan");
    } finally {
      setBusy(false);
    }
  };

  const handleReassess = async () => {
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      const report = await replan();
      setNotice(report.message);
      loadRef.current();
      onChanged?.();
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reassessment failed");
    } finally {
      setBusy(false);
    }
  };

  const handleAiInterpret = async () => {
    setAiBusy(true);
    try {
      const result = await refreshTriage(incidentId, true);
      setTriage(result);
      setNotice(
        result.ai_summary
          ? "AI interpretation added. The urgency level still comes from the documented rules."
          : "AI interpretation unavailable — no model is configured or the call failed. Rules-only triage shown.",
      );
    } catch (err) {
      setNotice(
        err instanceof Error
          ? `AI interpretation failed: ${err.message}`
          : "AI interpretation failed",
      );
    } finally {
      setAiBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading rescue plan…
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-accent" />
          <h2 className="text-[10px] tracking-widest text-muted font-medium">
            ADAPTIVE RESCUE PLAN
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadRef.current()}
            className="p-1 text-muted hover:text-foreground transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
          <button
            onClick={handleReassess}
            disabled={busy}
            className="flex items-center gap-1.5 px-2 py-1 text-[9px] tracking-wider font-bold text-muted border border-card-border rounded hover:text-foreground transition-colors disabled:opacity-50"
            title="Evaluate replanning triggers for all active assignments"
          >
            <ListChecks className="h-2.5 w-2.5" />
            REASSESS
          </button>
          <button
            onClick={handleGenerate}
            disabled={busy}
            className="flex items-center gap-1.5 px-2 py-1 text-[9px] tracking-wider font-bold text-accent border border-accent/30 rounded hover:bg-accent-dim/20 transition-colors disabled:opacity-50"
          >
            {busy ? (
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
            ) : (
              <Plus className="h-2.5 w-2.5" />
            )}
            GENERATE PLAN
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-[10px] text-danger mb-3">
          <AlertTriangle className="h-3 w-3" />
          {error}
        </div>
      )}
      {notice && (
        <div className="flex items-center gap-2 text-[10px] text-info mb-3">
          <CheckCircle2 className="h-3 w-3" />
          {notice}
        </div>
      )}

      {triage && (
        <TriageCard
          triage={triage}
          onRefreshAi={handleAiInterpret}
          aiBusy={aiBusy}
        />
      )}

      {plans.length > 0 ? (
        <PlanComparison
          plans={plans}
          onChanged={() => {
            loadRef.current();
            onChanged?.();
          }}
        />
      ) : (
        !error && (
          <div className="bg-card border border-card-border rounded-lg p-6 text-center">
            <GitBranch className="h-7 w-7 text-muted/30 mx-auto mb-2" />
            <p className="text-xs text-muted mb-1">No rescue plan yet.</p>
            <p className="text-[10px] text-muted/60">
              Generate a proposal to see the recommended assignment, the reason
              behind it, and alternatives. A human must approve before any
              assignment changes.
            </p>
          </div>
        )
      )}

      <AuditTrail events={events} />
    </div>
  );
}
