"""
End-to-end API integration tests verifying the exact contracts and flows
expected by the React dashboard:
- GET /health and GET /health/ready
- GET /resources and GET /resources/{id}
- GET /incidents and GET /incidents/{id}
- GET /metrics and GET /metrics/{id}
- POST /simulate/failure (injected failure lifecycle)
- POST /simulate/recover and POST /simulate/reset/{id}
"""

import pytest
from fastapi.testclient import TestClient

from app.models.resource import (
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)
from app.repositories.resource_repository import ResourceRepository


@pytest.fixture
def seeded_resources(mock_all_tables) -> list[SimulatedResource]:
    """Seed initial resources into mocked DynamoDB."""
    repo = ResourceRepository()
    resources = [
        SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            current_state=ResourceState.HEALTHY,
            health_status=HealthStatus.HEALTHY,
            cpu_utilization=25.0,
            memory_utilization=30.0,
            storage_utilization=20.0,
            network_latency_ms=15.0,
        ),
        SimulatedResource(
            resource_id="API-001",
            resource_type=ResourceType.API,
            current_state=ResourceState.HEALTHY,
            health_status=HealthStatus.HEALTHY,
            cpu_utilization=18.0,
            memory_utilization=40.0,
            storage_utilization=10.0,
            network_latency_ms=22.0,
        ),
    ]
    for r in resources:
        repo.put(r)
    return resources


def test_dashboard_initial_load_flow(client: TestClient, seeded_resources: list[SimulatedResource]):
    """
    Simulate the initial Dashboard mount sequence:
    1. Check API health & readiness
    2. Fetch all resources
    3. Fetch all incidents (initially empty)
    4. Fetch reliability metrics
    """
    # 1. Health check
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"

    # 2. Resources list
    res_list = client.get("/resources")
    assert res_list.status_code == 200
    resources = res_list.json()
    assert len(resources) == 2
    ids = {r["resource_id"] for r in resources}
    assert "VM-001" in ids
    assert "API-001" in ids

    # Single resource inspection
    vm_res = client.get("/resources/VM-001")
    assert vm_res.status_code == 200
    assert vm_res.json()["current_state"] == "HEALTHY"
    assert vm_res.json()["cpu_utilization"] == 25.0

    # 3. Incidents list
    inc_list = client.get("/incidents")
    assert inc_list.status_code == 200
    assert inc_list.json() == []

    # 4. Metrics list
    met_list = client.get("/metrics")
    assert met_list.status_code == 200
    assert isinstance(met_list.json(), list)


def test_dashboard_failure_to_recovery_lifecycle_flow(
    client: TestClient, seeded_resources: list[SimulatedResource]
):
    """
    Simulate the full 5-stage failure simulator lifecycle:
    Stage 1: HEALTHY (initial baseline)
    Stage 2: Inject failure via POST /simulate/failure
    Stage 3: Verify FAILURE_DETECTED state and new incident created
    Stage 4: Verify incident detail retrieval
    Stage 5: Recovery via POST /simulate/recover -> resource restored to HEALTHY, incident resolved
    """
    # 1. Verify initially HEALTHY
    vm_before = client.get("/resources/VM-001").json()
    assert vm_before["current_state"] == "HEALTHY"
    assert vm_before["health_status"] == "HEALTHY"

    # 2. Inject failure scenario FS-01 (High CPU)
    inject_res = client.post(
        "/simulate/failure",
        json={
            "resourceId": "VM-001",
            "failureType": "HIGH_CPU",
            "severity": "HIGH",
            "parameters": {"cpu_utilization": 98.5},
        },
    )
    assert inject_res.status_code == 201
    inject_data = inject_res.json()
    assert inject_data["scenario_id"] == "FS-01"
    assert inject_data["resource"]["current_state"] == "FAILURE_DETECTED"
    assert inject_data["resource"]["cpu_utilization"] == 98.5
    incident_id = inject_data["incident"]["incident_id"]
    assert incident_id is not None

    # 3. Query resources — VM-001 is now degraded/failed
    resources_after = client.get("/resources").json()
    vm_after = next(r for r in resources_after if r["resource_id"] == "VM-001")
    assert vm_after["current_state"] == "FAILURE_DETECTED"
    assert vm_after["active_failure_type"] == "HIGH_CPU"

    # 4. Query incidents — 1 active incident
    incidents = client.get("/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["incident_id"] == incident_id
    assert incidents[0]["status"] == "OPEN"
    assert incidents[0]["resource_id"] == "VM-001"

    # Query incident by ID
    incident_detail = client.get(f"/incidents/{incident_id}").json()
    assert incident_detail["incident_id"] == incident_id
    assert incident_detail["failure_type"] == "HIGH_CPU"
    assert incident_detail["severity"] == "HIGH"

    # 5. Recover resource via POST /simulate/recover
    recover_res = client.post("/simulate/recover", json={"resourceId": "VM-001"})
    assert recover_res.status_code == 200
    recover_data = recover_res.json()
    assert recover_data["resource"]["current_state"] == "HEALTHY"
    assert incident_id in recover_data["resolved_incidents"]

    # 6. Verify VM-001 is HEALTHY and metrics reset
    vm_recovered = client.get("/resources/VM-001").json()
    assert vm_recovered["current_state"] == "HEALTHY"
    assert vm_recovered["active_failure_type"] is None
    assert vm_recovered["cpu_utilization"] == 25.0

    # 7. Verify incident is now RESOLVED
    incidents_final = client.get("/incidents").json()
    assert len(incidents_final) == 1
    assert incidents_final[0]["status"] == "RESOLVED"


def test_dashboard_reset_by_path_flow(
    client: TestClient, seeded_resources: list[SimulatedResource]
):
    """Test manual reset via /simulate/reset/{id} path endpoint."""
    # Inject
    client.post(
        "/simulate/failure",
        json={"resourceId": "API-001", "failureType": "SERVICE_FAILURE"},
    )
    # Reset
    reset_res = client.post("/simulate/reset/API-001")
    assert reset_res.status_code == 200
    assert reset_res.json()["resource"]["current_state"] == "HEALTHY"

    # Verify resource restored
    api_res = client.get("/resources/API-001").json()
    assert api_res["current_state"] == "HEALTHY"
