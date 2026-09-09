"""
Unit tests for the CloudPulse failure simulation engine.

Covers all 5 failure scenarios:
- FS-01: High CPU Utilization
- FS-02: Service Failure
- FS-03: Storage Exhaustion
- FS-04: Network Latency
- FS-05: Service Downtime

Also verifies:
- State machine protection (cannot double-inject without reset)
- Custom parameter overrides
- CloudWatch metric publishing
- Incident creation and linking
- Manual resource reset/recovery
- API route behavior and HTTP status codes
"""

import pytest
from fastapi.testclient import TestClient

from app.models.incident import IncidentSeverity, IncidentStatus
from app.models.resource import (
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)
from app.services.monitoring_service import MonitoringService
from app.services.simulation_service import SimulationService
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.simulation_service import SimulationService


@pytest.fixture
def sample_resource(mock_all_tables) -> SimulatedResource:
    """Create and persist a healthy VM-001 resource."""
    repo = ResourceRepository()
    resource = SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        health_status=HealthStatus.HEALTHY,
        cpu_utilization=25.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
    )
    repo.put(resource)
    return resource


# ═════════════════════════════════════════════════════════════════════════════
# Service Level Failure Scenario Tests (FS-01 to FS-05)
# ═════════════════════════════════════════════════════════════════════════════


def test_scenario_fs01_high_cpu(sample_resource: SimulatedResource):
    """FS-01: High CPU Utilization spikes CPU above failure threshold."""
    svc = SimulationService()
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.HIGH_CPU)

    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert res.health_status == HealthStatus.CRITICAL
    assert res.active_failure_type == FailureType.HIGH_CPU
    assert res.cpu_utilization == 92.0

    # Incident created
    assert inc.resource_id == "VM-001"
    assert inc.failure_type == FailureType.HIGH_CPU
    assert inc.severity == IncidentSeverity.HIGH
    assert inc.status == IncidentStatus.OPEN
    assert inc.state_at_detection == ResourceState.FAILURE_DETECTED

    # CloudWatch metrics emitted
    assert metrics["CPUUtilization"] == 92.0


def test_scenario_fs02_service_failure(sample_resource: SimulatedResource):
    """FS-02: Service Failure spikes network latency to failure level."""
    svc = SimulationService()
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.SERVICE_FAILURE)

    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert res.health_status == HealthStatus.CRITICAL
    assert res.active_failure_type == FailureType.SERVICE_FAILURE
    assert res.network_latency_ms == 980.0

    assert inc.severity == IncidentSeverity.CRITICAL
    assert inc.status == IncidentStatus.OPEN
    assert metrics["NetworkLatency"] == 980.0


def test_scenario_fs03_storage_exhaustion(sample_resource: SimulatedResource):
    """FS-03: Storage Exhaustion spikes storage above 90% threshold."""
    svc = SimulationService()
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.STORAGE_EXHAUSTION)

    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert res.health_status == HealthStatus.CRITICAL
    assert res.active_failure_type == FailureType.STORAGE_EXHAUSTION
    assert res.storage_utilization == 96.0

    assert inc.severity == IncidentSeverity.MEDIUM
    assert inc.status == IncidentStatus.OPEN
    assert metrics["StorageUtilization"] == 96.0


def test_scenario_fs04_network_latency(sample_resource: SimulatedResource):
    """FS-04: Network Latency spikes latency to 750ms."""
    svc = SimulationService()
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.NETWORK_LATENCY)

    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert res.health_status == HealthStatus.CRITICAL
    assert res.active_failure_type == FailureType.NETWORK_LATENCY
    assert res.network_latency_ms == 750.0

    assert inc.severity == IncidentSeverity.MEDIUM
    assert metrics["NetworkLatency"] == 750.0


def test_scenario_fs05_service_downtime(sample_resource: SimulatedResource):
    """FS-05: Service Downtime drops CPU/memory to 0 and raises latency to 9999ms."""
    svc = SimulationService()
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.SERVICE_DOWNTIME)

    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert res.health_status == HealthStatus.CRITICAL
    assert res.active_failure_type == FailureType.SERVICE_DOWNTIME
    assert res.cpu_utilization == 0.0
    assert res.network_latency_ms == 9999.0

    assert inc.severity == IncidentSeverity.CRITICAL
    assert metrics["CPUUtilization"] == 0.0
    assert metrics["NetworkLatency"] == 9999.0


def test_parameter_overrides(sample_resource: SimulatedResource):
    """Custom parameter overrides customize deterministic metric values."""
    svc = SimulationService()
    res, inc, _ = svc.inject_failure(
        "VM-001",
        FailureType.HIGH_CPU,
        severity=IncidentSeverity.CRITICAL,
        parameters={"cpu_utilization": 99.5},
    )

    assert res.cpu_utilization == 99.5
    assert inc.severity == IncidentSeverity.CRITICAL


def test_state_machine_prevents_double_failure(sample_resource: SimulatedResource):
    """Simulation state machine prevents injecting on already-failed resource."""
    from app.exceptions import SimulationError

    svc = SimulationService()
    svc.inject_failure("VM-001", FailureType.HIGH_CPU)

    with pytest.raises(SimulationError, match="Reset the resource before injecting a new failure"):
        svc.inject_failure("VM-001", FailureType.STORAGE_EXHAUSTION)


