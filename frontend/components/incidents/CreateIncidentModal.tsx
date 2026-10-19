"use client";

import { useState } from "react";
import { X, Radio, Wifi, Loader2, MapPin, AlertTriangle } from "lucide-react";
import type { EdgeConnectivity } from "@/lib/types";
import { createIncident } from "@/lib/api";
import { submitToEdge } from "@/lib/edge-api";

interface CreateIncidentModalProps {
  onClose: () => void;
  onCreated: () => void;
  connectivity: EdgeConnectivity | null;
}

export function CreateIncidentModal({
  onClose,
  onCreated,
  connectivity,
}: CreateIncidentModalProps) {
  const [description, setDescription] = useState("");
  const [peopleAffected, setPeopleAffected] = useState(1);
  const [latitude, setLatitude] = useState("24.8607");
  const [longitude, setLongitude] = useState("67.0011");
  const [via, setVia] = useState<"edge" | "backend">(
    connectivity?.online === false ? "edge" : "backend"
  );
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    id?: string;
  } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);

    try {
      const data = {
        description,
        people_affected: peopleAffected,
        latitude: parseFloat(latitude),
        longitude: parseFloat(longitude),
      };

      if (via === "edge") {
        const res = await submitToEdge(data);
        setResult({
          success: true,
          message: res.message,
          id: res.packet_id,
        });
      } else {
        const res = await createIncident(data);
        setResult({
          success: true,
          message: "Incident created directly in backend",
          id: res.incident_id,
        });
      }
      onCreated();
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : "Failed to create incident",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const useCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(pos.coords.latitude.toFixed(4));
          setLongitude(pos.coords.longitude.toFixed(4));
        },
        () => {
          // Fallback to demo location
          setLatitude("24.8607");
          setLongitude("67.0011");
        }
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface border border-card-border rounded-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-card-border">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-danger" />
            <h2 className="text-sm font-bold tracking-wide">REPORT EMERGENCY</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-muted hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {result ? (
          <div className="px-5 py-6">
            <div
              className={`px-4 py-3 rounded border ${
                result.success
                  ? "bg-success-dim/20 border-success/30 text-success"
                  : "bg-danger-dim/20 border-danger/30 text-danger"
              }`}
            >
              <div className="text-sm font-medium mb-1">
                {result.success ? "INCIDENT REPORTED" : "FAILED"}
              </div>
              <p className="text-xs opacity-80">{result.message}</p>
              {result.id && (
                <p className="text-xs font-mono mt-1">{result.id}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="mt-4 w-full px-4 py-2 bg-card border border-card-border rounded text-xs font-medium hover:bg-card/80 transition-colors"
            >
              CLOSE
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
            {/* Route selection */}
            <div>
              <label className="text-[10px] tracking-wider text-muted font-medium mb-2 block">
                SUBMISSION ROUTE
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setVia("backend")}
                  className={`flex items-center gap-2 px-3 py-2 rounded border text-xs transition-colors ${
                    via === "backend"
                      ? "border-success/50 bg-success-dim/20 text-success"
                      : "border-card-border text-muted hover:border-card-border/80"
                  }`}
                >
                  <Wifi className="h-3 w-3" />
                  <div className="text-left">
                    <div className="font-medium">DIRECT BACKEND</div>
                    <div className="text-[9px] opacity-70">ONLINE</div>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => setVia("edge")}
                  className={`flex items-center gap-2 px-3 py-2 rounded border text-xs transition-colors ${
                    via === "edge"
                      ? "border-accent/50 bg-accent-dim/20 text-accent"
                      : "border-card-border text-muted hover:border-card-border/80"
                  }`}
                >
                  <Radio className="h-3 w-3" />
                  <div className="text-left">
                    <div className="font-medium">EDGE GATEWAY</div>
                    <div className="text-[9px] opacity-70">OFFLINE-SAFE</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="text-[10px] tracking-wider text-muted font-medium mb-1 block">
                EMERGENCY DESCRIPTION *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                rows={3}
                placeholder="Describe the emergency situation..."
                className="w-full bg-card border border-card-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted/50 focus:outline-none focus:border-accent/50 resize-none"
              />
            </div>

            {/* People affected */}
            <div>
              <label className="text-[10px] tracking-wider text-muted font-medium mb-1 block">
                PEOPLE AFFECTED *
              </label>
              <input
                type="number"
                value={peopleAffected}
                onChange={(e) => setPeopleAffected(parseInt(e.target.value) || 1)}
                min={1}
                required
                className="w-full bg-card border border-card-border rounded px-3 py-2 text-sm text-foreground focus:outline-none focus:border-accent/50"
              />
            </div>

            {/* Location */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[10px] tracking-wider text-muted font-medium">
                  LOCATION
                </label>
                <button
                  type="button"
                  onClick={useCurrentLocation}
                  className="flex items-center gap-1 text-[10px] text-accent hover:text-accent/80 transition-colors"
                >
                  <MapPin className="h-2.5 w-2.5" />
                  USE CURRENT LOCATION
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[9px] text-muted block mb-0.5">LATITUDE</label>
                  <input
                    type="number"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    step="0.0001"
                    required
                    className="w-full bg-card border border-card-border rounded px-3 py-2 text-sm text-foreground font-mono focus:outline-none focus:border-accent/50"
                  />
                </div>
                <div>
                  <label className="text-[9px] text-muted block mb-0.5">LONGITUDE</label>
                  <input
                    type="number"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    step="0.0001"
                    required
                    className="w-full bg-card border border-card-border rounded px-3 py-2 text-sm text-foreground font-mono focus:outline-none focus:border-accent/50"
                  />
                </div>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting || !description.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-danger text-white text-xs font-bold tracking-wider rounded hover:bg-danger/90 transition-colors disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5" />
              )}
              {submitting
                ? "SUBMITTING..."
                : via === "edge"
                ? "SUBMIT VIA EDGE GATEWAY"
                : "SUBMIT TO BACKEND"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
