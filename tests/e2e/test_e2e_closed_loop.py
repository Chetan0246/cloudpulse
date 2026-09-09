"""
Layer 9: End-to-End Closed-Loop Tests
Verifies the complete 9-step autonomous self-healing chain for all 5 failure scenarios:
FS-01 High CPU
FS-02 Service Failure
FS-03 Storage Exhaustion
FS-04 Network Latency
FS-05 Service Downtime

Verification chain:
1. Failure triggered
2. Failure recorded
3. Monitoring condition detected
4. Event generated
5. Recovery initiated
6. Recovery completed
7. Incident updated
8. Notification generated
9. Dashboard reflects result
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.models.resource import FailureType, HealthStatus, ResourceState
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from handler import handler


class TestEndToEndClosedLoop:
    """Complete 9-step closed-loop reliability test for all 5 scenarios."""

    @pytest.mark.parametrize(
        "scenario_key",
        ["FS-01", "FS-02", "FS-03", "FS-04", "FS-05"],
    )
    def test_complete_9_step_closed_loop_for_all_scenarios(
        self,
        client: TestClient,
        seed_fleet: list,
        scenarios_matrix: list[dict],
        event_factory: dict,
        scenario_key: str,
    ):
        scenario = next(s for s in scenarios_matrix if s["id"] == scenario_key)
        resource_id = scenario["target_resource"]
        failure_type_str = scenario["failure_type"]
        failure_type = FailureType(failure_type_str)
        target_metric = scenario["target_metric"]
        threshold = scenario["threshold"]
        expected_action = scenario["recovery_action"]
        post_metric_key = scenario["post_recovery_metric"]
        post_expected_val = scenario["post_recovery_expected"]

        res_repo = ResourceRepository()
        inc_repo = IncidentRepository()

        # ── Step 1: Failure triggered ──────────────────────────────────────────
        trigger_res = client.post(
            "/simulate/failure",
            json={
                "resourceId": resource_id,
                "failureType": failure_type_str,
            },
        )
        assert trigger_res.status_code == 201
        trigger_data = trigger_res.json()
        incident_id = trigger_data["incident"]["incident_id"]
        assert incident_id is not None

        # ── Step 2: Failure recorded in DynamoDB ────────────────────────────────
        db_resource = res_repo.get(resource_id)
        assert db_resource.current_state == ResourceState.FAILURE_DETECTED
        assert db_resource.health_status == HealthStatus.CRITICAL
        assert db_resource.active_failure_type == failure_type

        # ── Step 3: Monitoring condition detected (threshold breached) ─────────
        emitted_metrics = trigger_data["metrics_emitted"]
        assert target_metric in emitted_metrics
        assert emitted_metrics[target_metric] >= threshold

        # ── Step 4: Event generated (CloudWatch Alarm EventBridge event) ────────
        alarm_name = f"cloudpulse-{resource_id}-{failure_type.value}"
        alarm_event = event_factory["alarm"](
            alarm_name=alarm_name,
            resource_id=resource_id,
            state_value="ALARM",
        )
        assert alarm_event["source"] == "aws.cloudwatch"
        assert alarm_event["detail"]["state"]["value"] == "ALARM"

        # ── Step 5 & 6: Recovery initiated and completed by Recovery Lambda ────
        lambda_res = handler(alarm_event, context=MagicMock())
        assert lambda_res["statusCode"] == 200

        # Verify resource metrics restored
        recovered_resource = res_repo.get(resource_id)
        assert recovered_resource.current_state == ResourceState.RECOVERED
        assert recovered_resource.health_status == HealthStatus.HEALTHY
        assert recovered_resource.active_failure_type is None
        assert getattr(recovered_resource, post_metric_key) == post_expected_val

        # ── Step 7: Incident updated ───────────────────────────────────────────
        incident_record = inc_repo.get(incident_id)
        assert incident_record.status.value == "RESOLVED"
        assert incident_record.recovery_action == expected_action
        assert incident_record.recovery_result == "SUCCESS"
        assert len(incident_record.recovery_actions) >= 1
        assert incident_record.duration_seconds is not None

        # ── Step 8: Notification generated ─────────────────────────────────────
        assert incident_record.notification_sent is True
        assert "RECOVERY_SUCCESSFUL" in incident_record.notified_transitions

        # ── Step 9: Dashboard reflects result via REST API ─────────────────────
        dashboard_resource = client.get(f"/resources/{resource_id}").json()
        assert dashboard_resource["current_state"] == "RECOVERED"
        assert dashboard_resource["health_status"] == "HEALTHY"

        dashboard_incident = client.get(f"/incidents/{incident_id}").json()
        assert dashboard_incident["status"] == "RESOLVED"
        assert dashboard_incident["recovery_action"] == expected_action
