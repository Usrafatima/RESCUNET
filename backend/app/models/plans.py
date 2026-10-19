"""
Pydantic models for RescuNet Adaptive Rescue Planning.

Covers:
- Route / corridor records and their restriction status
- Emergency triage results (documented urgency criteria)
- Resource-matching candidates with explanations
- Versioned rescue plans (proposed → pending approval → approved)
- Replanning reports (what changed, what was revised, what is unresolved)

All safety-critical values (urgency, feasibility) are produced by
deterministic rules in the service layer; the LLM may only enrich the
interpretation of free-text reports when it is configured.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Routes / corridors ──────────────────────────────────────────────────────


class RouteStatus(str, Enum):
    open = "open"
    closed = "closed"


class RouteCreate(BaseModel):
    """Request body for creating a route/corridor record."""

    name: str = Field(..., min_length=1, max_length=120)
    from_lat: float = Field(..., ge=-90, le=90)
    from_lng: float = Field(..., ge=-180, le=180)
    to_lat: float = Field(..., ge=-90, le=90)
    to_lng: float = Field(..., ge=-180, le=180)
    status: RouteStatus = Field(default=RouteStatus.open)
    restriction_reason: Optional[str] = Field(
        default=None, description="Why the route is restricted, when closed"
    )
    scope_resource_id: Optional[str] = Field(
        default=None,
        description=(
            "If set, this restriction only affects this specific resource "
            "(its dedicated access route). If null it is a general corridor: "
            "it blocks any assignment whose direct path crosses it."
        ),
    )


class RouteUpdate(BaseModel):
    """Request body for updating a route's restriction state."""

    status: RouteStatus = Field(..., description="New route status (open/closed)")
    restriction_reason: Optional[str] = Field(
        default=None, description="Why the route became restricted"
    )
    actor: Optional[str] = Field(default=None, description="Who changed the status")


class RouteInfo(BaseModel):
    """A route/corridor with its current restriction status."""

    route_id: str
    name: str
    status: RouteStatus
    restriction_reason: Optional[str] = None
    scope_resource_id: Optional[str] = None
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    updated_at: str


class RouteStatusResponse(BaseModel):
    """Response after creating or updating a route."""

    route: RouteInfo
    message: str
    affected_assignments: list[str] = Field(
        default_factory=list,
        description="Incidents whose current assignment is affected by this change",
    )
    plans_proposed: list[str] = Field(
        default_factory=list,
        description="New plan proposal IDs created because of this change",
    )


# ─── Triage ──────────────────────────────────────────────────────────────────


class TriageCriterion(BaseModel):
    """A single documented urgency criterion that fired (or did not fire)."""

    rule_id: str = Field(description="Stable rule identifier, e.g. U1")
    matched: bool = Field(description="Whether this rule fired for the incident")
    description: str = Field(description="Plain-language statement of the criterion")
    evidence: list[str] = Field(
        default_factory=list,
        description="Exact evidence found in the report that made the rule fire",
    )


class TriageLocation(BaseModel):
    """Location as reported — never invented."""

    latitude: float
    longitude: float
    source: str = Field(
        default="reported_coordinates",
        description="Where the coordinates came from (reported / unknown)",
    )
    note: Optional[str] = Field(
        default=None,
        description="Data-quality note, e.g. coordinates look like a default value",
    )


class TriageResult(BaseModel):
    """Deterministic emergency triage for one incident."""

    incident_id: str
    incident_type: str = Field(description="Classified incident type")
    urgency_level: str = Field(
        description="critical | high | medium | low — assigned by documented rules"
    )
    urgency_score: int = Field(
        ge=0, le=100, description="Deterministic 0-100 urgency score"
    )
    criteria: list[TriageCriterion] = Field(
        description="All evaluated criteria with their evidence"
    )
    hazards: list[str] = Field(default_factory=list, description="Detected hazards")
    requested_assistance: list[str] = Field(
        default_factory=list, description="Assistance the reporter asked for"
    )
    people_affected: int
    people_affected_stated_in_text: Optional[int] = Field(
        default=None,
        description="Number mentioned in the free text, if any (flagged on mismatch)",
    )
    location: TriageLocation
    missing_info: list[str] = Field(
        default_factory=list, description="Information that was not provided"
    )
    uncertain: list[str] = Field(
        default_factory=list, description="Information that is ambiguous or conflicting"
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="True when no urgency rule matched; a conservative level is used",
    )
    source: str = Field(
        default="rules",
        description="'rules' or 'rules+ai' (AI only ever adds interpretation)",
    )
    ai_summary: Optional[str] = Field(
        default=None,
        description="LLM interpretation of the free-text report, when configured",
    )
    generated_at: str
    criteria_version: str = Field(
        default="U1-U4/v1", description="Version of the documented criteria set"
    )


