"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Search,
  CheckCircle2,
  Clock,
  ShieldAlert,
  Loader2,
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  Shield,
  Activity,
  CheckCircle,
  XCircle,
  Radio,
} from "lucide-react";
import { getIncident } from "@/lib/api";
import { getEdgeQueue } from "@/lib/edge-api";
import type { Incident, IncidentStatus, EdgePacket } from "@/lib/types";
import { useCitizenLanguage } from "./LanguageContext";

interface IncidentStatusTrackerProps {
  initialReferenceId?: string;
  onBackToReport?: () => void;
}

function getStepProgress(status: IncidentStatus): number {
  switch (status) {
    case "queued":
      return 0;
    case "processing":
      return 1;
    case "awaiting_approval":
      return 2;
    case "approved":
    case "dispatched":
      return 3;
    case "resolved":
      return 4;
    case "cancelled":
      return -1;
    default:
      return 0;
  }
}

export function IncidentStatusTracker({
  initialReferenceId = "",
  onBackToReport,
}: IncidentStatusTrackerProps) {
  const { t } = useCitizenLanguage();

  const [searchId, setSearchId] = useState(initialReferenceId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Result state
  const [incident, setIncident] = useState<Incident | null>(null);
  const [edgePacket, setEdgePacket] = useState<EdgePacket | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const fetchStatus = useCallback(
    async (idToQuery: string) => {
      const cleanId = idToQuery.trim().toUpperCase();
      if (!cleanId) return;

      setLoading(true);
      setError(null);
      setIncident(null);
      setEdgePacket(null);

      try {
        // First try central backend
        try {
          const res = await getIncident(cleanId);
          if (res) {
            setIncident(res);
            setLastRefreshed(new Date());
            setLoading(false);
            return;
          }
        } catch {
          // If not found in backend or backend is offline, check edge if it's an edge reference
        }

        // Check local edge gateway queue if it looks like an edge packet or if backend missed
        if (cleanId.startsWith("EDGE-")) {
          try {
            const queue = await getEdgeQueue();
            const matched = queue.find((p) => p.packet_id === cleanId);
            if (matched) {
              setEdgePacket(matched);
              setLastRefreshed(new Date());
              setLoading(false);
              return;
            }
          } catch {
            // Edge failed too
          }
        }

        setError(
          `${t.trackNotFound} "${cleanId}".`
        );
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to retrieve status. Please check your reference number."
        );
      } finally {
        setLoading(false);
      }
    },
    [t.trackNotFound]
  );

  useEffect(() => {
    if (!initialReferenceId) return;
    let cancelled = false;

    async function loadInitial() {
      const cleanId = initialReferenceId.trim().toUpperCase();
      if (!cleanId) return;

      try {
        const res = await getIncident(cleanId);
        if (!cancelled && res) {
          setIncident(res);
          setLastRefreshed(new Date());
          return;
        }
      } catch {
        // Fallback to edge
      }

      if (cleanId.startsWith("EDGE-")) {
        try {
          const queue = await getEdgeQueue();
          const matched = queue.find((p) => p.packet_id === cleanId);
          if (!cancelled && matched) {
            setEdgePacket(matched);
            setLastRefreshed(new Date());
            return;
          }
        } catch {
          // Edge unreachable
        }
      }

      if (!cancelled) {
        setError(
          `${t.trackNotFound} "${cleanId}".`
        );
      }
    }

    loadInitial();
    return () => {
      cancelled = true;
    };
  }, [initialReferenceId, t.trackNotFound]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchStatus(searchId);
  };

  const getStatusBadge = (status: IncidentStatus) => {
    switch (status) {
      case "queued":
        return {
          label: t.statusBadgeQueued,
          bg: "bg-warning/10 text-warning-ink border-warning/30",
          icon: Clock,
        };
      case "processing":
        return {
          label: t.statusBadgeTriage,
          bg: "bg-accent/10 text-accent border-accent/30",
          icon: Activity,
        };
      case "awaiting_approval":
        return {
          label: t.statusBadgeApproval,
          bg: "bg-tangerine/15 text-info border-tangerine/30",
          icon: Shield,
        };
      case "approved":
      case "dispatched":
        return {
          label: t.statusBadgeDispatched,
          bg: "bg-success/10 text-success border-success/30",
          icon: CheckCircle2,
        };
      case "resolved":
        return {
          label: t.statusBadgeResolved,
          bg: "bg-neutral/10 text-neutral border-neutral/30",
          icon: CheckCircle,
        };
      case "cancelled":
        return {
          label: t.statusBadgeCancelled,
          bg: "bg-danger/10 text-danger border-danger/30",
          icon: XCircle,
        };
      default:
        return {
          label: status,
          bg: "bg-surface text-muted border-card-border",
          icon: Clock,
        };
    }
  };

  const getCitizenMessage = (status: IncidentStatus): string => {
    switch (status) {
      case "queued":
        return t.statusMsgQueued;
      case "processing":
        return t.statusMsgProcessing;
      case "awaiting_approval":
        return t.statusMsgApproval;
      case "approved":
      case "dispatched":
        return t.statusMsgDispatched;
      case "resolved":
        return t.statusMsgResolved;
      case "cancelled":
        return t.statusMsgCancelled;
      default:
        return "Processing emergency report...";
    }
  };

  const lifecycleSteps = [
    {
      key: "queued",
      label: t.trackStepQueued,
      description: t.trackStepQueuedDesc,
    },
    {
      key: "processing",
      label: t.trackStepTriage,
      description: t.trackStepTriageDesc,
    },
    {
      key: "awaiting_approval",
      label: t.trackStepPlan,
      description: t.trackStepPlanDesc,
    },
    {
      key: "dispatched",
      label: t.trackStepDispatched,
      description: t.trackStepDispatchedDesc,
    },
    {
      key: "resolved",
      label: t.trackStepResolved,
      description: t.trackStepResolvedDesc,
    },
  ];

  const currentStep = incident ? getStepProgress(incident.status) : 0;
  const statusBadge = incident ? getStatusBadge(incident.status) : null;
  const StatusIcon = statusBadge ? statusBadge.icon : Clock;

  return (
    <div className="bg-card border border-card-border rounded-2xl shadow-xs overflow-hidden">
      {/* Header Search Bar */}
      <div className="p-5 sm:p-6 border-b border-card-border bg-surface/40">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-foreground">
              {t.trackTitle}
            </h2>
            <p className="text-xs text-muted">
              {t.trackSubtitle}
            </p>
          </div>
          {onBackToReport && (
            <button
              onClick={onBackToReport}
              className="text-xs font-semibold text-accent hover:underline flex items-center gap-1 cursor-pointer"
            >
              <span>{t.trackBackToReport}</span>
              <ArrowRight className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input
              type="text"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              placeholder={t.trackPlaceholder}
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-surface rounded-xl border border-card-border focus:border-accent focus:outline-hidden font-mono uppercase"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !searchId.trim()}
            className="px-5 py-2.5 rounded-xl bg-accent hover:bg-accent-hover text-white font-semibold text-sm transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <span>{t.trackButton}</span>
            )}
          </button>
        </form>
      </div>

      <div className="p-5 sm:p-6">
        {/* Loading State */}
        {loading && (
          <div className="py-12 text-center text-muted space-y-2">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-accent" />
            <p className="text-sm">{t.trackSearching}</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="p-4 bg-danger/10 border border-danger/30 rounded-xl text-xs text-danger flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold">{error}</div>
              <div className="text-[11px] text-danger/80 mt-1">
                Make sure the reference starts with <strong>RSN-</strong> or <strong>EDGE-</strong> followed by 6 digits.
              </div>
            </div>
          </div>
        )}

        {/* Edge Packet Buffered State (Not yet in central dispatch) */}
        {!loading && edgePacket && !incident && (
          <div className="space-y-6">
            <div className="p-4 bg-tangerine/10 border border-tangerine/30 rounded-xl space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Radio className="h-4 w-4 text-tangerine animate-pulse" />
                  <span className="font-bold text-foreground text-sm">
                    {t.trackEdgeBufferedTitle}
                  </span>
                </div>
                <span className="text-xs font-mono font-bold text-accent">
                  {edgePacket.packet_id}
                </span>
              </div>
              <p className="text-xs text-muted">
                {t.trackEdgeBufferedDesc}
              </p>
              <div className="text-[11px] text-muted flex items-center gap-4 pt-1">
                <span>Status: <strong className="uppercase">{edgePacket.status}</strong></span>
                <span>Attempts: {edgePacket.attempt_count}</span>
                {edgePacket.synced_at && (
                  <span>Synced At: {new Date(edgePacket.synced_at).toLocaleTimeString()}</span>
                )}
              </div>
            </div>

            <div className="p-4 bg-surface rounded-xl border border-card-border text-xs text-muted space-y-1.5">
              <div className="font-semibold text-foreground">What happens next?</div>
              <p>{t.trackEdgeNextStep}</p>
            </div>
          </div>
        )}

        {/* Main Incident Display (Safe Citizen View) */}
        {!loading && incident && (
          <div className="space-y-6">
            {/* Top Status Card */}
            <div className="bg-surface/50 border border-card-border rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="space-y-1">
                  <div className="text-xs uppercase tracking-wider text-muted font-semibold">
                    {t.trackRefLabel}
                  </div>
                  <div className="font-mono text-2xl font-black text-foreground tracking-wide">
                    {incident.incident_id}
                  </div>
                </div>

                {statusBadge && (
                  <div
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${statusBadge.bg}`}
                  >
                    <StatusIcon className="h-4 w-4" />
                    <span>{statusBadge.label}</span>
                  </div>
                )}
              </div>

              {/* Status explanation */}
              <p className="text-sm text-foreground/90 font-medium">
                {getCitizenMessage(incident.status)}
              </p>

              {/* Timestamps & details */}
              <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-card-border/60 text-[11px] text-muted">
                <div className="flex items-center gap-3">
                  <span>
                    {t.trackReportedAt} {new Date(incident.created_at).toLocaleString()}
                  </span>
                  <span>
                    {t.trackAffectedLabel} {incident.people_affected}
                  </span>
                </div>
                {lastRefreshed && (
                  <button
                    onClick={() => fetchStatus(incident.incident_id)}
                    className="inline-flex items-center gap-1 text-accent hover:underline cursor-pointer"
                  >
                    <RefreshCw className="h-3 w-3" />
                    <span>{t.trackUpdatedNow} {lastRefreshed.toLocaleTimeString()}</span>
                  </button>
                )}
              </div>
            </div>

            {/* Lifecycle Progress Bar */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
                {t.trackProgressTitle}
              </h3>

              <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-card-border">
                {lifecycleSteps.map((step, idx) => {
                  const isDone = currentStep > idx;
                  const isCurrent = currentStep === idx;

                  return (
                    <div key={step.key} className="relative flex items-start gap-3">
                      {/* Step Circle Indicator */}
                      <span
                        className={`absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                          isDone
                            ? "bg-success text-white ring-4 ring-card"
                            : isCurrent
                            ? "bg-accent text-white ring-4 ring-accent/20 animate-pulse"
                            : "bg-surface border border-card-border text-muted ring-4 ring-card"
                        }`}
                      >
                        {isDone ? "✓" : idx + 1}
                      </span>

                      <div className="text-xs">
                        <div
                          className={`font-bold ${
                            isCurrent
                              ? "text-accent"
                              : isDone
                              ? "text-foreground"
                              : "text-muted"
                          }`}
                        >
                          {step.label}
                        </div>
                        <div className="text-[11px] text-muted">
                          {step.description}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Privacy & Safety Note */}
            <div className="p-3.5 bg-surface rounded-xl border border-card-border text-xs text-muted flex items-start gap-2.5">
              <ShieldAlert className="h-4 w-4 text-accent shrink-0 mt-0.5" />
              <div>{t.trackPrivacyNotice}</div>
            </div>
          </div>
        )}

        {/* Empty Search State */}
        {!loading && !error && !incident && !edgePacket && (
          <div className="py-8 text-center text-muted space-y-2">
            <Search className="h-8 w-8 mx-auto text-muted/50" />
            <p className="text-xs">
              {t.trackPlaceholder}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
