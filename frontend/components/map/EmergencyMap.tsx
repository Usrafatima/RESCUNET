"use client";

import { useEffect, useRef, useState } from "react";
import type {
  Resource,
  RouteInfo,
  UnifiedIncident,
} from "@/lib/types";
import { ChevronRight, WifiOff } from "lucide-react";
import Link from "next/link";

// ─── Color helpers ────────────────────────────────────────────────────
// Palette: teal #168C91 · tangerine #FF945E · red #D64545
//          amber #D97706 · green #21845A · neutral #718486

function incidentColor(status: string): string {
  switch (status) {
    case "queued":
      return "#d97706"; // amber
    case "syncing":
      return "#ff945e"; // tangerine
    case "failed":
      return "#d64545"; // red
    case "analyzing":
      return "#d97706"; // amber
    case "awaiting_approval":
      return "#ff945e"; // tangerine — invites operator action
    case "approved":
      return "#21845a"; // green (transitional)
    case "dispatched":
      return "#168c91"; // teal — active response
    case "resolved":
      return "#718486"; // neutral (shouldn't appear on active map)
    default:
      return "#d97706";
  }
}

function resourceColor(type: string, status?: string): string {
  if (status === "deployed") return "#ff945e"; // tangerine for deployed
  if (status === "unavailable") return "#718486"; // neutral for unavailable
  switch (type) {
    case "medical":
      return "#d64545";
    case "rescue":
      return "#d97706";
    case "fire":
      return "#ff945e";
    case "supplies":
      return "#168c91";
    case "shelter":
      return "#21845a";
    default:
      return "#718486";
  }
}

// ─── Offset helper for close coordinates ──────────────────────────────

function offsetCoord(
  lat: number,
  lng: number,
  referenceLat: number,
  referenceLng: number,
  offsetMeters: number = 50,
): [number, number] {
  const dist = Math.sqrt(
    Math.pow((lat - referenceLat) * 111320, 2) +
      Math.pow((lng - referenceLng) * 111320 * Math.cos((lat * Math.PI) / 180), 2),
  );
  if (dist < offsetMeters) {
    // Offset slightly northeast
    const dLat = offsetMeters / 111320;
    const dLng = offsetMeters / (111320 * Math.cos((lat * Math.PI) / 180));
    return [lat + dLat, lng + dLng];
  }
  return [lat, lng];
}

// ─── Props ────────────────────────────────────────────────────────────

interface RouteLine {
  from: { lat: number; lng: number; label: string };
  to: { lat: number; lng: number; label: string };
  color?: string;
  distance?: string;
}

interface EmergencyMapProps {
  incidents: UnifiedIncident[];
  resources: Resource[];
  routeLine?: RouteLine | null;
  /** Known route restrictions (corridors) — drawn open/closed on the map. */
  routes?: RouteInfo[];
  selectedIncidentId?: string | null;
  onSelectIncident?: (incident: UnifiedIncident | null) => void;
}

// ─── Component ────────────────────────────────────────────────────────

