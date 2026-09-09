"""
Layer 2: API Tests
Tests all FastAPI REST endpoints, routing, serialization, filters, and HTTP status codes.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.reliability_metric import MetricWindowType, ReliabilityMetric
from app.repositories.incident_repository import IncidentRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.resource_repository import ResourceRepository


class TestApiLayer:
    """REST API endpoint tests using TestClient."""

    def test_health_endpoints(self, client: TestClient):
        """GET /health and GET /health/ready return 200 OK."""
        liveness = client.get("/health")
        assert liveness.status_code == 200
        assert liveness.json()["status"] == "ok"

        readiness = client.get("/health/ready")
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "ready"

    def test_resources_endpoints(self, client: TestClient, seed_fleet: list):
        """GET /resources lists fleet; GET /resources/{id} retrieves detail."""
        res = client.get("/resources")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 4
        ids = {r["resource_id"] for r in data}
        assert "VM-001" in ids

        single = client.get("/resources/VM-001")
        assert single.status_code == 200
        assert single.json()["resource_id"] == "VM-001"

        # 404 on missing
        assert client.get("/resources/MISSING-999").status_code == 404

        # 422 on invalid regex
        assert client.get("/resources/invalid@id").status_code == 422

    def test_incidents_endpoints(self, client: TestClient, seed_fleet: list):
        """GET /incidents supports filtering by resource, status, failure type."""
        repo = IncidentRepository()
        inc_id = str(uuid.uuid4())
        inc = Incident(
            incident_id=inc_id,
            resource_id="VM-001",
            failure_type="HIGH_CPU",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection="FAILURE_DETECTED",
        )
        repo.create(inc)

        # List all
        res = client.get("/incidents")
        assert res.status_code == 200
        assert len(res.json()) >= 1

        # Filter by resource
        res_filter = client.get("/incidents?resource_id=VM-001")
        assert res_filter.status_code == 200
        assert len(res_filter.json()) == 1

        # Filter by status
        status_filter = client.get("/incidents?status=OPEN")
        assert len(status_filter.json()) >= 1

        # Detail by UUID
        detail = client.get(f"/incidents/{inc_id}")
        assert detail.status_code == 200
        assert detail.json()["incident_id"] == inc_id

        # 422 on malformed UUID
        assert client.get("/incidents/not-a-valid-uuid").status_code == 422

    def test_metrics_endpoints(self, client: TestClient, seed_fleet: list):
        """GET /metrics returns reliability metric snapshots."""
        repo = MetricRepository()
        now = datetime.now(UTC)
        metric = ReliabilityMetric(
            resource_id="VM-001",
            window_key="DAILY#2026-09-09",
            window_type=MetricWindowType.DAILY,
            window_start=now - timedelta(hours=24),
            window_end=now,
            total_incidents=2,
            resolved_incidents=2,
            failed_recoveries=0,
            mttr_seconds=8.5,
            mtbf_seconds=1800.0,
            availability_pct=99.99,
        )
        repo.put(metric)

        res = client.get("/metrics")
        assert res.status_code == 200
        assert len(res.json()) >= 1

        latest = client.get("/metrics/VM-001")
        assert latest.status_code == 200
        assert latest.json()["resource_id"] == "VM-001"

    def test_simulation_failure_and_recovery_endpoints(self, client: TestClient, seed_fleet: list):
        """POST /simulate/failure and POST /simulate/recover perform state machine actions."""
        # Inject
        inject_res = client.post(
            "/simulate/failure",
            json={"resourceId": "VM-001", "failureType": "HIGH_CPU"},
        )
        assert inject_res.status_code == 201
        data = inject_res.json()
        assert data["resource"]["current_state"] == "FAILURE_DETECTED"

        # Conflict on double injection without reset
        conflict_res = client.post(
            "/simulate/failure",
            json={"resourceId": "VM-001", "failureType": "HIGH_CPU"},
        )
        assert conflict_res.status_code == 409

        # Recover via /simulate/recover
        recover_res = client.post("/simulate/recover", json={"resourceId": "VM-001"})
        assert recover_res.status_code == 200
        assert recover_res.json()["resource"]["current_state"] == "HEALTHY"

        # Reset via path /simulate/reset/{id}
        client.post("/simulate/failure", json={"resourceId": "VM-001", "failureType": "FS-01"})
        reset_res = client.post("/simulate/reset/VM-001")
        assert reset_res.status_code == 200
        assert reset_res.json()["resource"]["current_state"] == "HEALTHY"
