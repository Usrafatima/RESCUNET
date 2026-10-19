"""
Pydantic models for RescuNet response plans.

Response plans are created when a human approves an AI recommendation.
They link an incident to an assigned resource with distance and status.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResponsePlanStatus(str, Enum):
    """Status of a response plan."""

    created = "created"
    resource_assigned = "resource_assigned"
    dispatch_ready = "dispatch_ready"
    dispatched = "dispatched"
    completed = "completed"
    cancelled = "cancelled"


class ApprovalRequest(BaseModel):
    """Request body for approving an AI recommendation."""

    resource_id: str = Field(
        ..., description="ID of the recommended resource (e.g. RES-001)"
    )
    distance_km: float = Field(
        ..., ge=0, description="Calculated distance from incident to resource"
    )
    reason: str = Field(
        ..., min_length=1, description="Reason for selecting this resource"
    )
    approver: Optional[str] = Field(
        default=None,
        max_length=80,
        description="Authorized human decision maker (recorded in the audit trail)",
    )
    plan_id: Optional[str] = Field(
        default=None,
        description="Optional rescue-plan proposal id this approval refers to",
    )


class ResponsePlanResource(BaseModel):
    """Resource information in the response plan."""

    id: str = Field(description="Resource ID")
    name: str = Field(description="Resource name")
    type: str = Field(description="Resource type")
    status: str = Field(default="available", description="Resource deployment status")


class ApprovalResponse(BaseModel):
    """Response body for a successful approval."""

    incident_id: str = Field(description="Incident ID")
    status: str = Field(description="Response plan status")
    resource: ResponsePlanResource = Field(description="Assigned resource")
    distance_km: float = Field(description="Distance to incident")
    message: str = Field(description="Status message")
    real_world_dispatch: bool = Field(
        default=False,
        description="Whether a real dispatch was performed (always false)",
    )


class ResponsePlan(BaseModel):
    """Full response plan record."""

    plan_id: str
    incident_id: str
    resource_id: str
    resource_name: str
    resource_type: str
    distance_km: float
    reason: str
    status: ResponsePlanStatus
    approved_at: str
    created_at: str
