"""
Unit tests for the CloudPulse complete incident lifecycle.

Verifies:
1. Incident model field tracking for all 14 required fields:
   - incidentId / incident_id
   - resourceId / resource_id
   - failureType / failure_type
   - severity
   - createdAt / created_at
   - detectedAt / detected_at
   - recoveryStartedAt / recovery_started_at
   - recoveredAt / recovered_at
   - status
   - recoveryAction / recovery_action
   - recoveryResult / recovery_result
   - notificationStatus / notification_status
   - retryCount / retry_count
   - errorMessage / error_message
2. SNS email notifications for the 4 key transitions:
   - Failure detected
   - Recovery started
   - Recovery successful
   - Recovery failed
3. De-duplication: duplicate notifications are prevented for the same transition
4. Human-readable message formatting (incident ID, resource, failure type, status, duration)
5. Dashboard-facing APIs (/incidents and /incidents/{id}) returning complete lifecycle data
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.models.incident import (
    Incident,
    IncidentDetail,
    IncidentSeverity,
    IncidentStatus,
    IncidentSummary,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.resource import FailureType, ResourceState
from app.repositories.incident_repository import IncidentRepository
from app.services.notification_service import (
    NotificationService,
    NotificationTransition,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _create_sample_incident(**kwargs) -> Incident:
    now = datetime.now(UTC)
    detected_at = kwargs.pop("detected_at", now - timedelta(seconds=20))
    created_at = kwargs.pop("created_at", detected_at)
    defaults = {
        "incident_id": str(uuid.uuid4()),
        "resource_id": "VM-001",
        "failure_type": FailureType.HIGH_CPU,
        "severity": IncidentSeverity.HIGH,
        "status": IncidentStatus.OPEN,
        "state_at_detection": ResourceState.FAILURE_DETECTED,
        "created_at": created_at,
        "detected_at": detected_at,
        "recovery_attempts": 0,
        "retry_count": 0,
        "recovery_actions": [],
    }
    defaults.update(kwargs)
    return Incident(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Incident Field Tracking Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestIncidentFieldTracking:
    def test_all_14_lifecycle_fields_present_and_accessible(self):
        now = datetime.now(UTC)
        recovered_time = now + timedelta(seconds=12)
        inc_id = str(uuid.uuid4())

        action = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=RecoveryActionType.SCALE_OUT,
            status=RecoveryActionStatus.SUCCEEDED,
            started_at=now,
            completed_at=recovered_time,
            outcome_message="Scale-out completed",
        )

        incident = Incident(
            incident_id=inc_id,
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RESOLVED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            state_at_resolution=ResourceState.RECOVERED,
            created_at=now,
            detected_at=now,
            recovery_started_at=now,
            recovery_initiated_at=now,
            recovered_at=recovered_time,
            resolved_at=recovered_time,
            duration_seconds=12.0,
            recovery_action="SCALE_OUT",
            recovery_result="SUCCESS",
            notification_status="SENT",
            retry_count=1,
            recovery_attempts=1,
            error_message=None,
            recovery_actions=[action],
        )

        # 1. incidentId / incident_id
        assert incident.incident_id == inc_id
        assert incident.incidentId == inc_id

        # 2. resourceId / resource_id
        assert incident.resource_id == "VM-001"
        assert incident.resourceId == "VM-001"

        # 3. failureType / failure_type
        assert incident.failure_type == FailureType.HIGH_CPU
        assert incident.failureType == "HIGH_CPU"

        # 4. severity
        assert incident.severity == IncidentSeverity.HIGH

        # 5. createdAt / created_at
        assert incident.created_at == now
        assert incident.createdAt == now.isoformat()

        # 6. detectedAt / detected_at
        assert incident.detected_at == now
        assert incident.detectedAt == now.isoformat()

        # 7. recoveryStartedAt / recovery_started_at
        assert incident.recovery_started_at == now
        assert incident.recoveryStartedAt == now.isoformat()

        # 8. recoveredAt / recovered_at
        assert incident.recovered_at == recovered_time
        assert incident.recoveredAt == recovered_time.isoformat()

        # 9. status
        assert incident.status == IncidentStatus.RESOLVED

        # 10. recoveryAction / recovery_action
        assert incident.recovery_action == "SCALE_OUT"
        assert incident.recoveryAction == "SCALE_OUT"

        # 11. recoveryResult / recovery_result
        assert incident.recovery_result == "SUCCESS"
        assert incident.recoveryResult == "SUCCESS"

        # 12. notificationStatus / notification_status
        assert incident.notification_status == "SENT"
        assert incident.notificationStatus == "SENT"

        # 13. retryCount / retry_count
        assert incident.retry_count == 1
        assert incident.retryCount == 1

        # 14. errorMessage / error_message
        assert incident.error_message is None
        assert incident.errorMessage is None

    def test_error_message_tracked_on_failure(self):
        now = datetime.now(UTC)
        action = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=RecoveryActionType.SERVICE_RESTART,
            status=RecoveryActionStatus.FAILED,
            started_at=now,
            completed_at=now + timedelta(seconds=2),
            outcome_message="Service failed to restart",
            error_detail="Timeout connecting to socket /var/run/service.sock",
        )

        incident = Incident(
            incident_id=str(uuid.uuid4()),
            resource_id="API-001",
            failure_type=FailureType.SERVICE_FAILURE,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.ESCALATED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            state_at_resolution=ResourceState.MANUAL_INTERVENTION_REQUIRED,
            detected_at=now,
            escalated_at=now + timedelta(seconds=2),
            recovery_action="SERVICE_RESTART",
            recovery_result="FAILED",
            error_message="Timeout connecting to socket /var/run/service.sock",
            retry_count=1,
            recovery_attempts=1,
            recovery_actions=[action],
        )

        assert incident.error_message == "Timeout connecting to socket /var/run/service.sock"
        assert incident.errorMessage == "Timeout connecting to socket /var/run/service.sock"
        assert incident.recovery_result == "FAILED"
        assert incident.recoveryResult == "FAILED"


# ═════════════════════════════════════════════════════════════════════════════
# 2. SNS Notification Formatting & Transitions
# ═════════════════════════════════════════════════════════════════════════════


class TestNotificationTransitions:
    def test_failure_detected_notification_content(self):
        incident = _create_sample_incident()
        svc = NotificationService(topic_arn="arn:aws:sns:us-east-1:123456789012:test")

        subject, body = svc.format_message(NotificationTransition.FAILURE_DETECTED, incident)

        assert "[CloudPulse] FAILURE DETECTED: VM-001 — HIGH_CPU" in subject
        assert incident.incident_id in body
        assert "VM-001" in body
        assert "HIGH_CPU" in body
        assert "OPEN" in body
        assert "HIGH" in body

    def test_recovery_started_notification_content(self):
        incident = _create_sample_incident(
            status=IncidentStatus.RECOVERING,
            recovery_started_at=datetime.now(UTC),
            recovery_action="SCALE_OUT",
        )
        svc = NotificationService(topic_arn="arn:aws:sns:us-east-1:123456789012:test")

        subject, body = svc.format_message(
            NotificationTransition.RECOVERY_STARTED,
            incident,
            action_name="SCALE_OUT",
            attempt=1,
            max_attempts=3,
        )

        assert "[CloudPulse] RECOVERY STARTED: VM-001 — HIGH_CPU" in subject
        assert incident.incident_id in body
        assert "VM-001" in body
        assert "HIGH_CPU" in body
        assert "RECOVERING" in body
        assert "SCALE_OUT" in body
        assert "Attempt 1/3" in body

    def test_recovery_successful_notification_content(self):
        now = datetime.now(UTC)
        incident = _create_sample_incident(
            status=IncidentStatus.RESOLVED,
            state_at_resolution=ResourceState.RECOVERED,
            recovered_at=now,
            resolved_at=now,
            duration_seconds=8.45,
            recovery_action="SCALE_OUT",
            recovery_result="SUCCESS",
            recovery_attempts=1,
            retry_count=1,
            recovery_actions=[
                RecoveryAction(
                    action_id=str(uuid.uuid4()),
                    action_type=RecoveryActionType.SCALE_OUT,
                    status=RecoveryActionStatus.SUCCEEDED,
                    started_at=now - timedelta(seconds=8),
                    completed_at=now,
                    outcome_message="Scale-out succeeded",
                )
            ],
        )
        svc = NotificationService(topic_arn="arn:aws:sns:us-east-1:123456789012:test")

        subject, body = svc.format_message(
            NotificationTransition.RECOVERY_SUCCESSFUL,
            incident,
            action_name="SCALE_OUT",
            duration_seconds=8.45,
        )

        assert "[CloudPulse] RECOVERED: VM-001 — HIGH_CPU" in subject
        assert incident.incident_id in body
        assert "VM-001" in body
        assert "RESOLVED" in body
        assert "SCALE_OUT" in body
        assert "8.45 seconds" in body

    def test_recovery_failed_notification_content(self):
        now = datetime.now(UTC)
        action_1 = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=RecoveryActionType.SCALE_OUT,
            status=RecoveryActionStatus.FAILED,
            started_at=now - timedelta(seconds=10),
            completed_at=now - timedelta(seconds=8),
            outcome_message="Attempt 1 failed",
            error_detail="Simulated disk write failure",
        )
        action_2 = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=RecoveryActionType.SCALE_OUT,
            status=RecoveryActionStatus.FAILED,
            started_at=now - timedelta(seconds=5),
            completed_at=now,
            outcome_message="Attempt 2 failed",
            error_detail="Simulated disk write failure",
        )
        incident = _create_sample_incident(
            status=IncidentStatus.RECOVERING,
            error_message="Simulated disk write failure",
            retry_count=2,
            recovery_attempts=2,
            recovery_actions=[action_1, action_2],
        )
        svc = NotificationService(topic_arn="arn:aws:sns:us-east-1:123456789012:test")

        subject, body = svc.format_message(
            NotificationTransition.RECOVERY_FAILED,
            incident,
            error_message="Simulated disk write failure",
            attempt=2,
            max_attempts=3,
        )

        assert "[CloudPulse] RECOVERY FAILED: VM-001 — HIGH_CPU" in subject
        assert incident.incident_id in body
        assert "VM-001" in body
        assert "Simulated disk write failure" in body
        assert "Attempt 2/3" in body


# ═════════════════════════════════════════════════════════════════════════════
# 3. Duplicate Notification Prevention
# ═════════════════════════════════════════════════════════════════════════════


class TestNotificationDeduplication:
    def test_duplicate_notification_skipped(self):
        incident = _create_sample_incident()
        mock_sns = MagicMock()
        svc = NotificationService(
            sns_client=mock_sns,
            topic_arn="arn:aws:sns:us-east-1:123456789012:test-topic",
        )

        # First call: should send
        updated_inc, was_sent = svc.notify(incident, NotificationTransition.FAILURE_DETECTED)
        assert was_sent is True
        assert mock_sns.publish.call_count == 1
        assert NotificationTransition.FAILURE_DETECTED.value in updated_inc.notified_transitions

        # Second call with same transition: MUST be skipped
        second_inc, second_sent = svc.notify(updated_inc, NotificationTransition.FAILURE_DETECTED)
        assert second_sent is False
        assert mock_sns.publish.call_count == 1  # Not incremented!
        assert len(second_inc.notified_transitions) == 1

    def test_distinct_transitions_both_sent(self):
        incident = _create_sample_incident()
        mock_sns = MagicMock()
        svc = NotificationService(
            sns_client=mock_sns,
            topic_arn="arn:aws:sns:us-east-1:123456789012:test-topic",
        )

        # Transition 1: Failure detected
        inc_1, sent_1 = svc.notify_failure_detected(incident)
        assert sent_1 is True
        assert mock_sns.publish.call_count == 1

        # Transition 2: Recovery started
        inc_2, sent_2 = svc.notify_recovery_started(inc_1, action_name="SCALE_OUT")
        assert sent_2 is True
        assert mock_sns.publish.call_count == 2

        # Transition 3: Recovery successful
        inc_3, sent_3 = svc.notify_recovery_successful(inc_2, duration_seconds=5.0)
        assert sent_3 is True
        assert mock_sns.publish.call_count == 3

        assert len(inc_3.notified_transitions) == 3
        assert NotificationTransition.FAILURE_DETECTED.value in inc_3.notified_transitions
        assert NotificationTransition.RECOVERY_STARTED.value in inc_3.notified_transitions
        assert NotificationTransition.RECOVERY_SUCCESSFUL.value in inc_3.notified_transitions

    def test_missing_topic_arn_gracefully_handled(self):
        incident = _create_sample_incident()
        svc = NotificationService(topic_arn="")

        updated_inc, was_sent = svc.notify_failure_detected(incident)
        assert was_sent is False
        assert updated_inc.notification_status == "NOT_CONFIGURED"

    def test_sns_client_error_gracefully_handled(self):
        incident = _create_sample_incident()
        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "TopicNotFound", "Message": "Topic does not exist"}},
            "Publish",
        )
        svc = NotificationService(
            sns_client=mock_sns,
            topic_arn="arn:aws:sns:us-east-1:123456789012:missing",
        )

        updated_inc, was_sent = svc.notify_failure_detected(incident)
        assert was_sent is False
        assert updated_inc.notification_status == "FAILED"


# ═════════════════════════════════════════════════════════════════════════════
# 4. Dashboard-Facing APIs
# ═════════════════════════════════════════════════════════════════════════════


class TestDashboardFacingApis:
    def test_list_incidents_returns_both_snake_and_camel_case(self, client: TestClient):
        repo = IncidentRepository()
        inc_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        incident = Incident(
            incident_id=inc_id,
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            created_at=now,
            detected_at=now,
            recovery_action=None,
            recovery_result="PENDING",
            notification_status="NOT_SENT",
            retry_count=0,
            recovery_attempts=0,
            error_message=None,
        )
        repo.create(incident)

        res = client.get("/incidents")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1

        matched = next(item for item in items if item["incident_id"] == inc_id)

        # Standard snake_case
        assert matched["incident_id"] == inc_id
        assert matched["resource_id"] == "VM-001"
        assert matched["failure_type"] == "HIGH_CPU"
        assert matched["status"] == "OPEN"
        assert matched["severity"] == "HIGH"
        assert matched["notification_status"] == "NOT_SENT"
        assert matched["retry_count"] == 0

        # Frontend camelCase aliases
        assert matched["incidentId"] == inc_id
        assert matched["resourceId"] == "VM-001"
        assert matched["failureType"] == "HIGH_CPU"
        assert matched["notificationStatus"] == "NOT_SENT"
        assert matched["retryCount"] == 0
        assert matched["recoveryResult"] == "PENDING"

    def test_get_incident_detail_returns_complete_lifecycle(self, client: TestClient):
        repo = IncidentRepository()
        inc_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        recovered_time = now + timedelta(seconds=7)

        action = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=RecoveryActionType.STORAGE_CLEANUP,
            status=RecoveryActionStatus.SUCCEEDED,
            started_at=now,
            completed_at=recovered_time,
            outcome_message="Storage cleaned",
        )

        incident = Incident(
            incident_id=inc_id,
            resource_id="STORAGE-001",
            failure_type=FailureType.STORAGE_EXHAUSTION,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.RESOLVED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            state_at_resolution=ResourceState.RECOVERED,
            created_at=now,
            detected_at=now,
            recovery_started_at=now,
            recovery_initiated_at=now,
            recovered_at=recovered_time,
            resolved_at=recovered_time,
            duration_seconds=7.0,
            recovery_action="STORAGE_CLEANUP",
            recovery_result="SUCCESS",
            notification_status="SENT",
            retry_count=1,
            recovery_attempts=1,
            error_message=None,
            recovery_actions=[action],
            recovery_notes=["Cleaned 30% temp capacity"],
        )
        repo.create(incident)

        res = client.get(f"/incidents/{inc_id}")
        assert res.status_code == 200
        data = res.json()

        assert data["incidentId"] == inc_id
        assert data["resourceId"] == "STORAGE-001"
        assert data["failureType"] == "STORAGE_EXHAUSTION"
        assert data["status"] == "RESOLVED"
        assert data["recoveryAction"] == "STORAGE_CLEANUP"
        assert data["recoveryResult"] == "SUCCESS"
        assert data["retryCount"] == 1
        assert data["duration_seconds"] == 7.0
        assert len(data["recovery_actions"]) == 1
        assert len(data["recovery_notes"]) == 1
