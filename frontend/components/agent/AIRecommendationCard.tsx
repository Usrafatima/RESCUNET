"use client";

import {
  Shield,
  CheckCircle2,
  XCircle,
  MapPin,
  Truck,
  Zap,
  AlertTriangle,
} from "lucide-react";
import type {
  RecommendedResourceDetail,
  RecommendationResponse,
} from "@/lib/types";

// ─── Capability badge ────────────────────────────────────────────────
function CapabilityBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] tracking-wider font-medium rounded bg-success-dim/15 text-success border border-success/15">
      <CheckCircle2 className="h-2 w-2" />
      {name.replace(/_/g, " ").toUpperCase()}
    </span>
  );
}

// ─── Match score bar ─────────────────────────────────────────────────
function MatchScoreBar({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-success"
      : score >= 60
        ? "bg-accent"
        : score >= 40
          ? "bg-info"
          : "bg-muted";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] tracking-wider text-muted font-medium">
          MATCH SCORE
        </span>
        <span className="text-sm font-bold font-mono text-foreground">
          {score.toFixed(0)}%
        </span>
      </div>
      <div className="h-2 bg-muted/20 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────
interface AIRecommendationCardProps {
  recommendation: RecommendationResponse;
  onApprove?: () => void;
}

export function AIRecommendationCard({
  recommendation,
}: AIRecommendationCardProps) {
  const resource = recommendation.recommended_resource;

  // ── No resource available state ──
  if (recommendation.status === "no_resource_available" || !resource) {
    return (
      <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-3 bg-danger-dim/10 border-b border-card-border">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-danger" />
            <span className="text-xs font-bold tracking-wider text-danger">
              NO SUITABLE RESPONDER AVAILABLE
            </span>
          </div>
        </div>
        <div className="p-4 text-center">
          <XCircle className="h-8 w-8 text-danger/30 mx-auto mb-3" />
          <p className="text-sm text-muted mb-1">
            {recommendation.total_resources_checked} resources checked
          </p>
          <p className="text-xs text-muted/60">
            {recommendation.available_resources} available resources match the
            required capabilities.
          </p>
        </div>
      </div>
    );
  }

  // ── Dispatched state ──
  if (recommendation.status === "dispatched") {
    return (
      <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
        <div className="px-4 py-3 bg-success-dim/10 border-b border-card-border">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            <span className="text-xs font-bold tracking-wider text-success">
              ✓ DISPATCHED
            </span>
          </div>
        </div>
        <div className="p-4 space-y-3">
          <ResourceHeader resource={resource} />
          <div className="flex items-center gap-2 text-xs text-success">
            <Truck className="h-3.5 w-3.5" />
            <span className="font-bold">STATUS: DEPLOYED</span>
          </div>
          <div className="text-[10px] text-muted">
            Destination: Incident {recommendation.incident_id}
          </div>
        </div>
      </div>
    );
  }

  // ── Recommendation ready state ──
  return (
    <div className="bg-card border border-card-border rounded-lg overflow-hidden mb-4">
      {/* Header */}
      <div className="px-4 py-3 bg-success-dim/10 border-b border-card-border">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-success" />
          <span className="text-xs font-bold tracking-wider text-success">
            AI RECOMMENDED RESPONDER
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Resource header */}
        <ResourceHeader resource={resource} />

        {/* Status + Distance row */}
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[9px] tracking-wider text-muted font-medium mb-1">
              STATUS
            </div>
            <span
              className={`text-xs font-bold tracking-wider ${
                resource.is_available ? "text-success" : "text-danger"
              }`}
            >
              {resource.is_available ? "AVAILABLE" : resource.status.toUpperCase()}
            </span>
          </div>
          <div>
            <div className="text-[9px] tracking-wider text-muted font-medium mb-1">
              DISTANCE
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="h-3 w-3 text-info" />
              <span className="text-sm font-bold font-mono text-info">
                {resource.distance_km.toFixed(1)} km
              </span>
            </div>
          </div>
        </div>

        {/* Capabilities */}
        <div>
          <div className="text-[9px] tracking-wider text-muted font-medium mb-2">
            CAPABILITIES
          </div>
          <div className="flex flex-wrap gap-1.5">
            {resource.equipment.map((cap) => (
              <CapabilityBadge key={cap} name={cap} />
            ))}
          </div>
        </div>

        {/* Match score */}
        <MatchScoreBar score={resource.match_score} />

        {/* Why this resource */}
        <div>
          <div className="text-[9px] tracking-wider text-muted font-medium mb-1">
            WHY THIS RESOURCE?
          </div>
          <p className="text-xs text-foreground/80 italic leading-relaxed">
            Best available match for a {recommendation.incident_type} emergency
            based on required capabilities, availability, and proximity.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Resource header sub-component ───────────────────────────────────
function ResourceHeader({ resource }: { resource: RecommendedResourceDetail }) {
  return (
    <div>
      <div className="text-[9px] tracking-wider text-muted font-medium mb-1">
        RESOURCE
      </div>
      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4 text-success" />
        <span className="text-sm font-bold text-success">{resource.name}</span>
      </div>
      <div className="text-[10px] font-mono text-muted mt-0.5">
        {resource.resource_id} · {resource.type.toUpperCase()}
      </div>
    </div>
  );
}
