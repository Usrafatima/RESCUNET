"use client";

import { useState } from "react";
import {
  Heart,
  Flame,
  Droplets,
  Car,
  AlertCircle,
  CheckCircle,
  XCircle,
  PhoneCall,
  ShieldAlert,
} from "lucide-react";
import { useCitizenLanguage } from "./LanguageContext";

export type EmergencyCategory = "medical" | "fire" | "flood" | "accident" | "other";

interface GuideItem {
  id: EmergencyCategory;
  title: string;
  icon: typeof Heart;
  badgeColor: string;
  bgColor: string;
  summary: string;
  immediateActions: string[];
  doNots: string[];
}

const GUIDELINES_EN: GuideItem[] = [
  {
    id: "medical",
    title: "Medical Emergency",
    icon: Heart,
    badgeColor: "text-danger border-danger/30 bg-danger/10",
    bgColor: "border-danger/20",
    summary: "Immediate steps for unconsciousness, severe bleeding, chest pain, or breathing failure.",
    immediateActions: [
      "Check responsiveness: Tap shoulders firmly and call out loudly. Check if they are breathing normally.",
      "Severe bleeding: Apply direct, firm pressure with a clean cloth or clothing. Do not release pressure to check.",
      "Chest pain / Cardiac: Keep the patient sitting comfortably, loosen tight clothing, and keep them calm.",
      "Choking: If conscious and unable to speak/cough, deliver 5 sharp back blows between shoulder blades, then 5 abdominal thrusts.",
      "Seizure: Clear hard objects nearby. Do NOT put anything in their mouth. Turn them onto their side once seizing stops.",
    ],
    doNots: [
      "Do NOT move someone with potential neck or spinal injury unless there is immediate danger (fire, collapse).",
      "Do NOT give food, water, or medicine to an unconscious or semi-conscious person.",
      "Do NOT leave an injured individual unattended.",
    ],
  },
  {
    id: "fire",
    title: "Fire & Smoke",
    icon: Flame,
    badgeColor: "text-info border-info/30 bg-info/10",
    bgColor: "border-info/20",
    summary: "Evacuation protocols, smoke inhalation avoidance, and burn management.",
    immediateActions: [
      "Evacuate immediately: Alert others, leave all belongings behind, and head for the nearest clear exit.",
      "Stay low: Crawl on hands and knees below smoke where the air is coolest and cleanest.",
      "Check doors before opening: Feel door handles and edges with the back of your hand. If hot, DO NOT open.",
      "If clothes catch fire: STOP, DROP to the ground, and ROLL back and forth covering your face.",
      "Once outside: Move to an open assembly point at least 100 meters away from the structure.",
    ],
    doNots: [
      "Do NOT use elevators under any circumstances during a fire.",
      "Do NOT open hot doors or break upper-floor windows unless trapped with no other escape.",
      "Do NOT re-enter a burning or smoke-filled building for any reason.",
    ],
  },
  {
    id: "flood",
    title: "Flood & Rising Water",
    icon: Droplets,
    badgeColor: "text-accent border-accent/30 bg-accent/10",
    bgColor: "border-accent/20",
    summary: "Survival steps for flash floods, urban inundation, and water hazards.",
    immediateActions: [
      "Head to high ground: Move immediately to the highest accessible level or elevated ground.",
      "Disconnect utilities if safe: Shut off main power switches and gas valves before water reaches outlets.",
      "Signal for assistance: Use a flashlight, bright cloth, or phone light to signal rescuers from high visible points.",
      "If vehicle is taking on water: Unbuckle immediately, unlock doors, roll down windows before electronics short, and exit to vehicle roof.",
    ],
    doNots: [
      "Do NOT walk through moving water. Just 15 cm (6 inches) of rapid current can knock an adult off their feet.",
      "Do NOT drive through flooded roads or underpasses. Most flood fatalities occur in vehicles.",
      "Do NOT touch electrical equipment, switches, or downed power wires in or near standing water.",
    ],
  },
  {
    id: "accident",
    title: "Vehicle / Industrial Accident",
    icon: Car,
    badgeColor: "text-warning-ink border-warning/30 bg-warning/10",
    bgColor: "border-warning/20",
    summary: "Road collisions, machinery accidents, and structural entrapment safety.",
    immediateActions: [
      "Protect the scene: Turn on hazard lights. Stand safely off the active roadway on the shoulder or behind barriers.",
      "Turn off ignitions: If safe to reach, turn off vehicle engines to reduce fire hazard.",
      "Keep casualties stable: Speak calmly to injured passengers to keep them conscious and still.",
      "Check for hazards: Look out for fuel spills, downed power lines, or oncoming traffic before stepping forward.",
    ],
    doNots: [
      "Do NOT pull injured passengers from vehicles unless there is an imminent risk of fire or vehicle submersion.",
      "Do NOT remove a motorcycle helmet unless the airway is obstructed.",
      "Do NOT smoke or ignite flares near accident scenes due to vapor explosion risk.",
    ],
  },
  {
    id: "other",
    title: "Hazmat & Other Emergencies",
    icon: AlertCircle,
    badgeColor: "text-neutral border-neutral/30 bg-surface",
    bgColor: "border-neutral/20",
    summary: "Chemical spills, structural collapse, extreme weather, and utility failures.",
    immediateActions: [
      "Upwind & uphill: If toxic fumes or chemical leaks are suspected, move immediately upwind and uphill.",
      "Structural instability: If a building is compromised, evacuate into open areas away from facades and power lines.",
      "Conserve phone battery: Switch phone to power-saving mode, reduce screen brightness, and use text instead of voice calls.",
      "Stay calm: Gather family or group members, take headcount, and stay together in a safe shelter zone.",
    ],
    doNots: [
      "Do NOT use open flames, matches, or lighters if you smell gas or unfamiliar odors.",
      "Do NOT approach fallen utility poles or dangling cables — treat all downed wires as live.",
      "Do NOT spread unverified rumors; rely on official public broadcast instructions.",
    ],
  },
];

