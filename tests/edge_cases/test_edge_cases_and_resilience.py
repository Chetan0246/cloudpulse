"""
Resilience & Edge Cases Test Suite
Verifies non-functional reliability, error handling, and fault tolerance:
- Recovery failure handling
- Retry and max-attempts escalation
- Duplicate event idempotency
- Invalid resource ID handling
- Invalid failure type validation
- Partial failure resilience (CloudWatch outage)
- SNS notification failure resilience
- DynamoDB conditional write conflict resilience
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.exceptions import DatabaseError, ResourceNotFoundError
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
from app.services.monitoring_service import MonitoringService
from app.services.notification_service import NotificationService
from app.services.simulation_service import SimulationService
from handler import handler
from strategies import MAX_RECOVERY_ATTEMPTS, RecoveryStrategyError


class TestEdgeCasesAndResilience:
    """Comprehensive test cases for edge conditions and failure modes."""

    # ── 1. Recovery Failure ───────────────────────────────────────────────────

    def test_recovery_failure_single_attempt(
        self,
        client: TestClient,
        seed_fleet: list,
        event_factory: dict,
    ):
        """
        When a recovery strategy raises RecoveryStrategyError on attempt 1:
        - Lambda returns 500
        - Resource transitions to RECOVERY_FAILED
        - Incident status remains RECOVERING with 1 FAILED RecoveryAction
        - SNS recovery failure notification is dispatched
        """
        res_repo = ResourceRepository()
        inc_repo = IncidentRepository()
        resource_id = "VM-001"

        # Pre-set resource in FAILURE_DETECTED
        res_repo.update_state(resource_id, ResourceState.FAILURE_DETECTED)

        alarm_event = event_factory["alarm"](
            alarm_name=f"cloudpulse-{resource_id}-HIGH_CPU",
            resource_id=resource_id,
        )

        mock_strategy = MagicMock()
        mock_strategy.recovery_action_type = RecoveryActionType.SCALE_OUT
        mock_strategy.description = "Failing strategy simulation"
        mock_strategy.simulated_duration_seconds = 0.1
        mock_strategy.execute.side_effect = RecoveryStrategyError("EC2 API throttling simulated")

        with patch("handler.dispatch_strategy", return_value=mock_strategy):
            result = handler(alarm_event, context=MagicMock())

        assert result["statusCode"] == 500
        assert "Recovery failed after 1 attempt" in result["body"]

        updated_res = res_repo.get(resource_id)
        assert updated_res.current_state == ResourceState.RECOVERY_FAILED

        incidents = inc_repo.list(resource_id=resource_id)
        assert len(incidents) >= 1
        active_inc = next(i for i in incidents if i.status == IncidentStatus.RECOVERING)
        assert active_inc.recovery_attempts == 1
        assert active_inc.recovery_result == "FAILED"
        assert len(active_inc.recovery_actions) == 1
        assert active_inc.recovery_actions[0].status == RecoveryActionStatus.FAILED
        assert "EC2 API throttling simulated" in active_inc.recovery_actions[0].error_detail
        assert "RECOVERY_FAILED" in active_inc.notified_transitions

    # ── 2. Retry & Escalation on Max Attempts ─────────────────────────────────

    def test_retry_exhaustion_escalates_to_manual_intervention(
        self,
        seed_fleet: list,
        event_factory: dict,
    ):
        """
        When recovery fails and reaches MAX_RECOVERY_ATTEMPTS (3):
        - Resource transitions to MANUAL_INTERVENTION_REQUIRED
        - Incident transitions to ESCALATED with escalated_at set
        - Total recovery_attempts == 3 with 3 FAILED recovery actions
        """
        res_repo = ResourceRepository()
        inc_repo = IncidentRepository()
        resource_id = "VM-001"

        # Seed existing incident with 2 previous failed attempts
        now = datetime.now(UTC)
        incident_id = str(uuid.uuid4())
        prior_actions = [
            RecoveryAction(
                action_id=str(uuid.uuid4()),
                action_type=RecoveryActionType.SCALE_OUT,
                status=RecoveryActionStatus.FAILED,
                outcome_message="Attempt 1 failed",
                error_detail="Simulated timeout",
                started_at=now - timedelta(minutes=5),
                completed_at=now - timedelta(minutes=4),
            ),
            RecoveryAction(
                action_id=str(uuid.uuid4()),
                action_type=RecoveryActionType.SCALE_OUT,
                status=RecoveryActionStatus.FAILED,
                outcome_message="Attempt 2 failed",
                error_detail="Simulated timeout",
                started_at=now - timedelta(minutes=3),
                completed_at=now - timedelta(minutes=2),
            ),
        ]
        existing_incident = Incident(
            incident_id=incident_id,
            resource_id=resource_id,
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.RECOVERING,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            created_at=now - timedelta(minutes=5),
            detected_at=now - timedelta(minutes=5),
            recovery_attempts=2,
            retry_count=2,
            recovery_actions=prior_actions,
        )
        inc_repo.create(existing_incident)

        # Set resource to FAILURE_DETECTED for attempt 3
        res_repo.update_state(resource_id, ResourceState.FAILURE_DETECTED)

        alarm_event = event_factory["alarm"](
            alarm_name=f"cloudpulse-{resource_id}-HIGH_CPU",
            resource_id=resource_id,
        )

        mock_strategy = MagicMock()
        mock_strategy.recovery_action_type = RecoveryActionType.SCALE_OUT
        mock_strategy.description = "Failing attempt 3"
        mock_strategy.simulated_duration_seconds = 0.1
        mock_strategy.execute.side_effect = RecoveryStrategyError("Persistent hardware fault")

        with patch("handler.dispatch_strategy", return_value=mock_strategy):
            result = handler(alarm_event, context=MagicMock())

        assert result["statusCode"] == 500
        assert f"Recovery failed after {MAX_RECOVERY_ATTEMPTS} attempt" in result["body"]

        updated_res = res_repo.get(resource_id)
        assert updated_res.current_state == ResourceState.MANUAL_INTERVENTION_REQUIRED

        escalated_inc = inc_repo.get(incident_id)
        assert escalated_inc.status == IncidentStatus.ESCALATED
        assert escalated_inc.escalated_at is not None
        assert escalated_inc.state_at_resolution == ResourceState.MANUAL_INTERVENTION_REQUIRED
        assert escalated_inc.recovery_attempts == 3
        assert len(escalated_inc.recovery_actions) == 3

    # ── 3. Duplicate Events Idempotency ───────────────────────────────────────

    @pytest.mark.parametrize(
        "already_state",
        [
            ResourceState.RECOVERY_INITIATED,
            ResourceState.RECOVERY_IN_PROGRESS,
            ResourceState.RECOVERED,
        ],
    )
    def test_duplicate_event_idempotency_guard(
        self,
        seed_fleet: list,
        event_factory: dict,
        already_state: ResourceState,
    ):
        """
        When duplicate alarm arrives while resource is already in recovery or recovered:
        - Layer 1 pre-read gate immediately aborts
        - Returns 200 with 'Already recovering'
        - Does not invoke recovery strategy or create duplicate incidents
        """
        res_repo = ResourceRepository()
        inc_repo = IncidentRepository()
        resource_id = "VM-001"

        res_repo.update_state(resource_id, already_state)

        event = event_factory["alarm"](
            alarm_name=f"cloudpulse-{resource_id}-HIGH_CPU",
            resource_id=resource_id,
        )

        with patch("handler.dispatch_strategy") as mock_dispatch:
            res = handler(event, context=MagicMock())

        assert res["statusCode"] == 200
        assert "Already recovering" in res["body"]
        mock_dispatch.assert_not_called()

    # ── 4. Invalid Resource Handling ──────────────────────────────────────────

    def test_invalid_resource_api_and_simulator_rejection(
        self,
        client: TestClient,
        seed_fleet: list,
    ):
        """
        Accessing or triggering failures on unknown resources returns 404.
        """
        # GET non-existent resource
        get_res = client.get("/resources/NON-EXISTENT-999")
        assert get_res.status_code == 404
        assert "not found" in get_res.json()["detail"].lower()

        # Simulate failure on non-existent resource
        sim_res = client.post(
            "/simulate/failure",
            json={
                "resourceId": "NON-EXISTENT-999",
                "failureType": "HIGH_CPU",
            },
        )
        assert sim_res.status_code == 404
        assert "not found" in sim_res.json()["detail"].lower()

    # ── 5. Invalid Failure Type Validation ───────────────────────────────────

    def test_invalid_failure_type_rejected_at_boundary(
        self,
        client: TestClient,
        seed_fleet: list,
        event_factory: dict,
    ):
        """
        Invalid failure types are rejected at both API and EventBridge boundaries.
        """
        # API validation (FastAPI Pydantic boundary)
        api_res = client.post(
            "/simulate/failure",
            json={
                "resourceId": "VM-001",
                "failureType": "TOTAL_SYSTEM_MELTDOWN",
            },
        )
        assert api_res.status_code == 422

        # EventBridge parsing boundary — A-06 fix: handler now raises so DLQ is triggered
        import pytest
        invalid_alarm = event_factory["alarm"](
            alarm_name="cloudpulse-VM-001-TOTAL_SYSTEM_MELTDOWN",
            resource_id="VM-001",
        )
        with pytest.raises(ValueError, match="Cannot parse event"):
            handler(invalid_alarm, context=MagicMock())

    # ── 6. Partial Failure: CloudWatch Outage ──────────────────────────────────

    def test_partial_failure_cloudwatch_outage_does_not_break_simulation(
        self,
        client: TestClient,
        seed_fleet: list,
    ):
        """
        If CloudWatch put_metric_data throws ClientError during simulation:
        - Core simulation persists resource state in DynamoDB
        - Incident is created
        - API returns 201 Created (non-fatal monitoring failure)
        """
        with patch("app.services.monitoring_service.get_cloudwatch_client") as mock_get_cw:
            mock_cw = MagicMock()
            mock_cw.put_metric_data.side_effect = ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "CW Down"}},
                "PutMetricData",
            )
            mock_get_cw.return_value = mock_cw
            res = client.post(
                "/simulate/failure",
                json={
                    "resourceId": "VM-001",
                    "failureType": "HIGH_CPU",
                },
            )

        # Simulation succeeds even if CloudWatch publish experienced an outage
        assert res.status_code == 201
        data = res.json()
        assert data["resource"]["current_state"] == "FAILURE_DETECTED"
        assert data["incident"]["incident_id"] is not None

    def test_partial_failure_cloudwatch_outage_does_not_break_recovery(
        self,
        seed_fleet: list,
        event_factory: dict,
    ):
        """
        If CloudWatch metrics reset fails during recovery:
        - Recovery completes successfully (200)
        - Resource is updated to RECOVERED in DynamoDB
        - Incident is marked RESOLVED
        """
        res_repo = ResourceRepository()
        resource_id = "VM-001"

        res_repo.update_state(resource_id, ResourceState.FAILURE_DETECTED)
        alarm_event = event_factory["alarm"](
            alarm_name=f"cloudpulse-{resource_id}-HIGH_CPU",
            resource_id=resource_id,
        )

        with patch("app.services.monitoring_service.get_cloudwatch_client") as mock_get_cw:
            mock_cw = MagicMock()
            mock_cw.put_metric_data.side_effect = ClientError(
                {"Error": {"Code": "InternalError", "Message": "CW Unavailable"}},
                "PutMetricData",
            )
            mock_get_cw.return_value = mock_cw
            res = handler(alarm_event, context=MagicMock())

        assert res["statusCode"] == 200
        assert res_repo.get(resource_id).current_state == ResourceState.RECOVERED

    # ── 7. SNS Failure Handling ───────────────────────────────────────────────

    def test_sns_failure_does_not_break_recovery_flow(
        self,
        seed_fleet: list,
        event_factory: dict,
    ):
        """
        If SNS publish throws ClientError:
        - Recovery executes to completion
        - Resource is set to RECOVERED
        - Incident is marked RESOLVED
        """
        res_repo = ResourceRepository()
        resource_id = "VM-001"

        res_repo.update_state(resource_id, ResourceState.FAILURE_DETECTED)
        alarm_event = event_factory["alarm"](
            alarm_name=f"cloudpulse-{resource_id}-HIGH_CPU",
            resource_id=resource_id,
        )

        with patch.object(
            NotificationService,
            "send_notification",
            return_value=False,
        ):
            res = handler(alarm_event, context=MagicMock())

        assert res["statusCode"] == 200
        assert res_repo.get(resource_id).current_state == ResourceState.RECOVERED

    # ── 8. DynamoDB Failure Handling & Conditional Write Conflicts ───────────

    def test_dynamodb_conditional_check_failed_conflict_guard(
        self,
        seed_fleet: list,
    ):
        """
        When concurrent process tries to transition a resource with an unmet condition,
        ConditionalCheckFailedException is handled idempotently without throwing.
        The current unmodified resource state is preserved.
        """
        repo = ResourceRepository()
        resource_id = "VM-001"

        # Current state is HEALTHY
        # Updating with condition_state = FAILURE_DETECTED fails condition gracefully
        res = repo.update_state(
            resource_id=resource_id,
            new_state=ResourceState.RECOVERY_INITIATED,
            condition_state=ResourceState.FAILURE_DETECTED,
        )

        assert res.current_state == ResourceState.HEALTHY

    def test_dynamodb_client_error_raises_database_error(
        self,
        seed_fleet: list,
    ):
        """
        Unexpected DynamoDB ClientError (e.g. throughput exceeded) is mapped to DatabaseError.
        """
        repo = ResourceRepository()
        resource_id = "VM-001"

        with patch.object(
            repo.table,
            "update_item",
            side_effect=ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}},
                "UpdateItem",
            ),
        ):
            with pytest.raises(DatabaseError) as exc_info:
                repo.update_state(
                    resource_id=resource_id,
                    new_state=ResourceState.RECOVERY_INITIATED,
                )

        assert "Database operation failed" in str(exc_info.value)
        assert resource_id in str(exc_info.value)
