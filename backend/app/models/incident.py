"""
Domain models for incidents.
"""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.resource import FailureType, ResourceState


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    RECOVERING = "RECOVERING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class Incident(BaseModel):
    """An incident record created when a virtual resource fails."""

    incident_id: str = Field(..., description="UUID v4")
    resource_id: str
    failure_type: FailureType
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    state_at_detection: ResourceState
    state_at_resolution: ResourceState | None = None
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    recovery_initiated_at: datetime | None = None
    resolved_at: datetime | None = None
    recovery_attempts: int = 0
    recovery_notes: list[str] = Field(default_factory=list)
    notification_sent: bool = False


class IncidentSummary(BaseModel):
    """Lightweight incident for list responses."""

    incident_id: str
    resource_id: str
    failure_type: FailureType
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: datetime
    resolved_at: datetime | None
