"""Unit tests for domain services."""

import uuid
from datetime import UTC, datetime, timedelta

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
from app.services.incident_service import IncidentService
from app.services.metric_service import MetricService
from app.services.resource_service import ResourceService


def test_resource_service(mock_all_tables):
    repo = ResourceRepository()
    svc = ResourceService(repo=repo)

    r = SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        health_status=HealthStatus.HEALTHY,
        cpu_utilization=10.0,
        memory_utilization=20.0,
        storage_utilization=30.0,
        network_latency_ms=40.0,
    )
    repo.put(r)

    # Test list_resources
    summaries = svc.list_resources()
    assert len(summaries) == 1
    assert summaries[0].resource_id == "VM-001"
    assert summaries[0].cpu_utilization == 10.0

    # Test get_resource
    res = svc.get_resource("VM-001")
    assert res.resource_id == "VM-001"


def test_incident_service(mock_all_tables):
    repo = IncidentRepository()
    svc = IncidentService(repo=repo)
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

    # Test list_incidents
    summaries = svc.list_incidents(resource_id="VM-001")
    assert len(summaries) == 1
    assert summaries[0].incident_id == inc_id

    # Test get_incident
    detail = svc.get_incident(inc_id)
    assert detail.incident_id == inc_id
    assert detail.status == IncidentStatus.OPEN
    assert detail.recovery_actions == []


def test_metric_service(mock_all_tables):
    repo = MetricRepository()
    svc = MetricService(repo=repo)
    now = datetime.now(UTC)

    metric = ReliabilityMetric(
        resource_id="VM-001",
        window_key="DAILY#2026-09-08",
        window_type=MetricWindowType.DAILY,
        window_start=now - timedelta(hours=24),
        window_end=now,
        total_incidents=1,
        resolved_incidents=1,
        failed_recoveries=0,
        mttr_seconds=5.0,
        availability_pct=99.9,
        failure_type_counts={"HIGH_CPU": 1},
    )
    repo.put(metric)

    # Test list_metrics
    summaries = svc.list_metrics(resource_id="VM-001")
    assert len(summaries) == 1
    assert summaries[0].resource_id == "VM-001"

    # Test get_metric
    m = svc.get_metric("VM-001", "DAILY#2026-09-08")
    assert m.resource_id == "VM-001"

    # Test get_latest_metric
    latest = svc.get_latest_metric("VM-001", MetricWindowType.DAILY)
    assert latest is not None
    assert latest.window_key == "DAILY#2026-09-08"
