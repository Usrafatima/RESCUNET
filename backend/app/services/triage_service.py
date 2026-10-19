"""
Emergency triage service for RescuNet.

Deterministic, auditable triage of incoming SOS reports:

1. Extract what the report actually says (type, hazards, requested help,
   people affected, location) using documented keyword evidence.
2. Assign an urgency level with EXPLICIT, documented criteria (U1-U4).
3. Record missing or uncertain information instead of guessing.
4. Optionally enrich the interpretation with the existing LLM agent —
   the LLM can ADD interpretation but can never lower a rule-derived
   urgency level.

Guiding rules:
- Never invent coordinates, victims, resources or incident details.
- Missing evidence never lowers urgency: when the report is too thin to
  classify, the conservative level is used and the report is flagged
  `insufficient_evidence`.
- Every fired criterion is returned with its evidence so a human can audit
  the decision.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.plans import TriageCriterion, TriageLocation, TriageResult
from app.services.recommendation_service import _infer_incident_type

logger = logging.getLogger(__name__)

CRITERIA_VERSION = "U1-U4/v1"

# Canonical urgency score per level (deterministic, documented).
URGENCY_SCORES = {
    "critical": 90,
    "high": 75,
    "medium": 50,
    "low": 25,
}

# Rank used to pick the highest triggered rule.
URGENCY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# ─── Documented urgency criteria ────────────────────────────────────────────
# Each rule is evaluated against evidence extracted from the report.
# The highest matching rule wins; if nothing matches, the conservative
# default (medium + insufficient_evidence) is applied.

URGENCY_RULES: list[dict] = [
    {
        "rule_id": "U1",
        "level": "critical",
        "description": (
            "Immediate threat to life: report contains life-threatening evidence, "
            "OR an active hazard affects 5 or more people."
        ),
    },
    {
        "rule_id": "U2",
        "level": "high",
        "description": (
            "Serious and time-sensitive: an active hazard is present, "
            "OR 5 or more people are affected, OR the reporter uses "
            "time-critical language (immediately, urgent, spreading...)."
        ),
    },
    {
        "rule_id": "U3",
        "level": "medium",
        "description": (
            "Needs response but not immediately life-threatening: injury, illness, "
            "damage or a concrete assistance request is reported, OR the report "
            "does not contain enough evidence to classify safely (conservative default)."
        ),
    },
    {
        "rule_id": "U4",
        "level": "low",
        "description": (
            "Explicitly non-urgent: the reporter states it is not urgent / minor "
            "and no hazard, injury or time-critical language is present."
        ),
    },
]

CONSERVATIVE_LEVEL = "medium"

# ─── Evidence lexicons (documented, deterministic) ──────────────────────────

LIFE_THREAT_TERMS = [
    "trapped",
    "cannot breathe",
    "can't breathe",
    "unconscious",
    "not breathing",
    "chest pain",
    "heart attack",
    "bleeding",
    "drowning",
    "under rubble",
    "under the rubble",
    "pinned",
    "choking",
    "stroke",
    "no pulse",
    "stuck under",
    "buried",
    "cannot move",
    "can't move",
    "severe injury",
    "broken bone",
]

ACTIVE_HAZARD_TERMS = {
    "fire": ["fire", "flames", "burning", "smoke"],
    "flood": ["flood", "floodwater", "rising water", "flash flood", "water level"],
    "gas": ["gas leak", "smell of gas", "gas line"],
    "electrical": ["electrical", "sparking", "power line", "electrocuted", "live wire"],
    "structural": ["collapsed", "collapse", "structural", "crumbling", "building shaking"],
    "chemical": ["chemical", "toxic", "fumes", "acid"],
    "landslide": ["landslide", "mudslide", "rockslide"],
    "earthquake": ["earthquake", "aftershock"],
}

TIME_CRITICAL_TERMS = [
    "immediately",
    "urgent",
    "urgently",
    "asap",
    "right away",
    "spreading",
    "getting worse",
    "no time",
    "hurry",
]

INJURY_ILLNESS_TERMS = [
    "injured",
    "injury",
    "hurt",
    "fracture",
    "wound",
    "sick",
    "ill",
    "fever",
    "asthma",
    "diabetic",
    "insulin",
    "medicine",
    "pain",
    "blood",
]

DAMAGE_TERMS = [
    "damaged",
    "destroyed",
    "roof blown",
    "window broken",
    "walls cracked",
    "road blocked",
    "power out",
    "no electricity",
    "displaced",
    "homeless",
]

NON_URGENT_TERMS = [
    "not urgent",
    "no rush",
    "minor",
    "no injuries",
    "no one is hurt",
    "no one hurt",
    "can wait",
    "not an emergency",
]

ASSISTANCE_MAP: dict[str, list[str]] = {
    "medical evacuation": ["ambulance", "hospital", "evacuate the injured", "medevac"],
    "medical treatment": ["doctor", "nurse", "medical team", "treatment", "clinic"],
    "medical supplies": ["medicine", "insulin", "oxygen", "first aid", "bandage"],
    "extraction / rescue": [
        "rescue",
        "get us out",
        "pull out",
        "extract",
        "dig out",
        "cut out",
    ],
    "firefighting": ["fire truck", "firefighters", "extinguish", "put out the fire"],
    "food / water": ["water", "food", "blankets", "supplies", "rations", "drinking"],
    "shelter": ["shelter", "tent", "place to sleep", "somewhere to stay"],
    "search for missing person": ["missing", "lost contact", "cannot find"],
}

REQUEST_LANGUAGE = ["need", "require", "please send", "help", "asking for", "send "]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_terms(text: str, terms: list[str]) -> list[str]:
    """Return the documented terms actually present in the report text."""
    return [t for t in terms if t in text]


def _neutralize_non_urgent(text: str) -> str:
    """Remove explicitly non-urgent phrasing before urgency scanning.

    Without this, "not urgent" would match the term "urgent" and inflate the
    assessed urgency of a report the reporter explicitly downgraded.
    """
    for phrase in NON_URGENT_TERMS:
        text = text.replace(phrase, " ")
    return text


def _extract_hazards(text: str) -> list[str]:
    return [name for name, terms in ACTIVE_HAZARD_TERMS.items() if _find_terms(text, terms)]


def _extract_assistance(text: str) -> list[str]:
    found: list[str] = []
    for category, terms in ASSISTANCE_MAP.items():
        hits = _find_terms(text, terms)
        if hits and any(l in text for l in REQUEST_LANGUAGE) or hits:
            # A concrete ask is recorded even without explicit request wording
            # (e.g. "fire in the kitchen" still maps to firefighting needs only
            # when request wording exists — handled below).
            if any(l in text for l in REQUEST_LANGUAGE):
                found.append(category)
    return found


def _extract_people_from_text(text: str) -> Optional[int]:
    """Best-effort extraction of a number of people mentioned in the text.

    Returns None when the report does not state a number. This value is only
    used to DETECT conflicts with the structured `people_affected` field —
    never to overwrite it.
    """
    import re

    words_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    match = re.search(r"(\d+)\s+(people|persons|men|women|children|kids|workers)", text)
    if match:
        return int(match.group(1))
    for word, value in words_to_num.items():
        if re.search(rf"\b{word}\s+(people|persons|of us|of them)\b", text):
            return value
    return None


def _assess_location(latitude: float, longitude: float) -> TriageLocation:
    """Record location exactly as reported, with a data-quality note."""
    note = None
    if latitude == 0.0 and longitude == 0.0:
        note = "Coordinates are (0,0) — location probably was not reported."
    return TriageLocation(
        latitude=latitude,
        longitude=longitude,
        source="reported_coordinates",
        note=note,
    )


def _evaluate_rules(
    text: str,
    people_affected: int,
    hazards: list[str],
) -> tuple[str, list[TriageCriterion], bool]:
    """Evaluate U1-U4 against extracted evidence.

    Returns (level, criteria, insufficient_evidence).
    """
    life_evidence = _find_terms(text, LIFE_THREAT_TERMS)
    time_evidence = _find_terms(_neutralize_non_urgent(text), TIME_CRITICAL_TERMS)
    injury_evidence = _find_terms(text, INJURY_ILLNESS_TERMS)
    damage_evidence = _find_terms(text, DAMAGE_TERMS)
    non_urgent_evidence = _find_terms(text, NON_URGENT_TERMS)

    active_hazard = bool(hazards)
    criteria: list[TriageCriterion] = []

    u1_matched = bool(life_evidence) or (active_hazard and people_affected >= 5)
    u1_evidence = list(life_evidence)
    if active_hazard and people_affected >= 5:
        u1_evidence.append(
            f"active hazard(s): {', '.join(hazards)} with {people_affected} people affected"
        )
    criteria.append(
        TriageCriterion(
            rule_id="U1",
            matched=u1_matched,
            description=URGENCY_RULES[0]["description"],
            evidence=u1_evidence,
        )
    )

    u2_evidence: list[str] = []
    if active_hazard:
        u2_evidence.append(f"hazard(s) present: {', '.join(hazards)}")
    if people_affected >= 5:
        u2_evidence.append(f"{people_affected} people affected")
    if time_evidence:
        u2_evidence.append(f"time-critical language: {', '.join(time_evidence)}")
    # U1 already implies a higher level, but the evidence is still recorded.
    u2_matched = (active_hazard or people_affected >= 5 or bool(time_evidence)) and not u1_matched
    criteria.append(
        TriageCriterion(
            rule_id="U2",
            matched=u2_matched,
            description=URGENCY_RULES[1]["description"],
            evidence=u2_evidence,
        )
    )

    has_concrete_need = bool(injury_evidence or damage_evidence)
    # Conservative default: a report with no evidence at all still lands on U3.
    no_evidence = not (
        life_evidence or active_hazard or time_evidence or injury_evidence
        or damage_evidence or non_urgent_evidence
    )
    u3_matched = (has_concrete_need and not u1_matched and not u2_matched) or no_evidence
    u3_evidence: list[str] = []
    if injury_evidence:
        u3_evidence.append(f"injury/illness evidence: {', '.join(injury_evidence)}")
    if damage_evidence:
        u3_evidence.append(f"damage evidence: {', '.join(damage_evidence)}")
    if no_evidence:
        u3_evidence.append(
            "no hazard, injury or time-critical evidence found — conservative default"
        )
    criteria.append(
        TriageCriterion(
            rule_id="U3",
            matched=u3_matched,
            description=URGENCY_RULES[2]["description"],
            evidence=u3_evidence,
        )
    )

    u4_matched = bool(non_urgent_evidence) and not (
        life_evidence or active_hazard or time_evidence or injury_evidence
    )
    criteria.append(
        TriageCriterion(
            rule_id="U4",
            matched=u4_matched,
            description=URGENCY_RULES[3]["description"],
            evidence=non_urgent_evidence,
        )
    )

    matched_levels = [
        rule["level"]
        for rule, crit in zip(URGENCY_RULES, criteria)
        if crit.matched
    ]
    if matched_levels:
        level = max(matched_levels, key=lambda lv: URGENCY_RANK[lv])
    else:  # pragma: no cover - U3 conservative default normally catches this
        level = CONSERVATIVE_LEVEL

    return level, criteria, no_evidence


def build_triage(incident: dict) -> TriageResult:
    """Build a deterministic triage result for an incident dict.

    Pure function of the stored incident — no network calls, no LLM.
    """
    text = (incident.get("description") or "").lower()
    people = incident.get("people_affected", 1)

    incident_type = _infer_incident_type(incident.get("description", ""))
    hazards = _extract_hazards(text)
    assistance = _extract_assistance(text)
    stated_people = _extract_people_from_text(text)

    level, criteria, insufficient = _evaluate_rules(text, people, hazards)

    missing: list[str] = []
    uncertain: list[str] = []

    if not hazards:
        missing.append("No hazard information provided in the report.")
    if not assistance:
        missing.append("Reporter did not state what assistance is needed.")
    if not _find_terms(text, TIME_CRITICAL_TERMS + LIFE_THREAT_TERMS):
        missing.append("Reporter did not state how time-critical the situation is.")

    location = _assess_location(
        float(incident.get("latitude", 0.0)), float(incident.get("longitude", 0.0))
    )
    if location.note:
        uncertain.append(location.note)
    if stated_people is not None and stated_people != people:
        uncertain.append(
            f"Report text mentions {stated_people} people but the structured field "
            f"says {people}. Using the structured field."
        )

    return TriageResult(
        incident_id=incident["incident_id"],
        incident_type=incident_type,
        urgency_level=level,
        urgency_score=URGENCY_SCORES[level],
        criteria=criteria,
        hazards=hazards,
        requested_assistance=assistance,
        people_affected=people,
        people_affected_stated_in_text=stated_people,
        location=location,
        missing_info=missing,
        uncertain=uncertain,
        insufficient_evidence=insufficient,
        source="rules",
        ai_summary=None,
        generated_at=_now_iso(),
        criteria_version=CRITERIA_VERSION,
    )


# ─── Optional LLM enrichment ────────────────────────────────────────────────


def _ai_interpret(incident: dict) -> Optional[str]:
    """Ask the existing Strands agent for a short interpretation of the report.

    Returns None when no model is configured, when the call fails, or when
    the response is empty. The result is advisory only: it never changes the
    rule-derived urgency level.
    """
    from agent.config import config

    if not config.has_api_key:
        return None

    try:
        from agent.rescuenet_agent import create_agent

        agent = create_agent(callback_handler=None)
        prompt = (
            "Read this emergency report and summarize, in at most 60 words: "
            "(1) what happened, (2) what hazards are present, (3) what help is "
            "being requested. Use ONLY facts stated in the report — if something "
            "is not stated, say 'not stated'. Do not invent people, locations, "
            "times or resources.\n\n"
            f"Report: {incident.get('description', '')}\n"
            f"People affected (structured field): {incident.get('people_affected')}"
        )
        result = agent(prompt)
        text = ""
        if hasattr(result, "message"):
            message = result.message
            if isinstance(message, dict) and "content" in message:
                for block in message["content"]:
                    if isinstance(block, dict) and "text" in block:
                        text = block["text"]
                        break
            if not text:
                text = str(message)
        else:
            text = str(result)
        text = text.strip()
        return text or None
    except Exception as exc:  # pragma: no cover - depends on live model access
        logger.warning("AI triage enrichment unavailable: %s", exc)
        return None


# ─── Persistence helpers ────────────────────────────────────────────────────


def _load_cached(incident_id: str) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT triage_json FROM incident_triage WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        return json.loads(row["triage_json"]) if row else None


def _save_cached(incident_id: str, triage: TriageResult) -> None:
    """Cache the enriched triage.

    Best effort: the cache must never break triage for an incident that is
    not (yet) stored, e.g. during tests or when triaging a draft report.
    """
    now = _now_iso()
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO incident_triage (incident_id, source, triage_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    source = excluded.source,
                    triage_json = excluded.triage_json,
                    updated_at = excluded.updated_at
                """,
                (incident_id, triage.source, triage.model_dump_json(), now, now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        logger.debug("Triage cache skipped for %s (incident not stored)", incident_id)


def get_triage(
    incident: dict,
    use_ai: bool = False,
    refresh_ai: bool = False,
) -> TriageResult:
    """Return the triage for an incident.

    The rule-based triage is always recomputed (it is cheap and must stay
    consistent with the stored report). Planning, matching and approval use
    this deterministic result.

    LLM interpretation is OPT-IN (`use_ai=True`, used by the triage endpoints)
    so safety-critical paths stay fast, reproducible and independent of model
    availability. Any previously cached AI enrichment is re-attached unless
    `refresh_ai` is set.
    """
    rules_triage = build_triage(incident)

    cached = _load_cached(incident["incident_id"])
    cached_ai = None
    if cached and cached.get("ai_summary"):
        cached_ai = cached.get("ai_summary")

    if use_ai and (refresh_ai or cached_ai is None):
        ai_summary = _ai_interpret(incident)
        if ai_summary:
            cached_ai = ai_summary

    if cached_ai:
        merged = rules_triage.model_copy(
            update={"ai_summary": cached_ai, "source": "rules+ai"}
        )
        _save_cached(incident["incident_id"], merged)
        return merged

    return rules_triage
