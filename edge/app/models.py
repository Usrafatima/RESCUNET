"""
Pydantic models for RescuNet Edge Gateway.

Defines request/response schemas for the edge ingestion, queue, and connectivity APIs.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    """Synchronization states for an edge packet."""

    queued = "queued"
    syncing = "syncing"
    synced = "synced"
    failed = "failed"


class EdgePacketCreate(BaseModel):
    """Request body for submitting a local SOS packet."""

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


class EdgePacketResponse(BaseModel):
    """Response after storing an edge packet."""

    packet_id: str = Field(..., description="Unique edge packet identifier")
    status: SyncStatus = Field(..., description="Current sync status")
    message: str = Field(..., description="Human-readable status message")


class EdgePacketDetail(BaseModel):
    """Full detail of an edge packet for queue inspection."""

    packet_id: str
    description: str
    people_affected: int
    latitude: float
    longitude: float
    created_at: str
    status: SyncStatus
    attempt_count: int
    last_error: Optional[str] = None
    synced_at: Optional[str] = None
    incident_id: Optional[str] = None


class ConnectivityResponse(BaseModel):
    """Response for the connectivity status endpoint."""

    online: bool
    mode: str = Field(..., description="OFFLINE or ONLINE")
    queued_packets: int = Field(..., description="Number of packets waiting to sync")


class ConnectivityUpdate(BaseModel):
    """Request body to toggle connectivity state."""

    online: bool