const GUIDELINES_UR: GuideItem[] = [
  {
    id: "medical",
    title: "Medical / Tibbi Imdad",
    icon: Heart,
    badgeColor: "text-danger border-danger/30 bg-danger/10",
    bgColor: "border-danger/20",
    summary: "Behoshi, khoon behne, dil ke daure ya saans band hone par fauri iqdamaat.",
    immediateActions: [
      "Hosh check karain: Mareez ke kandhay ko hila kar pukaarein. Check karain ke saans theek chal rahi hai ya nahi.",
      "Khoon behna: Saaf kapray se zakhm par musalsal aur mazboot dabao dalein. Dabao hata kar baar baar na dekhein.",
      "Dil ka daura / Chest pain: Mareez ko aaram deh halat mein bitha dein, tang kapray khol dein aur pur-sukoon rakhein.",
      "Gala ghutna (Choking): Agar mareez bol na sakay to peeth par 5 thapkiyan dein aur pait par dabao dalein.",
      "Jhatkay (Seizure): Qareeb se sakht cheezein hata dein. Munh mein koi cheez na dalein.",
    ],
    doNots: [
      "Gardan ya reedh ki haddi ki chot walay mareez ko hargiz na hilayein jab tak fauri jaan ka khatra na ho.",
      "Behosh ya neem-behosh shakhs ko paani, khana ya dawa hargiz na pilayein.",
      "Zakhmi shakhs ko akela mat chorein.",
    ],
  },
  {
    id: "fire",
    title: "Aag / Fire",
    icon: Flame,
    badgeColor: "text-info border-info/30 bg-info/10",
    bgColor: "border-info/20",
    summary: "Imarat khali karne, dhuwen se bachne aur jalanay ke iqdamaat.",
    immediateActions: [
      "Fauran bahir niklein: Sab ko aagah karain, samaan chor kar qareebi raste se foran nikal jayein.",
      "Neechay jhuk kar chalein: Dhuwen ke neechay zameen ke qareeb reng kar chalein jahan hawa saaf hoti hai.",
      "Darwazay check karain: Darwaza kholne se pehle haath ki ulti taraf se handle check karain. Garm ho to na kholein.",
      "Kapron mein aag lage to: Rukein, zameen par leatein (DROP), aur ghoom kar aag bujhayein (ROLL).",
      "Bahir pohanch kar: Imarat se kam az kam 100 meter door khuli jagah par jama hon.",
    ],
    doNots: [
      "Aag ke dauran kisi soorat mein lift (elevator) ka istemal na karain.",
      "Garm darwaza hargiz na kholein.",
      "Jalti hui ya dhuwen se bhari imarat mein dobara kisi cheez ke liye dakhil na hon.",
    ],
  },
  {
    id: "flood",
    title: "Sailaab / Flood",
    icon: Droplets,
    badgeColor: "text-accent border-accent/30 bg-accent/10",
    bgColor: "border-accent/20",
    summary: "Sailaabi paani aur taiz bahaav se bachne ke hifazati usool.",
    immediateActions: [
      "Buland jagah par jayein: Imarat ki oopri manzil ya unchi zameen par fauran muntaqil hon.",
      "Bijli aur gas band karain: Agar safe ho to main bijli switch aur gas valve band kar dein.",
      "Madad ke liye ishara karain: Flashlight, phone ki roshni ya chamakdar kapray se rescuers ko ishara karain.",
      "Agar gaari paani mein phansay: Seatbelt foran kholein, sheeshay neechay karain aur gaari ki chhat par chadh jayein.",
    ],
    doNots: [
      "Behtay hue sailaabi paani mein hargiz paidal na chalein. Sirf 6 inch ka paani gira sakta hai.",
      "Doobi hui sarak par gaari na chalayein. Zyadatar amwaat gaariyon ke doobne se hoti hain.",
      "Kharay paani mein bijli ke taaron ya switches ko hargiz haath na lagayein.",
    ],
  },
  {
    id: "accident",
    title: "Haadsa / Accident",
    icon: Car,
    badgeColor: "text-warning-ink border-warning/30 bg-warning/10",
    bgColor: "border-warning/20",
    summary: "Road accident, takar aur malbay se bachao ke iqdamaat.",
    immediateActions: [
      "Scene ko mehfooz karain: Hazard lights on karain aur chalti sarak se hat kar kharay hon.",
      "Engine band karain: Agar mumkin ho to gaari ka switch band karain taakay aag na lagay.",
      "Zakhmiyon ko pur-sukoon rakhein: Mareez se aahista baat karain taakay wo hosh mein rahein.",
      "Khatraat check karain: Petrol leak, toota bijli ka taar ya tezi se aati gaariyon par nazar rakhein.",
    ],
    doNots: [
      "Zakhmi shakhs ko gaari se kheench kar bahir na nikalein jab tak aag ka fauri khatra na ho.",
      "Motorcycle helmet ko bila zaroorat mat utarein.",
      "Haadsay ki jagah par cigarette ya match-box hargiz na jalayein.",
    ],
  },
  {
    id: "other",
    title: "Deegar / Other",
    icon: AlertCircle,
    badgeColor: "text-neutral border-neutral/30 bg-surface",
    bgColor: "border-neutral/20",
    summary: "Chemical leak, gas ki boo, bijli ke giray taar aur qudrati aafaat.",
    immediateActions: [
      "Hawa ki simt mein jayein: Agar zehreeli gas ki boo ho to hawa ke rukh ke ulti taraf jayein.",
      "Imarat kamzor ho to bahir jayein: Khuli jagah par jayein jahan imarat ya khambay na gir sakein.",
      "Phone battery bachayein: Battery saver on karain aur sirf ahem zaroorat ke liye rabta karain.",
      "Apno ke sath ikathay rahein: Sab family azaa ko aik jagah mehfooz panah mein rakhein.",
    ],
    doNots: [
      "Gas ki boo aane par koi bijli ka button ya match-box na jalayein.",
      "Zameen par giray bijli ke taar ke qareeb hargiz na jayein.",
      "Afwahon par dehan na dein, sirf sarkari ailaanat par amal karain.",
    ],
  },
];

