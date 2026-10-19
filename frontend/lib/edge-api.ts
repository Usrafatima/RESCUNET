// ─── Edge Gateway API Client ──────────────────────────────────────────

import type { EdgePacket, EdgeConnectivity, EdgeSyncResult, EdgeGatewayStatus } from "./types";

const EDGE_URL = process.env.NEXT_PUBLIC_EDGE_URL || "http://127.0.0.1:8001";

async function edgeFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${EDGE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.message || `Edge error ${res.status}`);
  }
  return res.json();
}

// ─── Connectivity ─────────────────────────────────────────────────────

export async function getEdgeConnectivity(): Promise<EdgeConnectivity> {
  return edgeFetch<EdgeConnectivity>("/edge/connectivity");
}

export async function setEdgeConnectivity(online: boolean): Promise<{ online: boolean; mode: string; message: string }> {
  return edgeFetch("/edge/connectivity", {
    method: "POST",
    body: JSON.stringify({ online }),
  });
}

// ─── Queue ────────────────────────────────────────────────────────────

export async function getEdgeQueue(status?: string): Promise<EdgePacket[]> {
  const qs = status ? `?status=${status}` : "";
  return edgeFetch<EdgePacket[]>(`/edge/queue${qs}`);
}

// ─── Sync ─────────────────────────────────────────────────────────────

export async function syncEdgeQueue(): Promise<{ results: EdgeSyncResult[]; synced: number; failed: number }> {
  return edgeFetch("/edge/sync", { method: "POST" });
}

// ─── Submit to Edge ───────────────────────────────────────────────────

export async function submitToEdge(data: {
  description: string;
  people_affected: number;
  latitude: number;
  longitude: number;
}): Promise<{ packet_id: string; status: string; message: string }> {
  return edgeFetch("/edge/incidents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Edge Health Check ────────────────────────────────────────────────

export async function checkEdgeHealth(): Promise<boolean> {
  try {
    await edgeFetch("/health");
    return true;
  } catch {
    return false;
  }
}

// ─── Detailed gateway status ────────────────────────────────────

export async function getEdgeStatus(): Promise<EdgeGatewayStatus> {
  return edgeFetch<EdgeGatewayStatus>("/edge/status");
}
