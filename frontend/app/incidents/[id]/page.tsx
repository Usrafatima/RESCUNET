"use client";

import { useEffect, useState, useCallback, use, Suspense } from "react";
import {
  ArrowLeft,
  Bot,
  Users,
  MapPin,
  Clock,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Wifi,
  WifiOff,
  Shield,
  ArrowDown,
  Truck,
  Brain,
} from "lucide-react";
import type { PriorityQueueItem, RecommendationResponse } from "@/lib/types";
import { getPriorityQueue, getRecommendation } from "@/lib/api";
import type {
  Incident,
  AgentAnalysisResult,
  EdgePacket,
} from "@/lib/types";
import { mapBackendStatus } from "@/lib/types";
import { getIncident, analyzeIncident, updateIncidentStatus } from "@/lib/api";
import { getEdgeQueue } from "@/lib/edge-api";
import { AIAnalysisPanel } from "@/components/agent/AIAnalysisPanel";
import { AIRecommendationCard } from "@/components/agent/AIRecommendationCard";
import { AgentActivity } from "@/components/agent/AgentActivity"
import { RescuePlanPanel } from "@/components/plans/RescuePlanPanel";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

function statusColor(status: string): string {
  switch (status) {
    case "queued":
      return "text-info";
    case "syncing":
      return "text-accent";
    case "failed":
      return "text-danger";
    case "analyzing":
    case "awaiting_approval":
      return "text-warning-ink";
    case "approved":
    case "dispatched":
      return "text-success";
    case "resolved":
      return "text-neutral";
    default:
      return "text-neutral";
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "dispatched":
    case "approved":
      return <CheckCircle2 className="h-4 w-4 text-success" />;
    case "cancelled":
    case "failed":
      return <XCircle className="h-4 w-4 text-danger" />;
    case "processing":
    case "awaiting_approval":
    case "analyzing":
    case "syncing":
      return <Loader2 className="h-4 w-4 text-info animate-spin" />;
    default:
      return <Clock className="h-4 w-4 text-muted" />;
  }
}

export default function IncidentDetailPage(props: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full">
          <Loader2 className="h-6 w-6 text-muted animate-spin" />
        </div>
      }
    >
      <IncidentDetailContent {...props} />
    </Suspense>
  );
}

