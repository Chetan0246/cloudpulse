"""
SNS notification service for CloudPulse incident lifecycle transitions.

Dispatches human-readable email notifications via AWS SNS for key lifecycle events:
1. Failure detected
2. Recovery started
3. Recovery successful
4. Recovery failed

Guarantees:
- Duplicate notifications are prevented by tracking `incident.notified_transitions`.
- All messages are human-readable and contain:
  * Incident ID
  * Resource ID
  * Failure Type
  * Lifecycle Status
  * Recovery duration (when available)
- SNS errors are non-fatal — logged as warnings so notification failures never
  block the core recovery engine or failure simulation.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from botocore.exceptions import ClientError

from app.aws.clients import get_sns_client
from app.config import get_settings
from app.models.incident import Incident

logger = logging.getLogger(__name__)


class NotificationTransition(str, Enum):
    """Important incident lifecycle transitions that trigger SNS notifications."""

    FAILURE_DETECTED = "FAILURE_DETECTED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_SUCCESSFUL = "RECOVERY_SUCCESSFUL"
    RECOVERY_FAILED = "RECOVERY_FAILED"


class NotificationService:
    """Handles dispatching SNS notifications for incident lifecycle events."""

    def __init__(
        self,
        sns_client: Any | None = None,
        topic_arn: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self._sns_client = sns_client
        self._topic_arn = topic_arn
        self._region_name = region_name

    @property
    def sns_client(self) -> Any:
        if self._sns_client is None:
            settings = get_settings()
            region = self._region_name or settings.aws_region
            self._sns_client = get_sns_client(region)
        return self._sns_client

    @property
    def topic_arn(self) -> str:
        if self._topic_arn is None:
            self._topic_arn = get_settings().sns_topic_arn
        return self._topic_arn

    def format_message(
        self,
        transition: NotificationTransition,
        incident: Incident,
        *,
        action_name: str | None = None,
        duration_seconds: float | None = None,
        error_message: str | None = None,
        attempt: int | None = None,
        max_attempts: int | None = None,
    ) -> tuple[str, str]:
        """
        Build a human-readable email Subject and Body for an incident transition.

        Returns:
            Tuple of (subject, body).
        """
        resource_id = incident.resource_id
        failure_type = incident.failure_type.value
        incident_id = incident.incident_id
        status_val = incident.status.value

        divider = "=" * 70

        if transition == NotificationTransition.FAILURE_DETECTED:
            subject = f"[CloudPulse] FAILURE DETECTED: {resource_id} — {failure_type}"
            body = (
                f"{divider}\n"
                f"CLOUDPULSE ALERT: Failure Detected\n"
                f"{divider}\n"
                f"Incident ID:    {incident_id}\n"
                f"Correlation ID: {incident_id}\n"
                f"Resource:       {resource_id}\n"
                f"Failure Type:   {failure_type}\n"
                f"Severity:       {incident.severity.value}\n"
                f"Status:         {status_val}\n"
                f"Detected At:    {incident.detected_at.isoformat()}\n"
                f"{divider}\n"
                f"Description:\n"
                f"A failure condition has been detected on simulated resource '{resource_id}'.\n"
                f"Autonomous self-healing recovery will be initiated via EventBridge.\n"
                f"{divider}\n"
            )
            return subject, body

        if transition == NotificationTransition.RECOVERY_STARTED:
            action = action_name or incident.recovery_action or "AUTOMATED_STRATEGY"
            att_str = f"Attempt {attempt}/{max_attempts}" if attempt and max_attempts else f"Attempt {attempt or 1}"
            subject = f"[CloudPulse] RECOVERY STARTED: {resource_id} — {failure_type}"
            body = (
                f"{divider}\n"
                f"CLOUDPULSE ALERT: Recovery Started\n"
                f"{divider}\n"
                f"Incident ID:     {incident_id}\n"
                f"Correlation ID:  {incident_id}\n"
                f"Resource:        {resource_id}\n"
                f"Failure Type:    {failure_type}\n"
                f"Status:          {status_val}\n"
                f"Recovery Action: {action}\n"
                f"Progress:        {att_str}\n"
                f"Started At:      {(incident.recovery_started_at or incident.detected_at).isoformat()}\n"
                f"{divider}\n"
                f"Description:\n"
                f"Automated recovery workflow has started for resource '{resource_id}'.\n"
                f"Executing recovery action: {action}.\n"
                f"{divider}\n"
            )
            return subject, body

        if transition == NotificationTransition.RECOVERY_SUCCESSFUL:
            action = action_name or incident.recovery_action or "RECOVERY_ACTION"
            dur = duration_seconds if duration_seconds is not None else incident.duration_seconds
            dur_str = f"{dur:.2f} seconds" if dur is not None else "N/A"
            resolved_at = (incident.recovered_at or incident.resolved_at or incident.detected_at).isoformat()
            subject = f"[CloudPulse] RECOVERED: {resource_id} — {failure_type}"
            body = (
                f"{divider}\n"
                f"CLOUDPULSE ALERT: Recovery Successful\n"
                f"{divider}\n"
                f"Incident ID:       {incident_id}\n"
                f"Correlation ID:    {incident_id}\n"
                f"Resource:          {resource_id}\n"
                f"Failure Type:      {failure_type}\n"
                f"Status:            {status_val}\n"
                f"Recovery Action:   {action}\n"
                f"Recovery Duration: {dur_str}\n"
                f"Resolved At:       {resolved_at}\n"
                f"{divider}\n"
                f"Description:\n"
                f"Resource '{resource_id}' has been successfully recovered.\n"
                f"Synthetic metrics have returned to nominal operating thresholds.\n"
                f"{divider}\n"
            )
            return subject, body

        if transition == NotificationTransition.RECOVERY_FAILED:
            err = error_message or incident.error_message or "Unknown recovery error"
            att_str = f"Attempt {attempt}/{max_attempts}" if attempt and max_attempts else f"Attempt {attempt or 1}"
            subject = f"[CloudPulse] RECOVERY FAILED: {resource_id} — {failure_type}"
            body = (
                f"{divider}\n"
                f"CLOUDPULSE ALERT: Recovery Failed\n"
                f"{divider}\n"
                f"Incident ID:    {incident_id}\n"
                f"Correlation ID: {incident_id}\n"
                f"Resource:       {resource_id}\n"
                f"Failure Type:   {failure_type}\n"
                f"Status:         {status_val}\n"
                f"Progress:       {att_str}\n"
                f"Error Message:  {err}\n"
                f"{divider}\n"
                f"Description:\n"
                f"Automated recovery attempt failed for resource '{resource_id}'.\n"
                f"Manual intervention may be required if retry attempts are exhausted.\n"
                f"{divider}\n"
            )
            return subject, body

        raise ValueError(f"Unknown notification transition: {transition}")

    def send_notification(self, subject: str, message: str) -> bool:
        """
        Publish an SNS notification.

        Returns:
            True if message was accepted by SNS, False if skipped or failed.
        """
        if not self.topic_arn:
            logger.warning("SNS_TOPIC_ARN not configured; skipping notification publish")
            return False

        try:
            self.sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=message,
            )
            logger.info("SNS notification published successfully", extra={"subject": subject})
            return True
        except ClientError as exc:
            logger.warning("Failed to publish SNS notification (non-fatal): %s", exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error publishing SNS notification (non-fatal): %s", exc)
            return False

    def notify(
        self,
        incident: Incident,
        transition: NotificationTransition,
        *,
        action_name: str | None = None,
        duration_seconds: float | None = None,
        error_message: str | None = None,
        attempt: int | None = None,
        max_attempts: int | None = None,
    ) -> tuple[Incident, bool]:
        """
        Send notification for a transition if not already sent (duplicate guard).

        Returns:
            Tuple of (updated_incident, was_sent).
        """
        trans_val = transition.value

        # Duplicate protection guard
        if trans_val in incident.notified_transitions:
            logger.info(
                "Notification for %s already sent for incident %s; skipping duplicate.",
                trans_val,
                incident.incident_id,
            )
            return incident, False

        subject, message = self.format_message(
            transition=transition,
            incident=incident,
            action_name=action_name,
            duration_seconds=duration_seconds,
            error_message=error_message,
            attempt=attempt,
            max_attempts=max_attempts,
        )

        success = self.send_notification(subject, message)

        logger.info(
            "SNS lifecycle notification processed",
            extra={
                "stage": "notification",
                "correlation_id": incident.incident_id,
                "incident_id": incident.incident_id,
                "resource_id": incident.resource_id,
                "transition": trans_val,
                "status": "SENT" if success else ("NOT_CONFIGURED" if not self.topic_arn else "FAILED"),
            },
        )

        new_transitions = [*incident.notified_transitions, trans_val]
        updated_incident = incident.model_copy(
            update={
                "notified_transitions": new_transitions,
                "notification_status": "SENT" if success else ("NOT_CONFIGURED" if not self.topic_arn else "FAILED"),
                "notification_sent": True if success else incident.notification_sent,
            }
        )
        return updated_incident, success

    def notify_failure_detected(self, incident: Incident) -> tuple[Incident, bool]:
        return self.notify(incident, NotificationTransition.FAILURE_DETECTED)

    def notify_recovery_started(
        self,
        incident: Incident,
        action_name: str | None = None,
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> tuple[Incident, bool]:
        return self.notify(
            incident,
            NotificationTransition.RECOVERY_STARTED,
            action_name=action_name,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    def notify_recovery_successful(
        self,
        incident: Incident,
        action_name: str | None = None,
        duration_seconds: float | None = None,
    ) -> tuple[Incident, bool]:
        return self.notify(
            incident,
            NotificationTransition.RECOVERY_SUCCESSFUL,
            action_name=action_name,
            duration_seconds=duration_seconds,
        )

    def notify_recovery_failed(
        self,
        incident: Incident,
        error_message: str | None = None,
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> tuple[Incident, bool]:
        return self.notify(
            incident,
            NotificationTransition.RECOVERY_FAILED,
            error_message=error_message,
            attempt=attempt,
            max_attempts=max_attempts,
        )
