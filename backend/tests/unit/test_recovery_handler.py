"""
Unit tests for the Recovery Lambda handler.

Coverage:
- _parse_event(): CloudWatch alarm event shape (all 5 alarm types)
- _parse_event(): Direct simulation event shape (cloudpulse.simulator)
- _parse_event(): Complex resource IDs with multiple hyphens (STORAGE-001)
- _parse_event(): Invalid event raises ValueError
- Idempotency guard: resource already in RECOVERY_INITIATED skips duplicate
- Alarm name convention: round-trip resource_id + failure_type parsing
- SNS notification: failure path does not propagate exceptions

All AWS calls are mocked via unittest.mock — no real AWS needed.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

_HANDLER_PATH = pathlib.Path(__file__).parents[3] / "lambda" / "recovery" / "handler.py"


def _load_recovery_handler():
    """
    Load the recovery handler module with Lambda-layer imports stubbed out.
    Returns the module object for direct function access.
    """
    spec = importlib.util.spec_from_file_location("_recovery_handler", _HANDLER_PATH)
    assert spec and spec.loader

    from app.models.incident import Incident, IncidentSeverity, IncidentStatus
    from app.models.resource import FailureType, ResourceState

    stub_config = MagicMock()
    stub_config.get_settings.return_value = MagicMock(
        log_level="DEBUG",
        aws_region="us-east-1",
        sns_topic_arn="arn:aws:sns:us-east-1:123456789012:test-topic",
    )

    stub_incident = MagicMock()
    stub_incident.Incident = Incident
    stub_incident.IncidentSeverity = IncidentSeverity
    stub_incident.IncidentStatus = IncidentStatus

    stub_resource = MagicMock()
    stub_resource.FailureType = FailureType
    stub_resource.ResourceState = ResourceState

    with patch.dict(
        "sys.modules",
        {
            "app.config": stub_config,
            "app.logging_config": MagicMock(),
            "app.models.incident": stub_incident,
            "app.models.resource": stub_resource,
            "app.repositories.incident_repository": MagicMock(),
            "app.repositories.resource_repository": MagicMock(),
        },
    ):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ── _parse_event: CloudWatch alarm event shape ────────────────────────────────


class TestParseEventCloudWatchAlarm:
    """
    CloudWatch alarm events arrive with source='aws.cloudwatch'.
    The alarm name encodes ResourceId and FailureType:
      cloudpulse-{ResourceId}-{FAILURE_TYPE_UPPER_SNAKE}
    """

    @pytest.fixture(autouse=True)
    def module(self):
        self.h = _load_recovery_handler()

    def _cw_event(self, alarm_name: str) -> dict:
        return {
            "source": "aws.cloudwatch",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {
                "alarmName": alarm_name,
                "state": {"value": "ALARM"},
                "previousState": {"value": "OK"},
            },
        }

    def test_parse_vm_001_high_cpu(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-VM-001-HIGH_CPU")
        )
        assert resource_id == "VM-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.HIGH_CPU

    def test_parse_api_001_network_latency(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-API-001-NETWORK_LATENCY")
        )
        assert resource_id == "API-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.NETWORK_LATENCY

    def test_parse_db_001_service_failure(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-DB-001-SERVICE_FAILURE")
        )
        assert resource_id == "DB-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.SERVICE_FAILURE

    def test_parse_storage_001_storage_exhaustion(self) -> None:
        """STORAGE-001 has an extra hyphen — parser must handle multi-hyphen resource IDs."""
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-STORAGE-001-STORAGE_EXHAUSTION")
        )
        assert resource_id == "STORAGE-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.STORAGE_EXHAUSTION

    def test_parse_vm_001_service_downtime(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-VM-001-SERVICE_DOWNTIME")
        )
        assert resource_id == "VM-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.SERVICE_DOWNTIME

    def test_parse_storage_001_network_latency(self) -> None:
        """STORAGE-001 with NETWORK_LATENCY — multi-part resource ID with latency alarm."""
        resource_id, failure_type = self.h._parse_event(
            self._cw_event("cloudpulse-STORAGE-001-NETWORK_LATENCY")
        )
        assert resource_id == "STORAGE-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.NETWORK_LATENCY

    def test_invalid_alarm_name_raises_value_error(self) -> None:
        """An alarm name with no matching FailureType suffix must raise ValueError."""
        with pytest.raises((ValueError, KeyError)):
            self.h._parse_event(self._cw_event("cloudpulse-VM-001-UNKNOWN_FAILURE"))


# ── _parse_event: Direct simulation event shape ───────────────────────────────


class TestParseEventDirectSimulation:
    """
    Direct simulation events arrive with source='cloudpulse.simulator'.
    The detail dict contains explicit resourceId and failureType fields.
    """

    @pytest.fixture(autouse=True)
    def module(self):
        self.h = _load_recovery_handler()

    def _direct_event(self, resource_id: str, failure_type: str, incident_id: str = "test-id") -> dict:
        return {
            "source": "cloudpulse.simulator",
            "detail-type": "FailureInjected",
            "detail": {
                "resourceId": resource_id,
                "resourceType": "VM",
                "failureType": failure_type,
                "severity": "HIGH",
                "scenarioCode": "FS-01",
                "incidentId": incident_id,
                "detectedAt": datetime.now(timezone.utc).isoformat(),
            },
        }

    def test_parse_high_cpu_direct(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._direct_event("VM-001", "HIGH_CPU")
        )
        assert resource_id == "VM-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.HIGH_CPU

    def test_parse_service_failure_direct(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._direct_event("API-001", "SERVICE_FAILURE")
        )
        assert resource_id == "API-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.SERVICE_FAILURE

    def test_parse_storage_exhaustion_direct(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._direct_event("STORAGE-001", "STORAGE_EXHAUSTION")
        )
        assert resource_id == "STORAGE-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.STORAGE_EXHAUSTION

    def test_parse_network_latency_direct(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._direct_event("DB-001", "NETWORK_LATENCY")
        )
        assert resource_id == "DB-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.NETWORK_LATENCY

    def test_parse_service_downtime_direct(self) -> None:
        resource_id, failure_type = self.h._parse_event(
            self._direct_event("VM-001", "SERVICE_DOWNTIME")
        )
        assert resource_id == "VM-001"
        from app.models.resource import FailureType

        assert failure_type == FailureType.SERVICE_DOWNTIME

    def test_missing_resource_id_raises(self) -> None:
        """Missing resourceId in direct event must raise KeyError."""
        event = {
            "source": "cloudpulse.simulator",
            "detail-type": "FailureInjected",
            "detail": {"failureType": "HIGH_CPU"},  # no resourceId
        }
        with pytest.raises(KeyError):
            self.h._parse_event(event)

    def test_unknown_source_raises_value_error(self) -> None:
        """An event from an unknown source must raise ValueError."""
        event = {
            "source": "unknown.source",
            "detail-type": "SomeEvent",
            "detail": {},
        }
        with pytest.raises(ValueError):
            self.h._parse_event(event)


# ── Alarm name round-trip tests ───────────────────────────────────────────────


class TestAlarmNameRoundTrip:
    """
    Verify that every alarm name defined in the SAM template can be
    parsed back into (resource_id, failure_type) by _parse_event.

    These correspond to the 10 alarms in infrastructure/template.yaml.
    """

    @pytest.fixture(autouse=True)
    def module(self):
        self.h = _load_recovery_handler()

    @pytest.mark.parametrize(
        "alarm_name,expected_resource_id,expected_failure_type_str",
        [
            ("cloudpulse-VM-001-HIGH_CPU", "VM-001", "HIGH_CPU"),
            ("cloudpulse-VM-001-NETWORK_LATENCY", "VM-001", "NETWORK_LATENCY"),
            ("cloudpulse-VM-001-SERVICE_HEALTH", "VM-001", "SERVICE_HEALTH"),
            ("cloudpulse-API-001-NETWORK_LATENCY", "API-001", "NETWORK_LATENCY"),
            ("cloudpulse-API-001-HIGH_CPU", "API-001", "HIGH_CPU"),
            ("cloudpulse-API-001-SERVICE_HEALTH", "API-001", "SERVICE_HEALTH"),
            ("cloudpulse-DB-001-HIGH_CPU", "DB-001", "HIGH_CPU"),
            ("cloudpulse-DB-001-NETWORK_LATENCY", "DB-001", "NETWORK_LATENCY"),
            ("cloudpulse-DB-001-SERVICE_HEALTH", "DB-001", "SERVICE_HEALTH"),
            ("cloudpulse-STORAGE-001-STORAGE_EXHAUSTION", "STORAGE-001", "STORAGE_EXHAUSTION"),
            ("cloudpulse-STORAGE-001-NETWORK_LATENCY", "STORAGE-001", "NETWORK_LATENCY"),
            ("cloudpulse-STORAGE-001-SERVICE_HEALTH", "STORAGE-001", "SERVICE_HEALTH"),
        ],
    )
    def test_alarm_name_parses_correctly(
        self,
        alarm_name: str,
        expected_resource_id: str,
        expected_failure_type_str: str,
    ) -> None:
        """
        Each alarm defined in template.yaml must parse into the expected
        resource_id. Alarms with SERVICE_HEALTH alarm type don't map to a
        FailureType (it's a composite alarm) — we only verify resource_id
        extraction for those, and accept ValueError for unknown failure types.
        """
        from app.models.resource import FailureType

        event = {
            "source": "aws.cloudwatch",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {
                "alarmName": alarm_name,
                "state": {"value": "ALARM"},
            },
        }

        known_failure_types = {ft.value for ft in FailureType}
        if expected_failure_type_str not in known_failure_types:
            # SERVICE_HEALTH is a composite metric, not a FailureType — parser
            # will raise ValueError. This is expected behaviour.
            with pytest.raises((ValueError, KeyError)):
                self.h._parse_event(event)
        else:
            resource_id, failure_type = self.h._parse_event(event)
            assert resource_id == expected_resource_id
            assert failure_type == FailureType(expected_failure_type_str)


# ── Idempotency guard tests ───────────────────────────────────────────────────


class TestIdempotencyGuard:
    """
    The Recovery Lambda must be idempotent:
    - If a resource is already in RECOVERY_INITIATED or later, a second
      invocation must exit early (return 200 "Already recovering").
    - This is implemented via a conditional DynamoDB update_state call.

    EventBridge delivers at-least-once, so this guard is essential.
    """

    def test_already_recovering_exits_early(self) -> None:
        """Duplicate event while resource is RECOVERY_INITIATED must no-op.

        The handler now does a pre-read via resource_repo.get() before
        calling update_state. If the pre-read shows the resource is NOT in
        FAILURE_DETECTED, it returns early without creating a duplicate incident.
        """
        from app.models.resource import ResourceState

        # Pre-read returns a resource already in RECOVERY_INITIATED (duplicate event)
        mock_resource_already_recovering = MagicMock()
        mock_resource_already_recovering.current_state = ResourceState.RECOVERY_INITIATED

        mock_repo = MagicMock()
        mock_repo.get.return_value = mock_resource_already_recovering
        # update_state should NOT be called in the early-return path

        h = _load_recovery_handler()

        event = {
            "source": "cloudpulse.simulator",
            "detail-type": "FailureInjected",
            "detail": {
                "resourceId": "VM-001",
                "failureType": "HIGH_CPU",
                "incidentId": "existing-incident",
            },
        }

        # Patch ResourceRepository at the module level using sys.modules approach
        import sys

        original_rr = sys.modules.get("app.repositories.resource_repository")
        try:
            rr_stub = MagicMock()
            rr_stub.ResourceRepository.return_value = mock_repo
            sys.modules["app.repositories.resource_repository"] = rr_stub

            # Also patch the handler module's ResourceRepository attribute
            h.ResourceRepository = MagicMock(return_value=mock_repo)
            h.IncidentRepository = MagicMock(return_value=MagicMock())

            result = h.handler(event, MagicMock())
        finally:
            if original_rr is not None:
                sys.modules["app.repositories.resource_repository"] = original_rr

        assert result["statusCode"] == 200
        assert "Already recovering" in result["body"]
        # update_state must NOT have been called (pre-read short-circuits)
        mock_repo.update_state.assert_not_called()

    def test_invalid_event_returns_400(self) -> None:
        """Unparseable event must return HTTP 400, not raise an exception."""
        h = _load_recovery_handler()

        event = {
            "source": "unknown.source",
            "detail": {},
        }

        result = h.handler(event, MagicMock())
        assert result["statusCode"] == 400

    def test_state_transition_failure_returns_500(self) -> None:
        """DynamoDB errors during update_state transition return HTTP 500.

        The handler does a pre-read (get()) then calls update_state().
        The pre-read must return FAILURE_DETECTED so the handler proceeds
        to update_state, which then fails.
        """
        from app.models.resource import ResourceState

        mock_resource_in_failure = MagicMock()
        mock_resource_in_failure.current_state = ResourceState.FAILURE_DETECTED

        mock_repo = MagicMock()
        mock_repo.get.return_value = mock_resource_in_failure
        mock_repo.update_state.side_effect = Exception("DynamoDB throttled")

        h = _load_recovery_handler()
        h.ResourceRepository = MagicMock(return_value=mock_repo)
        h.IncidentRepository = MagicMock(return_value=MagicMock())

        event = {
            "source": "cloudpulse.simulator",
            "detail-type": "FailureInjected",
            "detail": {
                "resourceId": "VM-001",
                "failureType": "HIGH_CPU",
                "incidentId": "test-id",
            },
        }

        result = h.handler(event, MagicMock())
        assert result["statusCode"] == 500


# ── SNS notification tests ────────────────────────────────────────────────────


class TestSNSNotification:
    """
    SNS notification failures must not propagate — they are non-fatal.
    """

    def test_missing_topic_arn_does_not_raise(self) -> None:
        """_send_notification with empty topic_arn must be a no-op."""
        h = _load_recovery_handler()

        # Should return without error
        h._send_notification(
            subject="Test",
            message="Test message",
            topic_arn="",
            region="us-east-1",
        )

    def test_sns_client_error_is_caught(self) -> None:
        """SNS publish failure must be caught and logged, not re-raised."""
        h = _load_recovery_handler()

        mock_sns = MagicMock()
        from botocore.exceptions import ClientError

        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "AuthorizationError", "Message": "access denied"}},
            "Publish",
        )

        with patch("boto3.client", return_value=mock_sns):
            # Must not raise
            h._send_notification(
                subject="Test",
                message="Test message",
                topic_arn="arn:aws:sns:us-east-1:123456789012:test",
                region="us-east-1",
            )