# ─── Resource matching ───────────────────────────────────────────────────────


class MatchCandidate(BaseModel):
    """A resource considered for an assignment, with its reasoning."""

    resource_id: str
    name: str
    type: str
    status: str
    distance_km: float
    match_score: float
    feasible: bool = Field(
        description="True when every hard constraint is satisfied"
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Why this candidate is (or is not) suitable",
    )
    blockers: list[str] = Field(
        default_factory=list, description="Hard-constraint violations, if any"
    )
    max_people: int = 0
    assigned_incident_id: Optional[str] = None


class MatchResult(BaseModel):
    """Outcome of resource matching for one incident."""

    incident_id: str
    incident_type: str
    required_capabilities: list[str] = Field(default_factory=list)
    candidates: list[MatchCandidate] = Field(default_factory=list)
    best: Optional[MatchCandidate] = None
    requires_human_review: bool = Field(
        default=False,
        description="True when no safe automatic assignment can be made",
    )
    review_reasons: list[str] = Field(
        default_factory=list, description="Why human review is required"
    )
    shortages: list[str] = Field(
        default_factory=list, description="Resource shortages discovered while matching"
    )
    generated_at: str


# ─── Rescue plans ────────────────────────────────────────────────────────────


class PlanStatus(str, Enum):
    proposed = "proposed"          # generated, not yet reviewed
    pending_approval = "pending_approval"  # shown to a human for a decision
    approved = "approved"          # human approved → assignment created
    rejected = "rejected"          # human rejected
    superseded = "superseded"      # replaced by a newer plan
    stale = "stale"                # underlying conditions changed; must not be approved


class PlanTrigger(str, Enum):
    initial = "initial"
    route_closed = "route_closed"
    resource_unavailable = "resource_unavailable"
    resource_unsuitable = "resource_unsuitable"
    new_high_urgency = "new_high_urgency"
    incident_changed = "incident_changed"
    manual = "manual"


class PlanAssignmentView(BaseModel):
    """Human-readable view of what a plan assigns."""

    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    resource_type: Optional[str] = None
    distance_km: Optional[float] = None
    match_score: Optional[float] = None
    requires_human_review: bool = False


class RescuePlan(BaseModel):
    """A versioned rescue plan for one incident."""

    plan_id: str
    incident_id: str
    version: int
    status: PlanStatus
    trigger: PlanTrigger
    trigger_detail: Optional[str] = None
    previous_plan_id: Optional[str] = None
    assignment: PlanAssignmentView
    rationale: str = Field(
        description="What changed and why this recommendation was made"
    )
    alternatives: list[MatchCandidate] = Field(
        default_factory=list,
        description="Other feasible candidates that were not selected",
    )
    shortages: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    triage: Optional[TriageResult] = None
    match: Optional[MatchResult] = None
    created_by: str
    created_at: str
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


class PlanCreateRequest(BaseModel):
    """Request body for generating a rescue plan proposal."""

    trigger: PlanTrigger = Field(default=PlanTrigger.manual)
    actor: Optional[str] = Field(default=None)


class PlanDecisionRequest(BaseModel):
    """Request body for approving or rejecting a rescue plan proposal."""

    approver: str = Field(
        ..., min_length=1, max_length=80, description="Authorized human decision maker"
    )
    decision_reason: Optional[str] = Field(
        default=None, max_length=500, description="Why this decision was made"
    )


class PlanListResponse(BaseModel):
    """Response for plan listings."""

    plans: list[RescuePlan]
    total: int


# ─── Replanning ──────────────────────────────────────────────────────────────


class DetectedChange(BaseModel):
    """A difference between a plan's recorded context and current reality."""

    incident_id: str
    plan_id: str
    trigger: PlanTrigger
    field: str = Field(description="Which context field changed")
    previous: Optional[str] = None
    current: Optional[str] = None
    detail: str = Field(description="Plain-language description of the change")


class ReplanReport(BaseModel):
    """Result of evaluating replanning triggers across active assignments."""

    changes: list[DetectedChange] = Field(default_factory=list)
    plans_proposed: list[str] = Field(
        default_factory=list, description="New plan IDs created by this evaluation"
    )
    stale_plans: list[str] = Field(
        default_factory=list, description="Open proposals invalidated by this evaluation"
    )
    unresolved_incidents: list[str] = Field(
        default_factory=list,
        description="Active incidents with no feasible assignment (shortage)",
    )
    evaluated_assignments: int = 0
    message: str
    generated_at: str
