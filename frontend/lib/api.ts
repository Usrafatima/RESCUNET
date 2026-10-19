// ─── Backend API Client ───────────────────────────────────────────────

import type { Incident, IncidentCreate, IncidentUpdate, AgentAnalysisResult, ApprovalRequest, ApprovalResponse, Resource, PriorityQueueResponse, RecommendationResponse, PlanListResponse, RescuePlan, PlanDecisionPayload, ReplanReport, RouteListResponse, RouteStatusResponse, RouteStatusType, TriageResult, AuditTrailResponse } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

async function backendFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Backend error ${res.status}`);
  }
  return res.json();
}

// ─── Incidents ────────────────────────────────────────────────────────

export async function getIncidents(): Promise<Incident[]> {
  return backendFetch<Incident[]>("/api/incidents");
}

export async function getIncident(id: string): Promise<Incident> {
  return backendFetch<Incident>(`/api/incidents/${id}`);
}

export async function createIncident(data: IncidentCreate): Promise<Incident> {
  return backendFetch<Incident>("/api/incidents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateIncidentStatus(id: string, data: IncidentUpdate): Promise<Incident> {
  return backendFetch<Incident>(`/api/incidents/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ─── Health ───────────────────────────────────────────────────────────

export async function getHealth(): Promise<{ status: string; service: string }> {
  return backendFetch<{ status: string; service: string }>("/health");
}

// ─── Agent Analysis ───────────────────────────────────────────────────

export async function analyzeIncident(id: string): Promise<AgentAnalysisResult> {
  return backendFetch<AgentAnalysisResult>(`/api/agent/analyze/${id}`, {
    method: "POST",
  });
}

// ─── Resources ─────────────────────────────────────────────────────

export async function getResources(): Promise<Resource[]> {
  return backendFetch<Resource[]>("/api/resources");
}

// ─── Approval ────────────────────────────────────────────────────────

export async function approveRecommendation(
  incidentId: string,
  data: ApprovalRequest
): Promise<ApprovalResponse> {
  return backendFetch<ApprovalResponse>(`/api/agent/approve/${incidentId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Priority Queue ────────────────────────────────────────────────────

export async function getPriorityQueue(): Promise<PriorityQueueResponse> {
  return backendFetch<PriorityQueueResponse>("/api/incidents/priority-queue");
}

// ─── Recommendation ────────────────────────────────────────────────────

export async function getRecommendation(incidentId: string): Promise<RecommendationResponse> {
  return backendFetch<RecommendationResponse>(`/api/agent/recommendation/${incidentId}`);
}

// ─── Adaptive Rescue Planning ─────────────────────────────────────

export async function getPlans(incidentId?: string, planStatus?: string): Promise<PlanListResponse> {
  const params = new URLSearchParams();
  if (incidentId) params.set("incident_id", incidentId);
  if (planStatus) params.set("status", planStatus);
  const qs = params.toString();
  return backendFetch<PlanListResponse>(`/api/plans${qs ? `?${qs}` : ""}`);
}

export async function getIncidentPlans(incidentId: string): Promise<PlanListResponse> {
  return backendFetch<PlanListResponse>(`/api/incidents/${incidentId}/plans`);
}

export async function getPlan(planId: string): Promise<RescuePlan> {
  return backendFetch<RescuePlan>(`/api/plans/${planId}`);
}

export async function createPlan(incidentId: string, trigger?: string): Promise<RescuePlan> {
  return backendFetch<RescuePlan>(`/api/incidents/${incidentId}/plan`, {
    method: "POST",
    body: JSON.stringify({ trigger: trigger ?? "manual", actor: "operator" }),
  });
}

export async function approvePlan(
  planId: string,
  data: { approver: string; decision_reason?: string },
): Promise<PlanDecisionPayload> {
  return backendFetch<PlanDecisionPayload>(`/api/plans/${planId}/approve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function rejectPlan(
  planId: string,
  data: { approver: string; decision_reason?: string },
): Promise<RescuePlan> {
  return backendFetch<RescuePlan>(`/api/plans/${planId}/reject`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getTriage(incidentId: string, ai = false): Promise<TriageResult> {
  return backendFetch<TriageResult>(`/api/incidents/${incidentId}/triage?ai=${ai}`);
}

export async function refreshTriage(incidentId: string, ai = false): Promise<TriageResult> {
  return backendFetch<TriageResult>(`/api/incidents/${incidentId}/triage?ai=${ai}`, {
    method: "POST",
  });
}

export async function replan(actor = "operator"): Promise<ReplanReport> {
  return backendFetch<ReplanReport>(`/api/replan?actor=${encodeURIComponent(actor)}`, {
    method: "POST",
  });
}

export async function getReplanChanges(): Promise<ReplanReport> {
  return backendFetch<ReplanReport>(`/api/replan/changes`);
}

export async function getAuditTrail(incidentId: string): Promise<AuditTrailResponse> {
  return backendFetch<AuditTrailResponse>(`/api/incidents/${incidentId}/audit`);
}

// ─── Routes / corridors ────────────────────────────────────────────────

export async function getRoutes(status?: "open" | "closed"): Promise<RouteListResponse> {
  const qs = status ? `?status=${status}` : "";
  return backendFetch<RouteListResponse>(`/api/routes${qs}`);
}

export async function setRouteStatus(
  routeId: string,
  data: { status: RouteStatusType; restriction_reason?: string; actor?: string },
): Promise<RouteStatusResponse> {
  return backendFetch<RouteStatusResponse>(`/api/routes/${routeId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function updateResourceStatus(
  resourceId: string,
  status: "available" | "deployed" | "unavailable",
  actor = "operator",
): Promise<{ resource_id: string; status: string; replan: ReplanReport }> {
  return backendFetch<{ resource_id: string; status: string; replan: ReplanReport }>(
    `/api/resources/${resourceId}/status?status=${status}&actor=${encodeURIComponent(actor)}`,
    { method: "PATCH" },
  );
}

export interface ResourceResetSummary {
  resource_id: string;
  name: string;
  type: string;
  previous_status: string;
  previous_assignment: string | null;
  restored_capacity?: number;
  classification?: string;
}

export interface ResourceResetResponse {
  status: string;
  dry_run: boolean;
  mode: string;
  released_count: number;
  released_resources: ResourceResetSummary[];
  restored_capacities: Record<string, number>;
  limitations: string[];
  updated_incidents: string[];
  updated_plans: string[];
  preserved_active_count: number;
  preserved_active_resources: string[];
  target_databases: Record<string, string>;
  message?: string;
}

export async function resetResourcesForTesting(): Promise<ResourceResetResponse> {
  return backendFetch<ResourceResetResponse>(
    "/api/resources/reset?mode=all&confirm=true",
    {
      method: "POST",
    }
  );
}

// ─── Error type helper ────────────────────────────────────────────────

export class APIError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "APIError";
    this.status = status;
  }
}
