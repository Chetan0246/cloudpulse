"""
Unit tests for lambda/recovery/handler._parse_event

Covers (A-16 fix):
- Standard CloudWatch alarm names for all 5 failure types
- Multi-hyphen resource ID (STORAGE-001)
- SERVICE_HEALTH composite alarm — should raise ValueError (by design; filtered by EventBridge in production)
- Unknown EventBridge source — should raise ValueError
- Direct simulation event (source: cloudpulse.simulator)
"""
from __future__ import annotations

import sys
import os
import pytest

# Add lambda/recovery to path so we can import _parse_event
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda/recovery"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.models.resource import FailureType


def _make_alarm_event(alarm_name: str) -> dict:
    return {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": {
            "alarmName": alarm_name,
            "state": {"value": "ALARM"},
        },
    }


def _make_inject_event(resource_id: str, failure_type: str) -> dict:
    return {
        "source": "cloudpulse.simulator",
        "detail-type": "FailureInjected",
        "detail": {
            "resourceId": resource_id,
            "failureType": failure_type,
        },
    }


# Import the function under test after path setup
from handler import _parse_event  # noqa: E402


class TestParseEventCloudWatchAlarms:
    """Standard alarm-name parsing for all 5 failure types across all 4 resources."""

    @pytest.mark.parametrize("alarm_name,expected_resource,expected_failure", [
        # VM-001 alarms
        ("cloudpulse-VM-001-HIGH_CPU",         "VM-001",      FailureType.HIGH_CPU),
        ("cloudpulse-VM-001-NETWORK_LATENCY",  "VM-001",      FailureType.NETWORK_LATENCY),
        # API-001 alarms
        ("cloudpulse-API-001-HIGH_CPU",        "API-001",     FailureType.HIGH_CPU),
        ("cloudpulse-API-001-NETWORK_LATENCY", "API-001",     FailureType.NETWORK_LATENCY),
        # DB-001 alarms
        ("cloudpulse-DB-001-HIGH_CPU",         "DB-001",      FailureType.HIGH_CPU),
        ("cloudpulse-DB-001-NETWORK_LATENCY",  "DB-001",      FailureType.NETWORK_LATENCY),
        # STORAGE-001 alarms — multi-hyphen resource ID
        ("cloudpulse-STORAGE-001-STORAGE_EXHAUSTION", "STORAGE-001", FailureType.STORAGE_EXHAUSTION),
        ("cloudpulse-STORAGE-001-NETWORK_LATENCY",    "STORAGE-001", FailureType.NETWORK_LATENCY),
    ])
    def test_standard_alarm_names(self, alarm_name, expected_resource, expected_failure):
        event = _make_alarm_event(alarm_name)
        resource_id, failure_type = _parse_event(event)
        assert resource_id == expected_resource
        assert failure_type == expected_failure


class TestParseEventServiceHealthAlarm:
    """
    SERVICE_HEALTH composite alarms (e.g. cloudpulse-VM-001-SERVICE_HEALTH) are
    intentionally excluded from the EventBridge rule (A-14 fix in template.yaml).
    However _parse_event should raise ValueError if such an event somehow arrives,
    so the Lambda re-tries and routes to DLQ (A-06 fix).
    """

    @pytest.mark.parametrize("alarm_name", [
        "cloudpulse-VM-001-SERVICE_HEALTH",
        "cloudpulse-API-001-SERVICE_HEALTH",
        "cloudpulse-DB-001-SERVICE_HEALTH",
        "cloudpulse-STORAGE-001-SERVICE_HEALTH",
    ])
    def test_service_health_alarm_raises_value_error(self, alarm_name):
        event = _make_alarm_event(alarm_name)
        with pytest.raises(ValueError):
            _parse_event(event)


class TestParseEventDirectInjection:
    """Direct simulation event path (source: cloudpulse.simulator)."""

    @pytest.mark.parametrize("resource_id,failure_type_str,expected_failure", [
        ("VM-001",      "HIGH_CPU",           FailureType.HIGH_CPU),
        ("API-001",     "SERVICE_FAILURE",    FailureType.SERVICE_FAILURE),
        ("DB-001",      "NETWORK_LATENCY",    FailureType.NETWORK_LATENCY),
        ("STORAGE-001", "STORAGE_EXHAUSTION", FailureType.STORAGE_EXHAUSTION),
        ("VM-001",      "SERVICE_DOWNTIME",   FailureType.SERVICE_DOWNTIME),
    ])
    def test_direct_inject_event(self, resource_id, failure_type_str, expected_failure):
        event = _make_inject_event(resource_id, failure_type_str)
        parsed_resource, parsed_failure = _parse_event(event)
        assert parsed_resource == resource_id
        assert parsed_failure == expected_failure


class TestParseEventUnknownSource:
    """Unknown event source should raise ValueError (A-06: caller re-raises to DLQ)."""

    def test_unknown_source_raises(self):
        event = {
            "source": "unknown.service",
            "detail": {},
        }
        with pytest.raises(ValueError, match="Cannot parse event"):
            _parse_event(event)

    def test_missing_source_raises(self):
        event = {"detail": {}}
        with pytest.raises(ValueError, match="Cannot parse event"):
            _parse_event(event)
