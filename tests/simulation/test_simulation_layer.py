"""
Layer 5: Failure Simulation Tests
Tests failure simulation engine for all 5 scenarios (FS-01 to FS-05).
"""

import pytest

from app.models.incident import IncidentSeverity, IncidentStatus
from app.models.resource import FailureType, HealthStatus, ResourceState
from app.services.simulation_service import SimulationService


class TestSimulationLayer:
    """Failure simulation scenario tests."""

    @pytest.mark.parametrize(
        "scenario_code,failure_type,resource_id,expected_metric,threshold",
        [
            ("FS-01", FailureType.HIGH_CPU, "VM-001", "cpu_utilization", 85.0),
            ("FS-02", FailureType.SERVICE_FAILURE, "API-001", "network_latency_ms", 500.0),
            ("FS-03", FailureType.STORAGE_EXHAUSTION, "STORAGE-001", "storage_utilization", 90.0),
            ("FS-04", FailureType.NETWORK_LATENCY, "VM-001", "network_latency_ms", 500.0),
            ("FS-05", FailureType.SERVICE_DOWNTIME, "DB-001", "network_latency_ms", 500.0),
        ],
    )
    def test_all_five_scenarios_breach_thresholds(
        self,
        seed_fleet: list,
        scenario_code: str,
        failure_type: FailureType,
        resource_id: str,
        expected_metric: str,
        threshold: float,
    ):
        """Every failure scenario triggers metric values that breach alarm thresholds."""
        svc = SimulationService()
        resource, incident, emitted = svc.inject_failure(
            resource_id=resource_id,
            failure_type=failure_type,
        )

        assert resource.current_state == ResourceState.FAILURE_DETECTED
        assert resource.health_status == HealthStatus.CRITICAL
        assert resource.active_failure_type == failure_type

        # Verify metric breaches the threshold
        actual_metric_val = getattr(resource, expected_metric)
        assert actual_metric_val >= threshold

        # Verify incident record was created
        assert incident.resource_id == resource_id
        assert incident.failure_type == failure_type
        assert incident.status == IncidentStatus.OPEN

        # Verify CloudWatch emitted payload
        assert len(emitted) > 0

    def test_parameter_overrides_in_simulation(self, seed_fleet: list):
        """Simulation allows explicit metric parameter overrides."""
        svc = SimulationService()
        resource, incident, _ = svc.inject_failure(
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.CRITICAL,
            parameters={"cpu_utilization": 99.4},
        )
        assert resource.cpu_utilization == 99.4
        assert incident.severity == IncidentSeverity.CRITICAL

    def test_state_guard_prevents_double_injection(self, seed_fleet: list):
        """Injecting failure on already degraded resource raises SimulationError."""
        from app.exceptions import SimulationError

        svc = SimulationService()
        svc.inject_failure("VM-001", FailureType.HIGH_CPU)

        with pytest.raises(SimulationError) as exc:
            svc.inject_failure("VM-001", FailureType.HIGH_CPU)
        assert "Cannot inject failure" in str(exc.value)
