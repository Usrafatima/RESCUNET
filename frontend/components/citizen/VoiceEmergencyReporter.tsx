"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Info,
  Edit3,
  RotateCcw,
  ArrowRight,
  ShieldAlert,
} from "lucide-react";
import { useCitizenLanguage } from "./LanguageContext";
import type { EmergencyType } from "./EmergencyReportForm";

interface VoiceEmergencyReporterProps {
  onTranscriptApplied: (
    transcript: string,
    suggestedCategory: EmergencyType | null
  ) => void;
  currentDescription: string;
}

// Minimal standard Web Speech API typing without 'any'
interface SpeechRecognitionEvent {
  resultIndex?: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      length?: number;
      [index: number]: { transcript: string };
    };
  };
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

interface SpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

interface SpeechWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

function getSpeechConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const win = window as SpeechWindow;
  return win.SpeechRecognition || win.webkitSpeechRecognition || null;
}

// Keyword-based category suggestion (strictly deterministic, never invents missing information)
function inferCategoryFromSpeech(text: string): {
  category: EmergencyType | null;
  matchedKeywords: string[];
} {
  const lower = text.toLowerCase();

  const rules: { type: EmergencyType; keywords: string[] }[] = [
    {
      type: "Medical",
      keywords: [
        "heart",
        "chest pain",
        "breathing",
        "breath",
        "unconscious",
        "fainted",
        "bleeding",
        "blood",
        "injury",
        "injured",
        "diabetic",
        "seizure",
        "ambulance",
        "stroke",
        "saans",
        "behosh",
        "khoon",
        "dard",
        "dil",
        "mareez",
        "chot",
        "tabiyat",
        "gir",
        "gir gayi",
        "gir gaya",
        "fall",
        "stairs",
      ],
    },
    {
      type: "Fire",
      keywords: [
        "fire",
        "flame",
        "smoke",
        "explosion",
        "burning",
        "burnt",
        "gas cylinder",
        "aag",
        "dhuwan",
        "sholay",
        "dhamaka",
        "jal raha",
      ],
    },
    {
      type: "Flood",
      keywords: [
        "flood",
        "water",
        "drowning",
        "river",
        "submerged",
        "rain",
        "rising water",
        "roof",
        "sailaab",
        "paani",
        "doob",
        "chhat",
        "sarak doob",
      ],
    },
    {
      type: "Accident",
      keywords: [
        "accident",
        "crash",
        "collision",
        "overturned",
        "car",
        "truck",
        "motorcycle",
        "pinned",
        "trapped in car",
        "haadsa",
        "takar",
        "gaari ulat",
        "tasadum",
      ],
    },
    {
      type: "Other",
      keywords: [
        "chemical",
        "gas leak",
        "toxic",
        "power line",
        "live wire",
        "earthquake",
        "collapse",
        "missing",
        "boo",
        "bijli ka taar",
        "zalzala",
      ],
    },
  ];

  for (const rule of rules) {
    const matched = rule.keywords.filter((kw) => lower.includes(kw));
    if (matched.length > 0) {
      return { category: rule.type, matchedKeywords: matched };
    }
  }

  return { category: null, matchedKeywords: [] };
}

