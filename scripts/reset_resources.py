#!/usr/bin/env python3
"""
Reset all virtual resources to HEALTHY state with nominal metrics.
Useful for demo resets without redeploying.

Usage:
    python scripts/reset_resources.py --table cloudpulse-resources-dev
"""
import argparse
import os
from datetime import datetime, timezone

import boto3


def reset(table_name: str, region: str) -> None:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    now = datetime.now(timezone.utc).isoformat()
    response = table.scan()
    items = response.get("Items", [])

    for item in items:
        table.update_item(
            Key={"resource_id": item["resource_id"]},
            UpdateExpression=(
                "SET current_state = :s, health_status = :h, "
                "cpu_utilization = :cpu, memory_utilization = :mem, "
                "storage_utilization = :stor, network_latency_ms = :net, "
                "active_failure_type = :aft, updated_at = :u"
            ),
            ExpressionAttributeValues={
                ":s": "HEALTHY",
                ":h": "HEALTHY",
                ":cpu": "25.0",
                ":mem": "30.0",
                ":stor": "20.0",
                ":net": "15.0",
                ":aft": None,
                ":u": now,
            },
        )
        print(f"  Reset: {item['resource_id']}")

    print(f"\nReset {len(items)} resources to HEALTHY.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-dev"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    args = parser.parse_args()
    reset(args.table, args.region)
