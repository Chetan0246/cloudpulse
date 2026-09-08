#!/usr/bin/env python3
"""
Seed 4 virtual resources into DynamoDB.

Usage:
    # Dev (using profile)
    python scripts/seed_data.py --table cloudpulse-resources-dev --region ap-south-1

    # Or use environment variables:
    DYNAMODB_RESOURCES_TABLE=cloudpulse-resources-dev python scripts/seed_data.py
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3

# Load seed data from fixtures
FIXTURES_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "seed_resources.json"


def seed(table_name: str, region: str) -> None:
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    with open(FIXTURES_PATH) as f:
        resources = json.load(f)

    now = datetime.now(timezone.utc).isoformat()
    for r in resources:
        r["last_heartbeat"] = now
        r["updated_at"] = now
        # Remove null values (DynamoDB doesn't support null)
        item = {k: v for k, v in r.items() if v is not None}
        table.put_item(Item=item)
        print(f"  Seeded: {r['resource_id']}")

    print(f"\nSeeded {len(resources)} resources into '{table_name}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CloudPulse DynamoDB resources table")
    parser.add_argument(
        "--table",
        default=os.environ.get("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-dev"),
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "ap-south-1"),
    )
    args = parser.parse_args()
    seed(args.table, args.region)
