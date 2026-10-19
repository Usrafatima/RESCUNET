"use client";

import { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle,
  Bot,
  Wifi,
  WifiOff,
  Shield,
  Clock,
  Plus,
  RefreshCw,
} from "lucide-react";
import type {
  Incident,
  EdgeConnectivity,
  EdgePacket,
  Resource,
  UIIncidentStatus,
} from "@/lib/types";
import { mergeIncidents, isInsidePakistan } from "@/lib/types";
import { getIncidents, getResources, getRecommendation, getRoutes } from "@/lib/api";
import type { RecommendationResponse, RouteInfo } from "@/lib/types";
import {
  getEdgeConnectivity,
  getEdgeQueue,
} from "@/lib/edge-api";
import { EmergencyMap } from "@/components/map/EmergencyMap";
import { IncidentFeed } from "@/components/incidents/IncidentFeed";
import { EdgeStatusPanel } from "@/components/edge/EdgeStatusPanel";
import { PendingApprovals } from "@/components/plans/PendingApprovals";
import { PriorityQueue } from "@/components/dashboard/PriorityQueue";
import { CreateIncidentModal } from "@/components/incidents/CreateIncidentModal";
import Link from "next/link";

function isValidCoordinate(lat: unknown, lng: unknown): boolean {
  return (
    typeof lat === "number" &&
    typeof lng === "number" &&
    !isNaN(lat) &&
    !isNaN(lng) &&
    isFinite(lat) &&
    isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

export function DashboardContent() {
  const [backendIncidents, setBackendIncidents] = useState<Incident[]>([]);
  const [edgePackets, setEdgePackets] = useState<EdgePacket[]>([]);
  const [connectivity, setConnectivity] = useState<EdgeConnectivity | null>(
    null,
  );
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [resources, setResources] = useState<Resource[]>([]);
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [activeRecommendation, setActiveRecommendation] = useState<RecommendationResponse | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [incidentsData, connData, queueData, resourcesData, routesData] =
        await Promise.allSettled([
          getIncidents(),
          getEdgeConnectivity(),
          getEdgeQueue(),
          getResources(),
          getRoutes(),
        ]);

      if (incidentsData.status === "fulfilled")
        setBackendIncidents(incidentsData.value);
      if (connData.status === "fulfilled") setConnectivity(connData.value);
      if (queueData.status === "fulfilled") setEdgePackets(queueData.value);
      if (resourcesData.status === "fulfilled")
        setResources(resourcesData.value);
      if (routesData.status === "fulfilled")
        setRoutes(routesData.value.routes);
    } catch {
      // APIs may be unreachable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000);
    const handleRefresh = () => {
      fetchData();
    };
    window.addEventListener("rescunet:refresh", handleRefresh);
    window.addEventListener("focus", handleRefresh);
    return () => {
      clearInterval(interval);
      window.removeEventListener("rescunet:refresh", handleRefresh);
      window.removeEventListener("focus", handleRefresh);
    };
  }, [fetchData]);

  // Merge and deduplicate backend incidents with edge queue
  const allUnifiedIncidents = mergeIncidents(backendIncidents, edgePackets);

  // Filter: active emergencies appear on the map.
  // Exclude resolved, failed (cancelled) incidents, and any incident outside Pakistan.
  const mapIncidents = allUnifiedIncidents.filter(
    (i) =>
      !(["resolved", "failed"] as UIIncidentStatus[]).includes(i.status) &&
      isInsidePakistan(i.latitude, i.longitude),
  );

  // Active incident for map route display:
  // Use explicitly selected incident if valid, otherwise fallback to the newest incident displayed
  const currentIncident = (() => {
    if (selectedIncidentId) {
      const found = mapIncidents.find((i) => i.id === selectedIncidentId);
      if (found) return found;
    }
    return mapIncidents.length > 0 ? mapIncidents[0] : null;
  })();

  // Synchronize recommendation with currentIncident (selected or newest)
  useEffect(() => {
    let cancelled = false;

    if (!currentIncident?.id) {
      setActiveRecommendation(null);
      return;
    }

    const targetId = currentIncident.id;

    // Clear previous recommendation before fetching new one so stale route line disappears immediately
    setActiveRecommendation((prev) => (prev?.incident_id === targetId ? prev : null));

    getRecommendation(targetId)
      .then((rec) => {
        if (!cancelled) {
          if (rec && rec.incident_id === targetId && rec.recommended_resource) {
            setActiveRecommendation(rec);
          } else {
            setActiveRecommendation(null);
          }
        }
      })
      .catch(() => {
        // If recommendation not available or failed, ensure activeRecommendation is cleared
        if (!cancelled) {
          setActiveRecommendation(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentIncident?.id]);

  // Stats — use unified data for accurate counting
  const centralActive = backendIncidents.filter(
    (i) => !["resolved", "cancelled"].includes(i.status),
  );
  const edgeQueued = edgePackets.filter(
    (p) => p.status === "queued" || p.status === "failed",
  );
  const activeUnified = allUnifiedIncidents.filter(
    (i) => !["resolved", "cancelled", "synced"].includes(i.status),
  );
  const analyzedCount = backendIncidents.filter(
    (i) => i.status !== "queued",
  ).length;
  const availableResources = resources.filter((r) => r.status === "available");

  // Build validated route line strictly for current incident
  const validRouteLine = (() => {
    if (!activeRecommendation || !currentIncident) return null;
    if (activeRecommendation.incident_id !== currentIncident.id) return null;

    const res = activeRecommendation.recommended_resource;
    if (!res) return null;

    const fromLat = res.latitude;
    const fromLng = res.longitude;
    const toLat = currentIncident.latitude;
    const toLng = currentIncident.longitude;

    if (!isValidCoordinate(fromLat, fromLng) || !isValidCoordinate(toLat, toLng)) {
      return null;
    }

    return {
      from: {
        lat: fromLat,
        lng: fromLng,
        label: res.name || "Resource",
      },
      to: {
        lat: toLat,
        lng: toLng,
        label: currentIncident.id,
      },
      distance:
        typeof res.distance_km === "number" && !isNaN(res.distance_km)
          ? `${res.distance_km.toFixed(1)} km`
          : undefined,
    };
  })();

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-2.5 border-b border-card-border bg-surface">
        <div className="min-w-0">
          <h1 className="text-base font-semibold tracking-wide">
            Command Center
          </h1>
          <p className="text-[11px] text-muted truncate">
            AI emergency coordination
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium border ${
              connectivity?.online
                ? "bg-success/10 text-success border-success/30"
                : "bg-tangerine/15 text-info border-tangerine/40"
            }`}
          >
            {connectivity?.online ? (
              <Wifi className="h-3 w-3" />
            ) : (
              <WifiOff className="h-3 w-3" />
            )}
            {connectivity?.online ? "SYSTEM ONLINE" : "OFFLINE EDGE MODE"}
          </div>
          <button
            onClick={fetchData}
            className="p-1.5 text-muted hover:text-accent transition-colors"
            title="Refresh"
            aria-label="Refresh dashboard"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-xs font-semibold rounded-md hover:bg-accent-hover transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            REPORT EMERGENCY
          </button>
        </div>
      </div>

      {/* Stats row — 5 columns for richer breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 px-4 md:px-6 py-2.5 border-b border-card-border">
        <StatCard
          label="Central incidents"
          value={centralActive.length}
          icon={AlertTriangle}
          color="text-danger"
        />
        <StatCard
          label="Offline queued"
          value={edgeQueued.length}
          icon={Clock}
          color="text-info"
        />
        <StatCard
          label="Total active"
          value={activeUnified.length}
          icon={Shield}
          color="text-accent"
        />
        <StatCard
          label="AI analyzed"
          value={analyzedCount}
          icon={Bot}
          color="text-success"
        />
        <StatCard
          label="Available resources"
          value={availableResources.length}
          icon={Shield}
          color="text-success"
        />
      </div>

      {/* Main content grid — incidents panel | map */}
      <div className="flex-1 grid overflow-hidden" style={{ gridTemplateColumns: 'minmax(420px, 480px) minmax(0, 1fr)' }}>
        {/* Incidents / Priority Queue panel */}
        <div className="flex flex-col overflow-hidden border-r border-card-border min-h-0">
          <EdgeStatusPanel onSyncComplete={fetchData} />
          <div className="flex-1 overflow-y-auto">
            <PendingApprovals />
            <PriorityQueue />
            <IncidentFeed
              incidents={allUnifiedIncidents}
              loading={loading}
              selectedIncidentId={selectedIncidentId}
              onSelectIncident={(inc) => setSelectedIncidentId(inc.id)}
            />
          </div>
          <Link
            href="/incidents"
            className="block px-4 py-1.5 text-center text-[11px] text-muted hover:text-accent border-t border-card-border hover:bg-card transition-colors"
          >
            VIEW ALL INCIDENTS →
          </Link>
        </div>

        <div className="min-w-0 min-h-0 border-l border-card-border">
          <EmergencyMap
            incidents={mapIncidents}
            resources={resources}
            routeLine={validRouteLine}
            routes={routes}
            selectedIncidentId={selectedIncidentId}
            onSelectIncident={(inc) => setSelectedIncidentId(inc ? inc.id : null)}
          />
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

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  color: string;
}) {
  return (
    <div className="bg-card border border-card-border rounded-md px-3 py-2">
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className={`h-3 w-3 ${color}`} />
        <span className="text-[10px] text-muted truncate">{label}</span>
      </div>
      <div className={`text-xl font-semibold font-mono ${color}`}>
        {value}
      </div>
    </div>
  );
}
