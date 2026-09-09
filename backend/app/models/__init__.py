"""
CloudPulse domain models.

All entities are pure Pydantic models — no AWS SDK dependencies.

Exports:
    SimulatedResource  — virtual cloud resource (PK: resource_id)
    Incident           — failure incident record (PK: incident_id)
    RecoveryAction     — embedded recovery step (within Incident)
    ReliabilityMetric  — pre-aggregated statistics (PK: resource_id, SK: window_key)
"""

from app.models.incident import (
    MAX_RECOVERY_ACTIONS,
    Incident,
    IncidentDetail,
    IncidentSeverity,
    IncidentStatus,
    IncidentSummary,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.reliability_metric import (
    MetricWindowType,
    ReliabilityMetric,
    ReliabilityMetricSummary,
    build_window_key,
    parse_window_key,
)
from app.models.resource import (
    FailureType,
    HealthStatus,
    Resource,
    ResourceState,
    ResourceSummary,
    ResourceType,
    SimulatedResource,
)

__all__ = [
    # Resource
    "SimulatedResource",
    "Resource",
    "ResourceType",
    "ResourceState",
    "HealthStatus",
    "FailureType",
    "ResourceSummary",
    # Incident
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentSummary",
    "IncidentDetail",
    "MAX_RECOVERY_ACTIONS",
    # RecoveryAction
    "RecoveryAction",
    "RecoveryActionType",
    "RecoveryActionStatus",
    # ReliabilityMetric
    "ReliabilityMetric",
    "MetricWindowType",
    "ReliabilityMetricSummary",
    "build_window_key",
    "parse_window_key",
]
