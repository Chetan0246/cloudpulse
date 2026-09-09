"""
Business logic service for virtual resources.

Coordinates operations on virtual resources between routers and the
repository layer. Does not interact directly with AWS or DynamoDB.
"""

import logging

from app.models.resource import ResourceSummary, SimulatedResource
from app.repositories.resource_repository import ResourceRepository

logger = logging.getLogger(__name__)


class ResourceService:
    """Service handling resource business logic."""

    def __init__(self, repo: ResourceRepository | None = None) -> None:
        self._repo = repo or ResourceRepository()

    def get_resource(self, resource_id: str) -> SimulatedResource:
        """
        Retrieve a single resource by ID.

        Raises:
            ResourceNotFoundError: If resource is not found.
        """
        return self._repo.get(resource_id)

    def list_resources(self) -> list[ResourceSummary]:
        """
        List all virtual resources as lightweight summaries for dashboard display.
        """
        resources = self._repo.list()
        return [
            ResourceSummary(
                resource_id=r.resource_id,
                resource_type=r.resource_type,
                current_state=r.current_state,
                health_status=r.health_status,
                active_failure_type=r.active_failure_type,
                last_heartbeat=r.last_heartbeat,
                cpu_utilization=r.cpu_utilization,
                memory_utilization=r.memory_utilization,
                storage_utilization=r.storage_utilization,
                network_latency_ms=r.network_latency_ms,
            )
            for r in resources
        ]
