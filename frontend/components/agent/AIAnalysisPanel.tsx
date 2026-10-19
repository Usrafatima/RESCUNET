"use client";

import { useState } from "react";
import {
  Bot,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Shield,
  MapPin,
  ArrowDown,
  Loader2,
  Truck,
  Zap,
} from "lucide-react";
import type {
  AgentAnalysisResult,
  StructuredRecommendation,
  ApprovalResponse,
} from "@/lib/types";
import { approveRecommendation } from "@/lib/api";

type ApprovalState = "none" | "pending" | "approved" | "rejected" | "error";

interface AIAnalysisPanelProps {
  result: AgentAnalysisResult;
  incidentId: string;
  onRetry: () => void;
  onApprovalChange?: (state: ApprovalState) => void;
}

// ─── Priority / type badges ──────────────────────────────────────────

function PriorityBadge({ priority }: { priority: string }) {
  const color =
    priority === "critical"
      ? "bg-danger/20 text-danger border-danger/30"
      : priority === "high"
      ? "bg-warning/20 text-warning border-warning/30"
      : priority === "medium"
      ? "bg-info/20 text-info border-info/30"
      : "bg-muted/20 text-muted border-muted/30";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border ${color}`}
    >
      {priority.toUpperCase()}
    </span>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 text-[9px] tracking-widest font-bold rounded border bg-accent/10 text-accent border-accent/20">
      {type.toUpperCase()}
    </span>
  );
}

// ─── Agent workflow pipeline ──────────────────────────────────────────

function AgentWorkflow({ completed }: { completed: boolean }) {
  const steps = [
    "INCIDENT",
    "GET INCIDENT",
    "ASSESS",
    "FIND RESOURCES",
    "CHECK AVAILABILITY",
    "CALCULATE DISTANCE",
    "RECOMMEND",
    "HUMAN APPROVAL",
  ];
  return (
    <div className="mb-4">
      <div className="text-[9px] tracking-widest text-muted font-medium mb-2">
        AGENT PIPELINE
      </div>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
        {steps.map((step, i) => (
          <div key={step} className="flex items-center">
            <div
              className={`px-2 py-1 text-[9px] tracking-wider font-medium rounded ${
                completed
                  ? "bg-success-dim/20 text-success border border-success/20"
                  : "bg-info-dim/15 text-info border border-info/20"
              }`}
            >
              {step}
            </div>
            {i < steps.length - 1 && (
              <ArrowDown
                className={`h-2.5 w-2.5 mx-0.5 rotate-[-90deg] ${
                  completed ? "text-success/50" : "text-info/30"
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Classification card ──────────────────────────────────────────────

function ClassificationCard({
  rec,
}: {
  rec: StructuredRecommendation;
}) {
  const cls = rec.classification;
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      <div className="px-4 py-3 bg-accent-dim/10 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-accent" />
          <span className="text-xs font-bold tracking-wider text-accent">
            INCIDENT CLASSIFICATION
          </span>
        </div>
      </div>
      <div className="p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <TypeBadge type={cls.type} />
          <PriorityBadge priority={cls.priority} />
          <span className="text-[9px] tracking-widest text-muted">
            {cls.people_affected} PEOPLE AFFECTED
          </span>
        </div>
        <div>
          <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
            IMMEDIATE NEED
          </div>
          <div className="text-sm text-foreground/90">
            {cls.immediate_need}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Recommendation card ──────────────────────────────────────────────

function RecommendationCard({
  rec,
}: {
  rec: StructuredRecommendation;
}) {
  const act = rec.recommended_action;
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      <div className="px-4 py-3 bg-success-dim/10 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-success" />
          <span className="text-xs font-bold tracking-wider text-success">
            RECOMMENDED RESOURCE
          </span>
        </div>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
            RESOURCE
          </div>
          <div className="text-sm font-bold text-success">
            {act.resource_name}
          </div>
          <div className="text-[10px] font-mono text-muted">
            {act.resource_id} · {act.resource_type.toUpperCase()}
          </div>
        </div>

        <div>
          <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
            DISTANCE TO INCIDENT
          </div>
          <div className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 text-info" />
            <span className="text-lg font-bold font-mono text-info">
              {act.distance_km.toFixed(1)} km
            </span>
          </div>
        </div>

        <div>
          <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
            REASONING
          </div>
          <p className="text-xs text-foreground/80 italic leading-relaxed">
            {act.reason}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Fallback text display (when structured extraction failed) ────────

function RawAnalysisDisplay({ text }: { text: string }) {
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      <div className="px-4 py-3 bg-accent-dim/10 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-accent" />
          <span className="text-xs font-bold tracking-wider text-accent">
            AI ANALYSIS (RAW)
          </span>
        </div>
      </div>
      <div className="p-4">
        <div className="text-sm text-foreground/90 whitespace-pre-wrap font-mono leading-relaxed">
          {text}
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────

export function AIAnalysisPanel({
  result,
  incidentId,
  onRetry,
  onApprovalChange,
}: AIAnalysisPanelProps) {
  const [approvalState, setApprovalState] = useState<ApprovalState>("none");
  const [approvalResult, setApprovalResult] =
    useState<ApprovalResponse | null>(null);
  const [approving, setApproving] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  const recommendation = result.recommendation;

  const handleApprove = async () => {
    if (!recommendation) {
      setApprovalError(
        "No valid structured recommendation available. Please re-analyze."
      );
      setApprovalState("error");
      onApprovalChange?.("error");
      return;
    }

    setApproving(true);
    setApprovalError(null);
    setApprovalState("pending");
    onApprovalChange?.("pending");

    try {
      const response = await approveRecommendation(incidentId, {
        resource_id: recommendation.recommended_action.resource_id,
        distance_km: recommendation.recommended_action.distance_km,
        reason: recommendation.recommended_action.reason,
      });
      setApprovalResult(response);
      setApprovalState("approved");
      onApprovalChange?.("approved");
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("rescunet:refresh"));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Approval failed";
      setApprovalError(msg);
      setApprovalState("error");
      onApprovalChange?.("error");
    } finally {
      setApproving(false);
    }
  };

  const handleReject = () => {
    setApprovalState("rejected");
    onApprovalChange?.("rejected");
  };

  return (
    <div className="space-y-4">
      {/* Agent workflow pipeline */}
      <AgentWorkflow completed={true} />

      {/* ─── Structured recommendation ─────────────────────────────── */}
      {recommendation ? (
        <>
          <ClassificationCard rec={recommendation} />
          <RecommendationCard rec={recommendation} />
        </>
      ) : (
        <>
          <RawAnalysisDisplay text={result.analysis} />
          <div className="rounded-lg border border-warning/30 bg-warning-dim/10 px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-warning font-bold tracking-wider mb-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              STRUCTURED RECOMMENDATION NOT EXTRACTED
            </div>
            <p className="text-xs text-muted">
              AI analysis completed, but no valid resource recommendation was
              produced in structured format. You can re-analyze to try again.
            </p>
          </div>
        </>
      )}

      {/* ─── Human Approval Decision Center ─────────────────────────── */}

      {/* PENDING / NONE state */}
      {approvalState !== "approved" &&
        approvalState !== "rejected" &&
        approvalState !== "error" && (
          <div className="rounded-lg border border-accent/30 bg-accent-dim/10 overflow-hidden">
            <div className="px-4 py-3 border-b border-card-border/30">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-accent" />
                <span className="text-xs font-bold tracking-wider text-accent">
                  {approving
                    ? "PROCESSING APPROVAL..."
                    : "HUMAN APPROVAL REQUIRED"}
                </span>
              </div>
            </div>
            <div className="px-4 py-3">
              <p className="text-xs text-muted mb-3">
                The AI agent has produced a recommendation. A human coordinator
                must approve before any response is dispatched.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleApprove}
                  disabled={approving || !recommendation}
                  className="flex items-center gap-2 px-4 py-2 bg-success text-white text-xs font-bold tracking-wider rounded hover:bg-success/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {approving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  {approving ? "APPROVING..." : "APPROVE RESPONSE"}
                </button>
                <button
                  onClick={handleReject}
                  disabled={approving}
                  className="flex items-center gap-2 px-4 py-2 border border-danger/30 text-danger text-xs font-bold tracking-wider rounded hover:bg-danger-dim/20 transition-colors disabled:opacity-50"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  REJECT
                </button>
              </div>
              {!recommendation && (
                <p className="text-[10px] text-warning mt-2">
                  Approve is disabled because no structured recommendation was
                  extracted.
                </p>
              )}
            </div>
          </div>
        )}

      {/* ERROR state */}
      {approvalState === "error" && (
        <div className="rounded-lg border border-danger/30 bg-danger-dim/10 overflow-hidden">
          <div className="px-4 py-3 border-b border-card-border/30">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-danger" />
              <span className="text-xs font-bold tracking-wider text-danger">
                APPROVAL FAILED
              </span>
            </div>
          </div>
          <div className="px-4 py-3">
            <p className="text-xs text-muted mb-1">{approvalError}</p>
            <p className="text-[10px] text-muted/60 mb-3">
              The incident is still safely stored. No response was dispatched.
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                disabled={!recommendation}
                className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-bold tracking-wider text-accent border border-accent/30 rounded hover:bg-accent-dim/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                RETRY APPROVAL
              </button>
              <button
                onClick={onRetry}
                className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-bold tracking-wider text-muted border border-card-border rounded hover:bg-card transition-colors"
              >
                <RotateCcw className="h-3 w-3" />
                RE-ANALYZE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REJECTED state */}
      {approvalState === "rejected" && (
        <div className="rounded-lg border border-danger/30 bg-danger-dim/10 overflow-hidden">
          <div className="px-4 py-3 border-b border-card-border/30">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-danger" />
              <span className="text-xs font-bold tracking-wider text-danger">
                RESPONSE REJECTED
              </span>
            </div>
          </div>
          <div className="px-4 py-3">
            <div className="space-y-1 text-xs text-muted mb-3">
              <p>No response plan was created.</p>
              <p>No resource was assigned.</p>
              <p>No dispatch occurred.</p>
            </div>
            <button
              onClick={onRetry}
              className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-bold tracking-wider text-accent border border-accent/30 rounded hover:bg-accent-dim/20 transition-colors"
            >
              <RotateCcw className="h-3 w-3" />
              RUN ANALYSIS AGAIN
            </button>
          </div>
        </div>
      )}

      {/* ─── APPROVED — Response Dispatch Center ────────────────────── */}
      {approvalState === "approved" && approvalResult && (
        <div className="space-y-4">
          {/* Approval confirmation */}
          <div className="rounded-lg border border-success/30 bg-success-dim/10 overflow-hidden">
            <div className="px-4 py-3 border-b border-card-border/30">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-xs font-bold tracking-wider text-success">
                  RESPONSE APPROVED
                </span>
              </div>
            </div>
            <div className="px-4 py-3">
              <p className="text-xs text-success/80">
                Human authorization received
              </p>
            </div>
          </div>

          {/* Response Plan */}
          <div className="bg-card border border-card-border rounded-lg overflow-hidden">
            <div className="px-4 py-3 bg-surface border-b border-card-border">
              <div className="flex items-center gap-2">
                <Truck className="h-4 w-4 text-info" />
                <span className="text-xs font-bold tracking-wider text-info">
                  RESPONSE PLAN
                </span>
              </div>
            </div>
            <div className="p-4 space-y-3">
              <PlanRow
                label="INCIDENT"
                value={approvalResult.incident_id}
                mono
              />
              <PlanRow
                label="RECOMMENDED RESOURCE"
                value={approvalResult.resource.name}
                highlight
              />
              <PlanRow
                label="RESOURCE ID"
                value={approvalResult.resource.id}
                mono
              />
              <PlanRow
                label="RESOURCE TYPE"
                value={approvalResult.resource.type.toUpperCase()}
              />
              <PlanRow label="STATUS" value="DEPLOYED" highlight />

              {/* Distance */}
              {approvalResult.distance_km > 0 && (
                <div className="pt-2 border-t border-card-border/50">
                  <div className="text-[9px] tracking-widest text-muted font-medium mb-1">
                    DISTANCE TO INCIDENT
                  </div>
                  <div className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-info" />
                    <span className="text-lg font-bold font-mono text-info">
                      {approvalResult.distance_km.toFixed(1)} km
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Dispatch Status */}
          <div className="rounded-lg border border-success/30 bg-success-dim/10 overflow-hidden">
            <div className="px-4 py-3">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-xs font-bold tracking-wider text-success">
                  DISPATCHED
                </span>
              </div>
              <p className="text-xs text-muted mb-1">
                Response approved and dispatch initiated.
              </p>
              <div className="px-3 py-2 bg-surface border border-card-border rounded text-[10px] text-muted font-mono mt-2">
                ✦ No real-world dispatch was performed. Dispatch is simulated.
              </div>
            </div>
          </div>

          {/* Re-analyze button */}
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-3 py-1.5 text-[10px] font-bold tracking-wider border border-card-border rounded text-muted hover:text-foreground hover:bg-card transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            RE-ANALYZE
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Plan row sub-component ───────────────────────────────────────────

function PlanRow({
  label,
  value,
  mono,
  highlight,
}: {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: boolean;
}) {
  return (
    <div>
      <div className="text-[9px] tracking-widest text-muted font-medium mb-0.5">
        {label}
      </div>
      <div
        className={`text-sm ${
          highlight ? "text-success font-bold" : "text-foreground/90"
        } ${mono ? "font-mono" : ""}`}
      >
        {value}
      </div>
    </div>
  );
}
