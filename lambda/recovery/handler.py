"""
Recovery Lambda entry point — CloudPulse Self-Healing Engine.

SAFETY NOTICE: All recovery actions are SIMULATED. This handler mutates
virtual resource state in DynamoDB and resets synthetic CloudWatch metrics.
It does NOT call any real AWS compute/database infrastructure APIs
(no ec2:*, rds:*, ecs:*, or lambda:DeleteFunction calls).

Triggered by EventBridge when:
  1. A CloudWatch Alarm enters ALARM state (source: aws.cloudwatch)
  2. A direct injection event from the /simulate/failure API
     (source: cloudpulse.simulator) — fast path for demos

Recovery state machine:
  FAILURE_DETECTED
    → RECOVERY_INITIATED  (pre-read gate + conditional DynamoDB write)
    → RECOVERY_IN_PROGRESS (strategy dispatched)
    → RECOVERED            (strategy succeeded; metrics reset)
    → RECOVERY_FAILED      (strategy raised exception; attempt < MAX)
    → MANUAL_INTERVENTION_REQUIRED (max attempts exhausted)

Idempotency (two-layer guard):
  Layer 1 — Pre-read: if resource is not FAILURE_DETECTED, exit immediately.
  Layer 2 — Conditional DynamoDB update: only succeeds when current_state
             equals FAILURE_DETECTED. Concurrent duplicate events are
             serialised by DynamoDB conditional expressions.

Audit trail:
  Every recovery attempt creates a RecoveryAction embedded in the Incident
  document. The Incident model enforces that recovery_attempts always equals
  len(recovery_actions).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, "/opt/python")
sys.path.insert(0, os.path.dirname(__file__))  # Allow `from strategies import ...`

from app.config import get_settings
from app.logging_config import configure_logging
from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
)
from app.models.resource import FailureType, HealthStatus, ResourceState
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from app.services.monitoring_service import MonitoringService
from app.services.notification_service import NotificationService, NotificationTransition
from strategies import MAX_RECOVERY_ATTEMPTS, RecoveryStrategyError, dispatch_strategy

logger = logging.getLogger(__name__)


# ── Event Parsing ──────────────────────────────────────────────────────────────


def _parse_event(event: dict) -> tuple[str, FailureType]:
    """
    Extract resource_id and failure_type from an EventBridge event.

    Supports two event shapes:
      1. CloudWatch Alarm state change (source: aws.cloudwatch)
         Alarm naming convention: cloudpulse-{ResourceId}-{FailureType}
         e.g. cloudpulse-VM-001-HIGH_CPU, cloudpulse-STORAGE-001-STORAGE_EXHAUSTION

      2. Direct simulation event (source: cloudpulse.simulator)
         Detail: { "resourceId": "VM-001", "failureType": "HIGH_CPU" }
    """
    source = event.get("source", "")
    detail = event.get("detail", {})

    if source == "cloudpulse.simulator":
        return detail["resourceId"], FailureType(detail["failureType"])

    if source == "aws.cloudwatch":
        # Suffix-first parsing to handle multi-hyphen resource IDs like STORAGE-001
        alarm_name: str = detail.get("alarmName", "")
        parts = alarm_name.split("-")
        for i in range(len(parts) - 1, 1, -1):
            failure_candidate = "_".join(parts[i:]).upper()
            try:
                failure_type = FailureType(failure_candidate)
                resource_id = "-".join(parts[1:i]).upper()
                return resource_id, failure_type
            except ValueError:
                continue

    raise ValueError(f"Cannot parse event: source='{source}', detail={detail}")


# ── SNS Notification ───────────────────────────────────────────────────────────


def _send_notification(
    subject: str,
    message: str,
    topic_arn: str,
    region: str,
) -> None:
    """Publish an SNS notification. Non-fatal — errors are logged, not raised."""
    if not topic_arn:
        logger.warning("SNS_TOPIC_ARN not configured; skipping notification")
        return
    try:
        sns = boto3.client("sns", region_name=region)
        sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info("SNS notification sent", extra={"subject": subject})
    except ClientError:
        logger.exception("Failed to send SNS notification")


# ── CloudWatch metric reset (non-fatal) ────────────────────────────────────────


def _publish_recovery_metrics(resource: Any) -> None:
    """
    Publish reset metric values to CloudWatch so alarms can clear.
    Non-fatal — a monitoring outage must not block recovery audit records.
    """
    try:
        MonitoringService().publish_resource_metrics(resource)
    except Exception:
        logger.exception(
            "Failed to publish recovery metrics to CloudWatch "
            "(non-fatal — audit trail is still complete)"
        )


# ── Main Handler ───────────────────────────────────────────────────────────────


def handler(event: dict, context: Any) -> dict:
    """Recovery Lambda handler — CloudPulse self-healing entry point."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Recovery Lambda invoked", extra={"event": event})

    # ── 1. Parse event ─────────────────────────────────────────────────────────
    try:
        resource_id, failure_type = _parse_event(event)
    except (ValueError, KeyError) as e:
        logger.error("Failed to parse event", extra={"error": str(e), "event": event})
        return {"statusCode": 400, "body": f"Invalid event: {e}"}

    resource_repo = ResourceRepository()
    incident_repo = IncidentRepository()

    # ── 2. Idempotency pre-read gate ───────────────────────────────────────────
    #
    # Check current state BEFORE attempting a conditional update. This catches
    # the common duplicate-event case (second event arrives after the first has
    # already transitioned the resource past FAILURE_DETECTED) without hitting
    # DynamoDB conditionals unnecessarily.
    try:
        pre_update_resource = resource_repo.get(resource_id)
        if pre_update_resource.current_state != ResourceState.FAILURE_DETECTED:
            logger.info(
                "Recovery already in progress or completed — skipping (idempotent)",
                extra={
                    "resource_id": resource_id,
                    "state": pre_update_resource.current_state,
                },
            )
            return {"statusCode": 200, "body": "Already recovering"}

        # ── 3. Transition resource to RECOVERY_INITIATED ───────────────────────
        # Conditional write: only succeeds if current_state == FAILURE_DETECTED.
        # This handles concurrent duplicate events that both pass the pre-read.
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
            "State transition was a no-op — skipping (idempotent)",
            extra={"resource_id": resource_id, "state": updated_resource.current_state},
        )
        return {"statusCode": 200, "body": "Already recovering"}

    # ── 4. Lookup or create Incident ───────────────────────────────────────────
    incidents = incident_repo.list(resource_id=resource_id)
    active_incidents = [
        i for i in incidents
        if i.status in (IncidentStatus.OPEN, IncidentStatus.RECOVERING)
    ]

    notification_svc = NotificationService(
        topic_arn=settings.sns_topic_arn,
        region_name=settings.aws_region,
    )

    now_dt = datetime.now(timezone.utc)
    if active_incidents:
        # Reuse the most recent open/recovering incident (e.g., from direct injection)
        incident = max(active_incidents, key=lambda i: i.detected_at)
        incident_is_new = False
        logger.info(
            "Reusing existing incident",
            extra={"incident_id": incident.incident_id, "resource_id": resource_id},
        )
    else:
        incident = Incident(
            incident_id=str(uuid.uuid4()),
            resource_id=resource_id,
            failure_type=failure_type,
            severity=IncidentSeverity(failure_type.default_severity()),
            status=IncidentStatus.RECOVERING,
            state_at_detection=ResourceState.FAILURE_DETECTED,
            created_at=now_dt,
            detected_at=now_dt,
            recovery_started_at=now_dt,
            recovery_initiated_at=now_dt,
            recovery_attempts=0,
            retry_count=0,
            recovery_actions=[],
        )
        incident_is_new = True
        logger.info(
            "Created new incident",
            extra={"incident_id": incident.incident_id, "resource_id": resource_id},
        )
        # Notify failure detected for newly observed failure if not notified
        incident, _ = notification_svc.notify_failure_detected(incident)

    # ── 5. Transition resource to RECOVERY_IN_PROGRESS ────────────────────────
    resource_repo.update_state(resource_id, ResourceState.RECOVERY_IN_PROGRESS)

    # ── 6. Execute recovery strategy ───────────────────────────────────────────
    recovery_start_time = datetime.now(timezone.utc)

    # Notify recovery started
    try:
        preview_strategy = dispatch_strategy(failure_type)
        preview_action_name = preview_strategy.recovery_action_type.value
    except Exception:
        preview_action_name = "AUTOMATED_STRATEGY"

    incident, _ = notification_svc.notify_recovery_started(
        incident,
        action_name=preview_action_name,
        attempt=len(incident.recovery_actions) + 1,
        max_attempts=MAX_RECOVERY_ATTEMPTS,
    )

    try:
        strategy = dispatch_strategy(failure_type)
        logger.info(
            "Executing recovery strategy",
            extra={
                "resource_id": resource_id,
                "failure_type": failure_type.value,
                "strategy": strategy.description,
                "simulated_duration_s": strategy.simulated_duration_seconds,
            },
        )
        outcome_msg, metrics_delta = strategy.execute(resource_id)
        recovery_end_time = datetime.now(timezone.utc)

        # ── 7. Success path ────────────────────────────────────────────────────

        # Build the completed RecoveryAction record
        new_action = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=strategy.recovery_action_type,
            status=RecoveryActionStatus.SUCCEEDED,
            outcome_message=outcome_msg,
            started_at=recovery_start_time,
            completed_at=recovery_end_time,
        )

        # Apply metric delta to resource and persist
        current_resource = resource_repo.get(resource_id)
        updated_resource_obj = current_resource.model_copy(
            update={
                **metrics_delta,
                "current_state": ResourceState.RECOVERED,
                "health_status": HealthStatus.HEALTHY,
                "active_failure_type": None,
            }
        )
        resource_repo.put(updated_resource_obj)

        # Push nominal metrics to CloudWatch so alarms can clear (non-fatal)
        _publish_recovery_metrics(updated_resource_obj)

        # Build updated incident with recovery action logged
        new_actions = [*incident.recovery_actions, new_action]
        recovery_initiated_at = incident.recovery_initiated_at or recovery_start_time
        resolved_incident = incident.model_copy(
            update={
                "status": IncidentStatus.RESOLVED,
                "state_at_resolution": ResourceState.RECOVERED,
                "resolved_at": recovery_end_time,
                "recovered_at": recovery_end_time,
                "recovery_started_at": recovery_initiated_at,
                "recovery_initiated_at": recovery_initiated_at,
                "recovery_action": strategy.recovery_action_type.value,
                "recovery_result": "SUCCESS",
                "recovery_actions": new_actions,
                "recovery_attempts": len(new_actions),
                "retry_count": len(new_actions),
                "duration_seconds": (recovery_end_time - incident.detected_at).total_seconds(),
            }
        )

        # SNS recovery successful notification (with duplicate guard)
        resolved_incident, _ = notification_svc.notify_recovery_successful(
            resolved_incident,
            action_name=strategy.recovery_action_type.value,
            duration_seconds=resolved_incident.duration_seconds,
        )

        if incident_is_new:
            incident_repo.create(resolved_incident)
        else:
            incident_repo.update(resolved_incident)

        logger.info(
            "Recovery complete",
            extra={
                "resource_id": resource_id,
                "failure_type": failure_type.value,
                "incident_id": resolved_incident.incident_id,
                "duration_s": resolved_incident.duration_seconds,
            },
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "incident_id": resolved_incident.incident_id,
                "final_state": ResourceState.RECOVERED.value,
                "recovery_action_type": strategy.recovery_action_type.value,
                "duration_seconds": resolved_incident.duration_seconds,
                "attempt_number": len(new_actions),
            }),
        }

    except Exception as exc:
        # ── 8. Failure path ────────────────────────────────────────────────────
        recovery_end_time = datetime.now(timezone.utc)
        logger.exception(
            "Recovery action failed",
            extra={"resource_id": resource_id, "failure_type": failure_type.value},
        )

        # Determine the action type even if dispatch_strategy itself fails
        try:
            strategy_type = dispatch_strategy(failure_type).recovery_action_type
        except Exception:
            strategy_type = RecoveryActionType.MANUAL

        failed_action = RecoveryAction(
            action_id=str(uuid.uuid4()),
            action_type=strategy_type,
            status=RecoveryActionStatus.FAILED,
            error_detail=str(exc)[:2000],
            outcome_message=f"Recovery failed: {exc}"[:1000],
            started_at=recovery_start_time,
            completed_at=recovery_end_time,
        )

        new_actions = [*incident.recovery_actions, failed_action]
        new_attempts = len(new_actions)
        recovery_initiated_at = incident.recovery_initiated_at or recovery_start_time

        incident_updates: dict[str, Any] = {
            "recovery_actions": new_actions,
            "recovery_attempts": new_attempts,
            "retry_count": new_attempts,
            "recovery_initiated_at": recovery_initiated_at,
            "recovery_started_at": recovery_initiated_at,
            "recovery_action": strategy_type.value,
            "recovery_result": "FAILED",
            "error_message": str(exc)[:2000],
        }

        if new_attempts < MAX_RECOVERY_ATTEMPTS:
            # Retry is still available — resource enters RECOVERY_FAILED
            final_state = ResourceState.RECOVERY_FAILED
            incident_updates["status"] = IncidentStatus.RECOVERING
            logger.warning(
                "Recovery attempt %d/%d failed; resource set to RECOVERY_FAILED",
                new_attempts,
                MAX_RECOVERY_ATTEMPTS,
                extra={"resource_id": resource_id},
            )
        else:
            # Max attempts exhausted — escalate
            final_state = ResourceState.MANUAL_INTERVENTION_REQUIRED
            incident_updates["status"] = IncidentStatus.ESCALATED
            incident_updates["escalated_at"] = recovery_end_time
            incident_updates["state_at_resolution"] = ResourceState.MANUAL_INTERVENTION_REQUIRED
            logger.error(
                "Max recovery attempts (%d) exhausted — MANUAL_INTERVENTION_REQUIRED",
                MAX_RECOVERY_ATTEMPTS,
                extra={"resource_id": resource_id},
            )

        resource_repo.update_state(resource_id, final_state)

        failed_incident = incident.model_copy(update=incident_updates)

        # SNS recovery failed notification (with duplicate guard)
        failed_incident, _ = notification_svc.notify_recovery_failed(
            failed_incident,
            error_message=str(exc),
            attempt=new_attempts,
            max_attempts=MAX_RECOVERY_ATTEMPTS,
        )

        if incident_is_new:
            incident_repo.create(failed_incident)
        else:
            incident_repo.update(failed_incident)

        return {"statusCode": 500, "body": f"Recovery failed after {new_attempts} attempt(s)"}
