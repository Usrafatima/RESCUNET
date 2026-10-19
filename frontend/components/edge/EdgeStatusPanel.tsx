"use client";

// Edge gateway status panel — collapsible
import { useEffect, useState, useCallback } from "react";
import {
  Wifi,
  WifiOff,
  RefreshCw,
  ArrowUpCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { EdgeConnectivity, EdgePacket, EdgeGatewayStatus } from "@/lib/types";
import {
  getEdgeConnectivity,
  setEdgeConnectivity,
  getEdgeQueue,
  getEdgeStatus,
  syncEdgeQueue,
} from "@/lib/edge-api";

export function EdgeStatusPanel({
  onSyncComplete,
}: {
  onSyncComplete?: () => void;
}) {
  const [connectivity, setConnectivityState] =
    useState<EdgeConnectivity | null>(null);
  const [packets, setPackets] = useState<EdgePacket[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [syncResult, setSyncResult] = useState<{
    synced: number;
    failed: number;
  } | null>(null);
  const [edgeError, setEdgeError] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [gatewayStatus, setGatewayStatus] =
    useState<EdgeGatewayStatus | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [conn, queue, status] = await Promise.allSettled([
        getEdgeConnectivity(),
        getEdgeQueue(),
        getEdgeStatus(),
      ]);
      if (conn.status === "fulfilled") {
        setConnectivityState(conn.value);
        setEdgeError(false);
      } else {
        setEdgeError(true);
      }
      if (queue.status === "fulfilled") setPackets(queue.value);
      if (status.status === "fulfilled") setGatewayStatus(status.value);
    } catch {
      setEdgeError(true);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleConnectivity = async () => {
    if (!connectivity || toggling) return;
    setToggling(true);
    try {
      await setEdgeConnectivity(!connectivity.online);
      await fetchData();
    } catch {
      // ignore
    } finally {
      setToggling(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await syncEdgeQueue();
      setSyncResult({ synced: result.synced, failed: result.failed });
      await fetchData();
      onSyncComplete?.();
    } catch {
      setSyncResult({ synced: 0, failed: 0 });
    } finally {
      setSyncing(false);
    }
  };

  const queuedPackets = packets.filter(
    (p) => p.status === "queued" || p.status === "failed",
  );

  // ── Error state ──
  if (edgeError) {
    return (
      <div className="px-4 py-2 border-b border-card-border bg-danger/5">
        <div className="flex items-center gap-2 text-xs text-danger">
          <WifiOff className="h-3 w-3" />
          <span className="font-medium text-[11px]">EDGE UNREACHABLE</span>
        </div>
        <p className="text-[10px] text-muted mt-0.5">
          Start edge gateway on port 8001
        </p>
      </div>
    );
  }

  // ── Collapsed: thin status bar ──
  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full flex items-center justify-between px-4 py-1.5 border-b border-card-border bg-surface hover:bg-card transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`w-2 h-2 rounded-full shrink-0 ${
              connectivity?.online ? "bg-success" : "bg-tangerine"
            }`}
          />
          <span className="text-[11px] text-muted font-medium truncate">
            Edge
          </span>
          <span
            className={`text-[11px] font-semibold ${
              connectivity?.online ? "text-success" : "text-info"
            }`}
          >
            {connectivity?.mode || "UNKNOWN"}
          </span>
          {queuedPackets.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-tangerine/15 text-info font-mono font-bold border border-tangerine/40">
              {queuedPackets.length}
            </span>
          )}
        </div>
        <ChevronDown className="h-3 w-3 text-muted shrink-0" />
      </button>
    );
  }

  // ── Expanded: full panel ──
  return (
    <div className="border-b border-card-border">
      {/* Compact header with collapse toggle */}
      <button
        onClick={() => setExpanded(false)}
        className="w-full flex items-center justify-between px-4 py-1.5 hover:bg-card transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={`w-2 h-2 rounded-full shrink-0 ${
              connectivity?.online ? "bg-success" : "bg-tangerine"
            }`}
          />
          <span className="text-[11px] font-medium">
            Edge connectivity
          </span>
        </div>
        <ChevronUp className="h-3 w-3 text-muted shrink-0" />
      </button>

      <div className="px-4 pb-3 space-y-2">
        {/* Status + refresh */}
        <div className="flex items-center justify-between">
          <span
            className={`text-xs font-semibold ${
              connectivity?.online ? "text-success" : "text-info"
            }`}
          >
            {connectivity?.mode || "UNKNOWN"}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              fetchData();
            }}
            className="p-1 text-muted hover:text-foreground transition-colors"
            title="Refresh"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        </div>

        {/* Queue count */}
        <div className="text-[11px] text-muted">
          {queuedPackets.length > 0 ? (
            <span className="text-info font-medium">
              {queuedPackets.length} waiting to sync
            </span>
          ) : (
            <span>Local queue empty</span>
          )}
        </div>

        {/* Per-state breakdown + backend reachability */}
        {gatewayStatus && (
          <div className="grid grid-cols-4 gap-1 text-center">
            {(
              [
                ["QUEUED", gatewayStatus.packets.queued ?? 0, "text-info"],
                ["SYNCING", gatewayStatus.packets.syncing ?? 0, "text-accent"],
                ["SYNCED", gatewayStatus.packets.synced ?? 0, "text-success"],
                ["FAILED", gatewayStatus.packets.failed ?? 0, "text-danger"],
              ] as const
            ).map(([label, count, color]) => (
              <div
                key={label}
                className="rounded bg-card border border-card-border py-1"
              >
                <div className={`text-[11px] font-mono font-bold ${color}`}>
                  {count}
                </div>
                <div className="text-[8px] tracking-wider text-muted">
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}

        {gatewayStatus && gatewayStatus.online && (
          <div className="flex items-center gap-1.5 text-[9px] text-muted">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                gatewayStatus.backend_reachable ? "bg-success" : "bg-danger"
              }`}
            />
            Backend {gatewayStatus.backend_reachable ? "reachable" : "unreachable"}
            <span className="font-mono truncate">({gatewayStatus.backend_url})</span>
          </div>
        )}

        {/* Toggle button */}
        <button
          onClick={toggleConnectivity}
          disabled={toggling}
          className={`w-full flex items-center justify-center gap-2 px-3 py-1.5 text-[11px] font-semibold rounded-md border transition-colors ${
            connectivity?.online
              ? "border-danger/30 text-danger hover:bg-danger/10"
              : "border-success/30 text-success hover:bg-success/10"
          }`}
        >
          {toggling ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : connectivity?.online ? (
            <WifiOff className="h-3 w-3" />
          ) : (
            <Wifi className="h-3 w-3" />
          )}
          {connectivity?.online ? "GO OFFLINE" : "GO ONLINE"}
        </button>

        {/* Sync button */}
        {connectivity?.online && queuedPackets.length > 0 && (
          <button
            onClick={handleSync}
            disabled={syncing}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-[11px] font-semibold rounded-md border border-tangerine/50 text-info hover:bg-tangerine/10 transition-colors disabled:opacity-50"
          >
            {syncing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <ArrowUpCircle className="h-3 w-3" />
            )}
            SYNC NOW ({queuedPackets.length})
          </button>
        )}

        {/* Sync result */}
        {syncResult && (
          <div
            className={`text-[11px] px-2 py-1 rounded ${
              syncResult.failed > 0
                ? "bg-danger/10 text-danger"
                : "bg-success/10 text-success"
            }`}
          >
            Synced: {syncResult.synced} | Failed: {syncResult.failed}
          </div>
        )}

        {/* Packet list */}
        {packets.length > 0 && (
          <div className="space-y-1">
            <div className="text-[9px] text-muted tracking-wider font-medium">
              QUEUE ({packets.length})
            </div>
            {packets.slice(0, 5).map((pkt) => (
              <div
                key={pkt.packet_id}
                className="flex items-center gap-2 text-[10px] py-0.5"
              >
                <PacketStatusIcon status={pkt.status} />
                <span className="font-mono text-muted truncate flex-1">
                  {pkt.packet_id}
                </span>
                <span
                  className={`tracking-wide ${
                    pkt.status === "synced"
                      ? "text-success"
                      : pkt.status === "failed"
                        ? "text-danger"
                        : pkt.status === "syncing"
                          ? "text-accent"
                          : "text-info"
                  }`}
                >
                  {pkt.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PacketStatusIcon({ status }: { status: string }) {
  switch (status) {
    case "queued":
      return <Clock className="h-2.5 w-2.5 text-info" />;
    case "syncing":
      return <Loader2 className="h-2.5 w-2.5 text-accent animate-spin" />;
    case "synced":
      return <CheckCircle2 className="h-2.5 w-2.5 text-success" />;
    case "failed":
      return <XCircle className="h-2.5 w-2.5 text-danger" />;
    default:
      return <Clock className="h-2.5 w-2.5 text-muted" />;
  }
}
