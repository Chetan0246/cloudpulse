"""
Simulator Lambda entry point.

Triggered by EventBridge schedule (every 2 minutes).

Responsibilities:
  1. For each virtual resource in DynamoDB, generate updated metric values.
  2. Publish metrics to CloudWatch under the 'CloudPulse' namespace.
  3. Evaluate thresholds and update resource state (HEALTHY/WARNING/FAILURE_DETECTED).
  4. Write updated resource state back to DynamoDB.

This Lambda does NOT trigger recovery. It only changes resource state.
The CloudWatch alarm on the metrics will fire and route to EventBridge,
which then invokes the Recovery Lambda.

Design note:
  The simulator is intentionally separated from recovery. This demonstrates
  the event-driven, decoupled architecture — the simulator publishes facts
  (metrics), and the recovery system reacts to alarms derived from those facts.
"""
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Lambda layer path
sys.path.insert(0, "/opt/python")

from app.config import get_settings
from app.logging_config import configure_logging
from app.models.resource import (
    CPU_FAILURE_THRESHOLD,
    CPU_WARNING_THRESHOLD,
    MEMORY_FAILURE_THRESHOLD,
    MEMORY_WARNING_THRESHOLD,
    NETWORK_LATENCY_FAILURE_MS,
    NETWORK_LATENCY_WARNING_MS,
    STORAGE_FAILURE_THRESHOLD,
    STORAGE_WARNING_THRESHOLD,
    HealthStatus,
    Resource,
    ResourceState,
)
from app.repositories.resource_repository import ResourceRepository

logger = logging.getLogger(__name__)


def _jitter(value: float, max_delta: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Apply random walk to a metric value within bounds."""
    delta = random.uniform(-max_delta, max_delta)
    return round(max(min_val, min(max_val, value + delta)), 2)


def _compute_state(resource: Resource) -> tuple[ResourceState, HealthStatus]:
    """Derive state and health from current metric values."""
    health = resource.compute_health_status()
    if health == HealthStatus.CRITICAL:
        return ResourceState.FAILURE_DETECTED, health
    if health == HealthStatus.DEGRADED:
        return ResourceState.WARNING, health
    return ResourceState.HEALTHY, health


def _publish_metrics(resource: Resource, cw_client: Any, namespace: str) -> None:
    """Publish all metrics for a resource to CloudWatch."""
    dimensions = [
        {"Name": "ResourceId", "Value": resource.resource_id},
        {"Name": "ResourceType", "Value": resource.resource_type.value},
    ]
    metric_data = [
        {"MetricName": "CPUUtilization", "Value": resource.cpu_utilization, "Unit": "Percent"},
        {"MetricName": "MemoryUtilization", "Value": resource.memory_utilization, "Unit": "Percent"},
        {"MetricName": "StorageUtilization", "Value": resource.storage_utilization, "Unit": "Percent"},
        {"MetricName": "NetworkLatency", "Value": resource.network_latency_ms, "Unit": "Milliseconds"},
    ]
    cw_client.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {**m, "Dimensions": dimensions, "Timestamp": datetime.now(timezone.utc)}
            for m in metric_data
        ],
    )


def handler(event: dict, context: Any) -> dict:
    """Lambda handler for the simulator."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("Simulator invoked", extra={"event": event})

    repo = ResourceRepository()
    resources = repo.list()

    if not resources:
        logger.warning("No resources found in DynamoDB. Has seed data been loaded?")
        return {"statusCode": 200, "body": "No resources to simulate"}

    cw = boto3.client("cloudwatch", region_name=settings.aws_region)
    updated_count = 0

    for summary in resources:
        try:
            resource = repo.get(summary.resource_id)

            # Skip resources mid-recovery — do not disturb their metrics
            if resource.current_state in (
                ResourceState.RECOVERY_INITIATED,
                ResourceState.RECOVERY_IN_PROGRESS,
            ):
                logger.info(
                    "Skipping resource mid-recovery",
                    extra={"resource_id": resource.resource_id},
                )
                continue

            # Apply random walk to metrics
            updated = resource.model_copy(
                update={
                    "cpu_utilization": _jitter(resource.cpu_utilization, 10.0),
                    "memory_utilization": _jitter(resource.memory_utilization, 8.0),
                    "storage_utilization": _jitter(resource.storage_utilization, 3.0),
                    "network_latency_ms": _jitter(resource.network_latency_ms, 50.0, max_val=5000.0),
                    "last_heartbeat": datetime.now(timezone.utc),
                }
            )

            # Re-evaluate state from updated metrics
            new_state, new_health = _compute_state(updated)

            # Do not regress out of a FAILURE_DETECTED state via the simulator.
            # Only the Recovery Lambda resolves failures.
            if resource.current_state == ResourceState.FAILURE_DETECTED:
                new_state = ResourceState.FAILURE_DETECTED

            updated = updated.model_copy(
                update={"current_state": new_state, "health_status": new_health}
            )

            repo.put(updated)
            _publish_metrics(updated, cw, settings.cloudwatch_namespace)
            updated_count += 1

        except Exception:
            logger.exception(
                "Failed to simulate resource",
                extra={"resource_id": summary.resource_id},
            )

    logger.info("Simulation complete", extra={"updated_count": updated_count})
    return {"statusCode": 200, "body": json.dumps({"updated": updated_count})}
