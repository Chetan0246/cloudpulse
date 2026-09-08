"""
Recovery Lambda entry point.

Triggered by EventBridge when a CloudWatch Alarm enters ALARM state.

Event sources:
  1. CloudWatch Alarm state change → EventBridge → this Lambda
  2. Direct EventBridge PutEvents call from the /simulate/inject API
     (for fast demo, bypassing the CloudWatch alarm evaluation period)

Recovery state machine:
  FAILURE_DETECTED
    → RECOVERY_INITIATED  (this handler sets this immediately)
    → RECOVERY_IN_PROGRESS (action execution begins)
    → RECOVERED            (success)
    → RECOVERY_FAILED      (action threw exception)
    → MANUAL_INTERVENTION_REQUIRED (max retries exceeded)

Idempotency:
  The DynamoDB update_state call uses a conditional expression
  (condition_state=FAILURE_DETECTED). If the resource is already
  in a later recovery state (e.g., RECOVERY_IN_PROGRESS), the
  condition fails silently and we skip duplicate processing.
  This handles EventBridge at-least-once delivery.
"""
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, "/opt/python")

from app.config import get_settings
from app.logging_config import configure_logging
from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.resource import FailureType, ResourceState
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository

logger = logging.getLogger(__name__)


# ── Event Parsing ──────────────────────────────────────────────────────────────

def _parse_event(event: dict) -> tuple[str, FailureType]:
    """
    Extract resource_id and failure_type from an EventBridge event.

    Supports two event shapes:
      1. CloudWatch Alarm state change (source: aws.cloudwatch)
         Alarm naming convention: cloudpulse-{ResourceId}-{FailureType}
         e.g. cloudpulse-VM-001-HIGH_CPU

      2. Direct simulation event (source: cloudpulse.simulator)
         Detail: { "resourceId": "VM-001", "failureType": "HIGH_CPU" }
    """
    source = event.get("source", "")
    detail = event.get("detail", {})

    if source == "cloudpulse.simulator":
        # Direct injection event
        return detail["resourceId"], FailureType(detail["failureType"])

    if source == "aws.cloudwatch":
        # Parse alarm name: cloudpulse-{ResourceId}-{FailureType}
        alarm_name: str = detail.get("alarmName", "")
        parts = alarm_name.split("-")
        # Format: cloudpulse-VM-001-HIGH_CPU → parts: [cloudpulse, VM, 001, HIGH, CPU]
        # Reconstruct: resource_id = VM-001, failure_type = HIGH_CPU
        # Find the index of FailureType start by trying suffix combinations
        for i in range(len(parts) - 1, 1, -1):
            failure_candidate = "_".join(parts[i:]).upper()
            try:
                failure_type = FailureType(failure_candidate)
                resource_id = "-".join(parts[1:i]).upper()
                return resource_id, failure_type
            except ValueError:
                continue

    raise ValueError(f"Cannot parse event: source='{source}', detail={detail}")


# ── Recovery Actions (stubs; expanded in Phase 4) ──────────────────────────────

_RECOVERY_SIMULATED_DELAY: dict[FailureType, float] = {
    FailureType.HIGH_CPU: 3.0,
    FailureType.SERVICE_FAILURE: 5.0,
    FailureType.STORAGE_EXHAUSTION: 4.0,
    FailureType.NETWORK_LATENCY: 2.0,
    FailureType.SERVICE_DOWNTIME: 6.0,
}


def _execute_recovery_action(failure_type: FailureType, resource_id: str) -> str:
    """
    Simulate a recovery action. Returns a description of what was done.

    In a real system, this would call AWS APIs. Here we sleep briefly
    to simulate work and return a human-readable action description.
    """
    delay = _RECOVERY_SIMULATED_DELAY.get(failure_type, 3.0)
    logger.info(
        "Executing recovery action",
        extra={"resource_id": resource_id, "failure_type": failure_type, "simulated_delay": delay},
    )
    time.sleep(delay)  # Simulate recovery time

    action_descriptions = {
        FailureType.HIGH_CPU: "Simulated scale-out: increased virtual CPU allocation",
        FailureType.SERVICE_FAILURE: "Simulated service restart: health check resumed",
        FailureType.STORAGE_EXHAUSTION: "Simulated storage cleanup: freed 30% capacity",
        FailureType.NETWORK_LATENCY: "Simulated traffic reroute: alternate path active",
        FailureType.SERVICE_DOWNTIME: "Simulated failover: standby instance promoted",
    }
    return action_descriptions.get(failure_type, "Recovery action completed")


