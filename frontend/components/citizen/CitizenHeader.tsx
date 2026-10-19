"use client";

import { Radio, PhoneCall, Languages } from "lucide-react";
import { NetworkStatusBadge } from "./NetworkStatusBadge";
import { useCitizenLanguage } from "./LanguageContext";

export function CitizenHeader() {
  const { language, setLanguage, t } = useCitizenLanguage();

  return (
    <header className="border-b border-card-border bg-card/80 backdrop-blur-md sticky top-0 z-30">
      {/* Top emergency hotline bar */}
      <div className="bg-danger px-4 py-1.5 text-white text-xs font-semibold flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1.5">
          <PhoneCall className="h-3.5 w-3.5 animate-pulse" />
          <span>{t.hotlineBar}</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-bold tracking-wider">
          <span className="px-2 py-0.5 rounded bg-white/20">{t.hotlineAmbulance}</span>
          <span className="px-2 py-0.5 rounded bg-white/20">{t.hotlinePolice}</span>
          <span className="px-2 py-0.5 rounded bg-white/20">{t.hotlineFire}</span>
        </div>
      </div>

      {/* Main branding row */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-accent/10 text-accent border border-accent/20">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold tracking-widest text-foreground">
                {t.portalTitle}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
                {t.portalBadge}
              </span>
            </div>
            <div className="text-[11px] font-medium tracking-wide text-muted">
              {t.portalSubtitle}
            </div>
          </div>
        </div>

        {/* Right side controls: Language Switcher + Network Status */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Visible Language Switcher */}
          <div className="flex items-center p-1 rounded-xl bg-surface border border-card-border text-xs">
            <span className="text-muted px-2 py-1 flex items-center gap-1 text-[11px] font-medium">
              <Languages className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{t.languageSelect}:</span>
            </span>
            <button
              type="button"
              onClick={() => setLanguage("en")}
              className={`px-2.5 py-1 rounded-lg font-bold transition-all cursor-pointer ${
                language === "en"
                  ? "bg-accent text-white shadow-2xs"
                  : "text-muted hover:text-foreground"
              }`}
            >
              English
            </button>
            <button
              type="button"
              onClick={() => setLanguage("ur")}
              className={`px-2.5 py-1 rounded-lg font-bold transition-all cursor-pointer ${
                language === "ur"
                  ? "bg-accent text-white shadow-2xs"
                  : "text-muted hover:text-foreground"
              }`}
            >
              Roman Urdu
            </button>
          </div>

          <NetworkStatusBadge showDetails />
        </div>
      </div>
    </header>
  );
}
