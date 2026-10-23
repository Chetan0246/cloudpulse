#!/usr/bin/env python3
"""
Reset all virtual resources to HEALTHY state with nominal metrics.
Useful for demo resets without redeploying.

Also closes any incident left in OPEN/RECOVERING state so reliability
metrics do not keep counting the reset resource as down.

Usage:
    python scripts/reset_resources.py --table cloudpulse-resources-dev
    python scripts/reset_resources.py --table ... --incidents-table ...
"""
import argparse
import os
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

_ACTIVE_INCIDENT_STATUSES = {"OPEN", "RECOVERING"}


def _scan_all(table) -> list[dict]:
    """Scan every page of a DynamoDB table."""
    items: list[dict] = []
    scan_kwargs: dict = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return items


def _resolve_incidents(incidents_table_name: str, region: str, resource_ids: set[str]) -> int:
    """Mark active incidents for the reset resources as RESOLVED."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(incidents_table_name)
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    resolved = 0

    for incident in _scan_all(table):
        if incident.get("status") not in _ACTIVE_INCIDENT_STATUSES:
            continue
        if str(incident.get("resource_id", "")).upper() not in resource_ids:
            continue

        duration = 0.0
        raw_detected = incident.get("detected_at")
        if raw_detected:
            try:
                detected = datetime.fromisoformat(str(raw_detected).replace("Z", "+00:00"))
                if detected.tzinfo is None:
                    detected = detected.replace(tzinfo=UTC)
                duration = max(0.0, (now - detected).total_seconds())
            except ValueError:
                duration = 0.0

        try:
            table.update_item(
                Key={"incident_id": incident["incident_id"]},
                UpdateExpression=(
                    "SET #status = :s, state_at_resolution = :sr, "
                    "resolved_at = :r, recovered_at = :r, "
                    "recovery_action = :ra, recovery_result = :rr, "
                    "duration_seconds = :d, updated_at = :u"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":s": "RESOLVED",
                    ":sr": "RECOVERED",
                    ":r": now_iso,
                    ":ra": "MANUAL",
                    ":rr": "MANUALLY_RESOLVED",
                    ":d": Decimal(str(round(duration, 3))),
                    ":u": now_iso,
                },
            )
            resolved += 1
        except ClientError as e:
            print(f"  [WARN] Could not resolve incident {incident.get('incident_id')}: {e}")

    return resolved


def reset(table_name: str, region: str, incidents_table: str | None = None) -> None:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    now = datetime.now(UTC).isoformat()
    items = _scan_all(table)

    for item in items:
        table.update_item(
            Key={"resource_id": item["resource_id"]},
            UpdateExpression=(
                "SET current_state = :s, health_status = :h, "
                "cpu_utilization = :cpu, memory_utilization = :mem, "
                "storage_utilization = :stor, network_latency_ms = :net, "
                "updated_at = :u "
                "REMOVE active_failure_type"
            ),
            ExpressionAttributeValues={
                ":s": "HEALTHY",
                ":h": "HEALTHY",
                ":cpu": Decimal("25.0"),
                ":mem": Decimal("30.0"),
                ":stor": Decimal("20.0"),
                ":net": Decimal("15.0"),
                ":u": now,
            },
        )
        print(f"  Reset: {item['resource_id']}")

    resource_ids = {str(item["resource_id"]).upper() for item in items}
    resolved = 0
    if incidents_table and resource_ids:
        resolved = _resolve_incidents(incidents_table, region, resource_ids)

    print(f"\nReset {len(items)} resources to HEALTHY.")
    if incidents_table:
        print(f"Resolved {resolved} active incident(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--table",
        default=os.environ.get("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-dev"),
    )
    parser.add_argument(
        "--incidents-table",
        default=os.environ.get(
            "DYNAMODB_INCIDENTS_TABLE",
            os.environ.get("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-dev").replace(
                "resources", "incidents"
            ),
        ),
        help="Incidents table to reconcile (pass empty string to skip).",
    )
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()
    reset(args.table, args.region, args.incidents_table or None)
