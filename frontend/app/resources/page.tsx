"use client";

import { useEffect, useState } from "react";
import {
  Shield,
  Heart,
  Flame,
  Package,
  Home,
  Search,
  MapPin,
  Users,
  Wrench,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Truck,
  RotateCcw,
  X,
} from "lucide-react";
import type { Resource, ResourceType } from "@/lib/types";
import { getResources, resetResourcesForTesting } from "@/lib/api";

function typeIcon(type: ResourceType) {
  switch (type) {
    case "medical":
      return Heart;
    case "rescue":
      return Search;
    case "fire":
      return Flame;
    case "supplies":
      return Package;
    case "shelter":
      return Home;
    default:
      return Shield;
  }
}

function typeColor(type: ResourceType): string {
  switch (type) {
    case "medical":
      return "text-danger";
    case "rescue":
      return "text-warning-ink";
    case "fire":
      return "text-info";
    case "supplies":
      return "text-accent";
    case "shelter":
      return "text-success";
    default:
      return "text-neutral";
  }
}

function typeBg(type: ResourceType): string {
  switch (type) {
    case "medical":
      return "bg-danger/5";
    case "rescue":
      return "bg-warning/10";
    case "fire":
      return "bg-tangerine/10";
    case "supplies":
      return "bg-accent/5";
    case "shelter":
      return "bg-success/5";
    default:
      return "bg-muted/10";
  }
}