# ── SNS Notification ───────────────────────────────────────────────────────────

def _send_notification(
    subject: str,
    message: str,
    topic_arn: str,
    region: str,
) -> None:
    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN not configured; skipping notification")
        return
    try:
        sns = boto3.client("sns", region_name=region)
        sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info("SNS notification sent", extra={"subject": subject})
    except ClientError:
        logger.exception("Failed to send SNS notification")


# ── Main Handler ───────────────────────────────────────────────────────────────

def handler(event: dict, context: Any) -> dict:
    """Recovery Lambda handler."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Recovery Lambda invoked", extra={"event": event})

    # ── Parse event ──
    try:
        resource_id, failure_type = _parse_event(event)
    except (ValueError, KeyError) as e:
        logger.error("Failed to parse event", extra={"error": str(e), "event": event})
        return {"statusCode": 400, "body": f"Invalid event: {e}"}

    resource_repo = ResourceRepository()
    incident_repo = IncidentRepository()

    # ── Idempotency: only proceed if resource is in FAILURE_DETECTED ──
    try:
        updated_resource = resource_repo.update_state(
            resource_id=resource_id,
            new_state=ResourceState.RECOVERY_INITIATED,
            condition_state=ResourceState.FAILURE_DETECTED,
        )
    except Exception:
        logger.exception("Failed to transition resource to RECOVERY_INITIATED")
        return {"statusCode": 500, "body": "State transition failed"}

    if updated_resource.current_state != ResourceState.RECOVERY_INITIATED:
        logger.info(
            "Recovery already in progress or completed — skipping (idempotent)",
            extra={"resource_id": resource_id, "state": updated_resource.current_state},
        )
        return {"statusCode": 200, "body": "Already recovering"}

    # ── Create incident record ──
    incident = Incident(
        incident_id=str(uuid.uuid4()),
        resource_id=resource_id,
        failure_type=failure_type,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RECOVERING,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        recovery_initiated_at=datetime.now(timezone.utc),
        recovery_attempts=1,
    )
    incident_repo.create(incident)

    # ── Set RECOVERY_IN_PROGRESS ──
    resource_repo.update_state(resource_id, ResourceState.RECOVERY_IN_PROGRESS)

    # ── Execute simulated recovery action ──
    try:
        action_note = _execute_recovery_action(failure_type, resource_id)
        final_state = ResourceState.RECOVERED
        incident_status = IncidentStatus.RESOLVED
        notification_subject = f"[CloudPulse] RECOVERED: {resource_id} — {failure_type.value}"
        notification_message = (
            f"Resource {resource_id} has been automatically recovered.\n"
            f"Failure: {failure_type.value}\n"
            f"Action: {action_note}\n"
            f"Resolved at: {datetime.now(timezone.utc).isoformat()}"
        )
    except Exception as exc:
        logger.exception("Recovery action failed", extra={"resource_id": resource_id})
        final_state = ResourceState.RECOVERY_FAILED
        incident_status = IncidentStatus.ESCALATED
        action_note = f"Recovery failed: {exc}"
        notification_subject = f"[CloudPulse] RECOVERY FAILED: {resource_id} — {failure_type.value}"
        notification_message = (
            f"Recovery for {resource_id} FAILED. Manual intervention required.\n"
            f"Failure: {failure_type.value}\n"
            f"Error: {exc}"
        )

    # ── Update resource final state ──
    resource_repo.update_state(resource_id, final_state)

    # ── Close incident ──
    incident.status = incident_status
    incident.state_at_resolution = final_state
    incident.resolved_at = datetime.now(timezone.utc)
    incident.recovery_notes.append(action_note)
    incident.notification_sent = True
    incident_repo.update(incident)

    # ── SNS notification ──
    _send_notification(
        subject=notification_subject,
        message=notification_message,
        topic_arn=settings.sns_topic_arn,
        region=settings.aws_region,
    )

    logger.info(
        "Recovery complete",
        extra={
            "resource_id": resource_id,
            "failure_type": failure_type,
            "final_state": final_state,
            "incident_id": incident.incident_id,
        },
    )
    return {
        "statusCode": 200,
        "body": json.dumps({"incident_id": incident.incident_id, "final_state": final_state}),
    }
