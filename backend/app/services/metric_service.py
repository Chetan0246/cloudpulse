"""
Business logic service for reliability metrics.

Coordinates querying and calculating reliability metrics snapshots
and fleet-wide SRE indicators.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.models.incident import Incident
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

# Upper bound on records pulled for aggregation. The dashboard only ever
# displays a bounded fleet, but incidents can accumulate indefinitely.
_INCIDENT_SCAN_LIMIT = 500


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

    # ── Query API ─────────────────────────────────────────────────────────────

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

        Snapshots are recomputed from the incident records on every call so
        the dashboard never displays stale aggregates, and the freshly
        computed values are persisted (best-effort) for the snapshot
        endpoints. If no window type is supplied, all stored snapshots are
        listed (the dashboard always requests an explicit window). If no
        incidents exist at all, previously stored snapshots are returned
        unchanged.
        """
        stored = self._repo.list(
            resource_id=resource_id,
            window_type=window_type,
            limit=limit,
        )
        if window_type is None:
            return [self._summary_from_metric(m) for m in stored]

        w_type = window_type
        incidents = self._incident_repo.list(
            resource_id=resource_id,
            limit=_INCIDENT_SCAN_LIMIT,
        )

        # No incident data to aggregate (e.g. a manually-created snapshot or a
        # freshly seeded environment): fall back to the stored records.
        if stored and not incidents:
            return [self._summary_from_metric(m) for m in stored]

        resources = self._resource_repo.list()
        target_resources = (
            [r for r in resources if r.resource_id.upper() == resource_id.strip().upper()]
            if resource_id
            else resources
        )

        now = datetime.now(UTC)
        w_start = self._window_start(w_type, incidents, now)

        summaries = [
            calculate_resource_metric_summary(
                resource_id=r.resource_id,
                incidents=incidents,
                window_type=w_type,
                window_start=w_start,
                window_end=now,
            )
            for r in target_resources
        ]
        self._persist_summaries(summaries, stored)
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
        incidents = self._incident_repo.list(
            resource_id=resource_id,
            limit=_INCIDENT_SCAN_LIMIT,
        )
        resources = self._resource_repo.list()

        # A resource-filtered overview must not leak fleet-wide health data.
        if resource_id:
            normalized = resource_id.strip().upper()
            resources = [
                r for r in resources if r.resource_id.upper() == normalized
            ]

        now = datetime.now(UTC)
        w_type = window_type or MetricWindowType.DAILY
        w_start = self._window_start(w_type, incidents, now)

        overview = calculate_fleet_reliability_overview(
            incidents=incidents,
            resources=resources,
            window_start=w_start,
            window_end=now,
            window_type=w_type,
        )

        stored = self._repo.list(window_type=w_type, limit=200)
        self._persist_summaries(overview.resources_metrics, stored)
        return overview

    # ── Persistence ───────────────────────────────────────────────────────────

    def persist_snapshot(
        self,
        resource_id: str,
        window_type: MetricWindowType = MetricWindowType.DAILY,
    ) -> ReliabilityMetric:
        """Compute and persist a single resource snapshot (best-effort caller)."""
        incidents = self._incident_repo.list(
            resource_id=resource_id,
            limit=_INCIDENT_SCAN_LIMIT,
        )
        now = datetime.now(UTC)
        summary = calculate_resource_metric_summary(
            resource_id=resource_id,
            incidents=incidents,
            window_type=window_type,
            window_start=self._window_start(window_type, incidents, now),
            window_end=now,
        )
        metric = self._summary_to_metric(summary)
        self._repo.put(metric)
        return metric

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _window_start(
        window_type: MetricWindowType,
        incidents: list[Incident],
        now: datetime,
    ) -> datetime | None:
        if window_type == MetricWindowType.DAILY:
            return now - timedelta(days=1)
        if window_type == MetricWindowType.WEEKLY:
            return now - timedelta(days=7)
        # CUMULATIVE: let the calculator derive the true start from the data.
        detected = [
            i.detected_at for i in incidents if getattr(i, "detected_at", None) is not None
        ]
        return min(detected, default=None)

    @staticmethod
    def _summary_from_metric(metric: ReliabilityMetric) -> ReliabilityMetricSummary:
        concluded = metric.resolved_incidents + metric.failed_recoveries
        success_rate = (
            round((metric.resolved_incidents / concluded) * 100.0, 2)
            if concluded
            else 100.0
        )
        failure_rate = (
            round((metric.failed_recoveries / concluded) * 100.0, 2)
            if concluded
            else 0.0
        )
        return ReliabilityMetricSummary(
            resource_id=metric.resource_id,
            window_type=metric.window_type,
            window_key=metric.window_key,
            window_start=metric.window_start,
            window_end=metric.window_end,
            total_incidents=metric.total_incidents,
            resolved_incidents=metric.resolved_incidents,
            failed_recoveries=metric.failed_recoveries,
            mttr_seconds=metric.mttr_seconds,
            mtbf_seconds=metric.mtbf_seconds,
            availability_pct=metric.availability_pct,
            computed_at=metric.computed_at,
            failure_type_counts=metric.failure_type_counts,
            recovery_success_rate_pct=success_rate,
            recovery_failure_rate_pct=failure_rate,
            avg_recovery_time_seconds=metric.mttr_seconds,
        )

    @staticmethod
    def _summary_to_metric(summary: ReliabilityMetricSummary) -> ReliabilityMetric:
        return ReliabilityMetric(
            resource_id=summary.resource_id,
            window_key=summary.window_key,
            window_type=summary.window_type,
            window_start=summary.window_start,
            window_end=summary.window_end,
            total_incidents=summary.total_incidents,
            resolved_incidents=summary.resolved_incidents,
            failed_recoveries=summary.failed_recoveries,
            mttr_seconds=summary.mttr_seconds,
            mtbf_seconds=summary.mtbf_seconds,
            availability_pct=summary.availability_pct,
            failure_type_counts=summary.failure_type_counts,
            computed_at=summary.computed_at,
        )

    def _persist_summaries(
        self,
        summaries: list[ReliabilityMetricSummary],
        existing: list[ReliabilityMetric] | None = None,
    ) -> None:
        """
        Persist computed snapshots without write amplification.

        Only records whose aggregate values changed are written. Failures are
        logged and ignored — a metrics outage must never break the dashboard.
        """
        existing_by_key = {
            (m.resource_id, m.window_key): m for m in (existing or [])
        }
        for summary in summaries:
            key = (summary.resource_id, summary.window_key)
            previous = existing_by_key.get(key)
            if previous is not None and self._same_metric(previous, summary):
                continue
            try:
                self._repo.put(self._summary_to_metric(summary))
            except Exception:
                logger.warning(
                    "Failed to persist reliability snapshot for %s/%s (non-fatal)",
                    summary.resource_id,
                    summary.window_key,
                    exc_info=True,
                )

    @staticmethod
    def _same_metric(previous: ReliabilityMetric, summary: ReliabilityMetricSummary) -> bool:
        return (
            previous.total_incidents == summary.total_incidents
            and previous.resolved_incidents == summary.resolved_incidents
            and previous.failed_recoveries == summary.failed_recoveries
            and previous.mttr_seconds == summary.mttr_seconds
            and previous.mtbf_seconds == summary.mtbf_seconds
            and previous.availability_pct == summary.availability_pct
            and previous.failure_type_counts == summary.failure_type_counts
        )
