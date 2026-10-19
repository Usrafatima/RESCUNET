"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Search,
  BookOpen,
  Radio,
  Sparkles,
  Lock,
  HeartHandshake,
} from "lucide-react";
import { CitizenHeader } from "./CitizenHeader";
import { EmergencyReportForm } from "./EmergencyReportForm";
import { IncidentStatusTracker } from "./IncidentStatusTracker";
import { SafetyGuidance } from "./SafetyGuidance";
import { LanguageProvider, useCitizenLanguage } from "./LanguageContext";

export type CitizenTab = "report" | "track" | "guide";

function CitizenDashboardContent() {
  const { t } = useCitizenLanguage();
  const [activeTab, setActiveTab] = useState<CitizenTab>("report");
  const [activeIncidentId, setActiveIncidentId] = useState<string>("");

  const handleReportSubmitted = (id: string) => {
    setActiveIncidentId(id);
  };

  const handleTrackRequested = (id: string) => {
    setActiveIncidentId(id);
    setActiveTab("track");
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Public Header */}
      <CitizenHeader />

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-card-border">
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-surface border border-card-border overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveTab("report")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                activeTab === "report"
                  ? "bg-danger text-white shadow-xs"
                  : "text-muted hover:text-foreground hover:bg-card"
              }`}
            >
              <AlertTriangle className="h-4 w-4" />
              <span>{t.tabReport}</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("track")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                activeTab === "track"
                  ? "bg-accent text-white shadow-xs"
                  : "text-muted hover:text-foreground hover:bg-card"
              }`}
            >
              <Search className="h-4 w-4" />
              <span>{t.tabTrack}</span>
              {activeIncidentId && (
                <span className="text-[10px] bg-white/20 px-1.5 py-0.5 rounded-full font-mono">
                  {activeIncidentId}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("guide")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                activeTab === "guide"
                  ? "bg-foreground text-background shadow-xs"
                  : "text-muted hover:text-foreground hover:bg-card"
              }`}
            >
              <BookOpen className="h-4 w-4" />
              <span>{t.tabGuide}</span>
            </button>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted">
            <Lock className="h-3.5 w-3.5 text-accent" />
            <span>{t.secureIntake}</span>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === "report" && (
          <div className="space-y-6">
            <EmergencyReportForm
              onReportSubmitted={handleReportSubmitted}
              onTrackRequested={handleTrackRequested}
            />

            {/* Quick Survival Advice Preview */}
            <div className="pt-2">
              <SafetyGuidance compact />
            </div>
          </div>
        )}

        {activeTab === "track" && (
          <div className="space-y-6">
            <IncidentStatusTracker
              initialReferenceId={activeIncidentId}
              onBackToReport={() => setActiveTab("report")}
            />
          </div>
        )}

        {activeTab === "guide" && (
          <div className="space-y-6">
            <SafetyGuidance />
          </div>
        )}

        {/* Feature Highlights / Info Cards */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-card-border/60">
          <div className="p-4 rounded-xl bg-card border border-card-border shadow-2xs space-y-2">
            <div className="flex items-center gap-2 text-accent font-semibold text-xs uppercase tracking-wider">
              <Sparkles className="h-4 w-4" />
              <span>{t.cardTriageTitle}</span>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              {t.cardTriageDesc}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border shadow-2xs space-y-2">
            <div className="flex items-center gap-2 text-tangerine font-semibold text-xs uppercase tracking-wider">
              <Radio className="h-4 w-4" />
              <span>{t.cardEdgeTitle}</span>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              {t.cardEdgeDesc}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-card border border-card-border shadow-2xs space-y-2">
            <div className="flex items-center gap-2 text-success font-semibold text-xs uppercase tracking-wider">
              <HeartHandshake className="h-4 w-4" />
              <span>{t.cardApprovalTitle}</span>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              {t.cardApprovalDesc}
            </p>
          </div>
        </section>
      </main>

      {/* Public Footer */}
      <footer className="border-t border-card-border bg-surface/50 py-6 px-4 text-center space-y-3 mt-12">
        <div className="max-w-4xl mx-auto space-y-2">
          <div className="flex items-center justify-center gap-2 text-xs font-bold tracking-wider text-foreground">
            <Radio className="h-4 w-4 text-accent" />
            <span>{t.portalTitle} — {t.portalSubtitle}</span>
          </div>
          <p className="text-[11px] text-muted max-w-2xl mx-auto leading-relaxed">
            {t.footerDisclaimer}
          </p>
          <div className="text-[10px] text-muted/70 pt-1">
            {t.footerRights}
          </div>
        </div>
      </footer>
    </div>
  );
}

export function CitizenDashboard() {
  return (
    <LanguageProvider>
      <CitizenDashboardContent />
    </LanguageProvider>
  );
}
