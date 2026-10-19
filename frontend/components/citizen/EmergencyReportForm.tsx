"use client";

import { useState } from "react";
import {
  Heart,
  Flame,
  Droplets,
  Car,
  AlertCircle,
  Compass,
  CheckCircle2,
  Copy,
  Loader2,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Info,
  Radio,
  Wifi,
  FileCheck,
  Check,
} from "lucide-react";
import { createIncident } from "@/lib/api";
import { submitToEdge } from "@/lib/edge-api";
import type { IncidentCreate } from "@/lib/types";
import { NetworkStatusBadge, type NetworkMode } from "./NetworkStatusBadge";
import { VoiceEmergencyReporter } from "./VoiceEmergencyReporter";
import { useCitizenLanguage } from "./LanguageContext";

export type EmergencyType = "Medical" | "Fire" | "Flood" | "Accident" | "Other";

const PRESET_LOCATIONS = [
  { name: "Central District", lat: 24.8607, lng: 67.0011 },
  { name: "South Coast / Clifton", lat: 24.8138, lng: 67.0305 },
  { name: "East Sector / Gulshan", lat: 24.9207, lng: 67.0982 },
  { name: "North Nazimabad", lat: 24.9372, lng: 67.0428 },
  { name: "Industrial Zone", lat: 24.8258, lng: 67.1264 },
];

interface EmergencyReportFormProps {
  onReportSubmitted: (incidentId: string) => void;
  onTrackRequested: (incidentId: string) => void;
}

