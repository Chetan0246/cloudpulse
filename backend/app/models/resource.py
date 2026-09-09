"""
Domain model: SimulatedResource

Represents a virtual cloud resource tracked by CloudPulse.
This model is the authoritative definition of what a "resource" is — its
identity, live metrics, state, and health status.

Design notes:
- Pure Pydantic — no AWS/DynamoDB imports here.
- DynamoDB stores numbers as Decimal; the repository converts to float.
- All timestamps are UTC-aware datetime objects; serialized as ISO8601 strings.
- resource_id is normalised to UPPERCASE on creation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Enumerations ──────────────────────────────────────────────────────────────


class ResourceType(str, Enum):
    """The category of virtual resource being simulated."""

    VM = "VM"
    API = "API"
    DB = "DB"
    STORAGE = "STORAGE"


class ResourceState(str, Enum):
    """
    Lifecycle state of a virtual resource.

    Valid transitions (enforced by the domain layer, not DynamoDB):

        HEALTHY ──────────────► WARNING ──────────────► FAILURE_DETECTED
            ▲                      │                           │
            │                      │ (auto-recovery)           ▼
            │                      └──────────────► RECOVERY_INITIATED
            │                                              │
            │                                              ▼
            │                                   RECOVERY_IN_PROGRESS
            │                                        │         │
            │                                   SUCCESS      FAILURE
            │                                        │         │
            └───────────────────────── RECOVERED     ▼
                                              RECOVERY_FAILED
                                                      │
                                                      ▼
                                       MANUAL_INTERVENTION_REQUIRED
    """

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    RECOVERY_INITIATED = "RECOVERY_INITIATED"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RECOVERED = "RECOVERED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"

    # ── State machine helpers ────────────────────────────────────────────────

    def is_terminal(self) -> bool:
        """True if no further automatic transitions are possible."""
        return self in {
            ResourceState.RECOVERED,
            ResourceState.MANUAL_INTERVENTION_REQUIRED,
        }

    def is_in_recovery(self) -> bool:
        """True while a recovery workflow is active."""
        return self in {
            ResourceState.RECOVERY_INITIATED,
            ResourceState.RECOVERY_IN_PROGRESS,
        }

    def can_transition_to(self, target: ResourceState) -> bool:
        """Check whether a state transition is allowed."""
        allowed: dict[ResourceState, set[ResourceState]] = {
            ResourceState.HEALTHY: {
                ResourceState.WARNING,
                ResourceState.FAILURE_DETECTED,  # Direct injection bypass
            },
            ResourceState.WARNING: {
                ResourceState.HEALTHY,
                ResourceState.FAILURE_DETECTED,
            },
            ResourceState.FAILURE_DETECTED: {
                ResourceState.RECOVERY_INITIATED,
            },
            ResourceState.RECOVERY_INITIATED: {
                ResourceState.RECOVERY_IN_PROGRESS,
                ResourceState.RECOVERY_FAILED,
            },
            ResourceState.RECOVERY_IN_PROGRESS: {
                ResourceState.RECOVERED,
                ResourceState.RECOVERY_FAILED,
            },
            ResourceState.RECOVERED: {
                ResourceState.HEALTHY,
            },
            ResourceState.RECOVERY_FAILED: {
                ResourceState.MANUAL_INTERVENTION_REQUIRED,
                ResourceState.RECOVERY_INITIATED,  # Retry allowed
            },
            ResourceState.MANUAL_INTERVENTION_REQUIRED: {
                ResourceState.HEALTHY,  # Manual reset via API
            },
        }
        return target in allowed.get(self, set())


class HealthStatus(str, Enum):
    """Computed health status derived from metric thresholds."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class FailureType(str, Enum):
    """Category of failure being simulated."""

    HIGH_CPU = "HIGH_CPU"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    STORAGE_EXHAUSTION = "STORAGE_EXHAUSTION"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    SERVICE_DOWNTIME = "SERVICE_DOWNTIME"

    def default_severity(self) -> str:
        """Return the default IncidentSeverity string for this failure type."""
        severity_map = {
            FailureType.HIGH_CPU: "HIGH",
            FailureType.SERVICE_FAILURE: "CRITICAL",
            FailureType.STORAGE_EXHAUSTION: "MEDIUM",
            FailureType.NETWORK_LATENCY: "MEDIUM",
            FailureType.SERVICE_DOWNTIME: "CRITICAL",
        }
        return severity_map[self]


