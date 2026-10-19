"use client";

import { useEffect, useState, useCallback } from "react";
import { Wifi, WifiOff, Radio, RefreshCw } from "lucide-react";
import { getHealth } from "@/lib/api";
import { getEdgeConnectivity } from "@/lib/edge-api";
import { useCitizenLanguage } from "./LanguageContext";

export type NetworkMode = "online" | "edge" | "offline" | "checking";

interface NetworkStatusBadgeProps {
  onStatusChange?: (mode: NetworkMode) => void;
  showDetails?: boolean;
}

export function NetworkStatusBadge({
  onStatusChange,
  showDetails = false,
}: NetworkStatusBadgeProps) {
  const { t } = useCitizenLanguage();
  const [mode, setMode] = useState<NetworkMode>("checking");
  const [checking, setChecking] = useState(false);

  const checkStatus = useCallback(async () => {
    setChecking(true);
    let backendOnline = false;
    let edgeOnline = false;

    try {
      const backendRes = await getHealth();
      if (backendRes?.status === "healthy") {
        backendOnline = true;
      }
    } catch {
      backendOnline = false;
    }

    try {
      const edgeRes = await getEdgeConnectivity();
      if (edgeRes) {
        edgeOnline = true;
      }
    } catch {
      edgeOnline = false;
    }

    let resolvedMode: NetworkMode = "offline";
    if (backendOnline) {
      resolvedMode = "online";
    } else if (edgeOnline) {
      resolvedMode = "edge";
    } else {
      resolvedMode = "offline";
    }

    setMode(resolvedMode);
    onStatusChange?.(resolvedMode);
    setChecking(false);
  }, [onStatusChange]);

  useEffect(() => {
    let active = true;

    async function probe() {
      let backendOnline = false;
      let edgeOnline = false;

      try {
        const backendRes = await getHealth();
        if (backendRes?.status === "healthy") {
          backendOnline = true;
        }
      } catch {
        backendOnline = false;
      }

      try {
        const edgeRes = await getEdgeConnectivity();
        if (edgeRes) {
          edgeOnline = true;
        }
      } catch {
        edgeOnline = false;
      }

      if (!active) return;

      let resolvedMode: NetworkMode = "offline";
      if (backendOnline) {
        resolvedMode = "online";
      } else if (edgeOnline) {
        resolvedMode = "edge";
      } else {
        resolvedMode = "offline";
      }

      setMode(resolvedMode);
      onStatusChange?.(resolvedMode);
    }

    probe();
    const interval = setInterval(probe, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [onStatusChange]);

  return (
    <div className="inline-flex items-center gap-2">
      {mode === "online" && (
        <div
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-success/10 text-success border border-success/30"
          title="Direct connection to Central Dispatch is active"
        >
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
          </span>
          <Wifi className="h-3 w-3" />
          <span>{t.netOnline}</span>
        </div>
      )}

      {mode === "edge" && (
        <div
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-tangerine/15 text-info border border-tangerine/40"
          title="Connected to Local Edge Gateway. Reports will be buffered locally."
        >
          <Radio className="h-3 w-3 text-tangerine" />
          <span>{t.netEdge}</span>
        </div>
      )}

      {mode === "offline" && (
        <div
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-danger/10 text-danger border border-danger/30"
          title="Network unavailable. Reports will be queued locally if edge is available."
        >
          <WifiOff className="h-3 w-3" />
          <span>{t.netOffline}</span>
        </div>
      )}

      {mode === "checking" && (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs text-muted bg-surface border border-card-border">
          <RefreshCw className="h-3 w-3 animate-spin" />
          <span>{t.netChecking}</span>
        </div>
      )}

      {showDetails && (
        <button
          onClick={checkStatus}
          disabled={checking}
          aria-label="Refresh network connection"
          className="text-xs text-muted hover:text-foreground transition-colors p-1 cursor-pointer"
          title={t.netRefresh}
        >
          <RefreshCw className={`h-3 w-3 ${checking ? "animate-spin" : ""}`} />
        </button>
      )}
    </div>
  );
}
