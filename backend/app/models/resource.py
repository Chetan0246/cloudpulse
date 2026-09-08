"""
Domain models for virtual resources.

These are pure Pydantic models with no AWS or database dependencies.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class ResourceType(str, Enum):
    VM = "VM"
    API = "API"
    DB = "DB"
    STORAGE = "STORAGE"


class ResourceState(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    RECOVERY_INITIATED = "RECOVERY_INITIATED"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RECOVERED = "RECOVERED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class FailureType(str, Enum):
    HIGH_CPU = "HIGH_CPU"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    STORAGE_EXHAUSTION = "STORAGE_EXHAUSTION"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    SERVICE_DOWNTIME = "SERVICE_DOWNTIME"


# ── Thresholds ────────────────────────────────────────────────────────────────
CPU_WARNING_THRESHOLD = 75.0
CPU_FAILURE_THRESHOLD = 85.0
MEMORY_WARNING_THRESHOLD = 75.0
MEMORY_FAILURE_THRESHOLD = 85.0
STORAGE_WARNING_THRESHOLD = 80.0
STORAGE_FAILURE_THRESHOLD = 90.0
NETWORK_LATENCY_WARNING_MS = 300.0
NETWORK_LATENCY_FAILURE_MS = 500.0


class Resource(BaseModel):
    """A virtual resource tracked by CloudPulse."""

    resource_id: str = Field(..., description="Unique resource identifier, e.g. VM-001")
    resource_type: ResourceType
    current_state: ResourceState = ResourceState.HEALTHY
    cpu_utilization: Annotated[float, Field(ge=0.0, le=100.0)] = 0.0
    memory_utilization: Annotated[float, Field(ge=0.0, le=100.0)] = 0.0
    storage_utilization: Annotated[float, Field(ge=0.0, le=100.0)] = 0.0
    network_latency_ms: Annotated[float, Field(ge=0.0)] = 0.0
    last_heartbeat: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    health_status: HealthStatus = HealthStatus.HEALTHY
    active_failure_type: FailureType | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("resource_id must not be empty")
        return v.upper()

    def compute_health_status(self) -> HealthStatus:
        """Derive health status from current metric values."""
        if (
            self.cpu_utilization >= CPU_FAILURE_THRESHOLD
            or self.memory_utilization >= MEMORY_FAILURE_THRESHOLD
            or self.storage_utilization >= STORAGE_FAILURE_THRESHOLD
            or self.network_latency_ms >= NETWORK_LATENCY_FAILURE_MS
        ):
            return HealthStatus.CRITICAL
        if (
            self.cpu_utilization >= CPU_WARNING_THRESHOLD
            or self.memory_utilization >= MEMORY_WARNING_THRESHOLD
            or self.storage_utilization >= STORAGE_WARNING_THRESHOLD
            or self.network_latency_ms >= NETWORK_LATENCY_WARNING_MS
        ):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


class ResourceSummary(BaseModel):
    """Lightweight resource representation for list responses."""

    resource_id: str
    resource_type: ResourceType
    current_state: ResourceState
    health_status: HealthStatus
    active_failure_type: FailureType | None
    last_heartbeat: datetime
