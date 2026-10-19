// ─── Backend Incident Types ───────────────────────────────────────────

export type IncidentStatus =
  | "queued"
  | "processing"
  | "awaiting_approval"
  | "approved"
  | "dispatched"
  | "resolved"
  | "cancelled";

export interface Incident {
  incident_id: string;
  description: string;
  people_affected: number;
  latitude: number;
  longitude: number;
  status: IncidentStatus;
  packet_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentCreate {
  description: string;
  people_affected: number;
  latitude: number;
  longitude: number;
  packet_id?: string;
  auto_plan?: boolean;
}

export interface IncidentUpdate {
  status: IncidentStatus;
}

// ─── Edge Gateway Types ───────────────────────────────────────────────

export type EdgePacketStatus = "queued" | "syncing" | "synced" | "failed";

export interface EdgePacket {
  packet_id: string;
  description: string;
  people_affected: number;
  latitude: number;
  longitude: number;
  created_at: string;
  status: EdgePacketStatus;
  attempt_count: number;
  last_error: string | null;
  synced_at: string | null;
  incident_id: string | null;
}

export interface EdgeConnectivity {
  online: boolean;
  mode: "OFFLINE" | "ONLINE";
  queued_packets: number;
}

export interface EdgeSyncResult {
  packet_id: string;
  status: string;
  incident_id?: string;
  error?: string;
}

// ─── Agent / AI Types ────────────────────────────────────────────────

export type IncidentType =
  | "medical"
  | "rescue"
  | "fire"
  | "supplies"
  | "shelter"
  | "infrastructure"
  | "other";

export type Priority = "critical" | "high" | "medium" | "low";

export interface Classification {
  type: IncidentType;
  priority: Priority;
  people_affected: number;
  immediate_need: string;
}

export interface RecommendedAction {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  reason: string;
  distance_km: number;
}

export interface AgentRecommendation {
  incident_id: string;
  classification: Classification;
  recommended_action: RecommendedAction;
  human_approval_required: boolean;
}

export interface AgentAnalysisResponse {
  incident_id: string;
  status: string;
  recommendation: AgentRecommendation;
  human_approval_required: boolean;
}

// Agent text response (fallback when structured recommendation not extracted)
export interface AgentTextResponse {
  incident_id: string;
  analysis: string;
  status: string;
  human_approval_required: boolean;
}

// Agent analysis response (always returned by the backend)
// recommendation may be null if structured extraction failed
export interface AgentAnalysisResult {
  incident_id: string;
  analysis: string;
  status: string;
  human_approval_required: boolean;
  recommendation: StructuredRecommendation | null;
}

export interface StructuredRecommendation {
  incident_id: string;
  analysis: string;
  classification: {
    type: IncidentType;
    priority: Priority;
    people_affected: number;
    immediate_need: string;
  };
  recommended_action: {
    resource_id: string;
    resource_name: string;
    resource_type: string;
    reason: string;
    distance_km: number;
  };
  human_approval_required: boolean;
}

// ─── Response Plan Types ─────────────────────────────────────────────

export interface ApprovalRequest {
  resource_id: string;
  distance_km: number;
  reason: string;
}

export interface ResponsePlanResource {
  id: string;
  name: string;
  type: string;
  status?: string;
}

export interface ApprovalResponse {
  incident_id: string;
  status: string;
  resource: ResponsePlanResource;
  distance_km: number;
  message: string;
  real_world_dispatch: boolean;
}

// ─── Resource Types ───────────────────────────────────────────────────

export type ResourceType = "medical" | "rescue" | "fire" | "supplies" | "shelter";
export type ResourceStatusType = "available" | "deployed" | "dispatched" | "unavailable";

export interface Resource {
  resource_id: string;
  name: string;
  type: ResourceType;
  status: ResourceStatusType;
  assigned_incident_id: string | null;
  latitude: number;
  longitude: number;
  equipment: string[];
  max_people: number;
  created_at: string;
  updated_at: string;
}

// ─── UI-only Types ────────────────────────────────────────────────────

export type UIIncidentStatus =
  | "reported"
  | "queued"
  | "syncing"
  | "synced"
  | "analyzing"
  | "awaiting_approval"
  | "approved"
  | "dispatched"
  | "resolved"
  | "failed";

export function mapBackendStatus(status: IncidentStatus): UIIncidentStatus {
  const map: Record<IncidentStatus, UIIncidentStatus> = {
    queued: "queued",
    processing: "analyzing",
    awaiting_approval: "awaiting_approval",
    approved: "approved",
    dispatched: "dispatched",
    resolved: "resolved",
    cancelled: "failed",
  };
  return map[status] ?? "reported";
}

// ─── Unified Incident View ────────────────────────────────────────────
// Used by the map, feed, and dashboard to merge backend incidents
// with Edge-only queued incidents into one display list.

export type UnifiedIncidentSource = "central" | "edge";

export interface UnifiedIncident {
  /** Backend incident_id (e.g. RSN-000001) or Edge packet_id (e.g. EDGE-000001) */
  id: string;
  description: string;
  people_affected: number;
  latitude: number;
  longitude: number;
  /** Normalized status for display */
  status: UIIncidentStatus;
  source: UnifiedIncidentSource;
  created_at: string;
  updated_at: string;
  /** Original backend incident, if synced */
  backendIncident: Incident | null;
  /** Original edge packet, if still queued locally */
  edgePacket: EdgePacket | null;
}

/**
 * Merge backend incidents + edge packets, deduplicating by packet_id.
 * If a backend incident has a matching packet_id, the edge packet is
 * dropped (it has already been synchronized).
 */
export function mergeIncidents(
  backendIncidents: Incident[],
  edgePackets: EdgePacket[],
): UnifiedIncident[] {
  // Collect all packet_ids that have already synced to the backend
  const syncedPacketIds = new Set(
    backendIncidents
      .map((i) => i.packet_id)
      .filter((pid): pid is string => pid !== null),
  );

  const unified: UnifiedIncident[] = [];

  // Backend incidents become central-source unified incidents
  for (const inc of backendIncidents) {
    unified.push({
      id: inc.incident_id,
      description: inc.description,
      people_affected: inc.people_affected,
      latitude: inc.latitude,
      longitude: inc.longitude,
      status: mapBackendStatus(inc.status),
      source: "central",
      created_at: inc.created_at,
      updated_at: inc.updated_at,
      backendIncident: inc,
      edgePacket: null,
    });
  }

  // Edge packets that have NOT synced become edge-source unified incidents
  for (const pkt of edgePackets) {
    if (syncedPacketIds.has(pkt.packet_id)) continue;

    // Map edge status to UI status
    let uiStatus: UIIncidentStatus;
    switch (pkt.status) {
      case "queued":
        uiStatus = "queued";
        break;
      case "syncing":
        uiStatus = "syncing";
        break;
      case "synced":
        uiStatus = "synced";
        break;
      case "failed":
        uiStatus = "failed";
        break;
    }

    unified.push({
      id: pkt.packet_id,
      description: pkt.description,
      people_affected: pkt.people_affected,
      latitude: pkt.latitude,
      longitude: pkt.longitude,
      status: uiStatus,
      source: "edge",
      created_at: pkt.created_at,
      updated_at: pkt.synced_at ?? pkt.created_at,
      backendIncident: null,
      edgePacket: pkt,
    });
  }

  // Sort: most recent first
  unified.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return unified;
}

// ─── AI Priority Queue Types ───────────────────────────────────────────

export interface PriorityFactors {
  severity: number;
  people_affected: number;
  urgency: number;
  resource_need: number;
  reason: string;
}

export interface ResourceAvailabilityInfo {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  status: string;
  is_suitable: boolean;
}

export interface PriorityQueueItem {
  rank: number;
  incident_id: string;
  description: string;
  incident_type: string;
  priority_label: string;
  score: number;
  people_affected: number;
  waiting_time_seconds: number;
  waiting_time_display: string;
  recommended_resource: ResourceAvailabilityInfo;
  factors: PriorityFactors;
  reason: string;
}

export interface PriorityQueueResponse {
  queue: PriorityQueueItem[];
  total_active: number;
  generated_at: string;
  scoring_weights: Record<string, number>;
}

// ─── Recommendation Types ────────────────────────────────────────────

export interface RecommendedResourceDetail {
  resource_id: string;
  name: string;
  type: string;
  status: string;
  latitude: number;
  longitude: number;
  equipment: string[];
  max_people: number;
  distance_km: number;
  match_score: number;
  is_available: boolean;
  assigned_incident_id: string | null;
}

export interface AgentActivityStep {
  step: string;
  status: "completed" | "pending" | "warning" | "failed";
}

export interface RecommendationResponse {
  incident_id: string;
  incident_type: string;
  status: string;
  recommended_resource: RecommendedResourceDetail | null;
  activity: AgentActivityStep[];
  total_resources_checked: number;
  available_resources: number;
  resource_rankings: RecommendedResourceDetail[];
}

// ─── Dashboard Stats ──────────────────────────────────────────────────

export interface DashboardStats {
  activeIncidents: number;
  aiAnalyzed: number;
  queuedOffline: number;
  availableResources: number;
  centralIncidents: number;
  edgeQueued: number;
  totalActive: number;
}

// ─── Adaptive Rescue Planning Types ─────────────────────────────────────

export type UrgencyLevel = "critical" | "high" | "medium" | "low";

export interface TriageCriterion {
  rule_id: string;
  matched: boolean;
  description: string;
  evidence: string[];
}

export interface TriageLocation {
  latitude: number;
  longitude: number;
  source: string;
  note: string | null;
}

export interface TriageResult {
  incident_id: string;
  incident_type: IncidentType;
  urgency_level: UrgencyLevel;
  urgency_score: number;
  criteria: TriageCriterion[];
  hazards: string[];
  requested_assistance: string[];
  people_affected: number;
  people_affected_stated_in_text: number | null;
  location: TriageLocation;
  missing_info: string[];
  uncertain: string[];
  insufficient_evidence: boolean;
  source: string;
  ai_summary: string | null;
  generated_at: string;
  criteria_version: string;
}

export interface MatchCandidate {
  resource_id: string;
  name: string;
  type: string;
  status: string;
  distance_km: number;
  match_score: number;
  feasible: boolean;
  reasons: string[];
  blockers: string[];
  max_people: number;
  assigned_incident_id: string | null;
}

export interface MatchResult {
  incident_id: string;
  incident_type: string;
  required_capabilities: string[];
  candidates: MatchCandidate[];
  best: MatchCandidate | null;
  requires_human_review: boolean;
  review_reasons: string[];
  shortages: string[];
  generated_at: string;
}

export type PlanStatusType =
  | "proposed"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "superseded"
  | "stale";

export type PlanTriggerType =
  | "initial"
  | "manual"
  | "route_closed"
  | "resource_unavailable"
  | "resource_unsuitable"
  | "new_high_urgency"
  | "incident_changed";

export interface PlanAssignmentView {
  resource_id: string | null;
  resource_name: string | null;
  resource_type: string | null;
  distance_km: number | null;
  match_score: number | null;
  requires_human_review: boolean;
}

export interface RescuePlan {
  plan_id: string;
  incident_id: string;
  version: number;
  status: PlanStatusType;
  trigger: PlanTriggerType;
  trigger_detail: string | null;
  previous_plan_id: string | null;
  assignment: PlanAssignmentView;
  rationale: string;
  alternatives: MatchCandidate[];
  shortages: string[];
  review_reasons: string[];
  triage: TriageResult | null;
  match: MatchResult | null;
  created_by: string;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  decision_reason: string | null;
}

export interface PlanListResponse {
  plans: RescuePlan[];
  total: number;
}

export interface DetectedChange {
  incident_id: string;
  plan_id: string;
  trigger: PlanTriggerType;
  field: string;
  previous: string | null;
  current: string | null;
  detail: string;
}

export interface ReplanReport {
  changes: DetectedChange[];
  plans_proposed: string[];
  stale_plans: string[];
  unresolved_incidents: string[];
  evaluated_assignments: number;
  message: string;
  generated_at: string;
}

export type RouteStatusType = "open" | "closed";

export interface RouteInfo {
  route_id: string;
  name: string;
  status: RouteStatusType;
  restriction_reason: string | null;
  scope_resource_id: string | null;
  from_lat: number;
  from_lng: number;
  to_lat: number;
  to_lng: number;
  updated_at: string;
}

export interface RouteListResponse {
  routes: RouteInfo[];
  total: number;
}

export interface RouteStatusResponse {
  route: RouteInfo;
  message: string;
  affected_assignments: string[];
  plans_proposed: string[];
}

export interface PlanDecisionPayload {
  incident_id: string;
  status: string;
  resource: ResponsePlanResource;
  distance_km: number;
  message: string;
  real_world_dispatch: boolean;
  plan_id: string;
  version: number;
  released_resource_id: string | null;
}

export interface AuditEvent {
  event_id: number;
  incident_id: string | null;
  plan_id: string | null;
  event_type: string;
  detail: Record<string, unknown> | string;
  actor: string | null;
  created_at: string;
}

export interface AuditTrailResponse {
  incident_id: string;
  events: AuditEvent[];
  total: number;
}

// ─── Edge Gateway Status ─────────────────────────────────────────────────

export interface EdgeGatewayStatus {
  mode: "ONLINE" | "OFFLINE";
  online: boolean;
  packets: Record<string, number>;
  waiting_to_sync: number;
  backend_url: string;
  backend_reachable: boolean;
  last_synced_at: string | null;
  note: string;
}

// ─── Pakistan Geographic Bounds Validator ────────────────────────────
export function isInsidePakistan(lat: number, lng: number): boolean {
  // Pakistan geographic boundary box:
  // Latitude: ~23.0°N to ~37.5°N
  // Longitude: ~60.0°E to ~78.5°E
  return lat >= 23.0 && lat <= 37.5 && lng >= 60.0 && lng <= 78.5;
}

