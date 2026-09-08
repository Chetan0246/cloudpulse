"""
Simulation service — business logic for failure injection and resource reset.

This service is intentionally thin. It validates intent, delegates
metric mutation to the resource model, and persists via the repository.
Complex CloudWatch publishing and EventBridge event emission are done
in the Lambda layer (lambda/api/), not here, keeping this service
testable without AWS SDK calls.
"""
import logging
from datetime import datetime, timezone

from app.exceptions import ResourceNotFoundError, SimulationError
from app.models.resource import (
    CPU_FAILURE_THRESHOLD,
    NETWORK_LATENCY_FAILURE_MS,
    STORAGE_FAILURE_THRESHOLD,
    FailureType,
    HealthStatus,
    Resource,
    ResourceState,
)
from app.repositories.resource_repository import ResourceRepository

logger = logging.getLogger(__name__)

# Metric values injected per failure type
_FAILURE_METRICS: dict[FailureType, dict] = {
    FailureType.HIGH_CPU: {
        "cpu_utilization": 95.0,
        "memory_utilization": 60.0,
        "storage_utilization": 40.0,
        "network_latency_ms": 80.0,
    },
    FailureType.SERVICE_FAILURE: {
        "cpu_utilization": 10.0,
        "memory_utilization": 10.0,
        "storage_utilization": 40.0,
        "network_latency_ms": 2000.0,
    },
    FailureType.STORAGE_EXHAUSTION: {
        "cpu_utilization": 55.0,
        "memory_utilization": 55.0,
        "storage_utilization": 97.0,
        "network_latency_ms": 90.0,
    },
    FailureType.NETWORK_LATENCY: {
        "cpu_utilization": 30.0,
        "memory_utilization": 30.0,
        "storage_utilization": 30.0,
        "network_latency_ms": 900.0,
    },
    FailureType.SERVICE_DOWNTIME: {
        "cpu_utilization": 0.0,
        "memory_utilization": 0.0,
        "storage_utilization": 40.0,
        "network_latency_ms": 9999.0,
    },
}

_HEALTHY_METRICS: dict = {
    "cpu_utilization": 25.0,
    "memory_utilization": 30.0,
    "storage_utilization": 20.0,
    "network_latency_ms": 15.0,
}


class SimulationService:
    def __init__(self, repo: ResourceRepository) -> None:
        self._repo = repo

    def inject_failure(self, resource_id: str, failure_type: FailureType) -> Resource:
        """
        Apply failure metric values and transition resource to FAILURE_DETECTED.

        Raises:
            ResourceNotFoundError: If the resource does not exist.
            SimulationError: If the resource is already in a failure/recovery state.
        """
        resource = self._repo.get(resource_id)

        if resource.current_state not in (ResourceState.HEALTHY, ResourceState.WARNING):
            raise SimulationError(
                f"Cannot inject failure: resource '{resource_id}' is already "
                f"in state '{resource.current_state}'. "
                f"Reset the resource first."
            )

        metrics = _FAILURE_METRICS[failure_type]
        updated = resource.model_copy(
            update={
                **metrics,
                "current_state": ResourceState.FAILURE_DETECTED,
                "health_status": HealthStatus.CRITICAL,
                "active_failure_type": failure_type,
                "last_heartbeat": datetime.now(timezone.utc),
            }
        )
        self._repo.put(updated)
        logger.info(
            "Failure injected",
            extra={"resource_id": resource_id, "failure_type": failure_type},
        )
        return updated

    def reset_resource(self, resource_id: str) -> Resource:
        """Reset a resource to HEALTHY with nominal metrics."""
        resource = self._repo.get(resource_id)
        updated = resource.model_copy(
            update={
                **_HEALTHY_METRICS,
                "current_state": ResourceState.HEALTHY,
                "health_status": HealthStatus.HEALTHY,
                "active_failure_type": None,
                "last_heartbeat": datetime.now(timezone.utc),
            }
        )
        self._repo.put(updated)
        logger.info("Resource reset to HEALTHY", extra={"resource_id": resource_id})
        return updated
