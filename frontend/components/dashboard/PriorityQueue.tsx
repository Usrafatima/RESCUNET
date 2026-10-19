"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Clock,
  Users,
  Zap,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Brain,
} from "lucide-react";
import type { PriorityQueueResponse } from "@/lib/types";
import { getPriorityQueue } from "@/lib/api";

function priorityColor(label: string): string {
  switch (label) {
    case "critical":
      return "text-danger";
    case "high":
      return "text-warning-ink";
    case "medium":
      return "text-neutral";
    case "low":
      return "text-accent";
    default:
      return "text-neutral";
  }
}

function priorityBg(label: string): string {
  switch (label) {
    case "critical":
      return "bg-danger/10 border-danger/30";
    case "high":
      return "bg-warning/20 border-warning/50";
    case "medium":
      return "bg-muted/10 border-muted/30";
    case "low":
      return "bg-accent/10 border-accent/25";
    default:
      return "bg-muted/10 border-muted/30";
  }
}

function priorityDot(label: string): string {
  switch (label) {
    case "critical":
      return "bg-danger";
    case "high":
      return "bg-warning";
    case "medium":
      return "bg-neutral";
    case "low":
      return "bg-accent/70";
    default:
      return "bg-neutral";
  }
}

function ScoreBar({ score }: { score: number }) {
  const barColor =
    score >= 85
      ? "var(--color-danger)"
      : score >= 70
        ? "var(--color-warning)"
        : score >= 45
          ? "var(--color-accent)"
          : "var(--color-muted)";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted/15 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${score}%`, backgroundColor: barColor }}
        />
      </div>
      <span className="text-[10px] font-mono text-muted w-8 text-right">
        {score}
      </span>
    </div>
  );
}

export function PriorityQueue() {
  const [queueData, setQueueData] = useState<PriorityQueueResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [, setRetryCount] = useState(0);
  const MAX_RETRIES = 3;
  const RETRY_INTERVAL = 15000;

  const fetchQueue = useCallback(async () => {
    try {
      const data = await getPriorityQueue();
      setQueueData(data);
      setError(null);
      setRetryCount(0);
    } catch {
      // Backend unreachable — show friendly offline state, stop retrying after max attempts
      setRetryCount((prev) => {
        const next = prev + 1;
        if (next >= MAX_RETRIES) {
          setError("Backend offline — priority queue unavailable");
        }
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(() => {
      setRetryCount((current) => {
        if (current >= MAX_RETRIES) return current;
        fetchQueue();
        return current;
      });
    }, RETRY_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchQueue]);

  return (
    <div className="border-b border-card-border">
      <div className="px-4 py-2 border-b border-card-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-3.5 w-3.5 text-accent" />
          <h3 className="text-[11px] font-semibold text-foreground">
            AI Priority Queue
          </h3>
        </div>
        <button
          onClick={fetchQueue}
          className="p-1 text-muted hover:text-foreground transition-colors"
          title="Refresh queue"
        >
          <RefreshCw className="h-3 w-3" />
        </button>
      </div>

      {loading && queueData === null && (
        <div className="px-4 py-6 text-center">
          <div className="text-xs text-muted">Analyzing priorities...</div>
        </div>
      )}

      {error && (
        <div className="px-4 py-4 text-center">
          <div className="text-xs text-danger">{error}</div>
          <button
            onClick={fetchQueue}
            className="text-[10px] text-muted hover:text-foreground mt-1"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && queueData && queueData.queue.length === 0 && (
        <div className="px-4 py-6 text-center">
          <div className="text-xs text-muted">No active emergencies</div>
        </div>
      )}

      {queueData && queueData.queue.length > 0 && (
        <>
          {/* Summary */}
          <div className="px-4 py-1.5 bg-surface flex items-center justify-between text-[10px] text-muted">
            <span>
              {queueData.total_active} active emergency
              {queueData.total_active !== 1 ? "ies" : "y"}
            </span>
            <span className="font-mono">
              Updated{" "}
              {new Date(queueData.generated_at).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
              })}
            </span>
          </div>

          {/* Queue items */}
          <div className="max-h-[400px] overflow-y-auto">
            {queueData.queue.map((item) => (
              <div
                key={item.incident_id}
                className="border-b border-card-border/50 hover:bg-card/50 transition-colors"
              >
                {/* Main row */}
                <button
                  onClick={() =>
                    setExpandedItem(
                      expandedItem === item.incident_id
                        ? null
                        : item.incident_id,
                    )
                  }
                  className="w-full px-4 py-2.5 text-left"
                >
                  <div className="flex items-start gap-3">
                    {/* Rank */}
                    <div className="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center bg-surface border border-card-border">
                      <span className="text-[10px] font-semibold text-muted">
                        #{item.rank}
                      </span>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <div
                          className={`w-2 h-2 rounded-full shrink-0 ${priorityDot(item.priority_label)}`}
                        />
                        <span className="text-xs font-semibold text-foreground truncate">
                          {item.incident_type}
                        </span>
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${priorityBg(item.priority_label)} ${priorityColor(item.priority_label)}`}
                        >
                          {item.priority_label.toUpperCase()}
                        </span>
                      </div>

                      <p className="text-[11px] text-muted line-clamp-1 mb-1.5">
                        {item.description}
                      </p>

                      <div className="flex items-center gap-3 text-[10px] text-muted">
                        <span className="flex items-center gap-1">
                          <Users className="h-2.5 w-2.5" />
                          {item.people_affected}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-2.5 w-2.5" />
                          {item.waiting_time_display}
                        </span>
                        <span className="flex items-center gap-1 font-mono">
                          <Zap className="h-2.5 w-2.5" />
                          {item.score.toFixed(0)}/100
                        </span>
                      </div>

                      {/* Score bar */}
                      <div className="mt-1.5">
                        <ScoreBar score={item.score} />
                      </div>
                    </div>

                    {/* Expand indicator */}
                    <div className="flex-shrink-0 text-muted">
                      {expandedItem === item.incident_id ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded details */}
                {expandedItem === item.incident_id && (
                  <div className="px-4 pb-3 pt-0 ml-8">
                      {/* Resource info */}
                      <div className="mb-2 p-2 rounded bg-surface border border-card-border">
                        <div className="text-[10px] text-muted font-medium mb-1">
                          Recommended resource
                        </div>
                        <div className="flex items-center gap-2">
                          {item.recommended_resource.status === "available" ? (
                            <CheckCircle2 className="h-3 w-3 text-success" />
                          ) : (
                            <XCircle className="h-3 w-3 text-danger" />
                          )}
                          <span className="text-[11px] text-foreground">
                            {item.recommended_resource.resource_name}
                          </span>
                          <span
                            className={`text-[9px] font-semibold px-1 py-0.5 rounded ${
                              item.recommended_resource.status === "available"
                                ? "bg-success/10 text-success"
                                : "bg-danger/10 text-danger"
                            }`}
                          >
                            {item.recommended_resource.status.toUpperCase()}
                          </span>
                        </div>
                      </div>

                      {/* Why this priority */}
                      <div className="p-2 rounded bg-surface border border-card-border">
                        <div className="text-[10px] text-muted font-medium mb-1">
                          Why this priority
                        </div>
                        <p className="text-[11px] text-foreground/80 leading-relaxed">
                          {item.reason}
                        </p>

                      {/* Factor breakdown */}
                      <div className="mt-2 space-y-1">
                        <FactorRow
                          label="Severity"
                          value={item.factors.severity}
                        />
                        <FactorRow
                          label="People"
                          value={item.factors.people_affected}
                        />
                        <FactorRow
                          label="Urgency"
                          value={item.factors.urgency}
                        />
                        <FactorRow
                          label="Resource Need"
                          value={item.factors.resource_need}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Scoring weights footer */}
          {queueData.scoring_weights && (
            <div className="px-4 py-1.5 bg-surface border-t border-card-border">
              <div className="text-[9px] text-muted">
                SCORING: Severity{" "}
                {(queueData.scoring_weights.severity * 100).toFixed(0)}% ·
                People{" "}
                {(queueData.scoring_weights.people_affected * 100).toFixed(0)}%
                · Urgency{" "}
                {(queueData.scoring_weights.urgency * 100).toFixed(0)}% ·
                Waiting{" "}
                {(queueData.scoring_weights.waiting_time * 100).toFixed(0)}% ·
                Resources{" "}
                {(queueData.scoring_weights.resource_availability * 100).toFixed(
                  0,
                )}
                %
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FactorRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-[10px]">
      <span className="text-muted w-20">{label}</span>
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
