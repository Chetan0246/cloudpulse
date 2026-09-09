"""Unit tests for DynamoDB repositories."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.exceptions import IncidentNotFoundError, MetricNotFoundError, ResourceNotFoundError
from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
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


def test_resource_repository_crud(mock_all_tables):
    repo = ResourceRepository()

    # Initial get non-existent
    with pytest.raises(ResourceNotFoundError):
        repo.get("NONEXISTENT")

    # Put resource
    resource = SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        health_status=HealthStatus.HEALTHY,
        cpu_utilization=20.0,
        memory_utilization=30.0,
        storage_utilization=10.0,
        network_latency_ms=12.0,
    )
    repo.put(resource)

    # Get resource
    fetched = repo.get("VM-001")
    assert fetched.resource_id == "VM-001"
    assert fetched.cpu_utilization == 20.0

    # List resources
    all_res = repo.list()
    assert len(all_res) == 1
    assert all_res[0].resource_id == "VM-001"

    # Update state conditionally
    updated = repo.update_state(
        resource_id="VM-001",
        new_state=ResourceState.WARNING,
        condition_state=ResourceState.HEALTHY,
    )
    assert updated.current_state == ResourceState.WARNING

    # Condition fails (expected state is still HEALTHY, but current is WARNING) -> idempotent return
    unchanged = repo.update_state(
        resource_id="VM-001",
        new_state=ResourceState.RECOVERED,
        condition_state=ResourceState.HEALTHY,
    )
    assert unchanged.current_state == ResourceState.WARNING

    # Delete
    repo.delete("VM-001")
    with pytest.raises(ResourceNotFoundError):
        repo.get("VM-001")


def test_incident_repository_crud(mock_all_tables):
    repo = IncidentRepository()
    inc_id = str(uuid.uuid4())

    with pytest.raises(IncidentNotFoundError):
        repo.get(inc_id)

    incident = Incident(
        incident_id=inc_id,
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        state_at_detection=ResourceState.FAILURE_DETECTED,
    )
    repo.create(incident)

    fetched = repo.get(inc_id)
    assert fetched.incident_id == inc_id
    assert fetched.status == IncidentStatus.OPEN

    # Update incident to resolved
    action = RecoveryAction(
        action_id=str(uuid.uuid4()),
        action_type=RecoveryActionType.SCALE_OUT,
        status=RecoveryActionStatus.SUCCEEDED,
        outcome_message="Added capacity",
    )
    resolved_inc = fetched.model_copy(
        update={
            "status": IncidentStatus.RESOLVED,
            "resolved_at": datetime.now(UTC),
            "state_at_resolution": ResourceState.RECOVERED,
            "recovery_attempts": 1,
            "recovery_actions": [action],
        }
    )
    repo.update(resolved_inc)

    updated_fetched = repo.get(inc_id)
    assert updated_fetched.status == IncidentStatus.RESOLVED
    assert len(updated_fetched.recovery_actions) == 1

    # List with filters
    items = repo.list(resource_id="VM-001", status=IncidentStatus.RESOLVED)
    assert len(items) == 1
    assert items[0].incident_id == inc_id

    # Filter with non-matching status
    items_open = repo.list(resource_id="VM-001", status=IncidentStatus.OPEN)
    assert len(items_open) == 0

    repo.delete(inc_id)
    with pytest.raises(IncidentNotFoundError):
        repo.get(inc_id)


def test_metric_repository_crud(mock_all_tables):
    repo = MetricRepository()
    now = datetime.now(UTC)

    with pytest.raises(MetricNotFoundError):
        repo.get("VM-001", "DAILY#2026-09-08")

    metric = ReliabilityMetric(
        resource_id="VM-001",
        window_key="DAILY#2026-09-08",
        window_type=MetricWindowType.DAILY,
        window_start=now - timedelta(hours=24),
        window_end=now,
        total_incidents=2,
        resolved_incidents=2,
        failed_recoveries=0,
        mttr_seconds=8.5,
        mtbf_seconds=3600.0,
        availability_pct=99.8,
        failure_type_counts={"HIGH_CPU": 2},
    )
    repo.put(metric)

    fetched = repo.get("VM-001", "DAILY#2026-09-08")
    assert fetched.resource_id == "VM-001"
    assert fetched.mttr_seconds == 8.5

    # List metrics
    all_metrics = repo.list(resource_id="VM-001")
    assert len(all_metrics) == 1

    # Get latest
    latest = repo.get_latest("VM-001", MetricWindowType.DAILY)
    assert latest is not None
    assert latest.window_key == "DAILY#2026-09-08"

    # Delete
    repo.delete("VM-001", "DAILY#2026-09-08")
    with pytest.raises(MetricNotFoundError):
        repo.get("VM-001", "DAILY#2026-09-08")
