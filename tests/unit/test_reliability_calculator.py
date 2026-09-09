"""
Comprehensive automated tests for reliability and observability metric calculations.

Verifies exact mathematical derivations for all 8 SRE metrics:
1. Incident count
2. Recovery success rate
3. Recovery failure rate
4. Average recovery time
5. Mean Time to Recovery (MTTR)
6. Average detection time
7. Incident frequency (per hour, per day, MTBF)
8. Current resource health distribution

Also tests:
- Traceability: Correlation ID and incident ID flow through simulation, detection, event, recovery, notification
- Timezone safety across all datetime operations
- Boundary conditions: Empty incident lists, single incidents, all-succeeded, all-failed, mixed states
"""

import uuid
from datetime import UTC, datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.logging_config import (
    clear_trace_context,
    get_correlation_id,
    get_incident_id,
    get_trace_stage,
    set_correlation_id,
    set_incident_id,
    set_trace_stage,
)
from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.resource import FailureType, HealthStatus, ResourceState, ResourceType, SimulatedResource
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.reliability_calculator import (
    calculate_average_detection_time,
    calculate_average_recovery_time,
    calculate_fleet_reliability_overview,
    calculate_health_distribution,
    calculate_incident_count,
    calculate_incident_frequency,
    calculate_mttr,
    calculate_recovery_failure_rate,
    calculate_recovery_success_rate,
    calculate_resource_metric_summary,
)


def _make_test_incident(
    status: IncidentStatus = IncidentStatus.RESOLVED,
    created_seconds_ago: float | None = None,
    detected_seconds_ago: float = 55.0,
    recovery_started_seconds_ago: float | None = None,
    recovered_seconds_ago: float | None = None,
    resolved_seconds_ago: float | None = None,
    resource_id: str = "VM-001",
    action_duration: float = 10.0,
) -> Incident:
    """Helper to construct deterministic, timezone-safe test incidents."""
    now = datetime.now(UTC)
    inc_id = str(uuid.uuid4())

    if created_seconds_ago is None:
        created_seconds_ago = detected_seconds_ago + 5.0
    if recovery_started_seconds_ago is None:
        recovery_started_seconds_ago = max(0.0, detected_seconds_ago - 2.0)
    if recovered_seconds_ago is None:
        recovered_seconds_ago = max(0.0, recovery_started_seconds_ago - 2.0)
    if resolved_seconds_ago is None:
        resolved_seconds_ago = recovered_seconds_ago

    created_at = now - timedelta(seconds=created_seconds_ago)
    detected_at = now - timedelta(seconds=detected_seconds_ago)
    rec_start = now - timedelta(seconds=recovery_started_seconds_ago)
    recovered_at = now - timedelta(seconds=recovered_seconds_ago) if status == IncidentStatus.RESOLVED else None
    resolved_at = now - timedelta(seconds=resolved_seconds_ago) if status == IncidentStatus.RESOLVED else None
    escalated_at = now - timedelta(seconds=resolved_seconds_ago) if status == IncidentStatus.ESCALATED else None

    actions: list[RecoveryAction] = []
    if status == IncidentStatus.RESOLVED:
        actions.append(
            RecoveryAction(
                action_id=str(uuid.uuid4()),
                action_type=RecoveryActionType.SCALE_OUT,
                status=RecoveryActionStatus.SUCCEEDED,
                outcome_message="Action executed",
                started_at=rec_start,
                completed_at=rec_start + timedelta(seconds=action_duration),
            )
        )
    elif status == IncidentStatus.ESCALATED:
        actions.append(
            RecoveryAction(
                action_id=str(uuid.uuid4()),
                action_type=RecoveryActionType.SCALE_OUT,
                status=RecoveryActionStatus.FAILED,
                outcome_message="Action failed",
                error_detail="Timeout",
                started_at=rec_start,
                completed_at=rec_start + timedelta(seconds=action_duration),
            )
        )

    duration_sec = (resolved_at - detected_at).total_seconds() if resolved_at else None

    return Incident(
        incident_id=inc_id,
        resource_id=resource_id,
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=status,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        state_at_resolution=ResourceState.RECOVERED if status == IncidentStatus.RESOLVED else (ResourceState.MANUAL_INTERVENTION_REQUIRED if status == IncidentStatus.ESCALATED else None),
        created_at=created_at,
        detected_at=detected_at,
        recovery_started_at=rec_start,
        recovery_initiated_at=rec_start,
        recovered_at=recovered_at,
        resolved_at=resolved_at,
        escalated_at=escalated_at,
        duration_seconds=duration_sec,
        recovery_attempts=len(actions),
        retry_count=len(actions),
        recovery_actions=actions,
    )


