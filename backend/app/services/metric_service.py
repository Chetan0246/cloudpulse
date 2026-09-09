"""
Business logic service for reliability metrics.

Coordinates querying and calculating reliability metrics snapshots
and fleet-wide SRE indicators.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.models.reliability_metric import (
    FleetReliabilityOverview,
    MetricWindowType,
    ReliabilityMetric,
    ReliabilityMetricSummary,
)
from app.repositories.incident_repository import IncidentRepository
from app.repositories.metric_repository import MetricRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.reliability_calculator import (
    calculate_fleet_reliability_overview,
    calculate_resource_metric_summary,
)

logger = logging.getLogger(__name__)


class MetricService:
    """Service handling reliability metric business logic."""

    def __init__(
        self,
        repo: MetricRepository | None = None,
        incident_repo: IncidentRepository | None = None,
        resource_repo: ResourceRepository | None = None,
    ) -> None:
        self._repo = repo or MetricRepository()
        self._incident_repo = incident_repo or IncidentRepository()
        self._resource_repo = resource_repo or ResourceRepository()

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
        If no pre-computed snapshots exist in the repository, dynamically computes
        them from stored incident and resource records.
        """
        metrics = self._repo.list(
            resource_id=resource_id,
            window_type=window_type,
            limit=limit,
        )

        if metrics:
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
                    recovery_success_rate_pct=round(
                        (m.resolved_incidents / max(1, m.resolved_incidents + m.failed_recoveries)) * 100.0,
                        2,
                    ) if (m.resolved_incidents + m.failed_recoveries) > 0 else 100.0,
                    recovery_failure_rate_pct=round(
                        (m.failed_recoveries / max(1, m.resolved_incidents + m.failed_recoveries)) * 100.0,
                        2,
                    ) if (m.resolved_incidents + m.failed_recoveries) > 0 else 0.0,
                    avg_recovery_time_seconds=m.mttr_seconds,
                )
                for m in metrics
            ]

        # No pre-computed snapshots found; calculate dynamically from stored incidents
        incidents = self._incident_repo.list(resource_id=resource_id, limit=limit * 2)
        resources = self._resource_repo.list()

        target_resources = (
            [r for r in resources if r.resource_id.upper() == resource_id.upper()]
            if resource_id
            else resources
        )

        now = datetime.now(UTC)
        w_type = window_type or MetricWindowType.DAILY
        w_start = now - timedelta(days=1 if w_type == MetricWindowType.DAILY else 7 if w_type == MetricWindowType.WEEKLY else 30)

        summaries: list[ReliabilityMetricSummary] = []
        for r in target_resources:
            summaries.append(
                calculate_resource_metric_summary(
                    resource_id=r.resource_id,
                    incidents=incidents,
                    window_type=w_type,
                    window_start=w_start,
                    window_end=now,
                )
            )

        return summaries[:limit]

    def get_fleet_reliability_overview(
        self,
        resource_id: str | None = None,
        window_type: MetricWindowType | None = None,
    ) -> FleetReliabilityOverview:
        """
        Calculate and return the comprehensive 8-metric observability & reliability report
        from currently stored Incident and SimulatedResource records.
        """
        incidents = self._incident_repo.list(resource_id=resource_id, limit=200)
        resources = self._resource_repo.list()

        now = datetime.now(UTC)
        w_type = window_type or MetricWindowType.DAILY
        w_start = now - timedelta(days=1 if w_type == MetricWindowType.DAILY else 7 if w_type == MetricWindowType.WEEKLY else 30)

        return calculate_fleet_reliability_overview(
            incidents=incidents,
            resources=resources,
            window_start=w_start,
            window_end=now,
        )
