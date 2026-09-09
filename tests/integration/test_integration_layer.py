"""
Layer 3: Integration Tests
Tests integration between domain services and DynamoDB repositories.
"""

from datetime import UTC, datetime, timedelta

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.reliability_metric import MetricWindowType, ReliabilityMetric
from app.models.resource import FailureType, HealthStatus, ResourceState, ResourceType, SimulatedResource
from app.repositories.incident_repository import IncidentRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.incident_service import IncidentService
from app.services.metric_service import MetricService
from app.services.resource_service import ResourceService
from app.services.simulation_service import SimulationService


class TestIntegrationLayer:
    """Service-to-repository integration tests."""

    def test_resource_service_and_repository_integration(self, seed_fleet: list):
        """ResourceService queries ResourceRepository and returns hydrated domain objects."""
        svc = ResourceService()
        resources = svc.list_resources()
        assert len(resources) == 4

        vm = svc.get_resource("VM-001")
        assert vm.resource_id == "VM-001"
        assert vm.current_state == ResourceState.HEALTHY

    def test_incident_service_query_and_aggregation_integration(self, mock_aws_env: dict):
        """IncidentService creates, retrieves, and filters incidents via IncidentRepository."""
        repo = IncidentRepository()
        svc = IncidentService(repo=repo)

        now = datetime.now(UTC)
        # Create 3 incidents across 2 resources
        i1 = Incident(
            incident_id="11111111-1111-4111-8111-111111111111",
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
        )
        i2 = Incident(
            incident_id="22222222-2222-4222-8222-222222222222",
            resource_id="VM-001",
            failure_type=FailureType.NETWORK_LATENCY,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.RESOLVED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            detected_at=now - timedelta(seconds=60),
            resolved_at=now,
        )
        i3 = Incident(
            incident_id="33333333-3333-4333-8333-333333333333",
            resource_id="API-001",
            failure_type=FailureType.SERVICE_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
        )
        repo.create(i1)
        repo.create(i2)
        repo.create(i3)

        # Filter by resource
        vm_incidents = svc.list_incidents(resource_id="VM-001")
        assert len(vm_incidents) == 2

        # Filter by status
        open_incidents = svc.list_incidents(status=IncidentStatus.OPEN)
        assert len(open_incidents) == 2

    def test_metric_service_and_repository_integration(self, mock_aws_env: dict):
        """MetricService reads from MetricRepository across window types."""
        repo = MetricRepository()
        svc = MetricService(repo=repo)

        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        repo.put(
            ReliabilityMetric(
                resource_id="DB-001",
                window_key="DAILY#2026-09-09",
                window_type=MetricWindowType.DAILY,
                window_start=now - timedelta(days=1),
                window_end=now,
                total_incidents=1,
                resolved_incidents=1,
                availability_pct=99.99,
            )
        )
        repo.put(
            ReliabilityMetric(
                resource_id="DB-001",
                window_key="CUMULATIVE#ALL",
                window_type=MetricWindowType.CUMULATIVE,
                window_start=now - timedelta(days=30),
                window_end=now,
                total_incidents=4,
                resolved_incidents=4,
                availability_pct=99.95,
            )
        )

        daily = svc.get_latest_metric("DB-001", MetricWindowType.DAILY)
        assert daily is not None
        assert daily.window_key == "DAILY#2026-09-09"

        all_metrics = svc.list_metrics(resource_id="DB-001")
        assert len(all_metrics) == 2

    def test_simulation_service_orchestrates_both_repositories(self, seed_fleet: list):
        """SimulationService inject_failure mutates resource and creates incident in atomic workflow."""
        svc = SimulationService()
        resource, incident, emitted = svc.inject_failure(
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
        )

        assert resource.current_state == ResourceState.FAILURE_DETECTED
        assert incident.status == IncidentStatus.OPEN
        assert incident.resource_id == "VM-001"
        assert "CPUUtilization" in emitted

        # Reset resource resolves the incident
        updated_resource, resolved_ids = svc.reset_resource("VM-001")
        assert updated_resource.current_state == ResourceState.HEALTHY
        assert incident.incident_id in resolved_ids