def test_reset_resource(sample_resource: SimulatedResource):
    """Manual reset returns resource to HEALTHY and resolves open incidents."""
    svc = SimulationService()
    _, inc, _ = svc.inject_failure("VM-001", FailureType.HIGH_CPU)

    reset_res, resolved_ids = svc.reset_resource("VM-001")
    assert reset_res.current_state == ResourceState.HEALTHY
    assert reset_res.health_status == HealthStatus.HEALTHY
    assert reset_res.active_failure_type is None
    assert reset_res.cpu_utilization == 25.0
    assert inc.incident_id in resolved_ids

    # Verify incident in repo is now RESOLVED
    inc_repo = IncidentRepository()
    resolved_inc = inc_repo.get(inc.incident_id)
    assert resolved_inc.status == IncidentStatus.RESOLVED
    assert resolved_inc.state_at_resolution == ResourceState.RECOVERED
    assert len(resolved_inc.recovery_actions) == 1
    assert resolved_inc.recovery_actions[0].action_type == "MANUAL"


# ═════════════════════════════════════════════════════════════════════════════
# API Route Tests (POST /simulate/failure and POST /simulate/reset)
# ═════════════════════════════════════════════════════════════════════════════


def test_api_simulate_failure_fs01_enum(client: TestClient, sample_resource: SimulatedResource):
    """POST /simulate/failure with enum string."""
    payload = {
        "resourceId": "VM-001",
        "failureType": "HIGH_CPU",
    }
    response = client.post("/simulate/failure", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["scenario_id"] == "FS-01"
    assert data["scenario_name"] == "FS-01 High CPU Utilization"
    assert data["resource"]["current_state"] == "FAILURE_DETECTED"
    assert data["incident"]["status"] == "OPEN"
    assert data["metrics_emitted"]["CPUUtilization"] == 92.0


def test_api_simulate_failure_fs02_scenario_code(
    client: TestClient, sample_resource: SimulatedResource
):
    """POST /simulate/failure using scenario code 'FS-02'."""
    payload = {
        "resourceId": "VM-001",
        "failureType": "FS-02",
        "severity": "CRITICAL",
    }
    response = client.post("/simulate/failure", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["scenario_id"] == "FS-02"
    assert data["incident"]["severity"] == "CRITICAL"


def test_api_simulate_failure_not_found(client: TestClient):
    """POST /simulate/failure with non-existent resource returns 404."""
    payload = {
        "resourceId": "NONEXISTENT-999",
        "failureType": "HIGH_CPU",
    }
    response = client.post("/simulate/failure", json=payload)
    assert response.status_code == 404
    assert response.json()["error_code"] == "RESOURCE_NOT_FOUND"


def test_api_simulate_failure_conflict(client: TestClient, sample_resource: SimulatedResource):
    """POST /simulate/failure on an already failed resource returns 409 Conflict."""
    payload = {"resourceId": "VM-001", "failureType": "HIGH_CPU"}
    res1 = client.post("/simulate/failure", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/simulate/failure", json=payload)
    assert res2.status_code == 409
    assert res2.json()["error_code"] == "SIMULATION_ERROR"


def test_api_simulate_reset_endpoints(client: TestClient, sample_resource: SimulatedResource):
    """POST /simulate/reset/{id} and POST /simulate/recover."""
    # Inject failure first
    client.post("/simulate/failure", json={"resourceId": "VM-001", "failureType": "HIGH_CPU"})

    # Reset via path
    res = client.post("/simulate/reset/VM-001")
    assert res.status_code == 200
    assert res.json()["resource"]["current_state"] == "HEALTHY"
    assert len(res.json()["resolved_incidents"]) == 1

    # Inject again
    client.post("/simulate/failure", json={"resourceId": "VM-001", "failureType": "FS-03"})

    # Reset via body
    res_body = client.post("/simulate/reset", json={"resourceId": "VM-001"})
    assert res_body.status_code == 200
    assert res_body.json()["resource"]["current_state"] == "HEALTHY"

    # Alias /simulate/recover
    client.post("/simulate/failure", json={"resourceId": "VM-001", "failureType": "FS-04"})
    res_recover = client.post("/simulate/recover", json={"resourceId": "VM-001"})
    assert res_recover.status_code == 200
    assert res_recover.json()["resource"]["current_state"] == "HEALTHY"


def test_api_simulate_inject_alias(client: TestClient, sample_resource: SimulatedResource):
    """POST /simulate/inject works as a backward-compatible alias."""
    payload = {"resourceId": "VM-001", "failureType": "FS-01 High CPU Utilization"}
    res = client.post("/simulate/inject", json=payload)
    assert res.status_code == 201
    assert res.json()["scenario_id"] == "FS-01"


def test_cloudwatch_error_graceful(sample_resource: SimulatedResource):
    """Simulated failure injection succeeds even if CloudWatch put_metric_data raises an error."""

    class BrokenCW:
        def put_metric_data(self, *args, **kwargs):
            raise RuntimeError("CloudWatch service unavailable")

    broken_monitoring = MonitoringService(cloudwatch_client=BrokenCW())
    svc = SimulationService(monitoring_service=broken_monitoring)
    res, inc, metrics = svc.inject_failure("VM-001", FailureType.HIGH_CPU)
    assert res.current_state == ResourceState.FAILURE_DETECTED
    assert inc.status == IncidentStatus.OPEN
    assert "CPUUtilization" in metrics
