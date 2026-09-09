"""
Layer 6: EventBridge Flow Tests
Tests EventBridge pattern matching, event decomposition, and parsing rules.
"""

import pytest

from app.models.resource import FailureType
from handler import _parse_event


class TestEventBridgeFlowLayer:
    """EventBridge event parsing and routing tests."""

    @pytest.mark.parametrize(
        "alarm_name,expected_resource,expected_failure",
        [
            ("cloudpulse-VM-001-HIGH_CPU", "VM-001", FailureType.HIGH_CPU),
            ("cloudpulse-API-001-SERVICE_FAILURE", "API-001", FailureType.SERVICE_FAILURE),
            ("cloudpulse-STORAGE-001-STORAGE_EXHAUSTION", "STORAGE-001", FailureType.STORAGE_EXHAUSTION),
            ("cloudpulse-VM-001-NETWORK_LATENCY", "VM-001", FailureType.NETWORK_LATENCY),
            ("cloudpulse-DB-001-SERVICE_DOWNTIME", "DB-001", FailureType.SERVICE_DOWNTIME),
        ],
    )
    def test_cloudwatch_alarm_name_decomposition(
        self,
        event_factory: dict,
        alarm_name: str,
        expected_resource: str,
        expected_failure: FailureType,
    ):
        """Alarm names decompose reliably into resource ID and failure type enum."""
        event = event_factory["alarm"](alarm_name=alarm_name, resource_id=expected_resource)
        resource_id, failure_type = _parse_event(event)

        assert resource_id == expected_resource
        assert failure_type == expected_failure

    def test_direct_simulator_event_parsing(self, event_factory: dict):
        """Direct FailureInjected events parse accurately."""
        event = event_factory["inject"](resource_id="VM-001", failure_type="HIGH_CPU")
        resource_id, failure_type = _parse_event(event)

        assert resource_id == "VM-001"
        assert failure_type == FailureType.HIGH_CPU

    def test_unsupported_event_source_raises_error(self):
        """Events from unknown sources are rejected."""
        unknown_event = {
            "source": "unsupported.source",
            "detail": {},
        }
        with pytest.raises(ValueError) as exc:
            _parse_event(unknown_event)
        assert "Cannot parse event" in str(exc.value)

    def test_malformed_alarm_name_raises_error(self, event_factory: dict):
        """Alarms not matching cloudpulse-{id}-{failure} format raise ValueError."""
        event = event_factory["alarm"](alarm_name="random-alarm-name", resource_id="VM-001")
        with pytest.raises(ValueError) as exc:
            _parse_event(event)
        assert "Cannot parse event" in str(exc.value)

    def test_unknown_failure_type_in_alarm_raises_error(self, event_factory: dict):
        """Alarms with unregistered failure types raise ValueError."""
        event = event_factory["alarm"](
            alarm_name="cloudpulse-VM-001-UNREGISTERED_FAULT", resource_id="VM-001"
        )
        with pytest.raises(ValueError) as exc:
            _parse_event(event)
        assert "Cannot parse event" in str(exc.value)
