"""
Business logic service for incidents.

Coordinates incident retrieval, listing, and filtering between routers
and the repository layer.
"""

import logging

from app.models.incident import IncidentDetail, IncidentStatus, IncidentSummary
from app.models.resource import FailureType
from app.repositories.incident_repository import IncidentRepository

logger = logging.getLogger(__name__)


class IncidentService:
    """Service handling incident business logic."""

    def __init__(self, repo: IncidentRepository | None = None) -> None:
        self._repo = repo or IncidentRepository()

    def get_incident(self, incident_id: str) -> IncidentDetail:
        """
        Retrieve full incident details including embedded recovery actions.

        Raises:
            IncidentNotFoundError: If incident is not found.
        """
        incident = self._repo.get(incident_id)
        return IncidentDetail(
            incident_id=incident.incident_id,
            resource_id=incident.resource_id,
            failure_type=incident.failure_type,
            severity=incident.severity,
            status=incident.status,
            state_at_detection=incident.state_at_detection,
            state_at_resolution=incident.state_at_resolution,
            created_at=incident.created_at,
            detected_at=incident.detected_at,
            recovery_started_at=incident.recovery_started_at or incident.recovery_initiated_at,
            recovery_initiated_at=incident.recovery_initiated_at or incident.recovery_started_at,
            recovered_at=incident.recovered_at or incident.resolved_at,
            resolved_at=incident.resolved_at or incident.recovered_at,
            escalated_at=incident.escalated_at,
            updated_at=incident.updated_at,
            duration_seconds=incident.duration_seconds,
            recovery_action=incident.recovery_action,
            recovery_result=incident.recovery_result,
            notification_status=incident.notification_status,
            retry_count=incident.retry_count or incident.recovery_attempts,
            recovery_attempts=incident.recovery_attempts,
            error_message=incident.error_message,
            recovery_actions=incident.recovery_actions,
            recovery_notes=incident.recovery_notes,
            notification_sent=incident.notification_sent,
            notified_transitions=incident.notified_transitions,
        )

    def list_incidents(
        self,
        resource_id: str | None = None,
        status: IncidentStatus | None = None,
        failure_type: FailureType | None = None,
        limit: int = 50,
    ) -> list[IncidentSummary]:
        """
        List incidents matching query filters as lightweight summaries.
        """
        incidents = self._repo.list(
            resource_id=resource_id,
            status=status,
            failure_type=failure_type,
            limit=limit,
        )
        return [
            IncidentSummary(
                incident_id=inc.incident_id,
                resource_id=inc.resource_id,
                failure_type=inc.failure_type,
                severity=inc.severity,
                status=inc.status,
                created_at=inc.created_at,
                detected_at=inc.detected_at,
                recovery_started_at=inc.recovery_started_at or inc.recovery_initiated_at,
                recovered_at=inc.recovered_at or inc.resolved_at,
                resolved_at=inc.resolved_at or inc.recovered_at,
                escalated_at=inc.escalated_at,
                duration_seconds=inc.duration_seconds,
                recovery_action=inc.recovery_action,
                recovery_result=inc.recovery_result,
                notification_status=inc.notification_status,
                retry_count=inc.retry_count or inc.recovery_attempts,
                recovery_attempts=inc.recovery_attempts,
                error_message=inc.error_message,
            )
            for inc in incidents
        ]

