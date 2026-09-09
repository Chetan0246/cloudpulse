"""
Layer 8: Notification Tests
Tests SNS notification dispatch, template formatting, and deduplication logic.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.resource import FailureType, ResourceState
from app.services.notification_service import (
    NotificationService,
    NotificationTransition,
)


class TestNotificationLayer:
    """Notification publishing and deduplication tests."""

    @pytest.fixture
    def mock_sns_service(self):
        mock_client = MagicMock()
        mock_client.publish.return_value = {"MessageId": "msg-12345"}
        svc = NotificationService(
            sns_client=mock_client,
            topic_arn="arn:aws:sns:us-east-1:123456789012:test-topic",
            region_name="us-east-1",
        )
        return svc, mock_client

    def test_all_four_transitions_produce_notifications(self, mock_sns_service):
        """Failure detected, recovery started, success, and failure all publish SNS messages."""
        svc, mock_client = mock_sns_service
        inc = Incident(
            incident_id=str(uuid.uuid4()),
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
        )

        # 1. Failure detected
        inc, sent1 = svc.notify_failure_detected(inc)
        assert sent1 is True
        assert NotificationTransition.FAILURE_DETECTED.value in inc.notified_transitions

        # 2. Recovery started
        inc, sent2 = svc.notify_recovery_started(inc, action_name="SCALE_OUT", attempt=1)
        assert sent2 is True
        assert NotificationTransition.RECOVERY_STARTED.value in inc.notified_transitions

        # 3. Recovery successful
        inc, sent3 = svc.notify_recovery_successful(inc, action_name="SCALE_OUT", duration_seconds=5.2)
        assert sent3 is True
        assert NotificationTransition.RECOVERY_SUCCESSFUL.value in inc.notified_transitions

        # Verify call count
        assert mock_client.publish.call_count == 3

    def test_notification_deduplication_prevents_duplicate_sends(self, mock_sns_service):
        """Calling notify twice for the same transition does NOT send duplicate SNS alerts."""
        svc, mock_client = mock_sns_service
        inc = Incident(
            incident_id=str(uuid.uuid4()),
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
        )

        # First call sends
        inc, sent1 = svc.notify_failure_detected(inc)
        assert sent1 is True
        assert mock_client.publish.call_count == 1

        # Second call suppressed
        inc, sent2 = svc.notify_failure_detected(inc)
        assert sent2 is False
        assert mock_client.publish.call_count == 1  # Unchanged

    def test_message_formatting_includes_required_incident_fields(self, mock_sns_service):
        """SNS notifications include incident ID, resource, failure type, and status."""
        svc, mock_client = mock_sns_service
        inc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        inc = Incident(
            incident_id=inc_id,
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RESOLVED,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            detected_at=now - timedelta(seconds=10),
            resolved_at=now,
        )

        svc.notify_recovery_successful(inc, action_name="SCALE_OUT", duration_seconds=4.2)
        kwargs = mock_client.publish.call_args[1]

        subject = kwargs["Subject"]
        message = kwargs["Message"]

        assert "[CloudPulse]" in subject
        assert "RECOVERED" in subject
        assert inc_id in message
        assert "VM-001" in message
        assert "HIGH_CPU" in message
        assert "4.20 seconds" in message

    def test_sns_failure_does_not_raise(self):
        """ClientError from SNS is handled gracefully without crashing the caller."""
        broken_client = MagicMock()
        broken_client.publish.side_effect = ClientError(
            {"Error": {"Code": "EndpointDisabled", "Message": "Disabled"}}, "Publish"
        )
        svc = NotificationService(sns_client=broken_client, topic_arn="arn:aws:sns:...")

        inc = Incident(
            incident_id=str(uuid.uuid4()),
            resource_id="VM-001",
            failure_type=FailureType.HIGH_CPU,
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
        )

        # Must not raise
        updated_inc, sent = svc.notify_failure_detected(inc)
        assert sent is False
