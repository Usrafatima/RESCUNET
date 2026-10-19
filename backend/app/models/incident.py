"""
Pydantic models for RescuNet incident API.

These models define request/response schemas and are used by FastAPI
for automatic documentation and validation.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    """Allowed statuses for an incident lifecycle."""

    queued = "queued"
    processing = "processing"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    dispatched = "dispatched"
    resolved = "resolved"
    cancelled = "cancelled"


class IncidentCreate(BaseModel):
    """Request body for creating a new incident."""

    description: str = Field(
        ..., min_length=1, description="Description of the emergency situation"
    )
    people_affected: int = Field(
        ..., ge=1, description="Number of people affected by this incident"
    )
    latitude: float = Field(
        ..., ge=-90, le=90, description="Latitude coordinate of the incident"
    )
    longitude: float = Field(
        ..., ge=-180, le=180, description="Longitude coordinate of the incident"
    )
    packet_id: str | None = Field(
        default=None,
        description="Edge gateway packet ID for idempotent sync (e.g. EDGE-000001)",
    )
    auto_plan: bool = Field(
        default=False,
        description=(
            "When true, a high-urgency report also produces a rescue-plan "
            "proposal on arrival (trigger: new_high_urgency). Proposals always "
            "require human approval."
        ),
    )


class IncidentUpdate(BaseModel):
    """Request body for updating an incident's status."""

    status: IncidentStatus = Field(..., description="New status for the incident")


class IncidentResponse(BaseModel):
    """Response body representing an incident."""

    incident_id: str = Field(..., description="Unique incident identifier (e.g. RSN-000001)")
    description: str
    people_affected: int
    latitude: float
    longitude: float
    status: IncidentStatus
    packet_id: str | None = Field(default=None, description="Edge gateway packet ID if synced from edge")
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    """Response body for the health endpoint."""

    status: str
    service: str