export function EmergencyMap({
  incidents,
  resources,
  routeLine,
  routes = [],
  selectedIncidentId,
  onSelectIncident,
}: EmergencyMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapInstanceRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const leafletLibRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersLayerGroupRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const corridorsLayerGroupRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const routeLayerGroupRef = useRef<any>(null);
  const [selectedIncident, setSelectedIncident] =
    useState<UnifiedIncident | null>(null);
  const [leafletReady, setLeafletReady] = useState(false);
  const hasInitiallyFitted = useRef(false);

  // Sync selectedIncident when external selectedIncidentId changes
  useEffect(() => {
    if (selectedIncidentId) {
      const found = incidents.find((i) => i.id === selectedIncidentId);
      setSelectedIncident(found ?? null);
    } else {
      setSelectedIncident(null);
    }
  }, [selectedIncidentId, incidents]);

  // Initialize map
  useEffect(() => {
    if (!mapRef.current) return;

    const container = mapRef.current;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((container as any)._leaflet_id) return;

    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || !mapRef.current) return;
      leafletLibRef.current = L;

      // Fix default icon issue
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-shadow.png",
      });

      const map = L.map(mapRef.current!, {
        center: [24.8607, 67.0011],
        zoom: 13,
        zoomControl: true,
        attributionControl: true,
      });

      // Position zoom controls bottom-right to avoid legend overlap
      map.zoomControl.setPosition("bottomright");

      const cartoKey = process.env.NEXT_PUBLIC_CARTO_API_KEY || "";
      if (cartoKey) {
        const tileUrl = `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=${cartoKey}`;
        L.tileLayer(tileUrl, {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
      } else {
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }).addTo(map);
      }

      // Initialize dedicated layer groups attached to the map
      markersLayerGroupRef.current = L.layerGroup().addTo(map);
      corridorsLayerGroupRef.current = L.layerGroup().addTo(map);
      routeLayerGroupRef.current = L.layerGroup().addTo(map);

      mapInstanceRef.current = map;
      setLeafletReady(true);
    });

    return () => {
      cancelled = true;
      if (routeLayerGroupRef.current) {
        try {
          routeLayerGroupRef.current.clearLayers();
        } catch {}
        routeLayerGroupRef.current = null;
      }
      if (corridorsLayerGroupRef.current) {
        try {
          corridorsLayerGroupRef.current.clearLayers();
        } catch {}
        corridorsLayerGroupRef.current = null;
      }
      if (markersLayerGroupRef.current) {
        try {
          markersLayerGroupRef.current.clearLayers();
        } catch {}
        markersLayerGroupRef.current = null;
      }
      if (mapInstanceRef.current) {
        (mapInstanceRef.current as { remove: () => void }).remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Recalculate map size when container resizes (e.g. sidebar collapse/expand)
  useEffect(() => {
    if (!leafletReady || !mapRef.current) return;

    const ro = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (mapInstanceRef.current as any).invalidateSize();
      }
    });
    ro.observe(mapRef.current);
    return () => ro.disconnect();
  }, [leafletReady]);

  // ── Dedicated Route Line Effect ─────────────────────────────────
  // Holds only the current/newest incident's route polyline and midpoint distance marker.
  // Cleans up immediately when routeLine changes, unmounts, or becomes null/invalid.
  useEffect(() => {
    const routeGroup = routeLayerGroupRef.current;
    if (!leafletReady || !routeGroup) return;

    // Always clear existing route layers first to ensure no stale line persists
    routeGroup.clearLayers();

    if (!routeLine) {
      return;
    }

    const L = leafletLibRef.current;
    if (!L) return;

    const fromLat = routeLine.from?.lat;
    const fromLng = routeLine.from?.lng;
    const toLat = routeLine.to?.lat;
    const toLng = routeLine.to?.lng;

    // Validate coordinates strictly
    const isValidCoord = (lat?: number, lng?: number) =>
      typeof lat === "number" &&
      typeof lng === "number" &&
      !isNaN(lat) &&
      !isNaN(lng) &&
      lat >= -90 &&
      lat <= 90 &&
      lng >= -180 &&
      lng <= 180;

    if (!isValidCoord(fromLat, fromLng) || !isValidCoord(toLat, toLng)) {
      return;
    }

    try {
      const polyline = L.polyline(
        [
          [fromLat, fromLng],
          [toLat, toLng],
        ],
        {
          color: routeLine.color || "#168c91",
          weight: 3,
          opacity: 0.85,
          dashArray: "10, 6",
        },
      );
      routeGroup.addLayer(polyline);

      // Midpoint distance label if provided
      if (routeLine.distance) {
        const midLat = (fromLat + toLat) / 2;
        const midLng = (fromLng + toLng) / 2;
        const midMarker = L.marker([midLat, midLng], {
          icon: L.divIcon({
            className: "",
            html: `<div style="background:#ffffff;border:1px solid #168c91;border-radius:4px;padding:2px 8px;font-size:9px;font-weight:700;color:#11777b;white-space:nowrap;letter-spacing:0.5px;box-shadow:0 1px 4px rgba(38,58,59,0.15)">${routeLine.distance}</div>`,
            iconSize: [0, 0],
            iconAnchor: [0, 0],
          }),
        });
        routeGroup.addLayer(midMarker);
      }
    } catch (err) {
      console.error("[Map] Failed to render route line:", err);
      routeGroup.clearLayers();
    }

    return () => {
      routeGroup.clearLayers();
    };
  }, [leafletReady, routeLine]);

  // ── Dedicated Corridors Effect ──────────────────────────────────
  // Road restrictions: closed routes in red, open routes faintly in green
  useEffect(() => {
    const corridorsGroup = corridorsLayerGroupRef.current;
    if (!leafletReady || !corridorsGroup) return;

    corridorsGroup.clearLayers();

    const L = leafletLibRef.current;
    if (!L) return;

    routes.forEach((route) => {
      if (
        typeof route.from_lat !== "number" ||
        typeof route.from_lng !== "number" ||
        typeof route.to_lat !== "number" ||
        typeof route.to_lng !== "number"
      ) {
        return;
      }
      const closed = route.status === "closed";
      const color = closed ? "#d64545" : "#21845a";
      const label = closed ? "CLOSED" : "OPEN";

      const polyline = L.polyline(
        [
          [route.from_lat, route.from_lng],
          [route.to_lat, route.to_lng],
        ],
        {
          color,
          weight: closed ? 4 : 2,
          opacity: closed ? 0.9 : 0.35,
          dashArray: closed ? "6, 6" : "2, 8",
        },
      );
      corridorsGroup.addLayer(polyline);

      const midLat = (route.from_lat + route.to_lat) / 2;
      const midLng = (route.from_lng + route.to_lng) / 2;
      const marker = L.marker([midLat, midLng], {
        icon: L.divIcon({
          className: "",
          html: `<div style="background:#ffffff;border:1px solid ${color};border-radius:4px;padding:2px 6px;font-size:8px;font-weight:700;color:${color};white-space:nowrap;letter-spacing:0.5px;box-shadow:0 1px 4px rgba(38,58,59,0.15)">${label} · ${route.name}</div>`,
          iconSize: [0, 0],
          iconAnchor: [0, 0],
        }),
      });

      marker.bindTooltip(
        closed
          ? `${route.name} — CLOSED${
              route.restriction_reason ? `: ${route.restriction_reason}` : ""
            }${
              route.scope_resource_id
                ? ` (affects ${route.scope_resource_id})`
                : " (general corridor)"
            }`
          : `${route.name} — OPEN`,
        {
          className:
            "bg-card text-foreground border border-card-border text-xs px-2 py-1 rounded",
          direction: "top",
          offset: [0, -6],
        },
      );
      corridorsGroup.addLayer(marker);
    });

    return () => {
      corridorsGroup.clearLayers();
    };
  }, [leafletReady, routes]);

  // ── Dedicated Markers Effect ────────────────────────────────────
  // Holds incident markers and resource markers in markersLayerGroupRef
  useEffect(() => {
    const markersGroup = markersLayerGroupRef.current;
    if (!leafletReady || !markersGroup || !mapInstanceRef.current) return;

    markersGroup.clearLayers();

    const L = leafletLibRef.current;
    const map = mapInstanceRef.current as InstanceType<typeof L.Map>;
    if (!L || !map) return;

    // ── Incident markers ──────────────────────────────────────────
    incidents.forEach((item) => {
      if (
        typeof item.latitude !== "number" ||
        typeof item.longitude !== "number" ||
        isNaN(item.latitude) ||
        isNaN(item.longitude)
      ) {
        return;
      }
      const isEdge = item.source === "edge";
      const isDispatched = item.status === "dispatched";
      const color = incidentColor(item.status);

      // Marker sizing
      const baseSize = isDispatched ? 30 : 24;
      const innerSize = isDispatched ? 22 : 16;
      const offset = (baseSize - innerSize) / 2;

      let markerHtml = "";
      if (isDispatched && !isEdge) {
        markerHtml = `
          <div style="position:relative;width:${baseSize}px;height:${baseSize}px">
            <div style="position:absolute;width:${baseSize}px;height:${baseSize}px;border-radius:50%;background:${color};opacity:0.25" class="pulse-ring"></div>
            <div style="position:absolute;width:${baseSize}px;height:${baseSize}px;border-radius:50%;border:2.5px solid ${color};background:transparent"></div>
            <div style="position:absolute;top:${offset}px;left:${offset}px;width:${innerSize}px;height:${innerSize}px;border-radius:50%;background:${color};border:2px solid white"></div>
            <div style="position:absolute;top:${offset + 3}px;left:${offset + 3}px;width:${innerSize - 6}px;height:${innerSize - 6}px;border-radius:50%;border:1.5px solid rgba(255,255,255,0.6)"></div>
            <div style="position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);background:${color};color:#fff;font-size:7px;font-weight:700;letter-spacing:0.5px;padding:1px 4px;border-radius:2px;white-space:nowrap;border:1px solid rgba(22,140,145,0.5)">DISPATCHED</div>
          </div>`;
      } else if (isEdge) {
        const edgeRingStyle = `border:2px dashed ${color};border-radius:50%;width:${baseSize}px;height:${baseSize}px;position:absolute;top:0;left:0;opacity:0.7`;
        markerHtml = `
          <div style="position:relative;width:${baseSize}px;height:${baseSize}px">
            <div style="${edgeRingStyle}"></div>
            <div style="position:absolute;top:${offset}px;left:${offset}px;width:${innerSize}px;height:${innerSize}px;border-radius:50%;background:${color};border:2px solid #ffffff"></div>
            <div style="position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);background:#ff945e;color:#263a3b;font-size:7px;font-weight:700;letter-spacing:0.5px;padding:1px 3px;border-radius:2px;white-space:nowrap;border:1px solid #ffb48e">OFFLINE</div>
          </div>`;
      } else {
        markerHtml = `
          <div style="position:relative;width:${baseSize}px;height:${baseSize}px">
            <div style="position:absolute;width:${baseSize}px;height:${baseSize}px;border-radius:50%;background:${color};opacity:0.3" class="pulse-ring"></div>
            <div style="position:absolute;top:${offset}px;left:${offset}px;width:${innerSize}px;height:${innerSize}px;border-radius:50%;background:${color};border:2px solid white"></div>
          </div>`;
      }

      const icon = L.divIcon({
        className: "",
        html: markerHtml,
        iconSize: [baseSize, baseSize + (isEdge ? 8 : isDispatched ? 10 : 0)],
        iconAnchor: [baseSize / 2, baseSize / 2 + (isEdge ? 4 : isDispatched ? 5 : 0)],
      });

      const tooltipText = isEdge
        ? `${item.id} — QUEUED LOCALLY`
        : isDispatched
        ? `${item.id} — DISPATCHED`
        : `${item.id} — ${item.status.toUpperCase()}`;

      const marker = L.marker([item.latitude, item.longitude], { icon })
        .on("click", () => {
          setSelectedIncident(item);
          onSelectIncident?.(item);
        });

      marker.bindTooltip(tooltipText, {
        className:
          "bg-card text-foreground border border-card-border text-xs px-2 py-1 rounded",
        direction: "top",
        offset: [0, isEdge ? -16 : isDispatched ? -18 : -12],
      });

      markersGroup.addLayer(marker);
    });

    // ── Resource markers ──────────────────────────────────────────
    resources.forEach((resource) => {
      if (resource.status === "unavailable") return;
      if (
        typeof resource.latitude !== "number" ||
        typeof resource.longitude !== "number" ||
        isNaN(resource.latitude) ||
        isNaN(resource.longitude)
      ) {
        return;
      }

      const isDeployed = resource.status === "deployed";
      const color = resourceColor(resource.type, resource.status);
      const size = isDeployed ? 16 : 12;

      let resLat = resource.latitude;
      let resLng = resource.longitude;
      if (isDeployed && resource.assigned_incident_id) {
        const assignedIncident = incidents.find(
          (i) => i.id === resource.assigned_incident_id,
        );
        if (assignedIncident) {
          [resLat, resLng] = offsetCoord(
            resource.latitude,
            resource.longitude,
            assignedIncident.latitude,
            assignedIncident.longitude,
            60,
          );
        }
      }

      let resHtml = "";
      if (isDeployed) {
        resHtml = `
          <div style="position:relative">
            <div style="width:${size}px;height:${size}px;border-radius:3px;background:${color};border:1.5px solid white;box-shadow:0 0 6px rgba(255,148,94,0.7)"></div>
            <div style="position:absolute;top:-7px;right:-20px;background:${color};color:#263a3b;font-size:6px;font-weight:700;letter-spacing:0.5px;padding:1px 3px;border-radius:2px;white-space:nowrap">DEPLOYED</div>
          </div>`;
      } else {
        resHtml = `
          <div style="width:${size}px;height:${size}px;border-radius:3px;background:${color};border:1.5px solid white;opacity:0.85"></div>`;
      }

      const icon = L.divIcon({
        className: "",
        html: resHtml,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      });

      const tooltipContent = isDeployed
        ? `${resource.name} — DEPLOYED → ${resource.assigned_incident_id || "unknown"}`
        : `${resource.name} — AVAILABLE`;

      const marker = L.marker([resLat, resLng], { icon }).bindTooltip(
        tooltipContent,
        {
          className:
            "bg-card text-foreground border border-card-border text-xs px-2 py-1 rounded",
          direction: "top",
          offset: [0, isDeployed ? -14 : -8],
        },
      );

      markersGroup.addLayer(marker);
    });

    // ── Fit bounds ONLY on first load ─────────────────────────────
    if (!hasInitiallyFitted.current) {
      const allPoints: [number, number][] = [
        ...incidents.map((i) => [i.latitude, i.longitude] as [number, number]),
        ...resources
          .filter((r) => r.status !== "unavailable")
          .map((r) => [r.latitude, r.longitude] as [number, number]),
      ];
      if (allPoints.length > 0) {
        map.fitBounds(L.latLngBounds(allPoints).pad(0.2));
        hasInitiallyFitted.current = true;
      }
    }

    return () => {
      markersGroup.clearLayers();
    };
  }, [incidents, resources, leafletReady, onSelectIncident]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapRef} className="h-full w-full" />

      {/* Map legend */}
      <div className="absolute top-3 left-3 bg-card/95 backdrop-blur-sm border border-card-border rounded-md p-2.5 space-y-1 z-[1000] shadow-sm">
        <div className="text-[10px] font-semibold text-foreground mb-1">
          Incidents
        </div>
        {(
          ["queued", "analyzing", "dispatched", "resolved"] as const
        ).map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: incidentColor(s) }}
            />
            <span className="text-[9px] text-muted uppercase tracking-wider">
              {s}
            </span>
          </div>
        ))}
        {/* Edge offline legend entry */}
        <div className="flex items-center gap-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{
              background: "#ff945e",
              border: "1.5px dashed #ff945e",
            }}
          />
          <span className="text-[9px] text-muted uppercase tracking-wider">
            OFFLINE QUEUED
          </span>
        </div>
        <div className="text-[10px] font-semibold text-foreground mt-2 mb-1">
          Resources
        </div>
        {(["medical", "rescue", "fire", "supplies", "shelter"] as const).map(
          (t) => (
            <div key={t} className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-sm"
                style={{ background: resourceColor(t) }}
              />
              <span className="text-[9px] text-muted uppercase tracking-wider">
                {t}
              </span>
            </div>
          ),
        )}
        {/* Deployed resource legend */}
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-sm"
            style={{ background: "#ff945e", boxShadow: "0 0 4px #ff945e" }}
          />
          <span className="text-[9px] text-muted uppercase tracking-wider">
            DEPLOYED
          </span>
        </div>
      </div>

      {/* Selected incident popup */}
      {selectedIncident && (
        <div className="absolute bottom-3 left-3 right-3 md:left-auto md:right-3 md:w-80 bg-card/95 backdrop-blur-sm border border-card-border rounded-md p-4 z-[1000] shadow-lg">
          {/* Edge-only offline banner */}
          {selectedIncident.source === "edge" && (
            <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded bg-tangerine/10 border border-tangerine/40">
              <WifiOff className="h-3.5 w-3.5 text-info shrink-0" />
              <span className="text-[10px] font-semibold text-info">
                OFFLINE INCIDENT
              </span>
            </div>
          )}

          <div className="flex items-start justify-between mb-2">
            <div>
              <span className="text-xs font-mono text-accent">
                {selectedIncident.id}
              </span>
              <h3 className="text-sm font-medium mt-0.5">
                {selectedIncident.description}
              </h3>
            </div>
            <button
              onClick={() => {
                setSelectedIncident(null);
                onSelectIncident?.(null);
              }}
              className="text-muted hover:text-foreground text-xs"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs mb-3">
            <div>
              <span className="text-muted">People: </span>
              <span className="font-mono">
                {selectedIncident.people_affected}
              </span>
            </div>
            <div>
              <span className="text-muted">Status: </span>
              <span
                className="font-mono uppercase"
                style={{ color: incidentColor(selectedIncident.status) }}
              >
                {selectedIncident.status}
              </span>
            </div>
            <div>
              <span className="text-muted">Coords: </span>
              <span className="font-mono text-[10px]">
                {selectedIncident.latitude.toFixed(4)},{" "}
                {selectedIncident.longitude.toFixed(4)}
              </span>
            </div>
            <div>
              <span className="text-muted">Source: </span>
              <span className="font-mono uppercase">
                {selectedIncident.source === "edge" ? "EDGE" : "BACKEND"}
              </span>
            </div>
          </div>

          {/* Edge-specific offline waiting message */}
          {selectedIncident.source === "edge" && (
            <div className="flex items-center gap-2 text-xs text-info mb-3">
              <div className="w-1.5 h-1.5 rounded-full bg-tangerine animate-pulse" />
              QUEUED LOCALLY — Waiting for connectivity
            </div>
          )}

          <Link
            href={`/incidents/${selectedIncident.id}${
              selectedIncident.source === "edge" ? "?source=edge" : ""
            }`}
            className="flex items-center gap-1 text-xs text-accent hover:text-accent/80 transition-colors"
          >
            View details <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </div>
  );
}
