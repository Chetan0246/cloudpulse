"""
Monitoring service — CloudWatch metric publishing and EventBridge event emission.

Responsibilities:
- Publish 5 custom metrics per resource to CloudWatch (CPUUtilization,
  MemoryUtilization, StorageUtilization, NetworkLatency, ServiceHealth).
- Compute the composite ServiceHealth score from raw metrics.
- Emit direct EventBridge events for fast demo recovery triggering.

Design notes:
- Strictly separated from SimulationService: handles *observability* only.
- All CloudWatch and EventBridge calls are non-fatal — errors are logged as
  warnings so that a monitoring outage cannot block failure injection.
- Weights and thresholds are constants defined at module level for easy tuning.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.aws.clients import get_cloudwatch_client, get_eventbridge_client
from app.config import get_settings
from app.models.resource import (
    CPU_FAILURE_THRESHOLD,
    MEMORY_FAILURE_THRESHOLD,
    NETWORK_LATENCY_FAILURE_MS,
    STORAGE_FAILURE_THRESHOLD,
    SimulatedResource,
)

logger = logging.getLogger(__name__)

# ── ServiceHealth composite-score weights ─────────────────────────────────────
# Must sum to 1.0.  CPU is weighted highest because it is the most common
# failure mode in a virtualised environment.
_WEIGHT_CPU: float = 0.30
_WEIGHT_MEMORY: float = 0.25
_WEIGHT_STORAGE: float = 0.20
_WEIGHT_LATENCY: float = 0.25


def compute_service_health(resource: SimulatedResource) -> float:
    """
    Compute a composite ServiceHealth score in the range [0.0, 100.0].

    A score of 100 means the resource is operating at nominal levels on all
    four dimensions.  A score of 0 means every metric is at or beyond its
    failure threshold.

    Formula (weighted linear combination of normalised "headroom"):
        score = 100 × (
            W_cpu  × (1 − cpu / CPU_FAILURE_THRESHOLD)          +
            W_mem  × (1 − mem / MEM_FAILURE_THRESHOLD)          +
            W_stor × (1 − stor / STOR_FAILURE_THRESHOLD)        +
            W_lat  × (1 − clamp(lat / LAT_FAILURE_MS, 0, 1))
        )
    """
    cpu_ratio = min(resource.cpu_utilization / CPU_FAILURE_THRESHOLD, 1.0)
    mem_ratio = min(resource.memory_utilization / MEMORY_FAILURE_THRESHOLD, 1.0)
    stor_ratio = min(resource.storage_utilization / STORAGE_FAILURE_THRESHOLD, 1.0)
    lat_ratio = min(resource.network_latency_ms / NETWORK_LATENCY_FAILURE_MS, 1.0)

    raw = 100.0 * (
        _WEIGHT_CPU * (1.0 - cpu_ratio)
        + _WEIGHT_MEMORY * (1.0 - mem_ratio)
        + _WEIGHT_STORAGE * (1.0 - stor_ratio)
        + _WEIGHT_LATENCY * (1.0 - lat_ratio)
    )
    return round(max(0.0, min(100.0, raw)), 2)


class MonitoringService:
    """
    Handles CloudWatch metric publishing and EventBridge event emission for
    CloudPulse simulated resources.

    Both CloudWatch and EventBridge operations are non-fatal: a failure in
    either is logged as a warning and does not propagate to the caller.
    """

    def __init__(
        self,
        cloudwatch_client: Any | None = None,
        eventbridge_client: Any | None = None,
    ) -> None:
        self._cw_client = cloudwatch_client
        self._eb_client = eventbridge_client

    # ── Lazy client accessors ────────────────────────────────────────────────

    @property
    def _cloudwatch(self) -> Any:
        if self._cw_client is None:
            self._cw_client = get_cloudwatch_client()
        return self._cw_client

    @property
    def _eventbridge(self) -> Any:
        if self._eb_client is None:
            self._eb_client = get_eventbridge_client()
        return self._eb_client

    # ── Public API ───────────────────────────────────────────────────────────

    def publish_resource_metrics(self, resource: SimulatedResource) -> dict[str, float]:
        """
        Publish all five custom CloudWatch metrics for the given resource in a
        single batched PutMetricData call.

        Returns a dict of the metric values that were (attempted to be) published.
        The return value is safe to use for logging / API responses even if the
        CloudWatch call fails.
        """
        settings = get_settings()
        service_health = compute_service_health(resource)

        published: dict[str, float] = {
            "CPUUtilization": resource.cpu_utilization,
            "MemoryUtilization": resource.memory_utilization,
            "StorageUtilization": resource.storage_utilization,
            "NetworkLatency": resource.network_latency_ms,
            "ServiceHealth": service_health,
        }

        dimensions = [
            {"Name": "ResourceId", "Value": resource.resource_id},
            {"Name": "ResourceType", "Value": resource.resource_type.value},
        ]
        timestamp = resource.updated_at if resource.updated_at.tzinfo else datetime.now(UTC)

        metric_data = [
            {
                "MetricName": "CPUUtilization",
                "Dimensions": dimensions,
                "Value": resource.cpu_utilization,
                "Unit": "Percent",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "MemoryUtilization",
                "Dimensions": dimensions,
                "Value": resource.memory_utilization,
                "Unit": "Percent",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "StorageUtilization",
                "Dimensions": dimensions,
                "Value": resource.storage_utilization,
                "Unit": "Percent",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "NetworkLatency",
                "Dimensions": dimensions,
                "Value": resource.network_latency_ms,
                "Unit": "Milliseconds",
                "Timestamp": timestamp,
            },
            {
                "MetricName": "ServiceHealth",
                "Dimensions": dimensions,
                "Value": service_health,
                "Unit": "None",
                "Timestamp": timestamp,
            },
        ]

        try:
            self._cloudwatch.put_metric_data(
                Namespace=settings.cloudwatch_namespace,
                MetricData=metric_data,
            )
            logger.debug(
                "CloudWatch metrics published",
                extra={"resource_id": resource.resource_id, "service_health": service_health},
            )
        except Exception as exc:
            logger.warning(
                "Could not publish CloudWatch metrics for %s (non-fatal): %s",
                resource.resource_id,
                exc,
            )

        return published

    def emit_failure_event(
        self,
        resource: SimulatedResource,
        scenario_code: str,
        incident_id: str,
    ) -> bool:
        """
        Emit a direct 'FailureInjected' EventBridge event to bypass the alarm
        evaluation window during demos.

        The Recovery Lambda listens for this event shape in addition to alarm
        state changes, enabling immediate recovery triggering without waiting
        2+ minutes for CloudWatch alarm evaluation.

        Returns True if the event was successfully published, False otherwise.
        """
        if resource.active_failure_type is None:
            logger.warning(
                "emit_failure_event called but resource has no active_failure_type",
                extra={"resource_id": resource.resource_id},
            )
            return False

        settings = get_settings()
        detail = {
            "resourceId": resource.resource_id,
            "resourceType": resource.resource_type.value,
            "failureType": resource.active_failure_type.value,
            "severity": resource.active_failure_type.default_severity(),
            "scenarioCode": scenario_code,
            "incidentId": incident_id,
            "detectedAt": resource.updated_at.isoformat(),
        }

        try:
            self._eventbridge.put_events(
                Entries=[
                    {
                        "Source": "cloudpulse.simulator",
                        "DetailType": "FailureInjected",
                        "Detail": json.dumps(detail),
                        "EventBusName": settings.eventbridge_bus_name,
                    }
                ]
            )
            logger.info(
                "EventBridge FailureInjected event emitted",
                extra={
                    "resource_id": resource.resource_id,
                    "scenario_code": scenario_code,
                    "incident_id": incident_id,
                },
            )
            return True
        except Exception as exc:
            logger.warning(
                "Could not emit EventBridge event for %s (non-fatal): %s",
                resource.resource_id,
                exc,
            )
            return False
