"""
Simulation service — business logic for failure injection and resource recovery/reset.

This is a SIMULATOR. It modifies virtual resource states and emits custom CloudWatch
metrics. It does NOT interact with, stop, or destroy real AWS infrastructure.

Metric publishing and EventBridge event emission are delegated to MonitoringService
to keep this service focused on state machine logic only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.exceptions import SimulationError
from app.logging_config import set_correlation_id, set_incident_id, set_trace_stage
from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.resource import (
    FAILURE_METRIC_TARGETS,
    FailureType,
    HealthStatus,
    ResourceState,
    SimulatedResource,
)
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.metric_service import MetricService
from app.services.monitoring_service import MonitoringService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Hard bounds for client-supplied metric overrides. These mirror the field
# constraints on SimulatedResource; validating here prevents a bad override
# from being persisted (which would make every subsequent read fail).
_METRIC_BOUNDS: dict[str, tuple[float, float]] = {
    "cpu_utilization": (0.0, 100.0),
    "memory_utilization": (0.0, 100.0),
    "storage_utilization": (0.0, 100.0),
    "network_latency_ms": (0.0, 99999.0),
}


# Scenario mappings
SCENARIO_CODE_MAP: dict[FailureType, str] = {
    FailureType.HIGH_CPU: "FS-01",
    FailureType.SERVICE_FAILURE: "FS-02",
    FailureType.STORAGE_EXHAUSTION: "FS-03",
    FailureType.NETWORK_LATENCY: "FS-04",
    FailureType.SERVICE_DOWNTIME: "FS-05",
}

SCENARIO_NAME_MAP: dict[FailureType, str] = {
    FailureType.HIGH_CPU: "FS-01 High CPU Utilization",
    FailureType.SERVICE_FAILURE: "FS-02 Service Failure",
    FailureType.STORAGE_EXHAUSTION: "FS-03 Storage Exhaustion",
    FailureType.NETWORK_LATENCY: "FS-04 Network Latency",
    FailureType.SERVICE_DOWNTIME: "FS-05 Service Downtime",
}

_NOMINAL_METRICS: dict[str, float] = {
    "cpu_utilization": 25.0,
    "memory_utilization": 30.0,
    "storage_utilization": 20.0,
    "network_latency_ms": 15.0,
}


class SimulationService:
    """
    Coordinates safe, deterministic failure simulation on virtual resources.

    Steps executed on failure injection:
    1. Validate the target resource exists and is in an injectable state.
    2. Transition simulated health state to FAILURE_DETECTED (CRITICAL).
    3. Record the simulated fault metrics deterministically.
    4. Emit CloudWatch custom metrics via MonitoringService (non-fatal).
    5. Emit EventBridge FailureInjected event via MonitoringService (non-fatal).
    6. Create an Incident record in DynamoDB.
    7. Return a comprehensive simulation result.
    """

    def __init__(
        self,
        resource_repo: ResourceRepository | None = None,
        incident_repo: IncidentRepository | None = None,
        monitoring_service: MonitoringService | None = None,
        notification_service: NotificationService | None = None,
        metric_service: MetricService | None = None,
    ) -> None:
        self._resource_repo = resource_repo or ResourceRepository()
        self._incident_repo = incident_repo or IncidentRepository()
        self._monitoring = monitoring_service or MonitoringService()
        self._notification = notification_service or NotificationService()
        self._metric_service = metric_service or MetricService(
            incident_repo=self._incident_repo,
            resource_repo=self._resource_repo,
        )

    def inject_failure(
        self,
        resource_id: str,
        failure_type: FailureType,
        severity: IncidentSeverity | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> tuple[SimulatedResource, Incident, dict[str, float]]:
        """
        Inject a simulated failure scenario onto a virtual resource.

        Args:
            resource_id: Identifier of the virtual resource, e.g. 'VM-001'.
            failure_type: The failure scenario (HIGH_CPU, SERVICE_FAILURE, etc.).
            severity: Optional incident severity override.
            parameters: Optional custom metric overrides or test knobs.

        Returns:
            Tuple of (updated SimulatedResource, created Incident, emitted metrics dict).

        Raises:
            ResourceNotFoundError: If resource does not exist.
            SimulationError: If resource is already in failure/recovery state.
        """
        norm_resource_id = resource_id.strip().upper()
        resource = self._resource_repo.get(norm_resource_id)

        # 1. State machine validation
        if not resource.current_state.can_transition_to(ResourceState.FAILURE_DETECTED):
            raise SimulationError(
                f"Cannot inject failure: resource '{norm_resource_id}' is currently in state "
                f"'{resource.current_state.value}'. "
                "Reset the resource before injecting a new failure."
            )

        # 2 & 3. Calculate deterministic failure metrics
        metrics = dict(FAILURE_METRIC_TARGETS[failure_type])
        params = parameters or {}

        # Allow parameters to override metric targets if provided. Overrides are
        # validated against the same bounds as SimulatedResource so a bad value
        # can never reach DynamoDB and poison every later read.
        for metric_key, (lower, upper) in _METRIC_BOUNDS.items():
            if metric_key not in params:
                continue
            raw_value = params[metric_key]
            if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
                raise SimulationError(
                    f"Invalid override for '{metric_key}': expected a number, "
                    f"got {type(raw_value).__name__}"
                )
            value = float(raw_value)
            if not lower <= value <= upper:
                raise SimulationError(
                    f"Invalid override for '{metric_key}': {value} is outside "
                    f"the allowed range [{lower}, {upper}]"
                )
            metrics[metric_key] = value

        scenario_code = SCENARIO_CODE_MAP[failure_type]
        incident_id = str(uuid.uuid4())
        correlation_id = incident_id
        set_correlation_id(correlation_id)
        set_incident_id(incident_id)
        set_trace_stage("simulation")

        logger.info(
            "Simulation initiated: injecting failure condition",
            extra={
                "stage": "simulation",
                "correlation_id": correlation_id,
                "incident_id": incident_id,
                "resource_id": norm_resource_id,
                "failure_type": failure_type.value,
                "scenario": scenario_code,
            },
        )

        now = datetime.now(UTC)
        updated_resource = SimulatedResource.model_validate(
            {
                **{name: getattr(resource, name) for name in SimulatedResource.model_fields},
                **metrics,
                "current_state": ResourceState.FAILURE_DETECTED,
                "health_status": HealthStatus.CRITICAL,
                "active_failure_type": failure_type,
                "updated_at": now,
                "last_heartbeat": now,
            }
        )
        self._resource_repo.put(updated_resource)

        # Detection phase
        set_trace_stage("detection")
        logger.info(
            "Failure detected: resource entered FAILURE_DETECTED",
            extra={
                "stage": "detection",
                "correlation_id": correlation_id,
                "incident_id": incident_id,
                "resource_id": norm_resource_id,
                "failure_type": failure_type.value,
                "health_status": HealthStatus.CRITICAL.value,
            },
        )

        # 4. Emit CloudWatch metrics via MonitoringService (non-fatal)
        emitted_metrics = self._monitoring.publish_resource_metrics(updated_resource)

        # 5. Create Incident record
        inc_severity = severity or IncidentSeverity(failure_type.default_severity())
        incident = Incident(
            incident_id=incident_id,
            resource_id=norm_resource_id,
            failure_type=failure_type,
            severity=inc_severity,
            status=IncidentStatus.OPEN,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            created_at=now,
            detected_at=now,
            recovery_attempts=0,
            retry_count=0,
            recovery_actions=[],
        )
        self._incident_repo.create(incident)

        # 5b. Dispatch Failure Detected SNS notification (non-fatal, avoids duplicates)
        incident, _ = self._notification.notify_failure_detected(incident)
        self._incident_repo.update(incident)

        # 5c. Persist a reliability snapshot for the new incident (non-fatal)
        self._persist_snapshot(norm_resource_id)

        # 6. Emit EventBridge FailureInjected event (non-fatal, bypasses alarm wait)
        set_trace_stage("event")
        self._monitoring.emit_failure_event(
            resource=updated_resource,
            scenario_code=scenario_code,
            incident_id=incident_id,
        )

        logger.info(
            "Simulated failure injected successfully",
            extra={
                "stage": "event",
                "scenario": scenario_code,
                "resource_id": norm_resource_id,
                "failure_type": failure_type.value,
                "incident_id": incident_id,
                "correlation_id": correlation_id,
            },
        )
        return updated_resource, incident, emitted_metrics


    def reset_resource(self, resource_id: str) -> tuple[SimulatedResource, list[str]]:
        """
        Manually reset/recover a simulated resource to HEALTHY with nominal metrics.
        Closes any currently active (OPEN or RECOVERING) incidents.

        Returns:
            Tuple of (reset SimulatedResource, list of resolved incident IDs).
        """
        norm_resource_id = resource_id.strip().upper()
        resource = self._resource_repo.get(norm_resource_id)
        now = datetime.now(UTC)

        if not resource.current_state.can_transition_to(ResourceState.HEALTHY):
            raise SimulationError(
                f"Cannot reset resource '{norm_resource_id}' from state "
                f"'{resource.current_state.value}'."
            )

        # Reset resource state and metrics to nominal
        updated_resource = SimulatedResource.model_validate(
            {
                **{name: getattr(resource, name) for name in SimulatedResource.model_fields},
                **_NOMINAL_METRICS,
                "current_state": ResourceState.HEALTHY,
                "health_status": HealthStatus.HEALTHY,
                "active_failure_type": None,
                "updated_at": now,
                "last_heartbeat": now,
            }
        )
        self._resource_repo.put(updated_resource)

        # Emit nominal metrics to CloudWatch via MonitoringService (non-fatal)
        self._monitoring.publish_resource_metrics(updated_resource)

        # Resolve any active incidents for this resource
        active_incidents = self._incident_repo.list(
            resource_id=norm_resource_id,
            limit=20,
        )
        resolved_ids: list[str] = []

        for inc in active_incidents:
            if inc.status in (IncidentStatus.OPEN, IncidentStatus.RECOVERING):
                manual_action = RecoveryAction(
                    action_id=str(uuid.uuid4()),
                    action_type=RecoveryActionType.MANUAL,
                    status=RecoveryActionStatus.SUCCEEDED,
                    started_at=now,
                    completed_at=now,
                    outcome_message=(
                        f"Manual reset executed via simulation API for {norm_resource_id}"
                    ),
                )
                duration = (now - inc.detected_at).total_seconds()
                updated_inc = Incident.model_validate(
                    {
                        **{name: getattr(inc, name) for name in Incident.model_fields},
                        "status": IncidentStatus.RESOLVED,
                        "state_at_resolution": ResourceState.RECOVERED,
                        "resolved_at": now,
                        "recovered_at": now,
                        "recovery_action": RecoveryActionType.MANUAL.value,
                        "recovery_result": "MANUALLY_RESOLVED",
                        "duration_seconds": max(0.0, duration),
                        "recovery_attempts": inc.recovery_attempts + 1,
                        "retry_count": inc.recovery_attempts + 1,
                        "recovery_actions": [*inc.recovery_actions, manual_action],
                        "updated_at": now,
                    }
                )
                self._incident_repo.update(updated_inc)
                resolved_ids.append(inc.incident_id)

        # Refresh the persisted reliability snapshot (non-fatal)
        self._persist_snapshot(norm_resource_id)

        logger.info(
            "Resource manually reset to HEALTHY",
            extra={"resource_id": norm_resource_id, "resolved_incidents": resolved_ids},
        )
        return updated_resource, resolved_ids

    def _persist_snapshot(self, resource_id: str) -> None:
        """Persist a reliability snapshot without ever failing the caller."""
        try:
            self._metric_service.persist_snapshot(resource_id)
        except Exception:
            logger.warning(
                "Failed to persist reliability snapshot for %s (non-fatal)",
                resource_id,
                exc_info=True,
            )