function StatusBadge({ status }: { status: string }) {
  if (status === "deployed") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold rounded border bg-tangerine/15 text-info border-tangerine/40">
        <Truck className="h-2.5 w-2.5" />
        DEPLOYED
      </span>
    );
  }
  if (status === "available") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold rounded border bg-success/10 text-success border-success/30">
        <CheckCircle2 className="h-2.5 w-2.5" />
        AVAILABLE
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold rounded border bg-muted/10 text-neutral border-muted/30">
      {status.toUpperCase()}
    </span>
  );
}

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showResetModal, setShowResetModal] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);

  useEffect(() => {
    getResources()
      .then(setResources)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load resources"))
      .finally(() => setLoading(false));
  }, []);

  const handleConfirmReset = async () => {
    if (isResetting) return; // Prevent duplicate submissions
    setIsResetting(true);
    setResetError(null);
    setResetSuccessMessage(null);

    try {
      const result = await resetResourcesForTesting();
      // Immediately refresh the resource list and availability counts
      const refreshedResources = await getResources();
      setResources(refreshedResources);

      // Broadcast event so other components (e.g. Command Center map and counts) refresh
      window.dispatchEvent(new CustomEvent("rescunet:refresh"));

      const availableTotal = refreshedResources.filter((r) => r.status === "available").length;
      let msg = `All ${availableTotal} resources have been reset to available for testing with capacities restored.`;
      if (result.limitations && result.limitations.length > 0) {
        msg += ` Note: ${result.limitations.join(" ")}`;
      }
      setResetSuccessMessage(msg);
      setShowResetModal(false);
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "Failed to reset resources for testing.");
      // Preserve current UI state as required
    } finally {
      setIsResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 text-muted animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertTriangle className="h-8 w-8 text-danger" />
        <div className="text-sm text-danger">{error}</div>
      </div>
    );
  }

  const availableCount = resources.filter((r) => r.status === "available").length;
  const deployedCount = resources.filter((r) => r.status === "deployed").length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 md:px-6 py-2.5 border-b border-card-border bg-surface">
        <div>
          <h1 className="text-base font-semibold tracking-wide">Resources</h1>
          <p className="text-[11px] text-muted">
            {resources.length} community responders · {availableCount} available · {deployedCount} deployed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setResetError(null);
              setShowResetModal(true);
            }}
            disabled={isResetting}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-card border border-card-border hover:border-accent/60 text-xs font-semibold rounded-md text-foreground hover:text-accent transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed shadow-xs"
            title="Reset all resources to available for testing"
          >
            <RotateCcw className={`h-3.5 w-3.5 ${isResetting ? "animate-spin text-accent" : "text-muted"}`} />
            <span>Reset Resources for Testing</span>
          </button>
        </div>
      </div>

      {/* Success banner */}
      {resetSuccessMessage && (
        <div className="mx-4 md:mx-6 mt-3 px-3 py-2 bg-success/10 border border-success/30 rounded-md flex items-center justify-between gap-2 text-xs text-success animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
            <span>{resetSuccessMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setResetSuccessMessage(null)}
            className="text-success/70 hover:text-success p-1 transition-colors cursor-pointer"
            aria-label="Dismiss success message"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Error banner */}
      {resetError && (
        <div className="mx-4 md:mx-6 mt-3 px-3 py-2 bg-danger/10 border border-danger/30 rounded-md flex items-center justify-between gap-2 text-xs text-danger animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-danger" />
            <span>{resetError}</span>
          </div>
          <button
            type="button"
            onClick={() => setResetError(null)}
            className="text-danger/70 hover:text-danger p-1 transition-colors cursor-pointer"
            aria-label="Dismiss error message"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Confirmation Dialog */}
      {showResetModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-modal-title"
        >
          <div className="bg-card border border-card-border rounded-lg max-w-md w-full shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center gap-2.5 px-5 py-4 border-b border-card-border bg-surface">
              <div className="p-1.5 rounded-md bg-warning/10 text-warning-ink border border-warning/30">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <h2 id="reset-modal-title" className="text-sm font-semibold text-foreground">
                  Reset all resources to available for testing?
                </h2>
                <p className="text-[11px] text-muted">Testing environment action</p>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-3 text-xs text-muted leading-relaxed">
              <p>
                This action changes <strong className="text-foreground">resource availability</strong> and <strong className="text-foreground">capacity</strong>.
              </p>
              <p>
                All existing resources will be marked as <span className="text-success font-medium">AVAILABLE</span>, their active incident assignments will be released, and their available capacity will be restored to appropriate original configured values.
              </p>
              <div className="p-2.5 bg-surface border border-card-border rounded text-[11px] space-y-1">
                <div className="flex items-center gap-1.5 text-foreground font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                  <span>Preserves Data Integrity:</span>
                </div>
                <p className="text-muted pl-5">
                  Does not delete resources, incidents, assignments, incident history, or audit records. Incident statuses remain unchanged.
                </p>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2.5 px-5 py-3.5 border-t border-card-border bg-surface">
              <button
                type="button"
                onClick={() => {
                  if (!isResetting) setShowResetModal(false);
                }}
                disabled={isResetting}
                className="px-3 py-1.5 text-xs font-medium text-muted hover:text-foreground bg-card hover:bg-card-border/30 border border-card-border rounded-md transition-colors disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReset}
                disabled={isResetting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-md transition-colors disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed shadow-xs"
              >
                {isResetting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Resetting...</span>
                  </>
                ) : (
                  <>
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span>Confirm Reset</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resource grid */}
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {resources.map((resource) => {
            const Icon = typeIcon(resource.type);
            return (
              <div
                key={resource.resource_id}
                className={`bg-card border rounded-md overflow-hidden transition-colors ${
                  resource.status === "deployed"
                    ? "border-tangerine/50"
                    : "border-card-border hover:border-accent/40"
                }`}
              >
                {/* Type badge */}
                <div className={`px-3.5 py-1.5 border-b border-card-border ${typeBg(resource.type)}`}>
                  <div className="flex items-center gap-2">
                    <Icon className={`h-3.5 w-3.5 ${typeColor(resource.type)}`} />
                    <span className={`text-[10px] font-semibold ${typeColor(resource.type)}`}>
                      {resource.type.toUpperCase()}
                    </span>
                    <span className="ml-auto">
                      <StatusBadge status={resource.status} />
                    </span>
                  </div>
                </div>

                <div className="p-3.5">
                  <h3 className="text-sm font-semibold mb-0.5">{resource.name}</h3>
                  <span className="text-xs font-mono text-muted">{resource.resource_id}</span>

                  {/* Deployed incident assignment */}
                  {resource.status === "deployed" && resource.assigned_incident_id && (
                    <div className="mt-2 px-2 py-1 bg-tangerine/10 border border-tangerine/40 rounded text-[10px] text-info">
                      Assigned to: <span className="font-mono font-bold">{resource.assigned_incident_id}</span>
                    </div>
                  )}

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-3 mt-2.5">
                    <div className="flex items-center gap-1.5 text-xs text-muted">
                      <Users className="h-3 w-3" />
                      <span>Max {resource.max_people} people</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted">
                      <MapPin className="h-3 w-3" />
                      <span className="font-mono">
                        {resource.latitude.toFixed(3)}, {resource.longitude.toFixed(3)}
                      </span>
                    </div>
                  </div>

                  {/* Equipment */}
                  <div className="mt-2.5 pt-2.5 border-t border-card-border">
                    <div className="flex items-center gap-1 mb-1.5">
                      <Wrench className="h-3 w-3 text-muted" />
                      <span className="text-[9px] text-muted font-medium">
                        EQUIPMENT
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(Array.isArray(resource.equipment) ? resource.equipment : []).map((eq) => (
                        <span
                          key={eq}
                          className="px-2 py-0.5 text-[10px] bg-surface border border-card-border rounded text-muted"
                        >
                          {eq}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