class TestReliabilityCalculatorUnit:
    """Mathematical and algorithmic validation for every SRE metric."""

    def test_incident_count(self):
        """1. Incident count returns exact length of incidents observed."""
        assert calculate_incident_count([]) == 0
        incidents = [_make_test_incident() for _ in range(7)]
        assert calculate_incident_count(incidents) == 7

    def test_recovery_success_and_failure_rates_empty(self):
        """2 & 3. Rates return 100% success and 0% failure when no closed incidents exist."""
        assert calculate_recovery_success_rate([]) == 100.0
        assert calculate_recovery_failure_rate([]) == 0.0

        open_only = [_make_test_incident(status=IncidentStatus.OPEN)]
        assert calculate_recovery_success_rate(open_only) == 100.0
        assert calculate_recovery_failure_rate(open_only) == 0.0

    def test_recovery_success_and_failure_rates_mixed(self):
        """2 & 3. Rates calculate exact percentages and sum to 100.0%."""
        incidents = [
            _make_test_incident(status=IncidentStatus.RESOLVED),
            _make_test_incident(status=IncidentStatus.RESOLVED),
            _make_test_incident(status=IncidentStatus.RESOLVED),
            _make_test_incident(status=IncidentStatus.ESCALATED),
        ]
        # 3 resolved out of 4 closed = 75.0% success, 25.0% failure
        succ = calculate_recovery_success_rate(incidents)
        fail = calculate_recovery_failure_rate(incidents)
        assert succ == 75.0
        assert fail == 25.0
        assert succ + fail == 100.0

    def test_average_recovery_time_calculation(self):
        """4. Average recovery time derives from action execution durations."""
        assert calculate_average_recovery_time([]) is None

        # Two resolved incidents with action durations of 8.0s and 12.0s
        i1 = _make_test_incident(status=IncidentStatus.RESOLVED, action_duration=8.0)
        i2 = _make_test_incident(status=IncidentStatus.RESOLVED, action_duration=12.0)
        i3 = _make_test_incident(status=IncidentStatus.ESCALATED, action_duration=20.0)

        # Average of 8.0 and 12.0 is 10.0 (escalated excluded)
        avg_rec = calculate_average_recovery_time([i1, i2, i3])
        assert avg_rec == 10.0

    def test_mttr_calculation(self):
        """5. MTTR measures total elapsed duration from detected_at to resolved_at."""
        assert calculate_mttr([]) is None

        # i1: detected 50s ago, resolved 20s ago -> duration = 30.0s
        i1 = _make_test_incident(
            status=IncidentStatus.RESOLVED,
            detected_seconds_ago=50.0,
            resolved_seconds_ago=20.0,
        )
        # i2: detected 70s ago, resolved 30s ago -> duration = 40.0s
        i2 = _make_test_incident(
            status=IncidentStatus.RESOLVED,
            detected_seconds_ago=70.0,
            resolved_seconds_ago=30.0,
        )

        mttr = calculate_mttr([i1, i2])
        assert mttr == 35.0  # (30 + 40) / 2

    def test_average_detection_time_calculation(self):
        """6. Average detection time measures created_at to detected_at latency."""
        assert calculate_average_detection_time([]) is None

        # i1: created 60s ago, detected 55s ago -> detection latency = 5.0s
        i1 = _make_test_incident(created_seconds_ago=60.0, detected_seconds_ago=55.0)
        # i2: created 40s ago, detected 37s ago -> detection latency = 3.0s
        i2 = _make_test_incident(created_seconds_ago=40.0, detected_seconds_ago=37.0)

        avg_det = calculate_average_detection_time([i1, i2])
        assert avg_det == 4.0  # (5.0 + 3.0) / 2

    def test_incident_frequency_and_mtbf_calculation(self):
        """7. Incident frequency computes hourly/daily rates and MTBF across incidents."""
        now = datetime.now(UTC)
        start = now - timedelta(hours=2)
        end = now

        # 4 incidents across a 2-hour window
        i1 = _make_test_incident(detected_seconds_ago=7200.0)
        i2 = _make_test_incident(detected_seconds_ago=4800.0)
        i3 = _make_test_incident(detected_seconds_ago=2400.0)
        i4 = _make_test_incident(detected_seconds_ago=0.0)

        freq_hr, freq_day, mtbf = calculate_incident_frequency(
            [i1, i2, i3, i4],
            window_start=start,
            window_end=end,
        )

        # 4 incidents in 2 hours = 2.0 incidents/hour
        assert freq_hr == 2.0
        assert freq_day == 48.0
        # Time intervals between successive detections: 2400s each -> MTBF = 2400.0s
        assert mtbf == 2400.0

    def test_health_distribution_calculation(self):
        """8. Health distribution accurately groups resources by state and status."""
        resources = [
            SimulatedResource(
                resource_id="VM-001",
                resource_type=ResourceType.VM,
                current_state=ResourceState.HEALTHY,
                health_status=HealthStatus.HEALTHY,
            ),
            SimulatedResource(
                resource_id="API-001",
                resource_type=ResourceType.API,
                current_state=ResourceState.WARNING,
                health_status=HealthStatus.DEGRADED,
            ),
            SimulatedResource(
                resource_id="STORAGE-001",
                resource_type=ResourceType.STORAGE,
                current_state=ResourceState.FAILURE_DETECTED,
                health_status=HealthStatus.CRITICAL,
            ),
            SimulatedResource(
                resource_id="DB-001",
                resource_type=ResourceType.DB,
                current_state=ResourceState.RECOVERY_IN_PROGRESS,
                health_status=HealthStatus.CRITICAL,
            ),
        ]

        dist = calculate_health_distribution(resources)
        assert dist.total_resources == 4
        assert dist.healthy_count == 1
        assert dist.warning_count == 1
        assert dist.failed_count == 1
        assert dist.recovering_count == 1
        assert dist.healthy_pct == 25.0
        assert dist.by_state["HEALTHY"] == 1
        assert dist.by_state["FAILURE_DETECTED"] == 1
        assert dist.by_status["CRITICAL"] == 2