# ── Metric Thresholds ─────────────────────────────────────────────────────────

CPU_NOMINAL_MAX = 70.0  # Normal operating ceiling
CPU_WARNING_THRESHOLD = 75.0
CPU_FAILURE_THRESHOLD = 85.0

MEMORY_NOMINAL_MAX = 70.0
MEMORY_WARNING_THRESHOLD = 75.0
MEMORY_FAILURE_THRESHOLD = 85.0

STORAGE_NOMINAL_MAX = 75.0
STORAGE_WARNING_THRESHOLD = 80.0
STORAGE_FAILURE_THRESHOLD = 90.0

NETWORK_LATENCY_NOMINAL_MAX_MS = 200.0
NETWORK_LATENCY_WARNING_MS = 300.0
NETWORK_LATENCY_FAILURE_MS = 500.0

# Failure-injection target values (spike to just above failure threshold)
FAILURE_METRIC_TARGETS: dict[FailureType, dict[str, float]] = {
    FailureType.HIGH_CPU: {
        "cpu_utilization": 92.0,
        "memory_utilization": 60.0,
        "storage_utilization": 20.0,
        "network_latency_ms": 50.0,
    },
    FailureType.SERVICE_FAILURE: {
        "cpu_utilization": 15.0,
        "memory_utilization": 20.0,
        "storage_utilization": 10.0,
        "network_latency_ms": 980.0,  # Latency spikes → service unreachable
    },
    FailureType.STORAGE_EXHAUSTION: {
        "cpu_utilization": 30.0,
        "memory_utilization": 40.0,
        "storage_utilization": 96.0,
        "network_latency_ms": 50.0,
    },
    FailureType.NETWORK_LATENCY: {
        "cpu_utilization": 20.0,
        "memory_utilization": 25.0,
        "storage_utilization": 15.0,
        "network_latency_ms": 750.0,
    },
    FailureType.SERVICE_DOWNTIME: {
        "cpu_utilization": 0.0,
        "memory_utilization": 0.0,
        "storage_utilization": 10.0,
        "network_latency_ms": 9999.0,  # Unreachable
    },
}


# ── Domain Model ──────────────────────────────────────────────────────────────


