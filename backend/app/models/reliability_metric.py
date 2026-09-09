"""
Domain model: ReliabilityMetric

Pre-computed reliability statistics snapshots for a SimulatedResource
over a defined time window (DAILY, WEEKLY, or CUMULATIVE).

Computed by the Recovery Lambda on incident resolution and by a scheduled
aggregator. Stored in 'cloudpulse-metrics-{env}' DynamoDB table.

Design notes:
- Pure Pydantic — no AWS/DynamoDB imports here.
- PK = resource_id, SK = window_key (format: WINDOW_TYPE#YYYY-MM-DD)
- SK format enables lexicographic range queries (begins_with, between).
- mttr_seconds and mtbf_seconds are None when there is insufficient data.
- availability_pct is None until at least one incident window is closed.
- failure_type_counts maps FailureType string values to counts.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Enumerations ──────────────────────────────────────────────────────────────


class MetricWindowType(str, Enum):
    """
    The time window over which reliability metrics are aggregated.

    - DAILY      : Metrics for a single calendar day (UTC). SK: DAILY#YYYY-MM-DD
    - WEEKLY     : Metrics for a 7-day week starting on a Monday. SK: WEEKLY#YYYY-MM-DD
    - CUMULATIVE : All-time aggregate across the entire history. SK: CUMULATIVE#ALL
    """

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    CUMULATIVE = "CUMULATIVE"


# ── Window Key Helpers ────────────────────────────────────────────────────────

# Regex patterns for each window key format
_DAILY_PATTERN = re.compile(r"^DAILY#\d{4}-\d{2}-\d{2}$")
_WEEKLY_PATTERN = re.compile(r"^WEEKLY#\d{4}-\d{2}-\d{2}$")
_CUMULATIVE_PATTERN = re.compile(r"^CUMULATIVE#ALL$")


def build_window_key(window_type: MetricWindowType, date_str: str = "ALL") -> str:
    """
    Build a DynamoDB Sort Key for a metric snapshot.

    Args:
        window_type: The aggregation window (DAILY, WEEKLY, CUMULATIVE).
        date_str: ISO date string YYYY-MM-DD for DAILY/WEEKLY; 'ALL' for CUMULATIVE.

    Returns:
        e.g. 'DAILY#2026-09-08', 'WEEKLY#2026-09-07', 'CUMULATIVE#ALL'
    """
    if window_type == MetricWindowType.CUMULATIVE:
        return "CUMULATIVE#ALL"
    return f"{window_type.value}#{date_str}"


def parse_window_key(window_key: str) -> tuple[MetricWindowType, str]:
    """
    Parse a DynamoDB Sort Key back into (window_type, date_string).

    Returns:
        Tuple of (MetricWindowType, date_str) where date_str is 'ALL' for CUMULATIVE.

    Raises:
        ValueError: If the window_key format is not recognised.
    """
    if _CUMULATIVE_PATTERN.match(window_key):
        return MetricWindowType.CUMULATIVE, "ALL"
    if _DAILY_PATTERN.match(window_key):
        _, date_str = window_key.split("#", 1)
        return MetricWindowType.DAILY, date_str
    if _WEEKLY_PATTERN.match(window_key):
        _, date_str = window_key.split("#", 1)
        return MetricWindowType.WEEKLY, date_str
    raise ValueError(
        "Invalid window_key format. Expected DAILY#YYYY-MM-DD, "
        f"WEEKLY#YYYY-MM-DD, or CUMULATIVE#ALL. Got: {window_key!r}"
    )


# ── Domain Model: ReliabilityMetric ──────────────────────────────────────────


class ReliabilityMetric(BaseModel):
    """
    Pre-computed reliability statistics for one SimulatedResource over one window.

    DynamoDB Key:
    - PK: resource_id
    - SK: window_key  (e.g. 'DAILY#2026-09-08', 'CUMULATIVE#ALL')

    Validation rules:
    - resource_id: non-empty, uppercase-normalised, max 64 chars
    - window_key: must match DAILY#YYYY-MM-DD | WEEKLY#YYYY-MM-DD | CUMULATIVE#ALL
    - window_type must be consistent with window_key prefix
    - window_end must not precede window_start
    - total_incidents >= 0
    - resolved_incidents <= total_incidents
    - failed_recoveries <= total_incidents
    - resolved_incidents + failed_recoveries <= total_incidents
    - mttr_seconds >= 0 when present; None when resolved_incidents == 0
    - mtbf_seconds >= 0 when present; None when total_incidents < 2
    - availability_pct in [0.0, 100.0] when present
    - failure_type_counts values must be >= 0
    - sum(failure_type_counts.values()) <= total_incidents
    """

    # ── Identity / DynamoDB Keys ──────────────────────────────────────────────
    resource_id: str = Field(
        ...,
        description="ID of the SimulatedResource these metrics belong to (PK)",
        examples=["VM-001"],
    )
    window_key: str = Field(
        ...,
        description="DynamoDB Sort Key: DAILY#YYYY-MM-DD | WEEKLY#YYYY-MM-DD | CUMULATIVE#ALL",
        examples=["DAILY#2026-09-08", "WEEKLY#2026-09-07", "CUMULATIVE#ALL"],
    )

    # ── Window Definition ─────────────────────────────────────────────────────
    window_type: MetricWindowType = Field(
        ...,
        description="Aggregation window granularity",
    )
    window_start: datetime = Field(
        ...,
        description="Inclusive start of the window (UTC)",
    )
    window_end: datetime = Field(
        ...,
        description="Inclusive end of the window (UTC)",
    )

    # ── Incident Counts ───────────────────────────────────────────────────────
    total_incidents: int = Field(
        default=0,
        ge=0,
        description="Total incidents detected within this window",
    )
    resolved_incidents: int = Field(
        default=0,
        ge=0,
        description="Incidents that reached RESOLVED status within this window",
    )
    failed_recoveries: int = Field(
        default=0,
        ge=0,
        description="Incidents that reached ESCALATED status within this window",
    )

    # ── Reliability Statistics ────────────────────────────────────────────────
    mttr_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Mean Time To Recover (seconds). "
            "Average duration_seconds across RESOLVED incidents. "
            "None if no resolved incidents exist."
        ),
    )
    mtbf_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Mean Time Between Failures (seconds). "
            "Average time between consecutive incident detected_at timestamps. "
            "None if fewer than 2 incidents exist."
        ),
    )
    availability_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Estimated availability percentage. "
            "Computed as: (1 - total_downtime / window_duration) * 100. "
            "None until first incident window is closed."
        ),
    )

    # ── Breakdown ─────────────────────────────────────────────────────────────
    failure_type_counts: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Count of incidents per failure type within this window. "
            "Keys are FailureType string values, e.g. {'HIGH_CPU': 3, 'NETWORK_LATENCY': 1}"
        ),
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this snapshot was last computed",
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
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{0,63}", v):
            raise ValueError(
                f"resource_id may only contain uppercase letters, digits, and hyphens. Got: {v!r}"
            )
        return v

    @field_validator("window_key")
    @classmethod
    def validate_window_key(cls, v: str) -> str:
        v = v.strip()
        if not (
            _DAILY_PATTERN.match(v) or _WEEKLY_PATTERN.match(v) or _CUMULATIVE_PATTERN.match(v)
        ):
            raise ValueError(
                "window_key must match DAILY#YYYY-MM-DD, WEEKLY#YYYY-MM-DD, "
                f"or CUMULATIVE#ALL. Got: {v!r}"
            )
        return v

    @field_validator("failure_type_counts")
    @classmethod
    def validate_failure_type_counts(cls, v: dict[str, int]) -> dict[str, int]:
        for key, count in v.items():
            if not isinstance(key, str) or not key:
                raise ValueError("failure_type_counts keys must be non-empty strings")
            if not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"failure_type_counts values must be non-negative integers, "
                    f"got {key!r}: {count!r}"
                )
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> ReliabilityMetric:
        """Cross-field consistency rules enforced at the domain layer."""

        # window_end must not precede window_start
        if self.window_end < self.window_start:
            raise ValueError(
                "window_end must not precede window_start: "
                f"{self.window_end.isoformat()} < {self.window_start.isoformat()}"
            )

        # window_type must be consistent with window_key prefix
        key_prefix = self.window_key.split("#")[0]
        if key_prefix != self.window_type.value:
            raise ValueError(
                f"window_key prefix '{key_prefix}' is inconsistent with "
                f"window_type='{self.window_type.value}'"
            )

        # resolved + failed must not exceed total
        if self.resolved_incidents > self.total_incidents:
            raise ValueError(
                f"resolved_incidents ({self.resolved_incidents}) cannot exceed "
                f"total_incidents ({self.total_incidents})"
            )
        if self.failed_recoveries > self.total_incidents:
            raise ValueError(
                f"failed_recoveries ({self.failed_recoveries}) cannot exceed "
                f"total_incidents ({self.total_incidents})"
            )
        if self.resolved_incidents + self.failed_recoveries > self.total_incidents:
            raise ValueError(
                f"resolved_incidents + failed_recoveries "
                f"({self.resolved_incidents + self.failed_recoveries}) cannot exceed "
                f"total_incidents ({self.total_incidents})"
            )

        # mttr_seconds must be None when there are no resolved incidents
        if self.resolved_incidents == 0 and self.mttr_seconds is not None:
            raise ValueError("mttr_seconds must be None when resolved_incidents == 0")

        # mtbf_seconds must be None when fewer than 2 incidents
        if self.total_incidents < 2 and self.mtbf_seconds is not None:
            raise ValueError("mtbf_seconds must be None when total_incidents < 2")

        # failure_type_counts sum must not exceed total_incidents
        counts_sum = sum(self.failure_type_counts.values())
        if counts_sum > self.total_incidents:
            raise ValueError(
                f"sum(failure_type_counts) ({counts_sum}) cannot exceed "
                f"total_incidents ({self.total_incidents})"
            )

        return self

    # ── Domain Methods ────────────────────────────────────────────────────────

    def recovery_success_rate(self) -> float | None:
        """
        Fraction of incidents that were successfully resolved.

        Returns None if no incidents have concluded (all still open).
        """
        concluded = self.resolved_incidents + self.failed_recoveries
        if concluded == 0:
            return None
        return self.resolved_incidents / concluded

    def dominant_failure_type(self) -> str | None:
        """
        Return the failure type with the highest incident count.

        Returns None if no incidents were recorded.
        """
        if not self.failure_type_counts:
            return None
        return max(self.failure_type_counts, key=lambda k: self.failure_type_counts[k])

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Serialise to a DynamoDB-safe dict (excludes None and converts floats to Decimal)."""
        data = self.model_dump(mode="json")
        cleaned = {k: v for k, v in data.items() if v is not None}
        return cast(dict[str, Any], _floats_to_decimals(cleaned))

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> ReliabilityMetric:
        """Deserialise from a DynamoDB item dict (handles Decimal conversion)."""
        return cls.model_validate(_convert_decimals(item))


# ── API Response Models ───────────────────────────────────────────────────────


class ReliabilityMetricSummary(BaseModel):
    """
    Lightweight projection of a ReliabilityMetric for dashboard responses.

    Returns only the key KPIs needed for the reliability stats panel.
    """

    resource_id: str
    window_type: MetricWindowType
    window_key: str
    window_start: datetime
    window_end: datetime
    total_incidents: int
    resolved_incidents: int
    failed_recoveries: int
    mttr_seconds: float | None
    mtbf_seconds: float | None
    availability_pct: float | None
    computed_at: datetime


# ── Internal Helpers ──────────────────────────────────────────────────────────


def _convert_decimals(obj: Any) -> Any:
    """Recursively convert DynamoDB Decimal values to int or float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    return obj


def _floats_to_decimals(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB serialization."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimals(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_floats_to_decimals(i) for i in obj if i is not None]
    return obj
