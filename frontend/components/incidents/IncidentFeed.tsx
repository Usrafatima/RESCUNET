"use client";

import { useState } from "react";
import type { UnifiedIncident } from "@/lib/types";
import { Clock, Users, MapPin, WifiOff, ChevronDown, ChevronUp, ChevronRight } from "lucide-react";
import Link from "next/link";

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

function statusBg(status: string): string {
  switch (status) {
    case "queued":
      return "bg-tangerine/10 border-tangerine/40";
    case "syncing":
      return "bg-accent/10 border-accent/30";
    case "failed":
      return "bg-danger/10 border-danger/30";
    case "analyzing":
    case "awaiting_approval":
      return "bg-warning/15 border-warning/40";
    case "approved":
    case "dispatched":
      return "bg-success/10 border-success/30";
    case "resolved":
      return "bg-muted/10 border-muted/30";
    default:
      return "bg-muted/10 border-muted/30";
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "--:--";
  }
}

interface IncidentFeedProps {
  incidents: UnifiedIncident[];
  loading: boolean;
  selectedIncidentId?: string | null;
  onSelectIncident?: (incident: UnifiedIncident) => void;
}

export function IncidentFeed({
  incidents,
  loading,
  selectedIncidentId,
  onSelectIncident,
}: IncidentFeedProps) {
  const [expanded, setExpanded] = useState(false);

  // Only show active (not resolved/cancelled/synced)
  const active = incidents.filter(
    (i) => !["resolved", "cancelled", "synced"].includes(i.status),
  );

  // Sort incidents by creation/received time, newest first
  const sorted = [...active].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  // Display a maximum of 5 incidents by default
  const displayed = expanded ? sorted : sorted.slice(0, 5);

  return (
    <div className="border-b border-card-border">
      <div className="flex items-center justify-between px-4 py-2 border-b border-card-border bg-surface/30">
        <h3 className="text-[11px] font-semibold text-foreground">
          Active Incidents
        </h3>
        <span className="text-[10px] text-muted font-mono">
          {sorted.length} {sorted.length === 1 ? "incident" : "incidents"}
        </span>
      </div>

      {loading && sorted.length === 0 && (
        <div className="px-4 py-5 text-center">
          <div className="text-xs text-muted">Loading incidents...</div>
        </div>
      )}

      {!loading && sorted.length === 0 && (
        <div className="px-4 py-5 text-center">
          <div className="text-xs text-muted">No active incidents</div>
        </div>
      )}

      <div className="divide-y divide-card-border/50">
        {displayed.map((item) => {
          const isSelected = selectedIncidentId === item.id;
          return (
            <div
              key={item.id}
              onClick={() => onSelectIncident?.(item)}
              className={`block px-4 py-2.5 transition-colors cursor-pointer ${
                isSelected
                  ? "bg-accent/10 border-l-2 border-l-accent"
                  : "hover:bg-card border-l-2 border-l-transparent"
              }`}
            >
              <div className="flex items-start justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-mono text-accent font-semibold">
                    {item.id}
                  </span>
                  {item.source === "edge" && (
                    <span className="text-[8px] font-bold px-1 py-0.5 rounded border border-tangerine/40 bg-tangerine/10 text-info flex items-center gap-0.5">
                      <WifiOff className="h-2 w-2" />
                      OFFLINE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${statusBg(
                      item.status,
                    )} ${statusColor(item.status)}`}
                  >
                    {item.status.toUpperCase().replace("_", " ")}
                  </span>
                  <Link
                    href={`/incidents/${item.id}${
                      item.source === "edge" ? "?source=edge" : ""
                    }`}
                    onClick={(e) => e.stopPropagation()}
                    className="p-1 text-muted hover:text-accent transition-colors"
                    title="View details"
                    aria-label={`View details for ${item.id}`}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
              <p className="text-xs text-muted line-clamp-2 mb-1.5">
                {item.description}
              </p>
              <div className="flex items-center gap-3 text-[10px] text-muted">
                <span className="flex items-center gap-1">
                  <Users className="h-2.5 w-2.5" />
                  {item.people_affected}
                </span>
                <span className="flex items-center gap-1">
                  <MapPin className="h-2.5 w-2.5" />
                  {item.latitude.toFixed(3)}, {item.longitude.toFixed(3)}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-2.5 w-2.5" />
                  {formatTime(item.created_at)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Show See More / Show Less only when more than 5 incidents exist */}
      {sorted.length > 5 && (
        <div className="px-4 py-2 border-t border-card-border/60 bg-surface/50 text-center">
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-1 text-xs font-semibold text-accent hover:text-accent-hover hover:bg-card border border-card-border rounded-md transition-colors cursor-pointer w-full shadow-2xs"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                <span>Show Less</span>
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                <span>See More</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
