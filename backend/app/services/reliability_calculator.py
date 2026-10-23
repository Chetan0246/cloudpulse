"""
Reliability and observability metric calculator.

Calculates all core SRE and reliability metrics strictly derived from
stored Incident and SimulatedResource records in DynamoDB:
1. Incident count
2. Recovery success rate
3. Recovery failure rate
4. Average recovery time
5. Mean Time to Recovery (MTTR)
6. Average detection time
7. Incident frequency (per hour, per day, MTBF)
8. Current resource health distribution

Guarantees:
- Zero invented metrics: Every figure is mathematically derived from stored data.
- Timezone safety: All timestamps are evaluated in UTC.
- Robust boundary handling: Zero-division safe, handles empty fleet and empty incidents gracefully.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Sequence

from app.models.incident import Incident, IncidentStatus, RecoveryActionStatus
from app.models.reliability_metric import (
    FleetReliabilityOverview,
    HealthDistribution,
    MetricWindowType,
    ReliabilityMetricSummary,
)
from app.models.resource import ResourceState, SimulatedResource


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _filter_by_window(
    incidents: Sequence[Incident],
    window_start: datetime | None,
    window_end: datetime | None,
) -> list[Incident]:
    """
    Return only incidents whose detection time falls inside the window.

    A window with either bound missing is treated as unbounded on that side.
    """
    w_start = _ensure_utc(window_start)
    w_end = _ensure_utc(window_end)
    if w_start is None and w_end is None:
        return list(incidents)

    filtered: list[Incident] = []
    for incident in incidents:
        detected = _ensure_utc(incident.detected_at)
        if detected is None:
            continue
        if w_start is not None and detected < w_start:
            continue
        if w_end is not None and detected > w_end:
            continue
        filtered.append(incident)
    return filtered


def _overlap_seconds(
    start: datetime | None,
    end: datetime | None,
    window_start: datetime,
    window_end: datetime,
) -> float:
    """Seconds of [start, end] that fall inside [window_start, window_end]."""
    s = _ensure_utc(start)
    e = _ensure_utc(end)
    if s is None or e is None or e <= s:
        return 0.0
    overlap_start = max(s, window_start)
    overlap_end = min(e, window_end)
    if overlap_end <= overlap_start:
        return 0.0
    return (overlap_end - overlap_start).total_seconds()


def calculate_failure_type_counts(incidents: Sequence[Incident]) -> dict[str, int]:
    """Count incidents per FailureType value within the supplied set."""
    counts: dict[str, int] = {}
    for incident in incidents:
        key = incident.failure_type.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def calculate_incident_count(incidents: Sequence[Incident]) -> int:
    """
    1. Incident count.
    Total count of incident records observed.
    """
    return len(incidents)


def calculate_recovery_success_rate(incidents: Sequence[Incident]) -> float:
    """
    2. Recovery success rate (%).
    Percentage of completed recovery attempts / closed incidents that culminated
    in successful restoration to RESOLVED.

    Formula:
        Rate = (len(resolved) / len(closed)) * 100.0
        where closed = resolved + escalated.

    Returns:
        100.0 if no closed incidents exist (nominal baseline), rounded to 2 decimals.
    """
    closed = [
        i for i in incidents
        if i.status in (IncidentStatus.RESOLVED, IncidentStatus.ESCALATED)
    ]
    if not closed:
        return 100.0

    resolved = [i for i in closed if i.status == IncidentStatus.RESOLVED]
    return round((len(resolved) / len(closed)) * 100.0, 2)


def calculate_recovery_failure_rate(incidents: Sequence[Incident]) -> float:
    """
    3. Recovery failure rate (%).
    Percentage of completed recovery attempts / closed incidents that resulted
    in failure or escalation to MANUAL_INTERVENTION_REQUIRED.

    Formula:
        Rate = (len(escalated) / len(closed)) * 100.0
        where closed = resolved + escalated.

    Returns:
        0.0 if no closed incidents exist, rounded to 2 decimals.
        Guarantees: success_rate + failure_rate == 100.0 when closed > 0.
    """
    closed = [
        i for i in incidents
        if i.status in (IncidentStatus.RESOLVED, IncidentStatus.ESCALATED)
    ]
    if not closed:
        return 0.0

    escalated = [i for i in closed if i.status == IncidentStatus.ESCALATED]
    return round((len(escalated) / len(closed)) * 100.0, 2)


def calculate_average_recovery_time(incidents: Sequence[Incident]) -> float | None:
    """
    4. Average recovery time (seconds).
    The average duration of active recovery execution across resolved incidents.

    Calculation:
        For each resolved incident:
        - If successful RecoveryActions have started_at and completed_at:
            duration = sum(completed_at - started_at)
        - Else if recovered_at and recovery_started_at are recorded:
            duration = (recovered_at - recovery_started_at)
        - Fallback: duration_seconds recorded on the incident.

    Returns:
        Mean duration in seconds rounded to 2 decimals, or None if no resolved incidents.
    """
    resolved = [i for i in incidents if i.status == IncidentStatus.RESOLVED]
    if not resolved:
        return None

    durations: list[float] = []
    for inc in resolved:
        # Check action durations first
        action_durations: list[float] = []
        for a in inc.recovery_actions:
            if a.status == RecoveryActionStatus.SUCCEEDED and a.completed_at and a.started_at:
                c_at = _ensure_utc(a.completed_at)
                s_at = _ensure_utc(a.started_at)
                if c_at and s_at and c_at >= s_at:
                    action_durations.append((c_at - s_at).total_seconds())

        if action_durations:
            durations.append(sum(action_durations))
        elif inc.recovered_at and (inc.recovery_started_at or inc.recovery_initiated_at):
            rec_at = _ensure_utc(inc.recovered_at)
            start_at = _ensure_utc(inc.recovery_started_at or inc.recovery_initiated_at)
            if rec_at and start_at and rec_at >= start_at:
                durations.append((rec_at - start_at).total_seconds())
        elif inc.duration_seconds is not None and inc.duration_seconds >= 0:
            durations.append(float(inc.duration_seconds))

    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def calculate_mttr(incidents: Sequence[Incident]) -> float | None:
    """
    5. Mean Time to Recovery (MTTR) (seconds).
    Total time from failure detection (detected_at) to resolution (resolved_at)
    across all resolved incidents.

    Calculation:
        For each resolved incident:
        duration = inc.duration_seconds or (resolved_at - detected_at)

    Returns:
        Mean MTTR in seconds rounded to 2 decimals, or None if no resolved incidents.
    """
    resolved = [i for i in incidents if i.status == IncidentStatus.RESOLVED]
    if not resolved:
        return None

    durations: list[float] = []
    for inc in resolved:
        if inc.duration_seconds is not None and inc.duration_seconds >= 0:
            durations.append(float(inc.duration_seconds))
        elif inc.resolved_at and inc.detected_at:
            res_at = _ensure_utc(inc.resolved_at)
            det_at = _ensure_utc(inc.detected_at)
            if res_at and det_at and res_at >= det_at:
                durations.append((res_at - det_at).total_seconds())

    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def calculate_average_detection_time(incidents: Sequence[Incident]) -> float | None:
    """
    6. Average detection time (seconds).
    The elapsed time between when an underlying failure occurs / is injected
    (created_at) and when the monitoring condition is detected (detected_at).

    Calculation:
        For each incident:
        time = max(0.0, (detected_at - created_at).total_seconds())

    Returns:
        Mean detection time in seconds rounded to 3 decimals, or None if no incidents.
    """
    if not incidents:
        return None

    detection_times: list[float] = []
    for inc in incidents:
        created_at = _ensure_utc(inc.created_at)
        detected_at = _ensure_utc(inc.detected_at)
        if created_at and detected_at:
            delta = (detected_at - created_at).total_seconds()
            detection_times.append(max(0.0, delta))

    if not detection_times:
        return None
    return round(sum(detection_times) / len(detection_times), 3)


def calculate_incident_frequency(
    incidents: Sequence[Incident],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[float, float, float | None]:
    """
    7. Incident frequency.
    Calculates:
    - incident_frequency_per_hour (rate)
    - incident_frequency_per_day (rate)
    - mtbf_seconds (Mean Time Between Failures in seconds)

    Returns:
        Tuple of (frequency_per_hour, frequency_per_day, mtbf_seconds).
    """
    # Callers normally pass an already window-scoped sequence. Re-filtering
    # here would drop incidents detected a few microseconds after `window_end`
    # (common when callers capture `now` before constructing records).
    count = len(incidents)

    if window_start and window_end:
        w_start = _ensure_utc(window_start)
        w_end = _ensure_utc(window_end)
        span_seconds = max(60.0, (w_end - w_start).total_seconds()) if w_start and w_end else 86400.0
    elif count > 0:
        earliest = min(_ensure_utc(i.created_at) or datetime.now(UTC) for i in incidents)
        latest = max(_ensure_utc(i.resolved_at or i.detected_at) or datetime.now(UTC) for i in incidents)
        span_seconds = max(60.0, (latest - earliest).total_seconds())
    else:
        span_seconds = 86400.0

    span_hours = span_seconds / 3600.0
    span_days = span_seconds / 86400.0

    freq_per_hour = round(count / span_hours, 4)
    freq_per_day = round(count / span_days, 2)

    # MTBF: Mean time between consecutive failure detections
    mtbf: float | None = None
    if count >= 2:
        sorted_detected = sorted(
            _ensure_utc(i.detected_at) or datetime.now(UTC)
            for i in incidents
        )
        deltas = [
            (sorted_detected[idx + 1] - sorted_detected[idx]).total_seconds()
            for idx in range(len(sorted_detected) - 1)
        ]
        if deltas:
            mtbf = round(sum(deltas) / len(deltas), 1)

    return freq_per_hour, freq_per_day, mtbf


def calculate_health_distribution(resources: Sequence[SimulatedResource]) -> HealthDistribution:
    """
    8. Current resource health distribution.
    Provides counts and percentages across lifecycle states and health statuses.
    """
    total = len(resources)
    if total == 0:
        return HealthDistribution(
            total_resources=0,
            healthy_count=0,
            warning_count=0,
            failed_count=0,
            recovering_count=0,
            healthy_pct=100.0,
            by_state={},
            by_status={},
        )

    healthy_count = 0
    warning_count = 0
    failed_count = 0
    recovering_count = 0

    by_state: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for r in resources:
        st = r.current_state
        hs = r.health_status

        by_state[st.value] = by_state.get(st.value, 0) + 1
        by_status[hs.value] = by_status.get(hs.value, 0) + 1

        if st in (ResourceState.HEALTHY, ResourceState.RECOVERED):
            healthy_count += 1
        elif st == ResourceState.WARNING:
            warning_count += 1
        elif st in (
            ResourceState.FAILURE_DETECTED,
            ResourceState.RECOVERY_FAILED,
            ResourceState.MANUAL_INTERVENTION_REQUIRED,
        ):
            failed_count += 1
        elif st in (
            ResourceState.RECOVERY_INITIATED,
            ResourceState.RECOVERY_IN_PROGRESS,
        ):
            recovering_count += 1

    healthy_pct = round((healthy_count / total) * 100.0, 2)

    return HealthDistribution(
        total_resources=total,
        healthy_count=healthy_count,
        warning_count=warning_count,
        failed_count=failed_count,
        recovering_count=recovering_count,
        healthy_pct=healthy_pct,
        by_state=by_state,
        by_status=by_status,
    )


def calculate_resource_metric_summary(
    resource_id: str,
    incidents: Sequence[Incident],
    window_type: MetricWindowType = MetricWindowType.DAILY,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> ReliabilityMetricSummary:
    """Compute ReliabilityMetricSummary for a single resource."""
    now = datetime.now(UTC)
    w_end = window_end or now

    res_incidents = [i for i in incidents if i.resource_id.upper() == resource_id.upper()]

    if window_type == MetricWindowType.CUMULATIVE:
        # "All time" truly means all incidents, not an arbitrary 30-day slice.
        window_incidents = list(res_incidents)
        detected_times = [
            _ensure_utc(i.detected_at) for i in res_incidents if i.detected_at is not None
        ]
        w_start = min(
            (d for d in detected_times if d is not None),
            default=window_start or (w_end - timedelta(days=1)),
        )
    else:
        w_start = window_start or (w_end - timedelta(days=1))
        window_incidents = _filter_by_window(res_incidents, w_start, w_end)

    if w_start > w_end:
        w_start = w_end - timedelta(days=1)

    total_inc = calculate_incident_count(window_incidents)
    resolved_inc = sum(1 for i in window_incidents if i.status == IncidentStatus.RESOLVED)
    failed_inc = sum(1 for i in window_incidents if i.status == IncidentStatus.ESCALATED)

    succ_rate = calculate_recovery_success_rate(window_incidents)
    fail_rate = calculate_recovery_failure_rate(window_incidents)
    avg_rec = calculate_average_recovery_time(window_incidents)
    mttr = calculate_mttr(window_incidents)
    avg_det = calculate_average_detection_time(window_incidents)
    freq_hr, freq_day, mtbf = calculate_incident_frequency(window_incidents, w_start, w_end)

    # Availability: only the portion of each outage that overlaps this window
    # counts. Unresolved outages are assumed to still be down at window_end.
    total_window_sec = max(1.0, (w_end - w_start).total_seconds())
    downtime_sec = 0.0
    for inc in window_incidents:
        if inc.status == IncidentStatus.RESOLVED:
            outage_end = inc.resolved_at or inc.recovered_at
        else:
            outage_end = w_end
        downtime_sec += _overlap_seconds(inc.detected_at, outage_end, w_start, w_end)

    availability = round(
        max(0.0, min(100.0, (1.0 - (downtime_sec / total_window_sec)) * 100.0)), 3
    )

    return ReliabilityMetricSummary(
        resource_id=resource_id.upper(),
        window_type=window_type,
        window_key=f"{window_type.value}#{w_start.strftime('%Y-%m-%d') if window_type != MetricWindowType.CUMULATIVE else 'ALL'}",
        window_start=w_start,
        window_end=w_end,
        total_incidents=total_inc,
        resolved_incidents=resolved_inc,
        failed_recoveries=failed_inc,
        mttr_seconds=mttr,
        mtbf_seconds=mtbf,
        availability_pct=availability,
        computed_at=now,
        failure_type_counts=calculate_failure_type_counts(window_incidents),
        recovery_success_rate_pct=succ_rate,
        recovery_failure_rate_pct=fail_rate,
        avg_recovery_time_seconds=avg_rec,
        avg_detection_time_seconds=avg_det,
        incident_frequency_per_hour=freq_hr,
        incident_frequency_per_day=freq_day,
    )


def calculate_fleet_reliability_overview(
    incidents: Sequence[Incident],
    resources: Sequence[SimulatedResource],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    window_type: MetricWindowType = MetricWindowType.DAILY,
) -> FleetReliabilityOverview:
    """
    Produce the comprehensive 8-metric observability & reliability report.

    Every incident-derived metric is scoped to the requested window. Health
    distribution is a point-in-time snapshot and therefore covers the fleet
    passed by the caller.
    """
    now = datetime.now(UTC)
    w_end = window_end or now

    if window_type == MetricWindowType.CUMULATIVE:
        window_incidents = list(incidents)
        detected_times = [
            _ensure_utc(i.detected_at) for i in incidents if i.detected_at is not None
        ]
        w_start = min(
            (d for d in detected_times if d is not None),
            default=window_start or (w_end - timedelta(days=1)),
        )
    else:
        w_start = window_start or (w_end - timedelta(days=1))
        window_incidents = _filter_by_window(incidents, w_start, w_end)

    if w_start > w_end:
        w_start = w_end - timedelta(days=1)

    inc_count = calculate_incident_count(window_incidents)
    succ_rate = calculate_recovery_success_rate(window_incidents)
    fail_rate = calculate_recovery_failure_rate(window_incidents)
    avg_rec = calculate_average_recovery_time(window_incidents)
    mttr = calculate_mttr(window_incidents)
    avg_det = calculate_average_detection_time(window_incidents)
    freq_hr, freq_day, mtbf = calculate_incident_frequency(window_incidents, w_start, w_end)
    health_dist = calculate_health_distribution(resources)

    # Per-resource summaries
    resources_metrics: list[ReliabilityMetricSummary] = []
    for r in resources:
        resources_metrics.append(
            calculate_resource_metric_summary(
                resource_id=r.resource_id,
                incidents=incidents,
                window_type=window_type,
                window_start=w_start,
                window_end=w_end,
            )
        )

    return FleetReliabilityOverview(
        incident_count=inc_count,
        recovery_success_rate_pct=succ_rate,
        recovery_failure_rate_pct=fail_rate,
        avg_recovery_time_seconds=avg_rec,
        mttr_seconds=mttr,
        avg_detection_time_seconds=avg_det,
        incident_frequency_per_hour=freq_hr,
        incident_frequency_per_day=freq_day,
        mtbf_seconds=mtbf,
        health_distribution=health_dist,
        computed_at=datetime.now(UTC),
        resources_metrics=resources_metrics,
    )
