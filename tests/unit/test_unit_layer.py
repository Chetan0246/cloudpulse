"""
Layer 1: Unit Tests
Tests domain models, enums, validation, serialization, and mathematical metric calculations.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.reliability_metric import (
    MetricWindowType,
    ReliabilityMetric,
    parse_window_key,
)
from app.models.resource import (
    FAILURE_METRIC_TARGETS,
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)
from app.services.monitoring_service import compute_service_health


class TestDomainModelsUnit:
    """Unit tests for core CloudPulse domain models."""

    def test_resource_model_nominal_validation(self):
        """SimulatedResource initializes with correct defaults and uppercase ID."""
        res = SimulatedResource(
            resource_id="vm-001",
            resource_type=ResourceType.VM,
            current_state=ResourceState.HEALTHY,
            health_status=HealthStatus.HEALTHY,
            cpu_utilization=25.0,
            memory_utilization=30.0,
            storage_utilization=20.0,
            network_latency_ms=15.0,
        )
        assert res.resource_id == "VM-001"
        assert res.health_status == HealthStatus.HEALTHY
        assert res.active_failure_type is None

    def test_resource_model_bounds_validation(self):
        """Metrics outside valid ranges (e.g. CPU > 100) raise ValidationError."""
        with pytest.raises(ValidationError):
            SimulatedResource(
                resource_id="VM-001",
                resource_type=ResourceType.VM,
                cpu_utilization=150.0,  # invalid > 100
            )

        with pytest.raises(ValidationError):
            SimulatedResource(
                resource_id="VM-001",
                resource_type=ResourceType.VM,
                network_latency_ms=-10.0,  # invalid < 0
            )

    def test_resource_dynamodb_roundtrip(self):
        """Conversion between SimulatedResource and DynamoDB item preserves fields."""
        res = SimulatedResource(
            resource_id="DB-001",
            resource_type=ResourceType.DB,
            current_state=ResourceState.WARNING,
            health_status=HealthStatus.DEGRADED,
            cpu_utilization=78.5,
            memory_utilization=82.0,
            storage_utilization=65.0,
            network_latency_ms=45.2,
        )
        item = res.to_dynamodb_item()
        assert item["resource_id"] == "DB-001"
        assert float(item["cpu_utilization"]) == 78.5

        hydrated = SimulatedResource.from_dynamodb_item(item)
        assert hydrated.resource_id == res.resource_id
        assert hydrated.current_state == res.current_state
        assert hydrated.cpu_utilization == res.cpu_utilization

    def test_incident_model_14_fields_validation(self):
        """Incident model tracks all 14 lifecycle fields."""
        now = datetime.now(UTC)
        inc_id = str(uuid.uuid4())
        inc = Incident(
            incident_id=inc_id,
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            created_at=now,
            detected_at=now,
            recovery_started_at=now + timedelta(seconds=2),
            recovered_at=now + timedelta(seconds=10),
            recovery_action="SCALE_OUT",
            recovery_result="SUCCESS",
            notification_status="DELIVERED",
            retry_count=1,
            error_message=None,
            duration_seconds=8.0,
            recovery_attempts=1,
            recovery_actions=[
                RecoveryAction(
                    action_id=str(uuid.uuid4()),
                    action_type=RecoveryActionType.SCALE_OUT,
                    status=RecoveryActionStatus.SUCCEEDED,
                    outcome_message="Added 2 instances",
                )
            ],
        )
        assert inc.incident_id == inc_id
        assert inc.recovery_attempts == len(inc.recovery_actions)
        assert inc.duration_seconds == 8.0

        # DynamoDB roundtrip
        item = inc.to_dynamodb_item()
        restored = Incident.from_dynamodb_item(item)
        assert restored.incident_id == inc.incident_id
        assert restored.status == IncidentStatus.OPEN
        assert restored.recovery_action == "SCALE_OUT"

    def test_incident_recovery_attempts_constraint(self):
        """recovery_attempts must equal len(recovery_actions)."""
        with pytest.raises(ValidationError):
            Incident(
                incident_id=str(uuid.uuid4()),
                resource_id="VM-001",
                failure_type=FailureType.HIGH_CPU,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.OPEN,
                state_at_detection=ResourceState.FAILURE_DETECTED,
                recovery_attempts=2,  # Mismatch with empty actions list
                recovery_actions=[],
            )

    def test_reliability_metric_model_and_keys(self):
        """ReliabilityMetric window keys parse and format correctly."""
        w_type, w_val = parse_window_key("DAILY#2026-09-09")
        assert w_type == MetricWindowType.DAILY
        assert w_val == "2026-09-09"

        now = datetime.now(UTC)
        metric = ReliabilityMetric(
            resource_id="VM-001",
            window_key="CUMULATIVE#ALL",
            window_type=MetricWindowType.CUMULATIVE,
            window_start=now - timedelta(days=7),
            window_end=now,
            total_incidents=5,
            resolved_incidents=4,
            failed_recoveries=1,
            mttr_seconds=12.4,
            mtbf_seconds=3600.0,
            availability_pct=99.92,
        )
        assert (metric.resolved_incidents / metric.total_incidents) * 100 == 80.0
        assert metric.to_dynamodb_item()["availability_pct"] is not None

    def test_compute_service_health_algorithm(self):
        """ServiceHealth composite score reduces based on degraded metrics."""
        zero_res = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=0.0,
            memory_utilization=0.0,
            storage_utilization=0.0,
            network_latency_ms=0.0,
        )
        assert compute_service_health(zero_res) == 100.0

        healthy_res = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=20.0,
            memory_utilization=20.0,
            storage_utilization=20.0,
            network_latency_ms=10.0,
        )
        assert compute_service_health(healthy_res) > 80.0

        # Highly degraded resource
        failing_res = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=95.0,
            memory_utilization=90.0,
            storage_utilization=92.0,
            network_latency_ms=2500.0,
        )
        score = compute_service_health(failing_res)
        assert score < 50.0
        assert compute_service_health(healthy_res) > compute_service_health(failing_res)

    def test_all_failure_metric_targets_defined(self):
        """All 5 failure types have defined deterministic metric targets."""
        for ft in FailureType:
            assert ft in FAILURE_METRIC_TARGETS
            targets = FAILURE_METRIC_TARGETS[ft]
            assert "cpu_utilization" in targets
            assert "network_latency_ms" in targets