interface SafetyGuidanceProps {
  initialCategory?: EmergencyCategory;
  compact?: boolean;
}

export function SafetyGuidance({
  initialCategory = "medical",
  compact = false,
}: SafetyGuidanceProps) {
  const { language, t } = useCitizenLanguage();
  const [activeCategory, setActiveCategory] =
    useState<EmergencyCategory>(initialCategory);

  const guidelines = language === "ur" ? GUIDELINES_UR : GUIDELINES_EN;
  const currentGuide =
    guidelines.find((g) => g.id === activeCategory) || guidelines[0];

  return (
    <div className="bg-card border border-card-border rounded-xl shadow-xs overflow-hidden">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-card-border bg-surface/50">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-accent" />
            <div>
              <h3 className="font-semibold text-foreground text-sm sm:text-base">
                {t.guideTitle}
              </h3>
              <p className="text-xs text-muted">
                {t.guideSubtitle}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-danger font-medium px-2 py-1 rounded bg-danger/10 border border-danger/20">
            <PhoneCall className="h-3.5 w-3.5" />
            <span>{t.guideCallHotline}</span>
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pt-3 pb-1 scrollbar-none">
          {guidelines.map((guide) => {
            const Icon = guide.icon;
            const isSelected = activeCategory === guide.id;
            return (
              <button
                key={guide.id}
                type="button"
                onClick={() => setActiveCategory(guide.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all cursor-pointer ${
                  isSelected
                    ? "bg-accent text-white shadow-xs"
                    : "bg-surface hover:bg-card-border/60 text-muted hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{guide.title}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Guide Content */}
      <div className="p-4 sm:p-6 space-y-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${currentGuide.badgeColor}`}
            >
              <currentGuide.icon className="h-3 w-3" />
              {currentGuide.title}
            </span>
          </div>
          <p className="text-sm text-foreground/80 font-medium">
            {currentGuide.summary}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Immediate Do's */}
          <div className="p-4 rounded-lg bg-success/5 border border-success/20">
            <div className="flex items-center gap-2 mb-3 text-success font-semibold text-xs uppercase tracking-wider">
              <CheckCircle className="h-4 w-4" />
              <span>{t.guideDoTitle}</span>
            </div>
            <ul className="space-y-2 text-xs text-foreground/90">
              {currentGuide.immediateActions.map((action, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="font-bold text-success select-none">•</span>
                  <span className="leading-relaxed">{action}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Do NOTs */}
          <div className="p-4 rounded-lg bg-danger/5 border border-danger/20">
            <div className="flex items-center gap-2 mb-3 text-danger font-semibold text-xs uppercase tracking-wider">
              <XCircle className="h-4 w-4" />
              <span>{t.guideDontTitle}</span>
            </div>
            <ul className="space-y-2 text-xs text-foreground/90">
              {currentGuide.doNots.map((action, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="font-bold text-danger select-none">✕</span>
                  <span className="leading-relaxed">{action}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {!compact && (
          <div className="p-3 bg-surface rounded-lg border border-card-border text-[11px] text-muted flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-accent shrink-0 mt-0.5" />
            <div>{t.guideNotice}</div>
          </div>
        )}
      </div>
    </div>
  );
}