class SimulatedResource(BaseModel):
    """
    A virtual cloud resource tracked by CloudPulse.

    Validation rules:
    - resource_id: non-empty, uppercase-normalised, format "{TYPE}-{NUMBER}"
      e.g. VM-001, API-001, DB-001, STORAGE-001
    - Metric values: 0.0 ≤ x ≤ 100.0 for utilisation metrics
    - network_latency_ms: 0.0 ≤ x ≤ 99999.0
    - updated_at must not precede created_at
    - active_failure_type must be None when current_state is HEALTHY or WARNING
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    resource_id: str = Field(
        ...,
        description="Unique resource identifier, e.g. 'VM-001'",
        examples=["VM-001", "API-001", "DB-001", "STORAGE-001"],
    )
    resource_type: ResourceType = Field(
        ...,
        description="Category of simulated resource",
    )
    description: str = Field(
        default="",
        description="Human-readable resource description",
        max_length=500,
    )

    # ── State ─────────────────────────────────────────────────────────────────
    current_state: ResourceState = Field(
        default=ResourceState.HEALTHY,
        description="Current lifecycle state",
    )
    health_status: HealthStatus = Field(
        default=HealthStatus.HEALTHY,
        description="Computed health status based on metric thresholds",
    )
    active_failure_type: FailureType | None = Field(
        default=None,
        description="The active failure type when in a failure state",
    )

    # ── Metrics ───────────────────────────────────────────────────────────────
    cpu_utilization: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="CPU utilization percentage",
    )
    memory_utilization: float = Field(
        default=30.0,
        ge=0.0,
        le=100.0,
        description="Memory utilization percentage",
    )
    storage_utilization: float = Field(
        default=20.0,
        ge=0.0,
        le=100.0,
        description="Storage utilization percentage",
    )
    network_latency_ms: float = Field(
        default=15.0,
        ge=0.0,
        le=99999.0,
        description="Network latency in milliseconds",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the resource was first registered",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the resource was last modified",
    )
    last_heartbeat: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of last simulator heartbeat",
    )

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata tags",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("resource_id must not be empty")
        if len(v) > 64:
            raise ValueError("resource_id must not exceed 64 characters")
        # Allowed characters: alphanumeric and hyphens (re imported at module level — A-09)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{0,63}", v):
            raise ValueError(
                "resource_id may only contain uppercase letters, digits, and hyphens, "
                f"and must start with a letter or digit. Got: {v!r}"
            )
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def validate_consistency(self) -> SimulatedResource:
        """Cross-field consistency rules."""
        # active_failure_type must be None when state is healthy/warning
        if self.current_state in {ResourceState.HEALTHY, ResourceState.WARNING}:
            if self.active_failure_type is not None:
                raise ValueError(
                    f"active_failure_type must be None when state is "
                    f"{self.current_state.value}, got {self.active_failure_type.value}"
                )
        return self

    # ── Domain Methods ────────────────────────────────────────────────────────

    def compute_health_status(self) -> HealthStatus:
        """
        Compute health status from current metric values.

        Does NOT mutate self — returns the computed value only.
        The repository or service layer must apply this if auto-sync is needed.
        """
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

    def apply_failure_metrics(self, failure_type: FailureType) -> SimulatedResource:
        """Return a copy of this resource with failure-level metrics applied."""
        targets = FAILURE_METRIC_TARGETS[failure_type]
        return self.model_copy(
            update={
                **targets,
                "active_failure_type": failure_type,
                "current_state": ResourceState.FAILURE_DETECTED,
                "health_status": HealthStatus.CRITICAL,
                "updated_at": datetime.now(UTC),
            }
        )

    def reset_to_healthy(self) -> SimulatedResource:
        """Return a copy of this resource with nominal healthy metrics."""
        return self.model_copy(
            update={
                "cpu_utilization": 25.0,
                "memory_utilization": 30.0,
                "storage_utilization": 20.0,
                "network_latency_ms": 15.0,
                "current_state": ResourceState.HEALTHY,
                "health_status": HealthStatus.HEALTHY,
                "active_failure_type": None,
                "updated_at": datetime.now(UTC),
                "last_heartbeat": datetime.now(UTC),
            }
        )

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialize to a DynamoDB-safe dict (excludes None and converts floats to Decimal)."""
        data = self.model_dump(mode="json")
        cleaned = {k: v for k, v in data.items() if v is not None}
        return cast(dict[str, Any], _floats_to_decimals(cleaned))

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> SimulatedResource:
        """Deserialize from a DynamoDB item dict (handles Decimal → float)."""
        from decimal import Decimal

        def convert(v: Any) -> Any:
            if isinstance(v, Decimal):
                return float(v)
            if isinstance(v, dict):
                return {k2: convert(v2) for k2, v2 in v.items()}
            if isinstance(v, list):
                return [convert(i) for i in v]
            return v

        converted = {k: convert(v) for k, v in item.items()}
        return cls.model_validate(converted)


def _floats_to_decimals(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB serialization."""
    from decimal import Decimal

    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimals(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_floats_to_decimals(i) for i in obj if i is not None]
    return obj


# ── API Response Models ───────────────────────────────────────────────────────


class ResourceSummary(BaseModel):
    """Lightweight projection of SimulatedResource for list API responses."""

    resource_id: str
    resource_type: ResourceType
    current_state: ResourceState
    health_status: HealthStatus
    active_failure_type: FailureType | None
    last_heartbeat: datetime
    cpu_utilization: float
    memory_utilization: float
    storage_utilization: float
    network_latency_ms: float


# ── Backward compat alias ─────────────────────────────────────────────────────
# Keep the old name "Resource" available to avoid breaking existing imports
# in lambda handlers and tests during incremental migration.
Resource = SimulatedResource
