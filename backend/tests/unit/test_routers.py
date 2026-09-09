"""Unit tests for FastAPI routers using TestClient."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.reliability_metric import MetricWindowType, ReliabilityMetric
from app.models.resource import (
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)
from app.repositories.incident_repository import IncidentRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.resource_repository import ResourceRepository


def test_health_liveness(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "cloudpulse-api"


def test_health_readiness_success(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_health_readiness_failure(client: TestClient, monkeypatch):
    def mock_list(*args, **kwargs):
        raise RuntimeError("DynamoDB down")

    monkeypatch.setattr(ResourceRepository, "list", mock_list)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert "DynamoDB unreachable" in response.json()["detail"]


def test_resources_endpoints(client: TestClient):
    # Empty list
    res = client.get("/resources")
    assert res.status_code == 200
    assert res.json() == []

    # Seed a resource
    repo = ResourceRepository()
    resource = SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        health_status=HealthStatus.HEALTHY,
        cpu_utilization=15.0,
        memory_utilization=25.0,
        storage_utilization=35.0,
        network_latency_ms=45.0,
    )
    repo.put(resource)

    # List resources
    res = client.get("/resources")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["resource_id"] == "VM-001"
    assert items[0]["cpu_utilization"] == 15.0

    # Get single resource
    res = client.get("/resources/VM-001")
    assert res.status_code == 200
    data = res.json()
    assert data["resource_id"] == "VM-001"
    assert data["resource_type"] == "VM"

    # Get single resource case insensitive URL
    res = client.get("/resources/vm-001")
    assert res.status_code == 200
    assert res.json()["resource_id"] == "VM-001"

    # 404 for non-existent
    res = client.get("/resources/VM-999")
    assert res.status_code == 404
    err = res.json()
    assert err["error_code"] == "RESOURCE_NOT_FOUND"

    # 422 for invalid format
    res = client.get("/resources/@@@INVALID")
    assert res.status_code == 422


def test_incidents_endpoints(client: TestClient):
    # Empty list
    res = client.get("/incidents")
    assert res.status_code == 200
    assert res.json() == []

    # Create incident
    repo = IncidentRepository()
    inc_id = str(uuid.uuid4())
    incident = Incident(
        incident_id=inc_id,
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        state_at_detection=ResourceState.FAILURE_DETECTED,
    )
    repo.create(incident)

    # List incidents
    res = client.get("/incidents")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["incident_id"] == inc_id

    # Filter incidents by resource_id
    res = client.get("/incidents?resource_id=VM-001")
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = client.get("/incidents?resource_id=NONEXISTENT")
    assert res.status_code == 200
    assert len(res.json()) == 0

    # Filter by status
    res = client.get("/incidents?status=OPEN")
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = client.get("/incidents?status=RESOLVED")
    assert res.status_code == 200
    assert len(res.json()) == 0

    # Get single incident
    res = client.get(f"/incidents/{inc_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["incident_id"] == inc_id
    assert data["status"] == "OPEN"

    # 404 for non-existent
    missing_id = str(uuid.uuid4())
    res = client.get(f"/incidents/{missing_id}")
    assert res.status_code == 404
    assert res.json()["error_code"] == "INCIDENT_NOT_FOUND"

    # 422 for invalid UUID format
    res = client.get("/incidents/not-a-uuid")
    assert res.status_code == 422


def test_metrics_endpoints(client: TestClient):
    # Empty list
    res = client.get("/metrics")
    assert res.status_code == 200
    assert res.json() == []

    # Create metric snapshot
    repo = MetricRepository()
    now = datetime.now(UTC)
    metric = ReliabilityMetric(
        resource_id="VM-001",
        window_key="DAILY#2026-09-08",
        window_type=MetricWindowType.DAILY,
        window_start=now - timedelta(hours=24),
        window_end=now,
        total_incidents=3,
        resolved_incidents=3,
        failed_recoveries=0,
        mttr_seconds=6.5,
        mtbf_seconds=1200.0,
        availability_pct=99.95,
        failure_type_counts={"HIGH_CPU": 3},
    )
    repo.put(metric)

    # List metrics
    res = client.get("/metrics")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["resource_id"] == "VM-001"
    assert items[0]["mttr_seconds"] == 6.5

    # Get latest metric for resource
    res = client.get("/metrics/VM-001")
    assert res.status_code == 200
    data = res.json()
    assert data["resource_id"] == "VM-001"
    assert data["window_key"] == "DAILY#2026-09-08"

    # Get specific snapshot by window_key (URL-encode # as %23)
    from urllib.parse import quote

    encoded_key = quote("DAILY#2026-09-08", safe="")
    res = client.get(f"/metrics/VM-001/{encoded_key}")
    assert res.status_code == 200
    assert res.json()["resource_id"] == "VM-001"

    # 404 for non-existent latest metric
    res = client.get("/metrics/NONEXISTENT")
    assert res.status_code == 404
    assert res.json()["error_code"] == "METRIC_NOT_FOUND"

    # 404 for non-existent window_key
    non_existent_key = quote("DAILY#1999-01-01", safe="")
    res = client.get(f"/metrics/VM-001/{non_existent_key}")
    assert res.status_code == 404
    assert res.json()["error_code"] == "METRIC_NOT_FOUND"

    # 422 for invalid window_key
    res = client.get("/metrics/VM-001/INVALID_WINDOW_KEY")
    assert res.status_code == 422