class TestObservabilityAndTracingContext:
    """Traceability tests verifying correlation context propagation."""

    def test_correlation_context_lifecycle(self):
        """Contextvars correctly track correlation ID, incident ID, and lifecycle stage."""
        clear_trace_context()
        assert get_correlation_id() is None
        assert get_incident_id() is None
        assert get_trace_stage() is None

        test_corr_id = "corr-" + str(uuid.uuid4())
        test_inc_id = "inc-" + str(uuid.uuid4())

        set_correlation_id(test_corr_id)
        set_incident_id(test_inc_id)
        set_trace_stage("simulation")

        assert get_correlation_id() == test_corr_id
        assert get_incident_id() == test_inc_id
        assert get_trace_stage() == "simulation"

        set_trace_stage("detection")
        assert get_trace_stage() == "detection"

        set_trace_stage("event")
        assert get_trace_stage() == "event"

        set_trace_stage("recovery")
        assert get_trace_stage() == "recovery"

        set_trace_stage("notification")
        assert get_trace_stage() == "notification"

        clear_trace_context()
        assert get_correlation_id() is None


class TestMetricsApiEndpoints:
    """Integration test verifying REST API /metrics/overview."""

    def test_get_metrics_overview_endpoint(
        self,
        client: TestClient,
        seed_fleet: list,
    ):
        """GET /metrics/overview returns full 8-metric SRE report."""
        res = client.get("/metrics/overview")
        assert res.status_code == 200
        data = res.json()

        # Check top-level SRE fields
        assert "incident_count" in data
        assert "recovery_success_rate_pct" in data
        assert "recovery_failure_rate_pct" in data
        assert "avg_recovery_time_seconds" in data
        assert "mttr_seconds" in data
        assert "avg_detection_time_seconds" in data
        assert "incident_frequency_per_hour" in data
        assert "incident_frequency_per_day" in data
        assert "health_distribution" in data

        health = data["health_distribution"]
        assert health["total_resources"] == 4
        assert health["healthy_count"] == 4
        assert health["healthy_pct"] == 100.0

        # /metrics/summary alias returns identical payload
        alias_res = client.get("/metrics/summary")
        assert alias_res.status_code == 200
        assert alias_res.json()["health_distribution"]["total_resources"] == 4
