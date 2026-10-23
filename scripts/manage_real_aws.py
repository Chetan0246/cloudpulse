#!/usr/bin/env python3
"""
CloudPulse — Real AWS Resource Integration & CLI Management Utility.

Allows registering live AWS EC2 instances, Auto Scaling Groups, and RDS databases
into the CloudPulse autonomous reliability control plane.

Commands:
  python scripts/manage_real_aws.py discover
  python scripts/manage_real_aws.py register-ec2 <instance-id>
  python scripts/manage_real_aws.py register-asg <asg-name>
  python scripts/manage_real_aws.py test-remediation <resource-id> <failure-type>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION = os.environ.get("AWS_REGION_NAME", os.environ.get("AWS_REGION", "ap-south-1"))
RESOURCES_TABLE = os.environ.get("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-dev")


def ensure_aws_credentials():
    """Ensure AWS credentials from 'aws login' or environment are active."""
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        try:
            out = subprocess.check_output(
                ["aws", "configure", "export-credentials", "--format", "env"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in out.strip().splitlines():
                if line.startswith("export "):
                    k, v = line.replace("export ", "").split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass


def get_dynamo_table():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return dynamodb.Table(RESOURCES_TABLE)


def discover_live_aws_resources():
    """Discover real EC2 instances, ASGs, and RDS instances in the region."""
    print(f"\n🔍 Discovering live AWS resources in region '{REGION}'...")

    # 1. EC2 Instances
    ec2 = boto3.client("ec2", region_name=REGION)
    try:
        res = ec2.describe_instances()
        instances = []
        for r in res.get("Reservations", []):
            for i in r.get("Instances", []):
                state = i["State"]["Name"]
                iid = i["InstanceId"]
                itype = i["InstanceType"]
                instances.append((iid, itype, state))
        if instances:
            print("\n💻 Real EC2 Instances:")
            for iid, itype, state in instances:
                print(f"   • {iid} ({itype}) — State: {state}")
        else:
            print("\n💻 Real EC2 Instances: None currently running in this region.")
    except ClientError as e:
        print(f"   [Error querying EC2]: {e}")

    # 2. Auto Scaling Groups
    asg = boto3.client("autoscaling", region_name=REGION)
    try:
        res = asg.describe_auto_scaling_groups()
        groups = res.get("AutoScalingGroups", [])
        if groups:
            print("\n📈 Auto Scaling Groups:")
            for g in groups:
                print(f"   • {g['AutoScalingGroupName']} (Desired: {g['DesiredCapacity']}, Min: {g['MinSize']}, Max: {g['MaxSize']})")
        else:
            print("\n📈 Auto Scaling Groups: None found.")
    except ClientError as e:
        print(f"   [Error querying ASG]: {e}")

    # 3. RDS Instances
    rds = boto3.client("rds", region_name=REGION)
    try:
        res = rds.describe_db_instances()
        dbs = res.get("DBInstances", [])
        if dbs:
            print("\n🗄️ RDS Databases:")
            for d in dbs:
                print(f"   • {d['DBInstanceIdentifier']} ({d['DBInstanceClass']}) — Status: {d['DBInstanceStatus']}")
        else:
            print("\n🗄️ RDS Databases: None found.")
    except ClientError as e:
        print(f"   [Error querying RDS]: {e}")

    print("\n✅ Discovery complete.\n")


def register_real_resource(resource_id: str, resource_type: str, description: str = ""):
    """Register a real AWS resource ID into CloudPulse DynamoDB."""
    table = get_dynamo_table()
    now_iso = datetime.now(UTC).isoformat()

    item = {
        "resource_id": resource_id.strip().upper(),
        "resource_type": resource_type.upper(),
        "description": description or f"Live AWS {resource_type} registered via CLI",
        "current_state": "HEALTHY",
        "health_status": "HEALTHY",
        "cpu_utilization": Decimal("20.0"),
        "memory_utilization": Decimal("25.0"),
        "storage_utilization": Decimal("15.0"),
        "network_latency_ms": Decimal("10.0"),
        "created_at": now_iso,
        "updated_at": now_iso,
        "last_heartbeat": now_iso,
        "tags": {
            "ManagedBy": "CloudPulse",
            "ExecutionMode": os.environ.get("EXECUTION_MODE", "SIMULATION").upper(),
        },
    }

    try:
        table.put_item(Item=item)
        print(f"✅ Successfully registered real AWS resource '{resource_id}' ({resource_type}) into DynamoDB table '{RESOURCES_TABLE}'.")
        print("   It is now tracked by CloudPulse autonomous self-healing control plane.")
    except ClientError as e:
        print(f"❌ Failed to register resource: {e}")
        sys.exit(1)


def main():
    ensure_aws_credentials()
    parser = argparse.ArgumentParser(description="CloudPulse Real AWS Integration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # discover
    subparsers.add_parser("discover", help="Discover live AWS resources in the region")

    # register-ec2
    p_ec2 = subparsers.add_parser("register-ec2", help="Register a live EC2 instance ID")
    p_ec2.add_argument("instance_id", help="EC2 Instance ID (e.g. i-0123456789abcdef0)")
    p_ec2.add_argument("--desc", default="Production Web EC2 Instance", help="Description")

    # register-asg
    p_asg = subparsers.add_parser("register-asg", help="Register an Auto Scaling Group")
    p_asg.add_argument("asg_name", help="ASG Name (e.g. asg-app-cluster)")
    p_asg.add_argument("--desc", default="Application Auto Scaling Group", help="Description")

    # register-rds
    p_rds = subparsers.add_parser("register-rds", help="Register an RDS DB instance")
    p_rds.add_argument("db_id", help="RDS Identifier (e.g. db-production-cluster)")
    p_rds.add_argument("--desc", default="Primary RDS Cluster", help="Description")

    args = parser.parse_args()

    if args.command == "discover":
        discover_live_aws_resources()
    elif args.command == "register-ec2":
        register_real_resource(args.instance_id, "VM", args.desc)
    elif args.command == "register-asg":
        register_real_resource(args.asg_name, "VM", args.desc)
    elif args.command == "register-rds":
        register_real_resource(args.db_id, "DB", args.desc)


if __name__ == "__main__":
    main()