export function EmergencyReportForm({
  onReportSubmitted,
  onTrackRequested,
}: EmergencyReportFormProps) {
  const { t } = useCitizenLanguage();

  // Form State
  const [selectedType, setSelectedType] = useState<EmergencyType>("Medical");
  const [description, setDescription] = useState("");
  const [peopleAffected, setPeopleAffected] = useState(1);
  const [isLifeThreat, setIsLifeThreat] = useState(false);
  const [landmark, setLandmark] = useState("");

  // Location State
  const [latitude, setLatitude] = useState("24.8607");
  const [longitude, setLongitude] = useState("67.0011");
  const [locationStatus, setLocationStatus] = useState<
    "idle" | "requesting" | "granted" | "denied"
  >("idle");
  const [locationMessage, setLocationMessage] = useState("");

  // Review step modal state (explicit confirmation required before sending)
  const [showReviewStep, setShowReviewStep] = useState(false);

  // Submission State
  const [networkMode, setNetworkMode] = useState<NetworkMode>("online");
  const [submitting, setSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Result / Confirmation State
  const [submittedReference, setSubmittedReference] = useState<string | null>(
    null
  );
  const [submittedVia, setSubmittedVia] = useState<"backend" | "edge">(
    "backend"
  );
  const [copied, setCopied] = useState(false);

  // Geolocation Handler
  const handleRequestLocation = () => {
    if (!navigator.geolocation) {
      setLocationStatus("denied");
      setLocationMessage(t.gpsDenied);
      return;
    }

    setLocationStatus("requesting");
    setLocationMessage(t.detectingGps);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude.toFixed(4);
        const lng = pos.coords.longitude.toFixed(4);
        setLatitude(lat);
        setLongitude(lng);
        setLocationStatus("granted");
        const accuracy = Math.round(pos.coords.accuracy);
        setLocationMessage(`${t.gpsAcquired} (±${accuracy}m)`);
      },
      () => {
        setLocationStatus("denied");
        setLocationMessage(t.gpsDenied);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleApplyPreset = (lat: number, lng: number, name: string) => {
    setLatitude(lat.toFixed(4));
    setLongitude(lng.toFixed(4));
    setLandmark(name);
    setLocationStatus("idle");
    setLocationMessage(`Set to ${name}`);
  };

  const handleCopyReference = () => {
    if (submittedReference) {
      navigator.clipboard.writeText(submittedReference);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Callback from VoiceEmergencyReporter
  const handleTranscriptApplied = (
    text: string,
    suggestedCategory: EmergencyType | null
  ) => {
    setDescription(text);
    if (suggestedCategory) {
      setSelectedType(suggestedCategory);
    }
  };

  // Initial validation before opening explicit Review Step
  const handleOpenReview = (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) {
      setSubmissionError(t.validationDescRequired);
      return;
    }

    const latNum = parseFloat(latitude);
    const lngNum = parseFloat(longitude);

    if (isNaN(latNum) || latNum < -90 || latNum > 90) {
      setSubmissionError(t.validationLatRange);
      return;
    }
    if (isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
      setSubmissionError(t.validationLngRange);
      return;
    }

    setSubmissionError(null);
    setShowReviewStep(true);
  };

  // Explicit Final Confirmation Submission Handler
  const handleConfirmAndSend = async () => {
    const latNum = parseFloat(latitude);
    const lngNum = parseFloat(longitude);

    setSubmitting(true);
    setSubmissionError(null);

    // Build structured report description with emergency type and landmark context
    const parts: string[] = [];
    parts.push(`[${selectedType.toUpperCase()}]`);
    if (isLifeThreat) {
      parts.push("[URGENT: LIFE THREAT / CRITICAL]");
    }
    if (landmark.trim()) {
      parts.push(`Location Landmark: ${landmark.trim()}.`);
    }
    parts.push(description.trim());
    const fullDescription = parts.join(" ");

    const payload: IncidentCreate = {
      description: fullDescription,
      people_affected: peopleAffected,
      latitude: latNum,
      longitude: lngNum,
      auto_plan: true,
    };

    try {
      if (networkMode === "edge") {
        const edgeRes = await submitToEdge({
          description: fullDescription,
          people_affected: peopleAffected,
          latitude: latNum,
          longitude: lngNum,
        });
        setSubmittedReference(edgeRes.packet_id);
        setSubmittedVia("edge");
        setShowReviewStep(false);
        onReportSubmitted(edgeRes.packet_id);
      } else {
        try {
          const res = await createIncident(payload);
          setSubmittedReference(res.incident_id);
          setSubmittedVia("backend");
          setShowReviewStep(false);
          onReportSubmitted(res.incident_id);
        } catch (backendErr) {
          try {
            const edgeRes = await submitToEdge({
              description: fullDescription,
              people_affected: peopleAffected,
              latitude: latNum,
              longitude: lngNum,
            });
            setSubmittedReference(edgeRes.packet_id);
            setSubmittedVia("edge");
            setShowReviewStep(false);
            onReportSubmitted(edgeRes.packet_id);
          } catch {
            throw backendErr;
          }
        }
      }
    } catch (err) {
      setSubmissionError(
        err instanceof Error
          ? err.message
          : "Failed to submit emergency report. Please call 112 / 911 directly."
      );
      setShowReviewStep(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetForm = () => {
    setSubmittedReference(null);
    setDescription("");
    setLandmark("");
    setIsLifeThreat(false);
    setShowReviewStep(false);
    setSubmissionError(null);
  };

  const getPlaceholder = () => {
    switch (selectedType) {
      case "Medical":
        return t.descPlaceholderMedical;
      case "Fire":
        return t.descPlaceholderFire;
      case "Flood":
        return t.descPlaceholderFlood;
      case "Accident":
        return t.descPlaceholderAccident;
      case "Other":
        return t.descPlaceholderOther;
      default:
        return t.descPlaceholderMedical;
    }
  };

  // ─── Confirmation Screen ──────────────────────────────────────────
  if (submittedReference) {
    return (
      <div className="bg-card border border-success/30 rounded-2xl shadow-sm p-6 sm:p-8 space-y-6 animate-in fade-in">
        <div className="text-center space-y-3">
          <div className="inline-flex p-3 rounded-full bg-success/10 text-success border border-success/20">
            <CheckCircle2 className="h-10 w-10" />
          </div>
          <h2 className="text-2xl font-bold text-foreground">
            {t.confirmTitle}
          </h2>
          <p className="text-sm text-muted max-w-md mx-auto">
            {t.confirmSubtitle}
          </p>
        </div>

        {/* Reference Box */}
        <div className="bg-surface border border-card-border rounded-xl p-5 text-center space-y-2">
          <div className="text-xs uppercase tracking-wider text-muted font-semibold">
            {t.confirmRefLabel}
          </div>
          <div className="flex items-center justify-center gap-3">
            <span className="font-mono text-2xl sm:text-3xl font-extrabold text-accent tracking-wide">
              {submittedReference}
            </span>
            <button
              onClick={handleCopyReference}
              className="p-2 text-muted hover:text-foreground rounded-lg hover:bg-card transition-colors cursor-pointer"
              title="Copy Reference Number"
            >
              {copied ? (
                <CheckCircle2 className="h-5 w-5 text-success" />
              ) : (
                <Copy className="h-5 w-5" />
              )}
            </button>
          </div>
          <div className="text-xs text-muted">
            {submittedVia === "edge" ? (
              <span className="inline-flex items-center gap-1 text-info">
                <Radio className="h-3 w-3" /> {t.confirmViaEdge}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-success">
                <Wifi className="h-3 w-3" /> {t.confirmViaCentral}
              </span>
            )}
          </div>
        </div>

        {/* Report Summary */}
        <div className="bg-card border border-card-border rounded-xl p-4 space-y-2 text-xs">
          <div className="font-semibold text-foreground text-sm border-b border-card-border pb-1.5">
            {t.confirmSummaryTitle}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted">
            <div>
              <span className="font-medium text-foreground">
                {t.confirmSummaryCategory}
              </span>{" "}
              {selectedType}
            </div>
            <div>
              <span className="font-medium text-foreground">
                {t.confirmSummaryAffected}
              </span>{" "}
              {peopleAffected} {peopleAffected === 1 ? t.peoplePerson : t.peoplePlural}
            </div>
            <div>
              <span className="font-medium text-foreground">
                {t.confirmSummaryCoords}
              </span>{" "}
              {latitude}, {longitude}
            </div>
            <div>
              <span className="font-medium text-foreground">
                {t.confirmSummaryPriority}
              </span>{" "}
              {isLifeThreat ? t.confirmLifeThreat : t.confirmStandard}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="button"
            onClick={() => onTrackRequested(submittedReference)}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-accent hover:bg-accent-hover text-white font-semibold text-sm transition-all shadow-xs cursor-pointer"
          >
            <span>{t.confirmTrackBtn}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={handleResetForm}
            className="px-5 py-3 rounded-xl border border-card-border hover:bg-surface text-foreground font-medium text-sm transition-colors cursor-pointer"
          >
            {t.confirmSubmitAnother}
          </button>
        </div>

        {/* Safety Disclaimer */}
        <div className="p-3.5 bg-danger/5 border border-danger/20 rounded-xl text-xs text-danger-dim flex items-start gap-2.5">
          <ShieldAlert className="h-4 w-4 text-danger shrink-0 mt-0.5" />
          <div>{t.confirmSafetyReminder}</div>
        </div>
      </div>
    );
  }

  // ─── Main Form ────────────────────────────────────────────────────
  return (
    <>
      <form
        onSubmit={handleOpenReview}
        className="bg-card border border-card-border rounded-2xl shadow-xs overflow-hidden"
      >
        {/* Header bar */}
        <div className="p-5 sm:p-6 border-b border-card-border bg-surface/40 flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-danger/10 text-danger border border-danger/20">
                <AlertTriangle className="h-4 w-4" />
              </span>
              <h2 className="text-base sm:text-lg font-bold text-foreground">
                {t.reportTitle}
              </h2>
            </div>
            <p className="text-xs text-muted mt-0.5">{t.reportSubtitle}</p>
          </div>
          <NetworkStatusBadge onStatusChange={setNetworkMode} showDetails />
        </div>

        <div className="p-5 sm:p-6 space-y-6">
          {/* Voice-Assisted Reporting Module */}
          <VoiceEmergencyReporter
            onTranscriptApplied={handleTranscriptApplied}
            currentDescription={description}
          />

          {/* Step 1: Emergency Type */}
          <div className="space-y-2.5 pt-2 border-t border-card-border/60">
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground">
              {t.stepType} <span className="text-danger">{t.required}</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              {[
                {
                  id: "Medical" as EmergencyType,
                  label: t.catMedical,
                  desc: t.catMedicalDesc,
                  icon: Heart,
                  colorClass: "text-danger",
                  bgClass: "bg-danger/10",
                  borderClass: "border-danger/30 hover:border-danger/60",
                },
                {
                  id: "Fire" as EmergencyType,
                  label: t.catFire,
                  desc: t.catFireDesc,
                  icon: Flame,
                  colorClass: "text-warning-ink",
                  bgClass: "bg-warning/10",
                  borderClass: "border-warning/30 hover:border-warning/60",
                },
                {
                  id: "Flood" as EmergencyType,
                  label: t.catFlood,
                  desc: t.catFloodDesc,
                  icon: Droplets,
                  colorClass: "text-accent",
                  bgClass: "bg-accent/10",
                  borderClass: "border-accent/30 hover:border-accent/60",
                },
                {
                  id: "Accident" as EmergencyType,
                  label: t.catAccident,
                  desc: t.catAccidentDesc,
                  icon: Car,
                  colorClass: "text-info",
                  bgClass: "bg-info/10",
                  borderClass: "border-info/30 hover:border-info/60",
                },
                {
                  id: "Other" as EmergencyType,
                  label: t.catOther,
                  desc: t.catOtherDesc,
                  icon: AlertCircle,
                  colorClass: "text-neutral",
                  bgClass: "bg-surface",
                  borderClass: "border-card-border hover:border-foreground/30",
                },
              ].map((type) => {
                const Icon = type.icon;
                const isSelected = selectedType === type.id;
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() => setSelectedType(type.id)}
                    className={`flex flex-col items-center text-center p-3 sm:p-3.5 rounded-xl border transition-all text-left cursor-pointer ${
                      isSelected
                        ? `border-accent ring-2 ring-accent/20 ${type.bgClass}`
                        : `${type.borderClass} bg-surface/30`
                    }`}
                  >
                    <span
                      className={`p-2 rounded-lg mb-1.5 ${
                        isSelected
                          ? "bg-white text-accent shadow-xs"
                          : `${type.colorClass} bg-card`
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </span>
                    <span
                      className={`text-xs font-bold leading-tight ${
                        isSelected ? "text-foreground" : "text-muted"
                      }`}
                    >
                      {type.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 2: Location Sharing & Manual Fallback */}
          <div className="space-y-3 pt-2 border-t border-card-border/60">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-foreground">
                {t.stepLocation} <span className="text-danger">{t.required}</span>
              </label>
              <button
                type="button"
                onClick={handleRequestLocation}
                disabled={locationStatus === "requesting"}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-accent/10 hover:bg-accent/20 text-accent transition-colors border border-accent/20 cursor-pointer"
              >
                {locationStatus === "requesting" ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>{t.detectingGps}</span>
                  </>
                ) : (
                  <>
                    <Compass className="h-3.5 w-3.5" />
                    <span>{t.shareGps}</span>
                  </>
                )}
              </button>
            </div>

            {locationMessage && (
              <div
                className={`text-xs p-2.5 rounded-lg flex items-center gap-2 ${
                  locationStatus === "granted"
                    ? "bg-success/10 text-success border border-success/20"
                    : locationStatus === "denied"
                    ? "bg-warning/10 text-warning-ink border border-warning/20"
                    : "bg-surface text-muted border border-card-border"
                }`}
              >
                <Info className="h-3.5 w-3.5 shrink-0" />
                <span>{locationMessage}</span>
              </div>
            )}

            {/* Coordinates inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-muted mb-1">
                  {t.latitudeLabel}
                </label>
                <input
                  type="text"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  placeholder="24.8607"
                  required
                  className="w-full px-3 py-2 text-sm bg-surface rounded-lg border border-card-border focus:border-accent focus:outline-hidden font-mono"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-muted mb-1">
                  {t.longitudeLabel}
                </label>
                <input
                  type="text"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  placeholder="67.0011"
                  required
                  className="w-full px-3 py-2 text-sm bg-surface rounded-lg border border-card-border focus:border-accent focus:outline-hidden font-mono"
                />
              </div>
            </div>

            {/* Landmark / Street address input */}
            <div>
              <label className="block text-[11px] font-medium text-muted mb-1">
                {t.landmarkLabel}
              </label>
              <input
                type="text"
                value={landmark}
                onChange={(e) => setLandmark(e.target.value)}
                placeholder={t.landmarkPlaceholder}
                className="w-full px-3 py-2 text-sm bg-surface rounded-lg border border-card-border focus:border-accent focus:outline-hidden"
              />
            </div>

            {/* Quick preset locations */}
            <div>
              <span className="text-[11px] text-muted mr-2">
                {t.demoAreasLabel}
              </span>
              <div className="inline-flex flex-wrap gap-1.5 mt-1">
                {PRESET_LOCATIONS.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    onClick={() =>
                      handleApplyPreset(preset.lat, preset.lng, preset.name)
                    }
                    className="px-2 py-0.5 rounded text-[11px] bg-surface hover:bg-card-border text-muted hover:text-foreground border border-card-border transition-colors cursor-pointer"
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Step 3: People Affected */}
          <div className="space-y-2 pt-2 border-t border-card-border/60">
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground">
              {t.stepPeople} <span className="text-danger">{t.required}</span>
            </label>
            <div className="flex items-center gap-3">
              <div className="flex items-center border border-card-border rounded-lg bg-surface overflow-hidden">
                <button
                  type="button"
                  onClick={() => setPeopleAffected((n) => Math.max(1, n - 1))}
                  className="px-3.5 py-2 text-foreground font-bold hover:bg-card-border/50 transition-colors cursor-pointer"
                >
                  -
                </button>
                <span className="w-12 text-center text-sm font-bold text-foreground font-mono">
                  {peopleAffected}
                </span>
                <button
                  type="button"
                  onClick={() => setPeopleAffected((n) => n + 1)}
                  className="px-3.5 py-2 text-foreground font-bold hover:bg-card-border/50 transition-colors cursor-pointer"
                >
                  +
                </button>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                {[1, 2, 5, 10, 20].map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => setPeopleAffected(num)}
                    className={`px-2.5 py-1 text-xs rounded-lg border transition-colors cursor-pointer ${
                      peopleAffected === num
                        ? "bg-accent text-white border-accent"
                        : "bg-surface text-muted border-card-border hover:bg-card"
                    }`}
                  >
                    {num} {num === 1 ? t.peoplePerson : t.peoplePlural}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Step 4: Emergency Description */}
          <div className="space-y-2 pt-2 border-t border-card-border/60">
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground">
              {t.stepDesc} <span className="text-danger">{t.required}</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              required
              placeholder={getPlaceholder()}
              className="w-full px-3.5 py-2.5 text-sm bg-surface rounded-xl border border-card-border focus:border-accent focus:outline-hidden"
            />

            {/* Life-threat flag */}
            <label className="flex items-start gap-2.5 p-3 rounded-xl bg-danger/5 border border-danger/20 cursor-pointer">
              <input
                type="checkbox"
                checked={isLifeThreat}
                onChange={(e) => setIsLifeThreat(e.target.checked)}
                className="mt-0.5 rounded border-card-border text-danger focus:ring-danger"
              />
              <div className="text-xs">
                <span className="font-semibold text-danger">
                  {t.lifeThreatLabel}
                </span>
                <p className="text-muted text-[11px] mt-0.5">
                  {t.lifeThreatDesc}
                </p>
              </div>
            </label>
          </div>

          {/* Error message */}
          {submissionError && (
            <div className="p-3 bg-danger/10 border border-danger/30 rounded-xl text-xs text-danger flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{submissionError}</span>
            </div>
          )}

          {/* Review & Submit Trigger Button */}
          <div className="pt-2">
            <button
              type="submit"
              className="w-full py-4 rounded-xl bg-danger hover:bg-danger/90 text-white font-extrabold text-sm sm:text-base tracking-wide uppercase shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2.5 cursor-pointer"
            >
              <FileCheck className="h-5 w-5" />
              <span>
                {t.voiceReviewTitle.toUpperCase()} &rarr;
              </span>
            </button>
          </div>

          {/* Disclaimer */}
          <p className="text-center text-[11px] text-muted">
            {t.disclaimerIntake}
          </p>
        </div>
      </form>

      {/* ── Explicit Review & Confirmation Modal ──────────────────────── */}
      {showReviewStep && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-card border border-card-border rounded-2xl w-full max-w-lg shadow-xl overflow-hidden space-y-4 p-5 sm:p-6">
            <div className="flex items-center gap-2.5 pb-2 border-b border-card-border">
              <div className="p-2 rounded-xl bg-accent/10 text-accent">
                <FileCheck className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-foreground">
                  {t.voiceReviewTitle}
                </h3>
                <p className="text-xs text-muted">
                  {t.voiceReviewSubtitle}
                </p>
              </div>
            </div>

            {/* Summary Cards */}
            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-surface border border-card-border space-y-1">
                <div className="font-semibold text-muted uppercase text-[10px] tracking-wider">
                  {t.stepType}
                </div>
                <div className="font-bold text-sm text-foreground flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-accent"></span>
                  <span>{selectedType}</span>
                  {isLifeThreat && (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-danger/10 text-danger font-bold border border-danger/20">
                      {t.confirmLifeThreat}
                    </span>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-surface border border-card-border space-y-1">
                <div className="font-semibold text-muted uppercase text-[10px] tracking-wider">
                  {t.stepDesc}
                </div>
                <p className="text-foreground text-xs leading-relaxed italic bg-card p-2 rounded-lg border border-card-border/60">
                  &ldquo;{description}&rdquo;
                </p>
              </div>

              <div className="p-3 rounded-xl bg-surface border border-card-border space-y-1">
                <div className="font-semibold text-muted uppercase text-[10px] tracking-wider">
                  {t.voiceLocationConfirmPrompt}
                </div>
                <div className="font-mono text-xs text-foreground font-semibold">
                  {latitude}, {longitude}
                </div>
                {landmark && (
                  <div className="text-xs text-muted">
                    Landmark: <span className="text-foreground">{landmark}</span>
                  </div>
                )}
              </div>

              <div className="p-3 rounded-xl bg-surface border border-card-border flex items-center justify-between">
                <span className="font-semibold text-muted uppercase text-[10px] tracking-wider">
                  {t.voicePeopleConfirmPrompt}
                </span>
                <span className="font-bold text-sm text-foreground">
                  {peopleAffected} {peopleAffected === 1 ? t.peoplePerson : t.peoplePlural}
                </span>
              </div>
            </div>

            {/* Explicit Confirmation Buttons */}
            <div className="pt-2 flex flex-col sm:flex-row gap-2.5">
              <button
                type="button"
                onClick={handleConfirmAndSend}
                disabled={submitting}
                className="flex-1 py-3 px-4 rounded-xl bg-danger hover:bg-danger/90 text-white font-extrabold text-xs sm:text-sm tracking-wide uppercase shadow-md transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>{t.submittingButton}</span>
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    <span>{t.voiceConfirmSend}</span>
                  </>
                )}
              </button>

              <button
                type="button"
                disabled={submitting}
                onClick={() => setShowReviewStep(false)}
                className="py-3 px-4 rounded-xl border border-card-border hover:bg-surface text-foreground font-semibold text-xs sm:text-sm transition-colors cursor-pointer"
              >
                {t.voiceEditAgain}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
