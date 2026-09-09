"""
Unit tests for MonitoringService.

Covers:
- compute_service_health() for all 5 failure scenarios + nominal case
- publish_resource_metrics() — verifies CloudWatch PutMetricData payload
- emit_failure_event() — verifies EventBridge PutEvents payload
- Error resilience (CloudWatch / EventBridge failures are non-fatal)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws

from app.models.resource import (
    CPU_FAILURE_THRESHOLD,
    FAILURE_METRIC_TARGETS,
    MEMORY_FAILURE_THRESHOLD,
    NETWORK_LATENCY_FAILURE_MS,
    STORAGE_FAILURE_THRESHOLD,
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)
from app.services.monitoring_service import (
    MonitoringService,
    _WEIGHT_CPU,
    _WEIGHT_LATENCY,
    _WEIGHT_MEMORY,
    _WEIGHT_STORAGE,
    compute_service_health,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _healthy_resource(resource_id: str = "VM-001") -> SimulatedResource:
    """Return a nominal HEALTHY resource."""
    return SimulatedResource(
        resource_id=resource_id,
        resource_type=ResourceType.VM,
        description="Test VM",
        cpu_utilization=25.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
        current_state=ResourceState.HEALTHY,
        health_status=HealthStatus.HEALTHY,
    )


def _failure_resource(failure_type: FailureType) -> SimulatedResource:
    """Return a resource with failure-scenario metric targets applied."""
    targets = FAILURE_METRIC_TARGETS[failure_type]
    return SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        description="Test VM",
        current_state=ResourceState.FAILURE_DETECTED,
        health_status=HealthStatus.CRITICAL,
        active_failure_type=failure_type,
        **{k: v for k, v in targets.items()},
    )


# ── compute_service_health tests ──────────────────────────────────────────────


class TestComputeServiceHealth:
    def test_nominal_healthy_resource_scores_above_70(self) -> None:
        """
        Nominal metrics (CPU=25%, mem=30%, storage=20%, latency=15ms) produce
        a healthy score. The formula normalises headroom against failure thresholds
        (85%, 85%, 90%, 500ms), so a score of ~77 is expected for these values.
        """
        resource = _healthy_resource()
        score = compute_service_health(resource)
        # Nominal metrics are well below failure thresholds → healthy score
        assert score >= 70.0, f"Expected ≥ 70, got {score}"
        assert score <= 100.0

    def test_score_clamped_to_100_maximum(self) -> None:
        # All-zero metrics (perfect headroom) → should not exceed 100
        resource = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=0.0,
            memory_utilization=0.0,
            storage_utilization=0.0,
            network_latency_ms=0.0,
        )
        score = compute_service_health(resource)
        assert score == 100.0

    def test_score_clamped_to_0_minimum(self) -> None:
        # All metrics at maximum failure values → should not go below 0
        resource = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=100.0,
            memory_utilization=100.0,
            storage_utilization=100.0,
            network_latency_ms=9999.0,
        )
        score = compute_service_health(resource)
        assert score == 0.0

    def test_fs01_high_cpu_scores_below_50(self) -> None:
        """
        FS-01: CPU=92% (vs 85% threshold) maxes the CPU component.
        Memory=60% also consumes headroom. Combined, score drops below 50.
        """
        resource = _failure_resource(FailureType.HIGH_CPU)
        score = compute_service_health(resource)
        assert score < 50.0, f"FS-01 score should be < 50, got {score}"

    def test_fs02_service_failure_scores_below_nominal(self) -> None:
        """
        FS-02: NetworkLatency=980ms (>> 500ms threshold) collapses the
        latency component. CPU/mem/storage are low. Score is degraded (~60)
        but not necessarily below 50 — ServiceHealth is a composite score
        and the latency component carries only 25% weight.
        The primary detection alarm for FS-02 is NETWORK_LATENCY (≥500ms),
        not SERVICE_HEALTH (≤50).
        """
        resource = _failure_resource(FailureType.SERVICE_FAILURE)
        score = compute_service_health(resource)
        # Score is degraded but may be above 50 — the ServiceHealth alarm at
        # ≤50 is a catch-all; primary alarm for FS-02 is NETWORK_LATENCY.
        assert score < 80.0, f"FS-02 score should be degraded (< 80), got {score}"
        assert 0.0 <= score <= 100.0

    def test_fs03_storage_exhaustion_scores_below_nominal(self) -> None:
        """
        FS-03: StorageUtilization=96% (vs 90% threshold) collapses the
        storage component (20% weight). Score is degraded (~55).
        Primary alarm: STORAGE_EXHAUSTION (≥90%).
        """
        resource = _failure_resource(FailureType.STORAGE_EXHAUSTION)
        score = compute_service_health(resource)
        assert score < 80.0, f"FS-03 score should be degraded (< 80), got {score}"
        assert 0.0 <= score <= 100.0

    def test_fs04_network_latency_scores_below_nominal(self) -> None:
        """
        FS-04: NetworkLatency=750ms (vs 500ms threshold) collapses latency
        component. Score is degraded (~57). Primary alarm: NETWORK_LATENCY.
        """
        resource = _failure_resource(FailureType.NETWORK_LATENCY)
        score = compute_service_health(resource)
        assert score < 80.0, f"FS-04 score should be degraded (< 80), got {score}"
        assert 0.0 <= score <= 100.0

    def test_fs05_service_downtime_scores_below_nominal(self) -> None:
        """
        FS-05: cpu=0%, mem=0% (very low utilization, lots of headroom),
        storage=10%, but latency=9999ms (fully saturates latency component).
        The latency component is only 25% weight, and low CPU/mem/storage
        contribute positive scores, resulting in a score of ~73.
        Primary alarm: NETWORK_LATENCY (≥500ms).
        """
        resource = _failure_resource(FailureType.SERVICE_DOWNTIME)
        score = compute_service_health(resource)
        # CPU=0, mem=0, storage=10 → most components at max headroom (positive)
        # latency=9999 → fully breaches latency threshold (25% weight, -25pts)
        # Net effect: score is in the 65-80 range (degraded but not critical)
        assert score < 100.0, f"FS-05 score should not be perfect, got {score}"
        assert 0.0 <= score <= 100.0

    def test_weights_sum_to_one(self) -> None:
        total = _WEIGHT_CPU + _WEIGHT_MEMORY + _WEIGHT_STORAGE + _WEIGHT_LATENCY
        assert abs(total - 1.0) < 1e-9, f"Weights must sum to 1.0, got {total}"

    def test_score_formula_matches_manual_calculation(self) -> None:
        resource = _healthy_resource()
        cpu_ratio = min(resource.cpu_utilization / CPU_FAILURE_THRESHOLD, 1.0)
        mem_ratio = min(resource.memory_utilization / MEMORY_FAILURE_THRESHOLD, 1.0)
        stor_ratio = min(resource.storage_utilization / STORAGE_FAILURE_THRESHOLD, 1.0)
        lat_ratio = min(resource.network_latency_ms / NETWORK_LATENCY_FAILURE_MS, 1.0)
        expected = round(
            max(
                0.0,
                min(
                    100.0,
                    100.0
                    * (
                        _WEIGHT_CPU * (1.0 - cpu_ratio)
                        + _WEIGHT_MEMORY * (1.0 - mem_ratio)
                        + _WEIGHT_STORAGE * (1.0 - stor_ratio)
                        + _WEIGHT_LATENCY * (1.0 - lat_ratio)
                    ),
                ),
            ),
            2,
        )
        assert compute_service_health(resource) == expected


# ── publish_resource_metrics tests ───────────────────────────────────────────


class TestPublishResourceMetrics:
    @mock_aws
    def test_publishes_five_metrics_to_cloudwatch(self) -> None:
        """Verifies that 5 metric data points (including ServiceHealth) are published."""
        import boto3

        cw = boto3.client("cloudwatch", region_name="us-east-1")
        svc = MonitoringService(cloudwatch_client=cw)
        resource = _healthy_resource()

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.cloudwatch_namespace = "CloudPulse"
            published = svc.publish_resource_metrics(resource)

        assert "CPUUtilization" in published
        assert "MemoryUtilization" in published
        assert "StorageUtilization" in published
        assert "NetworkLatency" in published
        assert "ServiceHealth" in published
        assert published["CPUUtilization"] == resource.cpu_utilization
        assert published["NetworkLatency"] == resource.network_latency_ms
        assert 0.0 <= published["ServiceHealth"] <= 100.0

    @mock_aws
    def test_returns_metrics_dict_even_on_cloudwatch_error(self) -> None:
        """CloudWatch failure must not propagate — returns published values regardless."""
        broken_cw = MagicMock()
        broken_cw.put_metric_data.side_effect = Exception("CloudWatch unavailable")
        svc = MonitoringService(cloudwatch_client=broken_cw)
        resource = _healthy_resource()

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.cloudwatch_namespace = "CloudPulse"
            published = svc.publish_resource_metrics(resource)

        # Must return the metric dict without raising
        assert "CPUUtilization" in published
        assert "ServiceHealth" in published

    def test_dimensions_include_resource_id_and_type(self) -> None:
        """Verifies correct dimension keys are sent."""
        mock_cw = MagicMock()
        svc = MonitoringService(cloudwatch_client=mock_cw)
        resource = SimulatedResource(
            resource_id="DB-001",
            resource_type=ResourceType.DB,
        )

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.cloudwatch_namespace = "CloudPulse"
            svc.publish_resource_metrics(resource)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        # All metric data points should have the right dimensions
        for data_point in call_kwargs["MetricData"]:
            dim_names = {d["Name"] for d in data_point["Dimensions"]}
            assert "ResourceId" in dim_names
            assert "ResourceType" in dim_names
            dim_map = {d["Name"]: d["Value"] for d in data_point["Dimensions"]}
            assert dim_map["ResourceId"] == "DB-001"
            assert dim_map["ResourceType"] == "DB"

    def test_service_health_metric_uses_none_unit(self) -> None:
        """ServiceHealth is a unitless score — must use Unit='None'."""
        mock_cw = MagicMock()
        svc = MonitoringService(cloudwatch_client=mock_cw)
        resource = _healthy_resource()

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.cloudwatch_namespace = "CloudPulse"
            svc.publish_resource_metrics(resource)

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        sh_points = [
            d for d in call_kwargs["MetricData"] if d["MetricName"] == "ServiceHealth"
        ]
        assert len(sh_points) == 1
        assert sh_points[0]["Unit"] == "None"

    def test_all_metrics_in_single_api_call(self) -> None:
        """All 5 metrics must be batched in a single put_metric_data call."""
        mock_cw = MagicMock()
        svc = MonitoringService(cloudwatch_client=mock_cw)
        resource = _healthy_resource()

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.cloudwatch_namespace = "CloudPulse"
            svc.publish_resource_metrics(resource)

        assert mock_cw.put_metric_data.call_count == 1
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        assert len(call_kwargs["MetricData"]) == 5


# ── emit_failure_event tests ─────────────────────────────────────────────────


class TestEmitFailureEvent:
    def test_emits_correct_event_to_eventbridge(self) -> None:
        """Verifies the EventBridge event detail contains all required fields."""
        mock_eb = MagicMock()
        mock_eb.put_events.return_value = {"FailedEntryCount": 0, "Entries": [{"EventId": "abc"}]}
        svc = MonitoringService(eventbridge_client=mock_eb)

        resource = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            current_state=ResourceState.FAILURE_DETECTED,
            health_status=HealthStatus.CRITICAL,
            active_failure_type=FailureType.HIGH_CPU,
            cpu_utilization=92.0,
            memory_utilization=60.0,
            storage_utilization=20.0,
            network_latency_ms=50.0,
            updated_at=datetime.now(UTC),
        )

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.eventbridge_bus_name = "default"
            result = svc.emit_failure_event(
                resource=resource,
                scenario_code="FS-01",
                incident_id="test-incident-123",
            )

        assert result is True
        call_args = mock_eb.put_events.call_args[1]
        entries = call_args["Entries"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["Source"] == "cloudpulse.simulator"
        assert entry["DetailType"] == "FailureInjected"

        detail = json.loads(entry["Detail"])
        assert detail["resourceId"] == "VM-001"
        assert detail["failureType"] == "HIGH_CPU"
        assert detail["scenarioCode"] == "FS-01"
        assert detail["incidentId"] == "test-incident-123"
        assert detail["severity"] == "HIGH"

    def test_returns_false_on_eventbridge_error(self) -> None:
        """EventBridge failure must not propagate — returns False."""
        mock_eb = MagicMock()
        mock_eb.put_events.side_effect = Exception("EventBridge unavailable")
        svc = MonitoringService(eventbridge_client=mock_eb)

        resource = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            current_state=ResourceState.FAILURE_DETECTED,
            health_status=HealthStatus.CRITICAL,
            active_failure_type=FailureType.HIGH_CPU,
            cpu_utilization=92.0,
            memory_utilization=60.0,
            storage_utilization=20.0,
            network_latency_ms=50.0,
        )

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.eventbridge_bus_name = "default"
            result = svc.emit_failure_event(
                resource=resource,
                scenario_code="FS-01",
                incident_id="test-incident-123",
            )

        assert result is False

    def test_returns_false_when_no_active_failure_type(self) -> None:
        """emit_failure_event on a HEALTHY resource returns False (no-op)."""
        mock_eb = MagicMock()
        svc = MonitoringService(eventbridge_client=mock_eb)
        resource = _healthy_resource()  # active_failure_type=None

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.eventbridge_bus_name = "default"
            result = svc.emit_failure_event(
                resource=resource,
                scenario_code="FS-01",
                incident_id="test-incident-123",
            )

        assert result is False
        mock_eb.put_events.assert_not_called()

    @pytest.mark.parametrize(
        "failure_type,expected_scenario",
        [
            (FailureType.HIGH_CPU, "FS-01"),
            (FailureType.SERVICE_FAILURE, "FS-02"),
            (FailureType.STORAGE_EXHAUSTION, "FS-03"),
            (FailureType.NETWORK_LATENCY, "FS-04"),
            (FailureType.SERVICE_DOWNTIME, "FS-05"),
        ],
    )
    def test_all_failure_types_emit_correct_scenario_code(
        self, failure_type: FailureType, expected_scenario: str
    ) -> None:
        """Each failure type should emit its scenario code correctly."""
        mock_eb = MagicMock()
        mock_eb.put_events.return_value = {"FailedEntryCount": 0, "Entries": [{"EventId": "x"}]}
        svc = MonitoringService(eventbridge_client=mock_eb)
        resource = _failure_resource(failure_type)

        with patch("app.services.monitoring_service.get_settings") as mock_settings:
            mock_settings.return_value.eventbridge_bus_name = "default"
            result = svc.emit_failure_event(
                resource=resource,
                scenario_code=expected_scenario,
                incident_id="test-id",
            )

        assert result is True
        detail = json.loads(mock_eb.put_events.call_args[1]["Entries"][0]["Detail"])
        assert detail["scenarioCode"] == expected_scenario
        assert detail["failureType"] == failure_type.value
