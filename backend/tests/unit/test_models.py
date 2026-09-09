"""
Unit tests for CloudPulse domain models.

Coverage:
- SimulatedResource: field validation, health status computation, state machine,
  apply_failure_metrics, reset_to_healthy, DynamoDB serialisation
- RecoveryAction: field validation, consistency rules, duration computation,
  DynamoDB map serialisation
- Incident: field validation, consistency rules, lifecycle methods, DynamoDB serialisation
- ReliabilityMetric: field validation, consistency rules, window_key helpers,
  domain methods, DynamoDB serialisation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.incident import (
    MAX_RECOVERY_ACTIONS,
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
    build_window_key,
    parse_window_key,
)
from app.models.resource import (
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _uuid4() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _make_resource(**overrides) -> SimulatedResource:
    defaults = dict(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        cpu_utilization=25.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
    )
    defaults.update(overrides)
    return SimulatedResource(**defaults)


def _make_action(**overrides) -> RecoveryAction:
    defaults = dict(
        action_id=_uuid4(),
        action_type=RecoveryActionType.SCALE_OUT,
        status=RecoveryActionStatus.SUCCEEDED,
        outcome_message="Simulated scale-out completed successfully",
    )
    defaults.update(overrides)
    return RecoveryAction(**defaults)


def _make_open_incident(**overrides) -> Incident:
    defaults = dict(
        incident_id=_uuid4(),
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        recovery_attempts=0,
        recovery_actions=[],
    )
    defaults.update(overrides)
    return Incident(**defaults)


def _make_resolved_incident(**overrides) -> Incident:
    detected = _now() - timedelta(seconds=10)
    resolved = _now()
    action = _make_action()
    defaults = dict(
        incident_id=_uuid4(),
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RESOLVED,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        state_at_resolution=ResourceState.RECOVERED,
        detected_at=detected,
        recovery_initiated_at=detected + timedelta(seconds=1),
        resolved_at=resolved,
        duration_seconds=10.0,
        recovery_attempts=1,
        recovery_actions=[action],
    )
    defaults.update(overrides)
    return Incident(**defaults)


def _make_metric(**overrides) -> ReliabilityMetric:
    now = _now()
    defaults = dict(
        resource_id="VM-001",
        window_key="DAILY#2026-09-08",
        window_type=MetricWindowType.DAILY,
        window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
        window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
        total_incidents=4,
        resolved_incidents=3,
        failed_recoveries=1,
        mttr_seconds=7.5,
        mtbf_seconds=3600.0,
        availability_pct=99.79,
        failure_type_counts={"HIGH_CPU": 2, "NETWORK_LATENCY": 1, "STORAGE_EXHAUSTION": 1},
    )
    defaults.update(overrides)
    return ReliabilityMetric(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# SimulatedResource Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestSimulatedResourceValidation:
    def test_valid_resource_creation(self):
        r = _make_resource()
        assert r.resource_id == "VM-001"
        assert r.resource_type == ResourceType.VM

    def test_resource_id_uppercased(self):
        r = _make_resource(resource_id="vm-001")
        assert r.resource_id == "VM-001"

    def test_resource_id_empty_raises(self):
        with pytest.raises(ValueError, match="resource_id must not be empty"):
            _make_resource(resource_id="")

    def test_resource_id_too_long_raises(self):
        with pytest.raises(ValueError, match="must not exceed 64"):
            _make_resource(resource_id="A" * 65)

    def test_resource_id_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            _make_resource(resource_id="VM@001")

    def test_resource_id_starts_with_hyphen_raises(self):
        with pytest.raises(ValueError):
            _make_resource(resource_id="-VM-001")

    def test_resource_id_valid_with_numbers(self):
        r = _make_resource(resource_id="DB-002")
        assert r.resource_id == "DB-002"

    def test_cpu_utilization_out_of_range_raises(self):
        with pytest.raises(ValueError):
            _make_resource(cpu_utilization=101.0)

    def test_cpu_utilization_negative_raises(self):
        with pytest.raises(ValueError):
            _make_resource(cpu_utilization=-1.0)

    def test_network_latency_boundary_valid(self):
        r = _make_resource(network_latency_ms=99999.0)
        assert r.network_latency_ms == 99999.0

    def test_network_latency_exceeds_max_raises(self):
        with pytest.raises(ValueError):
            _make_resource(network_latency_ms=100000.0)

    def test_description_stripped(self):
        r = _make_resource(description="  a description  ")
        assert r.description == "a description"

    def test_active_failure_type_forbidden_in_healthy_state(self):
        with pytest.raises(ValueError, match="active_failure_type must be None"):
            _make_resource(
                current_state=ResourceState.HEALTHY,
                active_failure_type=FailureType.HIGH_CPU,
            )

    def test_active_failure_type_forbidden_in_warning_state(self):
        with pytest.raises(ValueError, match="active_failure_type must be None"):
            _make_resource(
                current_state=ResourceState.WARNING,
                active_failure_type=FailureType.NETWORK_LATENCY,
            )

    def test_active_failure_type_allowed_in_failure_state(self):
        r = _make_resource(
            current_state=ResourceState.FAILURE_DETECTED,
            active_failure_type=FailureType.HIGH_CPU,
            health_status=HealthStatus.CRITICAL,
        )
        assert r.active_failure_type == FailureType.HIGH_CPU


class TestSimulatedResourceHealthComputation:
    def test_healthy_all_nominal(self):
        r = _make_resource(
            cpu_utilization=25.0,
            memory_utilization=30.0,
            storage_utilization=20.0,
            network_latency_ms=15.0,
        )
        assert r.compute_health_status() == HealthStatus.HEALTHY

    def test_degraded_on_high_cpu(self):
        r = _make_resource(cpu_utilization=80.0)
        assert r.compute_health_status() == HealthStatus.DEGRADED

    def test_degraded_on_high_memory(self):
        r = _make_resource(memory_utilization=78.0)
        assert r.compute_health_status() == HealthStatus.DEGRADED

    def test_degraded_on_high_network_latency(self):
        r = _make_resource(network_latency_ms=350.0)
        assert r.compute_health_status() == HealthStatus.DEGRADED

    def test_critical_on_cpu_failure(self):
        r = _make_resource(cpu_utilization=95.0)
        assert r.compute_health_status() == HealthStatus.CRITICAL

    def test_critical_on_storage_exhaustion(self):
        r = _make_resource(storage_utilization=95.0)
        assert r.compute_health_status() == HealthStatus.CRITICAL

    def test_critical_on_network_latency_failure(self):
        r = _make_resource(network_latency_ms=600.0)
        assert r.compute_health_status() == HealthStatus.CRITICAL


class TestSimulatedResourceStateMachine:
    def test_healthy_can_transition_to_warning(self):
        assert ResourceState.HEALTHY.can_transition_to(ResourceState.WARNING)

    def test_healthy_can_transition_to_failure_direct_inject(self):
        assert ResourceState.HEALTHY.can_transition_to(ResourceState.FAILURE_DETECTED)

    def test_healthy_cannot_transition_to_recovered(self):
        assert not ResourceState.HEALTHY.can_transition_to(ResourceState.RECOVERED)

    def test_warning_can_return_to_healthy(self):
        assert ResourceState.WARNING.can_transition_to(ResourceState.HEALTHY)

    def test_failure_detected_can_only_go_to_recovery_initiated(self):
        assert ResourceState.FAILURE_DETECTED.can_transition_to(ResourceState.RECOVERY_INITIATED)
        assert not ResourceState.FAILURE_DETECTED.can_transition_to(ResourceState.HEALTHY)

    def test_recovered_is_terminal(self):
        # RECOVERED is terminal: no *automatic* transitions are triggered by the
        # state machine itself. The simulator heartbeat manually advances it to
        # HEALTHY on the next cycle, but is_terminal() refers to automatic flow.
        assert ResourceState.RECOVERED.is_terminal()
        # However, the explicit RECOVERED → HEALTHY transition is still registered
        assert ResourceState.RECOVERED.can_transition_to(ResourceState.HEALTHY)

    def test_manual_intervention_required_is_terminal_from_machine_perspective(self):
        # MANUAL_INTERVENTION_REQUIRED can only go to HEALTHY via API reset
        assert ResourceState.MANUAL_INTERVENTION_REQUIRED.can_transition_to(ResourceState.HEALTHY)

    def test_is_in_recovery(self):
        assert ResourceState.RECOVERY_INITIATED.is_in_recovery()
        assert ResourceState.RECOVERY_IN_PROGRESS.is_in_recovery()
        assert not ResourceState.HEALTHY.is_in_recovery()
        assert not ResourceState.RECOVERED.is_in_recovery()


class TestSimulatedResourceDomainMethods:
    def test_apply_failure_metrics_high_cpu(self):
        r = _make_resource()
        failed = r.apply_failure_metrics(FailureType.HIGH_CPU)
        assert failed.cpu_utilization == 92.0
        assert failed.current_state == ResourceState.FAILURE_DETECTED
        assert failed.health_status == HealthStatus.CRITICAL
        assert failed.active_failure_type == FailureType.HIGH_CPU

    def test_apply_failure_metrics_returns_copy(self):
        r = _make_resource()
        failed = r.apply_failure_metrics(FailureType.HIGH_CPU)
        assert failed.current_state == ResourceState.FAILURE_DETECTED
        # Original must be unmodified
        assert r.current_state == ResourceState.HEALTHY
        assert r.active_failure_type is None

    def test_reset_to_healthy(self):
        r = _make_resource(
            current_state=ResourceState.FAILURE_DETECTED,
            active_failure_type=FailureType.HIGH_CPU,
            health_status=HealthStatus.CRITICAL,
            cpu_utilization=92.0,
        )
        healthy = r.reset_to_healthy()
        assert healthy.current_state == ResourceState.HEALTHY
        assert healthy.active_failure_type is None
        assert healthy.health_status == HealthStatus.HEALTHY
        assert healthy.cpu_utilization == 25.0

    def test_to_dynamodb_item_excludes_none(self):
        r = _make_resource()
        item = r.to_dynamodb_item()
        assert "active_failure_type" not in item
        assert "resource_id" in item

    def test_from_dynamodb_item_handles_decimal(self):
        r = _make_resource()
        raw = r.to_dynamodb_item()
        # Simulate what DynamoDB returns for numbers
        raw["cpu_utilization"] = Decimal("25.0")
        raw["memory_utilization"] = Decimal("30.0")
        restored = SimulatedResource.from_dynamodb_item(raw)
        assert restored.cpu_utilization == 25.0
        assert isinstance(restored.cpu_utilization, float)

    def test_from_dynamodb_item_roundtrip(self):
        r = _make_resource()
        item = r.to_dynamodb_item()
        restored = SimulatedResource.from_dynamodb_item(item)
        assert restored.resource_id == r.resource_id
        assert restored.resource_type == r.resource_type


# ═════════════════════════════════════════════════════════════════════════════
# RecoveryAction Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestRecoveryActionValidation:
    def test_valid_action_creation(self):
        action = _make_action()
        assert action.action_type == RecoveryActionType.SCALE_OUT
        assert action.status == RecoveryActionStatus.SUCCEEDED

    def test_action_id_normalised_to_lowercase(self):
        uid = str(uuid.uuid4()).upper()
        action = _make_action(action_id=uid)
        assert action.action_id == uid.lower()

    def test_action_id_empty_raises(self):
        with pytest.raises(ValueError, match="action_id must not be empty"):
            _make_action(action_id="")

    def test_action_id_invalid_uuid_raises(self):
        with pytest.raises(ValueError, match="must be a valid UUID v4"):
            _make_action(action_id="not-a-uuid")

    def test_action_id_uuid_v1_rejected(self):
        # UUID v1 has a '1' in the third group
        v1 = "550e8400-e29b-11d4-a716-446655440000"
        with pytest.raises(ValueError, match="must be a valid UUID v4"):
            _make_action(action_id=v1)

    def test_outcome_message_stripped(self):
        action = _make_action(outcome_message="  trimmed  ")
        assert action.outcome_message == "trimmed"

    def test_outcome_message_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="outcome_message must not be empty"):
            _make_action(outcome_message="   ")

    def test_completed_at_before_started_at_raises(self):
        now = _now()
        with pytest.raises(ValueError, match="completed_at must not precede started_at"):
            _make_action(
                started_at=now,
                completed_at=now - timedelta(seconds=5),
                status=RecoveryActionStatus.SUCCEEDED,
            )

    def test_error_detail_without_failed_status_raises(self):
        with pytest.raises(ValueError, match="error_detail must only be set when status=FAILED"):
            _make_action(
                status=RecoveryActionStatus.SUCCEEDED,
                error_detail="Some error traceback",
            )

    def test_error_detail_allowed_on_failed_status(self):
        action = _make_action(
            status=RecoveryActionStatus.FAILED,
            error_detail="Connection timeout after 30s",
        )
        assert action.error_detail == "Connection timeout after 30s"

    def test_pending_action_no_completed_at(self):
        action = _make_action(
            status=RecoveryActionStatus.PENDING,
            completed_at=None,
        )
        assert action.completed_at is None
        assert action.duration_seconds() is None


class TestRecoveryActionDomainMethods:
    def test_duration_seconds_computed_correctly(self):
        started = _now()
        completed = started + timedelta(seconds=7)
        action = _make_action(
            started_at=started,
            completed_at=completed,
            status=RecoveryActionStatus.SUCCEEDED,
        )
        assert action.duration_seconds() == pytest.approx(7.0)

    def test_duration_seconds_none_when_not_completed(self):
        action = _make_action(
            status=RecoveryActionStatus.IN_PROGRESS,
            completed_at=None,
        )
        assert action.duration_seconds() is None

    def test_to_dynamodb_map_excludes_none(self):
        action = _make_action(status=RecoveryActionStatus.IN_PROGRESS, completed_at=None)
        m = action.to_dynamodb_map()
        assert "completed_at" not in m
        assert "error_detail" not in m
        assert "action_id" in m

    def test_from_dynamodb_map_roundtrip(self):
        action = _make_action()
        m = action.to_dynamodb_map()
        restored = RecoveryAction.from_dynamodb_map(m)
        assert restored.action_id == action.action_id
        assert restored.action_type == action.action_type

    def test_status_is_terminal(self):
        assert RecoveryActionStatus.SUCCEEDED.is_terminal()
        assert RecoveryActionStatus.FAILED.is_terminal()
        assert not RecoveryActionStatus.PENDING.is_terminal()
        assert not RecoveryActionStatus.IN_PROGRESS.is_terminal()


# ═════════════════════════════════════════════════════════════════════════════
# Incident Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestIncidentValidation:
    def test_valid_open_incident(self):
        inc = _make_open_incident()
        assert inc.status == IncidentStatus.OPEN
        assert inc.recovery_attempts == 0

    def test_incident_id_normalised_to_lowercase(self):
        uid = str(uuid.uuid4()).upper()
        inc = _make_open_incident(incident_id=uid)
        assert inc.incident_id == uid.lower()

    def test_incident_id_empty_raises(self):
        with pytest.raises(ValueError, match="incident_id must not be empty"):
            _make_open_incident(incident_id="")

    def test_incident_id_invalid_uuid_raises(self):
        with pytest.raises(ValueError, match="must be a valid UUID v4"):
            _make_open_incident(incident_id="not-valid")

    def test_resource_id_uppercased(self):
        inc = _make_open_incident(resource_id="vm-001")
        assert inc.resource_id == "VM-001"

    def test_resource_id_empty_raises(self):
        with pytest.raises(ValueError, match="resource_id must not be empty"):
            _make_open_incident(resource_id="")

    def test_resource_id_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            _make_open_incident(resource_id="VM@001")

    def test_resolved_at_before_detected_at_raises(self):
        now = _now()
        action = _make_action()
        with pytest.raises(ValueError, match="resolved_at must not precede detected_at"):
            Incident(
                incident_id=_uuid4(),
                resource_id="VM-001",
                failure_type=FailureType.HIGH_CPU,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.RESOLVED,
                state_at_detection=ResourceState.FAILURE_DETECTED,
                state_at_resolution=ResourceState.RECOVERED,
                detected_at=now,
                resolved_at=now - timedelta(seconds=5),
                recovery_attempts=1,
                recovery_actions=[action],
            )

    def test_escalated_at_before_detected_at_raises(self):
        now = _now()
        action = _make_action(status=RecoveryActionStatus.FAILED, error_detail="err")
        with pytest.raises(ValueError, match="escalated_at must not precede detected_at"):
            Incident(
                incident_id=_uuid4(),
                resource_id="VM-001",
                failure_type=FailureType.HIGH_CPU,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.ESCALATED,
                state_at_detection=ResourceState.FAILURE_DETECTED,
                state_at_resolution=ResourceState.RECOVERY_FAILED,
                detected_at=now,
                escalated_at=now - timedelta(seconds=5),
                recovery_attempts=1,
                recovery_actions=[action],
            )

    def test_recovery_initiated_at_before_detected_at_raises(self):
        now = _now()
        with pytest.raises(ValueError, match="recovery_initiated_at must not precede detected_at"):
            _make_open_incident(
                detected_at=now,
                recovery_initiated_at=now - timedelta(seconds=1),
            )

    def test_state_at_resolution_forbidden_when_open(self):
        with pytest.raises(ValueError, match="state_at_resolution must be None when status=OPEN"):
            _make_open_incident(state_at_resolution=ResourceState.RECOVERED)

    def test_state_at_resolution_forbidden_when_recovering(self):
        with pytest.raises(
            ValueError, match="state_at_resolution must be None when status=RECOVERING"
        ):
            _make_open_incident(
                status=IncidentStatus.RECOVERING,
                state_at_resolution=ResourceState.RECOVERED,
            )

    def test_resolved_status_requires_resolved_at(self):
        action = _make_action()
        with pytest.raises(ValueError, match="resolved_at is required when status=RESOLVED"):
            Incident(
                incident_id=_uuid4(),
                resource_id="VM-001",
                failure_type=FailureType.HIGH_CPU,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.RESOLVED,
                state_at_detection=ResourceState.FAILURE_DETECTED,
                state_at_resolution=ResourceState.RECOVERED,
                # resolved_at omitted intentionally
                recovery_attempts=1,
                recovery_actions=[action],
            )

    def test_escalated_status_requires_escalated_at(self):
        action = _make_action(status=RecoveryActionStatus.FAILED, error_detail="err")
        with pytest.raises(ValueError, match="escalated_at is required when status=ESCALATED"):
            Incident(
                incident_id=_uuid4(),
                resource_id="VM-001",
                failure_type=FailureType.HIGH_CPU,
                severity=IncidentSeverity.HIGH,
                status=IncidentStatus.ESCALATED,
                state_at_detection=ResourceState.FAILURE_DETECTED,
                state_at_resolution=ResourceState.RECOVERY_FAILED,
                # escalated_at omitted intentionally
                recovery_attempts=1,
                recovery_actions=[action],
            )

    def test_recovery_attempts_mismatch_raises(self):
        action = _make_action()
        with pytest.raises(ValueError, match="recovery_attempts.*must equal.*len"):
            _make_open_incident(
                recovery_attempts=2,  # but only 1 action
                recovery_actions=[action],
            )

    def test_recovery_actions_exceed_limit_raises(self):
        actions = [_make_action() for _ in range(MAX_RECOVERY_ACTIONS + 1)]
        with pytest.raises(ValueError, match=f"may not exceed {MAX_RECOVERY_ACTIONS}"):
            _make_open_incident(
                recovery_attempts=MAX_RECOVERY_ACTIONS + 1,
                recovery_actions=actions,
            )

    def test_valid_resolved_incident(self):
        inc = _make_resolved_incident()
        assert inc.status == IncidentStatus.RESOLVED
        assert inc.resolved_at is not None
        assert inc.state_at_resolution == ResourceState.RECOVERED


class TestIncidentStatusMachine:
    def test_open_can_transition_to_recovering(self):
        assert IncidentStatus.OPEN.can_transition_to(IncidentStatus.RECOVERING)

    def test_open_can_transition_to_escalated(self):
        assert IncidentStatus.OPEN.can_transition_to(IncidentStatus.ESCALATED)

    def test_open_cannot_transition_to_resolved_directly(self):
        assert not IncidentStatus.OPEN.can_transition_to(IncidentStatus.RESOLVED)

    def test_recovering_can_transition_to_resolved(self):
        assert IncidentStatus.RECOVERING.can_transition_to(IncidentStatus.RESOLVED)

    def test_resolved_is_terminal(self):
        assert IncidentStatus.RESOLVED.is_terminal()
        assert not IncidentStatus.RESOLVED.can_transition_to(IncidentStatus.OPEN)

    def test_escalated_is_terminal(self):
        assert IncidentStatus.ESCALATED.is_terminal()

    def test_open_is_active(self):
        assert IncidentStatus.OPEN.is_active()
        assert IncidentStatus.RECOVERING.is_active()
        assert not IncidentStatus.RESOLVED.is_active()


class TestIncidentSeverity:
    def test_numeric_ordering(self):
        assert IncidentSeverity.LOW.numeric() < IncidentSeverity.MEDIUM.numeric()
        assert IncidentSeverity.MEDIUM.numeric() < IncidentSeverity.HIGH.numeric()
        assert IncidentSeverity.HIGH.numeric() < IncidentSeverity.CRITICAL.numeric()


class TestIncidentDomainMethods:
    def test_compute_duration_seconds_resolved(self):
        detected = _now() - timedelta(seconds=8)
        resolved = _now()
        action = _make_action()
        inc = Incident(
            incident_id=_uuid4(),
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RESOLVED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            state_at_resolution=ResourceState.RECOVERED,
            detected_at=detected,
            resolved_at=resolved,
            recovery_attempts=1,
            recovery_actions=[action],
        )
        duration = inc.compute_duration_seconds()
        assert duration is not None
        assert duration == pytest.approx((resolved - detected).total_seconds(), abs=0.1)

    def test_compute_duration_seconds_open_returns_none(self):
        inc = _make_open_incident()
        assert inc.compute_duration_seconds() is None

    def test_latest_action_returns_most_recent(self):
        now = _now()
        a1 = _make_action(started_at=now - timedelta(seconds=10))
        a2 = _make_action(started_at=now - timedelta(seconds=5))
        inc = _make_open_incident(
            recovery_attempts=2,
            recovery_actions=[a1, a2],
        )
        assert inc.latest_action() == a2

    def test_latest_action_none_when_empty(self):
        inc = _make_open_incident()
        assert inc.latest_action() is None

    def test_to_dynamodb_item_excludes_none(self):
        inc = _make_open_incident()
        item = inc.to_dynamodb_item()
        assert "resolved_at" not in item
        assert "state_at_resolution" not in item
        assert "incident_id" in item

    def test_to_dynamodb_item_includes_recovery_actions_list(self):
        action = _make_action()
        inc = _make_open_incident(
            status=IncidentStatus.RECOVERING,
            recovery_attempts=1,
            recovery_actions=[action],
        )
        item = inc.to_dynamodb_item()
        assert isinstance(item["recovery_actions"], list)
        assert len(item["recovery_actions"]) == 1
        assert item["recovery_actions"][0]["action_id"] == action.action_id

    def test_from_dynamodb_item_roundtrip(self):
        inc = _make_resolved_incident()
        item = inc.to_dynamodb_item()
        restored = Incident.from_dynamodb_item(item)
        assert restored.incident_id == inc.incident_id
        assert restored.status == inc.status
        assert restored.resolved_at is not None

    def test_from_dynamodb_item_handles_decimal(self):
        inc = _make_resolved_incident()
        item = inc.to_dynamodb_item()
        # Simulate DynamoDB Decimal conversion
        item["duration_seconds"] = Decimal("10")
        item["recovery_attempts"] = Decimal("1")
        restored = Incident.from_dynamodb_item(item)
        assert restored.duration_seconds == 10.0
        assert restored.recovery_attempts == 1


# ═════════════════════════════════════════════════════════════════════════════
# ReliabilityMetric Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestWindowKeyHelpers:
    def test_build_daily_key(self):
        key = build_window_key(MetricWindowType.DAILY, "2026-09-08")
        assert key == "DAILY#2026-09-08"

    def test_build_weekly_key(self):
        key = build_window_key(MetricWindowType.WEEKLY, "2026-09-07")
        assert key == "WEEKLY#2026-09-07"

    def test_build_cumulative_key(self):
        key = build_window_key(MetricWindowType.CUMULATIVE)
        assert key == "CUMULATIVE#ALL"

    def test_parse_daily_key(self):
        window_type, date_str = parse_window_key("DAILY#2026-09-08")
        assert window_type == MetricWindowType.DAILY
        assert date_str == "2026-09-08"

    def test_parse_weekly_key(self):
        window_type, date_str = parse_window_key("WEEKLY#2026-09-07")
        assert window_type == MetricWindowType.WEEKLY
        assert date_str == "2026-09-07"

    def test_parse_cumulative_key(self):
        window_type, date_str = parse_window_key("CUMULATIVE#ALL")
        assert window_type == MetricWindowType.CUMULATIVE
        assert date_str == "ALL"

    def test_parse_invalid_key_raises(self):
        with pytest.raises(ValueError, match="Invalid window_key format"):
            parse_window_key("MONTHLY#2026-09")

    def test_build_parse_roundtrip_daily(self):
        key = build_window_key(MetricWindowType.DAILY, "2026-09-08")
        wt, ds = parse_window_key(key)
        assert wt == MetricWindowType.DAILY
        assert ds == "2026-09-08"


class TestReliabilityMetricValidation:
    def test_valid_metric_creation(self):
        m = _make_metric()
        assert m.resource_id == "VM-001"
        assert m.total_incidents == 4

    def test_resource_id_uppercased(self):
        m = _make_metric(resource_id="vm-001")
        assert m.resource_id == "VM-001"

    def test_resource_id_empty_raises(self):
        with pytest.raises(ValueError, match="resource_id must not be empty"):
            _make_metric(resource_id="")

    def test_invalid_window_key_raises(self):
        with pytest.raises(ValueError, match="window_key must match"):
            _make_metric(window_key="MONTHLY#2026-09")

    def test_window_key_type_mismatch_raises(self):
        with pytest.raises(ValueError, match="inconsistent with window_type"):
            _make_metric(
                window_key="WEEKLY#2026-09-07",
                window_type=MetricWindowType.DAILY,
            )

    def test_window_end_before_window_start_raises(self):
        now = _now()
        with pytest.raises(ValueError, match="window_end must not precede window_start"):
            _make_metric(
                window_start=now,
                window_end=now - timedelta(hours=1),
            )

    def test_resolved_incidents_exceeds_total_raises(self):
        with pytest.raises(ValueError, match="resolved_incidents.*cannot exceed"):
            _make_metric(total_incidents=2, resolved_incidents=3)

    def test_failed_recoveries_exceeds_total_raises(self):
        with pytest.raises(ValueError, match="failed_recoveries.*cannot exceed"):
            # resolved_incidents=0 so the failed_recoveries check fires first
            _make_metric(
                total_incidents=2,
                resolved_incidents=0,
                failed_recoveries=3,
                mttr_seconds=None,
                failure_type_counts={"HIGH_CPU": 2},
            )

    def test_resolved_plus_failed_exceeds_total_raises(self):
        with pytest.raises(ValueError, match=r"resolved_incidents \+ failed_recoveries"):
            _make_metric(
                total_incidents=3,
                resolved_incidents=2,
                failed_recoveries=2,
                mttr_seconds=5.0,
            )

    def test_mttr_seconds_forbidden_when_no_resolved_incidents(self):
        with pytest.raises(
            ValueError, match="mttr_seconds must be None when resolved_incidents == 0"
        ):
            _make_metric(
                total_incidents=0,
                resolved_incidents=0,
                failed_recoveries=0,
                mttr_seconds=5.0,
                mtbf_seconds=None,
                availability_pct=None,
                failure_type_counts={},
            )

    def test_mtbf_seconds_forbidden_when_fewer_than_2_incidents(self):
        now = _now()
        with pytest.raises(ValueError, match="mtbf_seconds must be None when total_incidents < 2"):
            ReliabilityMetric(
                resource_id="VM-001",
                window_key="DAILY#2026-09-08",
                window_type=MetricWindowType.DAILY,
                window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
                total_incidents=1,
                resolved_incidents=1,
                failed_recoveries=0,
                mttr_seconds=5.0,
                mtbf_seconds=3600.0,  # Not valid with only 1 incident
                failure_type_counts={"HIGH_CPU": 1},
            )

    def test_zero_incidents_valid(self):
        now = _now()
        m = ReliabilityMetric(
            resource_id="VM-001",
            window_key="DAILY#2026-09-08",
            window_type=MetricWindowType.DAILY,
            window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
            total_incidents=0,
            resolved_incidents=0,
            failed_recoveries=0,
            failure_type_counts={},
        )
        assert m.total_incidents == 0
        assert m.mttr_seconds is None
        assert m.mtbf_seconds is None

    def test_failure_type_counts_negative_value_raises(self):
        with pytest.raises(ValueError, match="values must be non-negative integers"):
            _make_metric(failure_type_counts={"HIGH_CPU": -1})

    def test_failure_type_counts_sum_exceeds_total_raises(self):
        with pytest.raises(ValueError, match="sum\\(failure_type_counts\\)"):
            _make_metric(
                total_incidents=2,
                resolved_incidents=2,
                failed_recoveries=0,
                mttr_seconds=5.0,
                failure_type_counts={"HIGH_CPU": 5},
            )

    def test_availability_pct_out_of_range_raises(self):
        with pytest.raises(ValueError):
            _make_metric(availability_pct=101.0)


class TestReliabilityMetricDomainMethods:
    def test_recovery_success_rate_computed(self):
        m = _make_metric(
            total_incidents=4,
            resolved_incidents=3,
            failed_recoveries=1,
        )
        rate = m.recovery_success_rate()
        assert rate == pytest.approx(0.75)

    def test_recovery_success_rate_none_when_no_concluded(self):
        now = _now()
        m = ReliabilityMetric(
            resource_id="VM-001",
            window_key="DAILY#2026-09-08",
            window_type=MetricWindowType.DAILY,
            window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
            total_incidents=2,
            resolved_incidents=0,
            failed_recoveries=0,
            failure_type_counts={"HIGH_CPU": 2},
        )
        assert m.recovery_success_rate() is None

    def test_dominant_failure_type(self):
        m = _make_metric(failure_type_counts={"HIGH_CPU": 3, "NETWORK_LATENCY": 1})
        assert m.dominant_failure_type() == "HIGH_CPU"

    def test_dominant_failure_type_none_when_empty(self):
        now = _now()
        m = ReliabilityMetric(
            resource_id="VM-001",
            window_key="DAILY#2026-09-08",
            window_type=MetricWindowType.DAILY,
            window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
            total_incidents=0,
            resolved_incidents=0,
            failed_recoveries=0,
            failure_type_counts={},
        )
        assert m.dominant_failure_type() is None

    def test_to_dynamodb_item_excludes_none(self):
        now = _now()
        m = ReliabilityMetric(
            resource_id="VM-001",
            window_key="DAILY#2026-09-08",
            window_type=MetricWindowType.DAILY,
            window_start=now.replace(hour=0, minute=0, second=0, microsecond=0),
            window_end=now.replace(hour=23, minute=59, second=59, microsecond=0),
            total_incidents=0,
            resolved_incidents=0,
            failed_recoveries=0,
            failure_type_counts={},
        )
        item = m.to_dynamodb_item()
        assert "mttr_seconds" not in item
        assert "mtbf_seconds" not in item
        assert "resource_id" in item
        assert "window_key" in item

    def test_from_dynamodb_item_roundtrip(self):
        m = _make_metric()
        item = m.to_dynamodb_item()
        restored = ReliabilityMetric.from_dynamodb_item(item)
        assert restored.resource_id == m.resource_id
        assert restored.window_key == m.window_key
        assert restored.total_incidents == m.total_incidents

    def test_from_dynamodb_item_handles_decimal(self):
        m = _make_metric()
        item = m.to_dynamodb_item()
        item["total_incidents"] = Decimal("4")
        item["mttr_seconds"] = Decimal("7.5")
        restored = ReliabilityMetric.from_dynamodb_item(item)
        assert restored.total_incidents == 4
        assert isinstance(restored.total_incidents, int)
        assert restored.mttr_seconds == pytest.approx(7.5)

    def test_cumulative_window_key(self):
        now = _now()
        m = ReliabilityMetric(
            resource_id="VM-001",
            window_key="CUMULATIVE#ALL",
            window_type=MetricWindowType.CUMULATIVE,
            window_start=now - timedelta(days=30),
            window_end=now,
            total_incidents=20,
            resolved_incidents=18,
            failed_recoveries=2,
            mttr_seconds=6.0,
            mtbf_seconds=1800.0,
            availability_pct=99.9,
            failure_type_counts={"HIGH_CPU": 10, "STORAGE_EXHAUSTION": 5, "NETWORK_LATENCY": 5},
        )
        assert m.window_type == MetricWindowType.CUMULATIVE
        assert m.window_key == "CUMULATIVE#ALL"