export function VoiceEmergencyReporter({
  onTranscriptApplied,
  currentDescription,
}: VoiceEmergencyReporterProps) {
  const { language, t } = useCitizenLanguage();

  const [hasMounted, setHasMounted] = useState(false);
  const [isSupported, setIsSupported] = useState(false);
  const [hasSpeechSynthesis, setHasSpeechSynthesis] = useState(false);

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState(currentDescription || "");
  const [interimText, setInterimText] = useState("");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [appliedSuccess, setAppliedSuccess] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const lastProcessedIndexRef = useRef<number>(0);

  // Detect client-side speech support on mount to prevent SSR hydration mismatches
  useEffect(() => {
    setHasMounted(true);
    setIsSupported(!!getSpeechConstructor());
    setHasSpeechSynthesis(typeof window !== "undefined" && "speechSynthesis" in window);
  }, []);

  // Derived category inference using useMemo (no cascading effect state updates)
  const { category: suggestedCategory, matchedKeywords: matchedTerms } =
    useMemo(() => {
      if (!transcript.trim()) {
        return { category: null, matchedKeywords: [] };
      }
      return inferCategoryFromSpeech(transcript);
    }, [transcript]);

  // Clean up recognition and read-aloud when component unmounts
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
      }
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const startListening = useCallback(() => {
    setVoiceError(null);
    setAppliedSuccess(false);
    setInterimText("");
    lastProcessedIndexRef.current = 0;

    const SpeechRecognition = getSpeechConstructor();

    if (!SpeechRecognition) {
      setVoiceError(t.voiceUnsupportedNotice);
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = language === "ur" ? "ur-PK" : "en-US";

      recognition.onstart = () => {
        setIsRecording(true);
        setVoiceError(null);
        setInterimText("");
      };

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const startIndex = typeof event.resultIndex === "number" ? event.resultIndex : 0;
        const fromIndex = Math.max(startIndex, lastProcessedIndexRef.current);

        let newlyFinalized = "";

        // 1. Accumulate newly finalized speech results using event.results and resultIndex
        for (let i = fromIndex; i < event.results.length; i++) {
          const res = event.results[i];
          if (res.isFinal) {
            const phrase = res[0]?.transcript?.trim();
            if (phrase) {
              newlyFinalized = newlyFinalized ? `${newlyFinalized} ${phrase}` : phrase;
            }
            lastProcessedIndexRef.current = i + 1;
          }
        }

        // 2. Accumulate current interim (provisional) speech results separately
        let interim = "";
        for (let i = startIndex; i < event.results.length; i++) {
          const res = event.results[i];
          if (!res.isFinal && res[0]?.transcript) {
            interim += res[0].transcript;
          }
        }

        // Display interim text separately from finalized text
        setInterimText(interim.trim());

        // Update finalized transcript without duplicating previously processed phrases
        if (newlyFinalized) {
          setTranscript((prev) => {
            const prevTrimmed = prev.trim();
            return prevTrimmed ? `${prevTrimmed} ${newlyFinalized}` : newlyFinalized;
          });
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        setIsRecording(false);
        setInterimText("");
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          setVoiceError(t.voicePermissionDenied);
        } else if (event.error === "no-speech") {
          setVoiceError(t.voiceNoSpeech);
        } else {
          setVoiceError(`Speech recognition message: ${event.error}`);
        }
      };

      recognition.onend = () => {
        setIsRecording(false);
        setInterimText("");
        lastProcessedIndexRef.current = 0;
      };

      recognition.start();
    } catch (err) {
      setIsRecording(false);
      setInterimText("");
      setVoiceError(
        err instanceof Error ? err.message : "Failed to initialize microphone."
      );
    }
  }, [language, t]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore
      }
    }
    setIsRecording(false);
    setInterimText("");
  }, []);

  const handleApply = () => {
    if (!transcript.trim()) {
      setVoiceError(t.validationDescRequired);
      return;
    }
    onTranscriptApplied(transcript.trim(), suggestedCategory);
    setAppliedSuccess(true);
    setTimeout(() => setAppliedSuccess(false), 3500);
  };

  const handleClear = () => {
    setTranscript("");
    setInterimText("");
    setVoiceError(null);
    lastProcessedIndexRef.current = 0;
  };

  const handleToggleReadAloud = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    const textToRead =
      transcript.trim() ||
      (language === "ur"
        ? "RescuNet emergency portal. Barah-e-karam apna masla bol kar ya likh kar bayan karain."
        : "RescuNet emergency coordination portal. Please describe your emergency by voice or text.");

    const utterance = new SpeechSynthesisUtterance(textToRead);
    utterance.lang = language === "ur" ? "ur-PK" : "en-US";
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  };

  return (
    <div className="bg-surface/60 border border-card-border rounded-xl p-4 sm:p-5 space-y-4">
      {/* Top Banner / Trigger */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <div
            className={`p-2 rounded-lg ${
              isRecording
                ? "bg-danger text-white animate-pulse"
                : "bg-accent/10 text-accent border border-accent/20"
            }`}
          >
            {isRecording ? (
              <Mic className="h-5 w-5" />
            ) : (
              <MicOff className="h-5 w-5" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">
              {t.voiceButton}
            </h3>
            <p className="text-xs text-muted">
              {isRecording ? t.voiceListening : t.voiceSupportedNotice}
            </p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {/* Read aloud helper */}
          {hasSpeechSynthesis && (
            <button
              type="button"
              onClick={handleToggleReadAloud}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors cursor-pointer ${
                isSpeaking
                  ? "bg-danger/10 text-danger border-danger/30"
                  : "bg-card hover:bg-surface text-muted hover:text-foreground border-card-border"
              }`}
              title={isSpeaking ? t.voiceStopReadAloud : t.voiceReadAloud}
            >
              {isSpeaking ? (
                <>
                  <VolumeX className="h-3.5 w-3.5" />
                  <span>{t.voiceStopReadAloud}</span>
                </>
              ) : (
                <>
                  <Volume2 className="h-3.5 w-3.5" />
                  <span>{t.voiceReadAloud}</span>
                </>
              )}
            </button>
          )}

          {/* Record / Stop Button */}
          {isRecording ? (
            <button
              type="button"
              onClick={stopListening}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-danger text-white font-bold text-xs shadow-xs animate-pulse hover:bg-danger/90 transition-all cursor-pointer"
            >
              <MicOff className="h-4 w-4" />
              <span>{t.voiceStop}</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={startListening}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white font-bold text-xs shadow-xs hover:bg-accent-hover transition-all cursor-pointer"
            >
              <Mic className="h-4 w-4" />
              <span>{t.voiceButton}</span>
            </button>
          )}
        </div>
      </div>

      {/* Browser Support Warning */}
      {hasMounted && !isSupported && (
        <div className="p-3 bg-warning/10 border border-warning/30 rounded-lg text-xs text-warning-ink flex items-start gap-2">
          <Info className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{t.voiceUnsupportedNotice}</span>
        </div>
      )}

      {/* Voice Error Display */}
      {voiceError && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-lg text-xs text-danger flex items-start gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{voiceError}</span>
        </div>
      )}

      {/* Live Interim feedback when recording */}
      {isRecording && interimText && (
        <div className="p-2.5 bg-accent/5 border border-accent/20 rounded-lg text-xs text-accent italic">
          <span className="font-semibold not-italic">Listening: </span>
          &ldquo;{interimText}&rdquo;
        </div>
      )}

      {/* Editable Transcript Field */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <label className="font-bold text-foreground flex items-center gap-1.5">
            <Edit3 className="h-3.5 w-3.5 text-accent" />
            <span>{t.voiceTranscriptLabel}</span>
          </label>
          {transcript && (
            <button
              type="button"
              onClick={handleClear}
              className="text-[11px] text-muted hover:text-danger flex items-center gap-1 cursor-pointer"
            >
              <RotateCcw className="h-3 w-3" />
              <span>{t.voiceClear}</span>
            </button>
          )}
        </div>

        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          rows={3}
          placeholder={
            language === "ur"
              ? "Aap ki boli hui awaz yahan tehreer ban kar aayegi. Aap isay hath se bhi theek kar saktay hain..."
              : "Recognized voice speech appears here. You can also edit, type, or correct text directly..."
          }
          className="w-full px-3 py-2 text-sm bg-card rounded-xl border border-card-border focus:border-accent focus:outline-hidden"
        />

        <p className="text-[11px] text-muted">{t.voiceTranscriptHint}</p>
      </div>

      {/* Category Suggestion & Keyword Transparency */}
      {transcript.trim() && (
        <div className="p-3 rounded-xl bg-card border border-card-border space-y-2">
          <div className="flex items-center justify-between flex-wrap gap-2 text-xs">
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-accent" />
              <span className="font-semibold text-foreground">
                {t.voiceSuggestedCategory}
              </span>
              {suggestedCategory ? (
                <span className="px-2 py-0.5 rounded-full bg-accent/15 text-accent font-bold">
                  {suggestedCategory}
                </span>
              ) : (
                <span className="text-muted italic">
                  {language === "ur"
                    ? "Koi makhsoos qisam nahi mili (form mein khud chuniye)"
                    : "No specific category detected (select manually)"}
                </span>
              )}
            </div>

            {matchedTerms.length > 0 && (
              <div className="text-[11px] text-muted">
                <span>Matched: </span>
                <span className="font-mono text-accent">
                  {matchedTerms.join(", ")}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between flex-wrap gap-2 pt-1 border-t border-card-border/60">
            <div className="text-[11px] text-muted flex items-center gap-1">
              <ShieldAlert className="h-3 w-3 text-warning-ink" />
              <span>
                {language === "ur"
                  ? "Location aur mutasira tadaad record se invent nahi ki jati — neechay khud tasdeeq karain."
                  : "Location and affected count are never guessed — please confirm them below."}
              </span>
            </div>

            <button
              type="button"
              onClick={handleApply}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-white font-bold text-xs hover:bg-accent-hover transition-colors shadow-2xs cursor-pointer"
            >
              <span>{t.voiceApplyToForm}</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Success Notification */}
      {appliedSuccess && (
        <div className="p-2.5 bg-success/10 border border-success/30 rounded-lg text-xs text-success flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>
            {language === "ur"
              ? "Voice report form mein shamil kar di gayi hai! Neechay location aur tadaad ki tasdeeq karain."
              : "Voice report applied to form! Please verify your location and affected count below."}
          </span>
        </div>
      )}
    </div>
  );
}
