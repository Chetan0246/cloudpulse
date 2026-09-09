"""
Business logic service for reliability metrics.

Coordinates querying and formatting of reliability metrics snapshots.
"""

import logging

from app.models.reliability_metric import (
    MetricWindowType,
    ReliabilityMetric,
    ReliabilityMetricSummary,
)
from app.repositories.metric_repository import MetricRepository

logger = logging.getLogger(__name__)


class MetricService:
    """Service handling reliability metric business logic."""

    def __init__(self, repo: MetricRepository | None = None) -> None:
        self._repo = repo or MetricRepository()

    def get_metric(self, resource_id: str, window_key: str) -> ReliabilityMetric:
        """
        Retrieve a specific reliability metric snapshot.

        Raises:
            MetricNotFoundError: If the metric is not found.
        """
        return self._repo.get(resource_id=resource_id, window_key=window_key)

    def get_latest_metric(
        self,
        resource_id: str,
        window_type: MetricWindowType = MetricWindowType.DAILY,
    ) -> ReliabilityMetric | None:
        """
        Retrieve the latest metric snapshot for a resource and window type.
        """
        return self._repo.get_latest(resource_id=resource_id, window_type=window_type)

    def list_metrics(
        self,
        resource_id: str | None = None,
        window_type: MetricWindowType | None = None,
        limit: int = 50,
    ) -> list[ReliabilityMetricSummary]:
        """
        List reliability metrics matching filters as summaries.
        """
        metrics = self._repo.list(
            resource_id=resource_id,
            window_type=window_type,
            limit=limit,
        )
        return [
            ReliabilityMetricSummary(
                resource_id=m.resource_id,
                window_type=m.window_type,
                window_key=m.window_key,
                window_start=m.window_start,
                window_end=m.window_end,
                total_incidents=m.total_incidents,
                resolved_incidents=m.resolved_incidents,
                failed_recoveries=m.failed_recoveries,
                mttr_seconds=m.mttr_seconds,
                mtbf_seconds=m.mtbf_seconds,
                availability_pct=m.availability_pct,
                computed_at=m.computed_at,
            )
            for m in metrics
        ]