function IncidentDetailContent(props: {
  params: Promise<{ id: string }>;
}) {
  const params = use(props.params);
  const searchParams = useSearchParams();
  const isEdgeSource = searchParams.get("source") === "edge";
  const incidentId = params.id;

  // Central backend incident
  const [incident, setIncident] = useState<Incident | null>(null);
  // Edge-only packet (when viewing offline incident)
  const [edgePacket, setEdgePacket] = useState<EdgePacket | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agentResult, setAgentResult] = useState<AgentAnalysisResult | null>(
    null,
  );
  const [analyzing, setAnalyzing] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [approvalState, setApprovalState] = useState<
    "none" | "pending" | "approved" | "rejected" | "error"
  >("none");
  const [priorityItem, setPriorityItem] = useState<PriorityQueueItem | null>(
    null,
  );
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(
    null,
  );

  const fetchIncident = useCallback(async () => {
    if (isEdgeSource) {
      // Edge-only: fetch from edge queue instead of central backend
      try {
        const packets = await getEdgeQueue();
        const found = packets.find((p) => p.packet_id === incidentId);
        if (found) {
          setEdgePacket(found);
        } else {
          setError("Edge packet not found — it may have been synchronized");
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load edge incident",
        );
      } finally {
        setLoading(false);
      }
      return;
    }

    // Central backend incident
    try {
      const data = await getIncident(incidentId);
      setIncident(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load incident",
      );
    } finally {
      setLoading(false);
    }
  }, [incidentId, isEdgeSource]);

  useEffect(() => {
    fetchIncident();

    // Fetch priority queue and recommendation in parallel
    if (!isEdgeSource) {
      getPriorityQueue()
        .then((pq) => {
          const found = pq.queue.find(
            (item) => item.incident_id === incidentId,
          );
          if (found) setPriorityItem(found);
        })
        .catch(() => {});

      getRecommendation(incidentId)
        .then((rec) => setRecommendation(rec))
        .catch(() => {});
    }
  }, [fetchIncident, incidentId, isEdgeSource]);

  const [resolving, setResolving] = useState(false);

  const handleApprovalChange = useCallback(
    (
      state: "none" | "pending" | "approved" | "rejected" | "error",
    ) => {
      setApprovalState(state);
      if (state === "approved") {
        fetchIncident();
        // Refresh recommendation after approval
        getRecommendation(incidentId)
          .then((rec) => setRecommendation(rec))
          .catch(() => {});
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("rescunet:refresh"));
        }
      }
    },
    [fetchIncident, incidentId],
  );

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAgentError(null);
    setApprovalState("pending");
    try {
      const result = await analyzeIncident(incidentId);
      setAgentResult(result);
      fetchIncident();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("rescunet:refresh"));
      }
    } catch (err) {
      setAgentError(
        err instanceof Error ? err.message : "Analysis failed",
      );
      setApprovalState("none");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResolve = async () => {
    setResolving(true);
    try {
      await updateIncidentStatus(incidentId, { status: "resolved" });
      await fetchIncident();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("rescunet:refresh"));
      }
    } catch (err) {
      console.error("Failed to resolve incident", err);
    } finally {
      setResolving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 text-muted animate-spin" />
      </div>
    );
  }

  if (error || (!incident && !edgePacket)) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertTriangle className="h-8 w-8 text-danger" />
        <div className="text-sm text-danger">
          {error || "Incident not found"}
        </div>
        <Link
          href="/incidents"
          className="text-xs text-accent hover:underline"
        >
          ← Back to incidents
        </Link>
      </div>
    );
  }

  // ── Edge-only offline detail view ────────────────────────────────
  if (edgePacket && !incident) {
    return (
      <div className="flex flex-col h-full overflow-auto">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 md:px-6 py-3 border-b border-card-border bg-surface">
          <Link
            href="/incidents"
            className="p-1 text-muted hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-accent">
                {edgePacket.packet_id}
              </span>
              <StatusIcon status={edgePacket.status} />
              <span className="text-[10px] tracking-wider font-medium text-accent">
                {edgePacket.status.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        {/* Offline banner */}
        <div className="mx-4 md:mx-6 mt-4 flex items-center gap-3 px-4 py-3 rounded-lg bg-accent-dim/20 border border-accent/30">
          <WifiOff className="h-5 w-5 text-accent shrink-0" />
          <div>
            <div className="text-sm font-bold text-accent tracking-wider">
              OFFLINE INCIDENT
            </div>
            <div className="text-xs text-accent/70 mt-0.5">
              Stored locally on Edge Gateway — Waiting for synchronization
            </div>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span className="text-[10px] text-accent font-bold tracking-wider">
              QUEUED LOCALLY
            </span>
          </div>
        </div>

        <div className="flex-1 p-4 md:p-6">
          {/* Incident details */}
          <h2 className="text-[10px] tracking-widest text-muted font-medium mb-3">
            INCIDENT DETAILS
          </h2>

          <div className="bg-card border border-card-border rounded-lg p-4 mb-4">
            <p className="text-sm text-foreground/90 mb-4">
              {edgePacket.description}
            </p>

            <div className="grid grid-cols-2 gap-3">
              <InfoItem label="PEOPLE AFFECTED">
                <div className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {edgePacket.people_affected}
                  </span>
                </div>
              </InfoItem>

              <InfoItem label="STATUS">
                <span className="text-sm font-mono text-accent">
                  QUEUED
                </span>
              </InfoItem>

              <InfoItem label="LOCATION">
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {edgePacket.latitude.toFixed(4)},{" "}
                    {edgePacket.longitude.toFixed(4)}
                  </span>
                </div>
              </InfoItem>

              <InfoItem label="CREATED">
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {new Date(edgePacket.created_at).toLocaleString(
                      "en-US",
                      {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      },
                    )}
                  </span>
                </div>
              </InfoItem>
            </div>

            {/* Edge packet metadata */}
            <div className="mt-3 pt-3 border-t border-card-border">
              <div className="flex items-center gap-2 text-xs text-muted">
                <WifiOff className="h-3 w-3" />
                <span>Edge Gateway packet</span>
                <span className="font-mono text-accent">
                  {edgePacket.packet_id}
                </span>
              </div>
              {edgePacket.attempt_count > 0 && (
                <div className="flex items-center gap-2 text-xs text-muted mt-1">
                  <span>Sync attempts: {edgePacket.attempt_count}</span>
                  {edgePacket.last_error && (
                    <span className="text-danger">— {edgePacket.last_error}</span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Timeline for offline */}
          <h2 className="text-[10px] tracking-widest text-muted font-medium mb-3">
            TIMELINE
          </h2>
          <div className="space-y-2">
            <TimelineEvent
              time={edgePacket.created_at}
              label="Incident reported via Edge Gateway"
              icon={<AlertTriangle className="h-3 w-3" />}
              color="text-accent"
            />
            <TimelineEvent
              time={edgePacket.created_at}
              label="Packet stored locally in edge queue"
              icon={<WifiOff className="h-3 w-3" />}
              color="text-accent"
            />
            {edgePacket.status === "syncing" && (
              <TimelineEvent
                time={new Date().toISOString()}
                label="Syncing to central backend..."
                icon={<Loader2 className="h-3 w-3 animate-spin" />}
                color="text-info"
              />
            )}
            {edgePacket.status === "synced" && edgePacket.synced_at && (
              <TimelineEvent
                time={edgePacket.synced_at}
                label="Synchronized to backend"
                icon={<CheckCircle2 className="h-3 w-3" />}
                color="text-success"
              />
            )}
          </div>

          {/* AI Analysis not available for offline incidents */}
          {/* AI Analysis not available for offline incidents */}
          <div className="mt-6 bg-card border border-card-border rounded-lg p-6 text-center">
            <Bot className="h-8 w-8 text-muted/30 mx-auto mb-3" />
            <p className="text-sm text-muted mb-2">
              AI analysis is not available for offline incidents.
            </p>
            <p className="text-[10px] text-muted/60">
              Once synchronized to the central backend, the Strands AI agent
              can analyze this incident and generate a response
              recommendation.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Central backend detail view (original behavior) ──────────────
  return (
    <div className="flex flex-col h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 md:px-6 py-2.5 border-b border-card-border bg-surface">
        <Link
          href="/incidents"
          className="p-1 text-muted hover:text-accent transition-colors"
          aria-label="Back to incidents"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono text-accent">
              {incident!.incident_id}
            </span>
            <StatusIcon status={incident!.status} />
            <span
              className={`text-[10px] font-semibold ${statusColor(incident!.status)}`}
            >
              {mapBackendStatus(incident!.status)
                .toUpperCase()
                .replace("_", " ")}
            </span>
          </div>
        </div>
        {incident!.status === "dispatched" && (
          <button
            onClick={handleResolve}
            disabled={resolving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-success/10 border border-success/40 text-success text-xs font-semibold rounded-md hover:bg-success/20 transition-colors disabled:opacity-50"
          >
            {resolving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5" />
            )}
            MARK AS RESOLVED
          </button>
        )}
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0">
        {/* Left: Incident details + Timeline */}
        <div className="p-4 border-b lg:border-b-0 lg:border-r border-card-border">
          <h2 className="text-[11px] font-semibold text-foreground mb-2.5">
            Incident Details
          </h2>

          <div className="bg-card border border-card-border rounded-md p-3.5 mb-3">
            <p className="text-sm text-foreground mb-3.5">
              {incident!.description}
            </p>

            <div className="grid grid-cols-2 gap-3">
              <InfoItem label="PEOPLE AFFECTED">
                <div className="flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {incident!.people_affected}
                  </span>
                </div>
              </InfoItem>

              <InfoItem label="STATUS">
                <span
                  className={`text-sm font-mono ${statusColor(incident!.status)}`}
                >
                  {incident!.status.toUpperCase()}
                </span>
              </InfoItem>

              <InfoItem label="LOCATION">
                <div className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {incident!.latitude.toFixed(4)},{" "}
                    {incident!.longitude.toFixed(4)}
                  </span>
                </div>
              </InfoItem>

              <InfoItem label="CREATED">
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm font-mono">
                    {new Date(incident!.created_at).toLocaleString(
                      "en-US",
                      {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      },
                    )}
                  </span>
                </div>
              </InfoItem>
            </div>

            {incident!.packet_id && (
              <div className="mt-3 pt-3 border-t border-card-border">
                <div className="flex items-center gap-2 text-xs text-muted">
                  <Wifi className="h-3 w-3" />
                  <span>Synchronized from Edge Gateway</span>
                  <span className="font-mono text-accent">
                    {incident!.packet_id}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Priority Explainability */}
          {priorityItem && (
            <div className="mb-3">
              <h2 className="text-[11px] font-semibold text-foreground mb-2.5">
                Why This Priority
              </h2>
              <div className="bg-card border border-card-border rounded-md p-3.5">
                <div className="flex items-center gap-3 mb-2.5">
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-accent" />
                    <span className="text-sm font-semibold text-foreground">
                      PRIORITY #{priorityItem.rank}
                    </span>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                      priorityItem.priority_label === "critical"
                        ? "bg-danger/10 border-danger/30 text-danger"
                        : priorityItem.priority_label === "high"
                          ? "bg-warning/20 border-warning/50 text-warning-ink"
                          : priorityItem.priority_label === "medium"
                            ? "bg-muted/10 border-muted/30 text-neutral"
                            : "bg-accent/10 border-accent/25 text-accent"
                    }`}
                  >
                    {priorityItem.priority_label.toUpperCase()}
                  </span>
                  <span className="text-xs font-mono text-muted ml-auto">
                    Score: {priorityItem.score.toFixed(0)}/100
                  </span>
                </div>

                {/* Score bar */}
                <div className="mb-2.5">
                  <div className="h-2 bg-muted/15 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${priorityItem.score}%`,
                        backgroundColor:
                          priorityItem.score >= 85
                            ? "var(--color-danger)"
                            : priorityItem.score >= 70
                              ? "var(--color-warning)"
                              : priorityItem.score >= 45
                                ? "var(--color-accent)"
                                : "var(--color-muted)",
                      }}
                    />
                  </div>
                </div>

                {/* Reason */}
                <p className="text-xs text-muted mb-2.5">
                  {priorityItem.reason}
                </p>

                {/* Factor breakdown */}
                <div className="space-y-1.5">
                  <div className="text-[10px] text-muted font-medium">
                    Factor breakdown
                  </div>
                  <PriorityFactorRow
                    label="Severity"
                    value={priorityItem.factors.severity}
                  />
                  <PriorityFactorRow
                    label="People Affected"
                    value={priorityItem.factors.people_affected}
                  />
                  <PriorityFactorRow
                    label="Urgency"
                    value={priorityItem.factors.urgency}
                  />
                  <PriorityFactorRow
                    label="Resource Need"
                    value={priorityItem.factors.resource_need}
                  />
                </div>

                {/* Waiting time and resource */}
                <div className="mt-3 pt-3 border-t border-card-border flex items-center gap-4 text-[10px] text-muted">
                  <span className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    Waiting: {priorityItem.waiting_time_display}
                  </span>
                  <span className="flex items-center gap-1">
                    {priorityItem.recommended_resource.status === "available" ? (
                      <CheckCircle2 className="h-2.5 w-2.5 text-success" />
                    ) : (
                      <XCircle className="h-2.5 w-2.5 text-danger" />
                    )}
                    {priorityItem.recommended_resource.resource_name}
                    <span
                      className={`${
                        priorityItem.recommended_resource.status === "available"
                          ? "text-success"
                          : "text-danger"
                      }`}
                    >
                      {priorityItem.recommended_resource.status === "available"
                        ? "✓"
                        : "✗"}
                    </span>
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Timeline */}
          <h2 className="text-[10px] tracking-widest text-muted font-medium mb-3">
            TIMELINE
          </h2>
          <div className="space-y-2">
            <TimelineEvent
              time={incident!.created_at}
              label="Incident reported"
              icon={<AlertTriangle className="h-3 w-3" />}
              color="text-accent"
            />
            {incident!.packet_id && (
              <TimelineEvent
                time={incident!.created_at}
                label="Packet stored locally in edge queue"
                icon={<Wifi className="h-3 w-3" />}
                color="text-accent"
              />
            )}
            {incident!.packet_id && incident!.status !== "queued" && (
              <TimelineEvent
                time={incident!.updated_at}
                label="Synchronized to backend"
                icon={<CheckCircle2 className="h-3 w-3" />}
                color="text-success"
              />
            )}
            {incident!.status !== "queued" && !incident!.packet_id && (
              <TimelineEvent
                time={incident!.updated_at}
                label="Status updated"
                icon={<Clock className="h-3 w-3" />}
                color="text-info"
              />
            )}
            {analyzing && (
              <TimelineEvent
                time={new Date().toISOString()}
                label="AI analysis in progress..."
                icon={<Loader2 className="h-3 w-3 animate-spin" />}
                color="text-info"
              />
            )}
            {agentResult && (
              <TimelineEvent
                time={new Date().toISOString()}
                label="AI analysis completed"
                icon={<Bot className="h-3 w-3" />}
                color="text-success"
              />
            )}
            {approvalState === "pending" && agentResult && (
              <TimelineEvent
                time={new Date().toISOString()}
                label="Human approval requested"
                icon={<Clock className="h-3 w-3" />}
                color="text-accent"
              />
            )}
            {approvalState === "approved" && (
              <>
                <TimelineEvent
                  time={new Date().toISOString()}
                  label="Response approved"
                  icon={<CheckCircle2 className="h-3 w-3" />}
                  color="text-success"
                />
                <TimelineEvent
                  time={new Date().toISOString()}
                  label="Response plan created"
                  icon={<Shield className="h-3 w-3" />}
                  color="text-success"
                />
                <TimelineEvent
                  time={new Date().toISOString()}
                  label="Resource assigned"
                  icon={<Truck className="h-3 w-3" />}
                  color="text-success"
                />
                <TimelineEvent
                  time={new Date().toISOString()}
                  label="Dispatch initiated"
                  icon={<CheckCircle2 className="h-3 w-3" />}
                  color="text-success"
                />
              </>
            )}
            {approvalState === "rejected" && (
              <TimelineEvent
                time={new Date().toISOString()}
                label="Response rejected"
                icon={<XCircle className="h-3 w-3" />}
                color="text-danger"
              />
            )}
          </div>
        </div>

        {/* Right: AI Analysis + Recommendation */}
        <div className="p-4">
          <h2 className="text-[11px] font-semibold text-foreground mb-2.5">
            Response Decision Center
          </h2>

          {/* AI Recommended Responder card */}
          {recommendation && (
            <>
              <AIRecommendationCard recommendation={recommendation} />
              {recommendation.activity && recommendation.activity.length > 0 && (
                <AgentActivity activity={recommendation.activity} />
              )}
            </>
          )}

          {!agentResult && !analyzing && !agentError && (
            <div className="bg-card border border-card-border rounded-md p-5 text-center">
              <Bot className="h-8 w-8 text-muted/30 mx-auto mb-3" />
              <p className="text-sm text-muted mb-1.5">
                Run the Strands AI agent to analyze this incident and
                generate a response recommendation.
              </p>
              <p className="text-[11px] text-muted/70 mb-4">
                The agent will retrieve incident data, classify the
                emergency, find resources, and recommend a response — all
                requiring human approval before dispatch.
              </p>
              <button
                onClick={handleAnalyze}
                className="flex items-center gap-2 mx-auto px-5 py-2.5 bg-accent text-white text-xs font-semibold rounded-md hover:bg-accent-hover transition-colors"
              >
                <Bot className="h-3.5 w-3.5" />
                ANALYZE WITH RESCUNET AI
              </button>
            </div>
          )}

          {analyzing && <AnalyzingOverlay />}

          {agentError && !analyzing && (
            <div className="bg-card border border-danger/30 rounded-md p-5">
              <div className="flex items-center gap-2 text-xs text-danger mb-2.5">
                <XCircle className="h-4 w-4" />
                <span className="font-semibold">AI ANALYSIS FAILED</span>
              </div>
              <p className="text-xs text-muted mb-1">{agentError}</p>
              <p className="text-[11px] text-muted/70 mb-4">
                The incident is still safely stored. No response was
                dispatched.
              </p>
              <button
                onClick={handleAnalyze}
                className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-accent border border-accent/30 rounded-md hover:bg-accent/10 transition-colors"
              >
                <AlertTriangle className="h-3 w-3" />
                RETRY ANALYSIS
              </button>
            </div>
          )}

          {agentResult && !analyzing && (
            <AIAnalysisPanel
              result={agentResult}
              incidentId={incidentId}
              onRetry={handleAnalyze}
              onApprovalChange={handleApprovalChange}
            />
          )}

          {/* Adaptive rescue plan: triage, proposed vs previous, audit trail */}
          <div className="mt-6">
            <RescuePlanPanel incidentId={incidentId} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Shared sub-components ────────────────────────────────────────────

function InfoItem({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-3">
      <div className="text-[10px] text-muted mb-1">{label}</div>
      {children}
    </div>
  );
}

function TimelineEvent({
  time,
  label,
  icon,
  color,
}: {
  time: string;
  label: string;
  icon: React.ReactNode;
  color: string;
}) {
  const formatted = new Date(time).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="font-mono text-muted w-12 shrink-0">
        {formatted}
      </span>
      <div
        className={`w-5 h-5 rounded-full bg-card border border-card-border flex items-center justify-center ${color}`}
      >
        {icon}
      </div>
      <span className="text-foreground/80">{label}</span>
    </div>
  );
}

// ─── Analyzing overlay with animated workflow ─────────────────────────

const ANALYZING_STEPS = [
  "Retrieving incident...",
  "Assessing emergency...",
  "Finding available resources...",
  "Checking resource status...",
  "Calculating distance...",
  "Generating response recommendation...",
];

function AnalyzingOverlay() {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentStep((prev) =>
        prev < ANALYZING_STEPS.length - 1 ? prev + 1 : prev,
      );
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="bg-card border border-accent/30 rounded-md p-5">
      <div className="mb-4">
        <div className="text-[10px] text-muted font-medium mb-2">
          Agent pipeline
        </div>
        <div className="flex flex-wrap items-center gap-x-1 gap-y-1">
          {WORKFLOW_STEPS_DISPLAY.map((step, i) => {
            const stepIdx = Math.floor(
              (i / WORKFLOW_STEPS_DISPLAY.length) * ANALYZING_STEPS.length,
            );
            const isActive = stepIdx === currentStep;
            const isDone = stepIdx < currentStep;
            return (
              <div key={step} className="flex items-center">
                <div
                  className={`px-2 py-1 text-[9px] font-medium rounded transition-all duration-500 ${
                    isDone
                      ? "bg-success/10 text-success border border-success/20"
                      : isActive
                        ? "bg-tangerine/15 text-info border border-tangerine/40 step-active"
                        : "bg-surface text-muted/40 border border-card-border"
                  }`}
                >
                  {step}
                </div>
                {i < WORKFLOW_STEPS_DISPLAY.length - 1 && (
                  <ArrowDown
                    className={`h-2.5 w-2.5 mx-0.5 rotate-[-90deg] transition-colors duration-500 ${
                      isDone ? "text-success/50" : "text-muted/20"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <Bot className="h-4 w-4 text-accent" />
        <span className="text-xs font-semibold text-accent">
          STRANDS AGENT ACTIVE
        </span>
      </div>
      <div className="space-y-2">
        {ANALYZING_STEPS.map((step, i) => (
          <div
            key={step}
            className={`flex items-center gap-2 text-xs transition-all duration-500 ${
              i < currentStep
                ? "text-success/70"
                : i === currentStep
                  ? "text-foreground step-active"
                  : "text-muted/20"
            }`}
          >
            {i < currentStep ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : i === currentStep ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <div className="w-3 h-3 rounded-full border border-muted/15" />
            )}
            {step}
          </div>
        ))}
      </div>
    </div>
  );
}

const WORKFLOW_STEPS_DISPLAY = [
  "INCIDENT",
  "GET INCIDENT",
  "ASSESS",
  "FIND RESOURCES",
  "CHECK AVAILABILITY",
  "CALCULATE DISTANCE",
  "RECOMMEND",
  "HUMAN APPROVAL",
];

function PriorityFactorRow({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2 text-[10px]">
      <span className="text-muted w-24">{label}</span>
      <div className="flex-1 h-1 bg-muted/20 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-info/60"
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="font-mono text-muted w-6 text-right">{value}</span>
    </div>
  );
}
