"use client";

import { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle,
  Users,
  MapPin,
  Clock,
  Plus,
  RefreshCw,
  ChevronRight,
  Loader2,
  WifiOff,
} from "lucide-react";
import type { UnifiedIncident } from "@/lib/types";
import { mergeIncidents } from "@/lib/types";
import { getIncidents } from "@/lib/api";
import {
  getEdgeConnectivity,
  getEdgeQueue,
} from "@/lib/edge-api";
import type { EdgeConnectivity } from "@/lib/types";
import { CreateIncidentModal } from "@/components/incidents/CreateIncidentModal";
import Link from "next/link";

function statusColor(status: string): string {
  switch (status) {
    case "queued": return "text-info";
    case "syncing": return "text-accent";
    case "failed": return "text-danger";
    case "analyzing":
    case "awaiting_approval": return "text-warning-ink";
    case "approved":
    case "dispatched": return "text-success";
    case "resolved": return "text-neutral";
    default: return "text-neutral";
  }
}

function statusBorder(status: string): string {
  switch (status) {
    case "queued": return "border-l-tangerine";
    case "syncing": return "border-l-accent";
    case "failed": return "border-l-danger";
    case "analyzing":
    case "awaiting_approval": return "border-l-warning";
    case "approved":
    case "dispatched": return "border-l-success";
    case "resolved": return "border-l-muted";
    default: return "border-l-muted";
  }
}

export default function IncidentsPage() {
  const [unifiedIncidents, setUnifiedIncidents] = useState<UnifiedIncident[]>([]);
  const [connectivity, setConnectivity] = useState<EdgeConnectivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  const fetchData = useCallback(async () => {
    try {
      const [incData, connData, queueData] = await Promise.allSettled([
        getIncidents(),
        getEdgeConnectivity(),
        getEdgeQueue(),
      ]);
      const backendIncidents = incData.status === "fulfilled" ? incData.value : [];
      const edgePackets = queueData.status === "fulfilled" ? queueData.value : [];
      setUnifiedIncidents(mergeIncidents(backendIncidents, edgePackets));
      if (connData.status === "fulfilled") setConnectivity(connData.value);
    } catch {
      // APIs may be unreachable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const filtered = unifiedIncidents.filter((item) => {
    if (filter === "all") return true;
    if (filter === "active") return !["resolved", "cancelled", "synced"].includes(item.status);
    return item.status === filter;
  });

  const activeCount = unifiedIncidents.filter(
    (i) => !["resolved", "cancelled", "synced"].includes(i.status),
  ).length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-2.5 border-b border-card-border bg-surface">
        <div className="min-w-0">
          <h1 className="text-base font-semibold tracking-wide">Incidents</h1>
          <p className="text-[11px] text-muted">
            {unifiedIncidents.length} total · {activeCount} active
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            className="p-1.5 text-muted hover:text-accent transition-colors"
            aria-label="Refresh incidents"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-semibold rounded-md hover:bg-accent-hover transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            REPORT
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-1.5 px-4 md:px-6 py-1.5 border-b border-card-border overflow-x-auto">
        {["all", "active", "queued", "analyzing", "dispatched", "resolved"].map(
          (f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 text-[11px] rounded-md border transition-colors whitespace-nowrap ${
                filter === f
                  ? "border-accent/50 bg-accent/10 text-accent font-semibold"
                  : "border-card-border text-muted hover:text-foreground hover:bg-card"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ),
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 text-muted animate-spin" />
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <AlertTriangle className="h-8 w-8 text-muted/30 mb-3" />
            <div className="text-sm text-muted">No incidents found</div>
            <div className="text-xs text-muted/70 mt-1">
              {filter !== "all" ? "Try a different filter" : "Report an emergency to get started"}
            </div>
          </div>
        )}

        <div className="divide-y divide-card-border/50">
          {filtered.map((item) => (
            <Link
              key={item.id}
              href={`/incidents/${item.id}${item.source === "edge" ? "?source=edge" : ""}`}
              className={`block px-4 md:px-6 py-3 hover:bg-card transition-colors border-l-2 ${statusBorder(
                item.status,
              )}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-accent">
                      {item.id}
                    </span>
                    {item.source === "edge" && (
                      <span className="flex items-center gap-0.5 text-[8px] font-bold px-1 py-0.5 rounded border border-tangerine/40 bg-tangerine/10 text-info">
                        <WifiOff className="h-2 w-2" />
                        OFFLINE
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-foreground mb-2 line-clamp-2">
                    {item.description}
                  </p>
                  <div className="flex items-center gap-4 text-[10px] text-muted">
                    <span className="flex items-center gap-1">
                      <Users className="h-2.5 w-2.5" />
                      {item.people_affected} affected
                    </span>
                    <span className="flex items-center gap-1">
                      <MapPin className="h-2.5 w-2.5" />
                      {item.latitude.toFixed(3)}, {item.longitude.toFixed(3)}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {new Date(item.created_at).toLocaleTimeString("en-US", {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: false,
                      })}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-3">
                  <span
                    className={`text-[9px] font-semibold px-2 py-0.5 rounded border ${statusColor(
                      item.status,
                    )} bg-card border-card-border`}
                  >
                    {item.status.toUpperCase().replace("_", " ")}
                  </span>
                  <ChevronRight className="h-4 w-4 text-muted/50" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {showCreateModal && (
        <CreateIncidentModal
          onClose={() => setShowCreateModal(false)}
          onCreated={fetchData}
          connectivity={connectivity}
        />
      )}
    </div>
  );
}
