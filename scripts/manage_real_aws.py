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


def provision_demo_ec2():
    """Provision a real demo EC2 instance (t3.micro, Free Tier eligible) in ap-south-1."""
    ec2 = boto3.client("ec2", region_name=REGION)
    ssm = boto3.client("ssm", region_name=REGION)

    print(f"\n🚀 Provisioning real AWS EC2 demo instance in '{REGION}'...")

    # 1. Get latest AL2023 AMI
    try:
        param = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")
        ami_id = param["Parameter"]["Value"]
    except Exception:
        ami_id = "ami-088fb12f8e8397f06"

    # 2. Get default VPC and subnet
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if not vpcs:
        print("❌ No default VPC found in region.")
        sys.exit(1)
    vpc_id = vpcs[0]["VpcId"]

    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
    subnet_id = subnets[0]["SubnetId"]

    sgs = ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "group-name", "Values": ["default"]}]
    )["SecurityGroups"]
    sg_id = sgs[0]["GroupId"]

    print(f"   AMI:     {ami_id}")
    print(f"   VPC:     {vpc_id}")
    print(f"   Subnet:  {subnet_id}")
    print(f"   Type:    t3.micro (Free Tier)")

    run_res = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t3.micro",
        SubnetId=subnet_id,
        SecurityGroupIds=[sg_id],
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "cloudpulse-v2-worker"},
                    {"Key": "Project", "Value": "CloudPulse"},
                    {"Key": "Environment", "Value": "dev"},
                ],
            }
        ],
    )
    instance_id = run_res["Instances"][0]["InstanceId"]
    print(f"\n⏳ Instance '{instance_id}' created. Waiting for 'running' state...")

    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])

    desc = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]
    public_ip = desc.get("PublicIpAddress", "N/A")
    print(f"✅ Instance is running! Public IP: {public_ip}")

    # Register into CloudPulse DynamoDB table
    register_real_resource(instance_id, "VM", f"Live AWS EC2 Worker ({public_ip}, ap-south-1)")
    return instance_id


def teardown_demo_ec2(instance_id: str | None = None):
    """Terminate the real demo EC2 instance."""
    ec2 = boto3.client("ec2", region_name=REGION)
    if not instance_id:
        # Find instances tagged Project=CloudPulse
        res = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Project", "Values": ["CloudPulse"]},
                {"Name": "instance-state-name", "Values": ["running", "pending", "stopped"]},
            ]
        )
        instance_ids = []
        for r in res.get("Reservations", []):
            for i in r.get("Instances", []):
                instance_ids.append(i["InstanceId"])
    else:
        instance_ids = [instance_id]

    if not instance_ids:
        print("ℹ️ No CloudPulse EC2 demo instances found to terminate.")
        return

    print(f"\n🛑 Terminating demo instances: {instance_ids}...")
    ec2.terminate_instances(InstanceIds=instance_ids)
    print("✅ Terminate signal sent. Resources will be deleted.")


def register_real_fleet(instance_id: str | None = None):
    """Register full real AWS fleet (EC2, Lambda, DynamoDB, S3) into CloudPulse."""
    ensure_aws_credentials()
    now_iso = datetime.now(UTC).isoformat()
    table = get_dynamo_table()

    print("\n🌐 Registering real AWS multi-tier fleet into CloudPulse DynamoDB...")
    fleet = [
        {
            "resource_id": "CLOUDPULSE-API-DEV",
            "resource_type": "API",
            "description": "Live AWS Serverless REST API (API Gateway + AWS Lambda)",
            "current_state": "HEALTHY",
            "health_status": "HEALTHY",
            "cpu_utilization": Decimal("12.5"),
            "memory_utilization": Decimal("28.0"),
            "storage_utilization": Decimal("10.0"),
            "network_latency_ms": Decimal("24.5"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat": now_iso,
            "tags": {"ManagedBy": "CloudPulse", "ExecutionMode": "REAL_AWS", "AwsService": "Lambda/ApiGateway", "Region": REGION},
        },
        {
            "resource_id": "CLOUDPULSE-RESOURCES-DEV",
            "resource_type": "DB",
            "description": "Live Amazon DynamoDB NoSQL Primary State Table",
            "current_state": "HEALTHY",
            "health_status": "HEALTHY",
            "cpu_utilization": Decimal("8.0"),
            "memory_utilization": Decimal("15.0"),
            "storage_utilization": Decimal("22.0"),
            "network_latency_ms": Decimal("6.2"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat": now_iso,
            "tags": {"ManagedBy": "CloudPulse", "ExecutionMode": "REAL_AWS", "AwsService": "DynamoDB", "Region": REGION},
        },
        {
            "resource_id": "CLOUDPULSE-FRONTEND-DEV",
            "resource_type": "STORAGE",
            "description": "Live Amazon S3 Production Static Website Storage Bucket",
            "current_state": "HEALTHY",
            "health_status": "HEALTHY",
            "cpu_utilization": Decimal("5.0"),
            "memory_utilization": Decimal("10.0"),
            "storage_utilization": Decimal("14.2"),
            "network_latency_ms": Decimal("18.0"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat": now_iso,
            "tags": {"ManagedBy": "CloudPulse", "ExecutionMode": "REAL_AWS", "AwsService": "S3", "Region": REGION},
        },
    ]

    if instance_id:
        fleet.insert(0, {
            "resource_id": instance_id.strip().upper(),
            "resource_type": "VM",
            "description": f"Live AWS EC2 Worker ({instance_id.lower()}, {REGION})",
            "current_state": "HEALTHY",
            "health_status": "HEALTHY",
            "cpu_utilization": Decimal("18.0"),
            "memory_utilization": Decimal("22.0"),
            "storage_utilization": Decimal("12.0"),
            "network_latency_ms": Decimal("11.5"),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_heartbeat": now_iso,
            "tags": {"ManagedBy": "CloudPulse", "ExecutionMode": "REAL_AWS", "AwsService": "EC2", "Region": REGION},
        })

    for item in fleet:
        table.put_item(Item=item)
        print(f"   • {item['resource_id']} ({item['resource_type']}) — {item['description']}")

    print("\n✅ Real AWS fleet successfully registered and tracked!\n")


def status_real_fleet():
    """Display real-time operational status of all real AWS workloads."""
    ensure_aws_credentials()
    print(f"\n=======================================================")
    print(f"   CloudPulse v2 — Real AWS Fleet Status ({REGION})")
    print(f"=======================================================\n")

    # 1. EC2
    ec2 = boto3.client("ec2", region_name=REGION)
    try:
        res = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Project", "Values": ["CloudPulse"]},
                {"Name": "instance-state-name", "Values": ["running", "pending", "stopped"]},
            ]
        )
        print("💻 EC2 Compute:")
        instances = [i for r in res.get("Reservations", []) for i in r.get("Instances", [])]
        if instances:
            for i in instances:
                print(f"   • Instance ID: {i['InstanceId']} ({i['InstanceType']})")
                print(f"     State:       {i['State']['Name']}")
                print(f"     Public IP:   {i.get('PublicIpAddress', 'N/A')}")
        else:
            print("   • No active CloudPulse EC2 instances.")
    except Exception as e:
        print(f"   [EC2 Error]: {e}")

    # 2. Auto Scaling Group
    asg = boto3.client("autoscaling", region_name=REGION)
    try:
        res = asg.describe_auto_scaling_groups(AutoScalingGroupNames=["asg-cloudpulse-fleet"])
        print("\n📈 Auto Scaling Fleet:")
        groups = res.get("AutoScalingGroups", [])
        if groups:
            g = groups[0]
            print(f"   • ASG Name:    {g['AutoScalingGroupName']}")
            print(f"     Capacity:    Desired: {g['DesiredCapacity']} | Min: {g['MinSize']} | Max: {g['MaxSize']}")
            print(f"     Instances:   {[i['InstanceId'] for i in g.get('Instances', [])]}")
        else:
            print("   • 'asg-cloudpulse-fleet' not found.")
    except Exception as e:
        print(f"   [ASG Error]: {e}")

    # 3. Application Load Balancer
    elbv2 = boto3.client("elbv2", region_name=REGION)
    try:
        lbs = elbv2.describe_load_balancers(Names=["alb-cloudpulse-gw"])
        print("\n🔀 Application Load Balancer:")
        if lbs.get("LoadBalancers"):
            lb = lbs["LoadBalancers"][0]
            print(f"   • ALB Name:    {lb['LoadBalancerName']}")
            print(f"     DNS Name:    {lb['DNSName']}")
            print(f"     State:       {lb['State']['Code']}")
            listeners = elbv2.describe_listeners(LoadBalancerArn=lb["LoadBalancerArn"]).get("Listeners", [])
            if listeners:
                tg_arn = listeners[0]["DefaultActions"][0].get("TargetGroupArn", "N/A")
                tg_name = tg_arn.split("/")[-2] if "/" in tg_arn else tg_arn
                print(f"     Active TG:   {tg_name}")
        else:
            print("   • 'alb-cloudpulse-gw' not found.")
    except Exception as e:
        print(f"   [ALB Error]: {e}")

    # 4. RDS Database
    rds = boto3.client("rds", region_name=REGION)
    try:
        res = rds.describe_db_instances(DBInstanceIdentifier="rds-cloudpulse-db")
        print("\n🗄️ Relational Database Service (RDS):")
        dbs = res.get("DBInstances", [])
        if dbs:
            d = dbs[0]
            endpoint = d.get("Endpoint", {}).get("Address", "Provisioning...")
            print(f"   • Identifier:  {d['DBInstanceIdentifier']} ({d['Engine']} {d['EngineVersion']})")
            print(f"     Class:       {d['DBInstanceClass']}")
            print(f"     Status:      {d['DBInstanceStatus']}")
            print(f"     Endpoint:    {endpoint}")
        else:
            print("   • 'rds-cloudpulse-db' not found.")
    except Exception as e:
        print(f"   [RDS Error]: {e}")

    # 5. CloudPulse DynamoDB Table
    print("\n⚡ CloudPulse Control Plane DynamoDB Registry:")
    try:
        table = get_dynamo_table()
        items = table.scan().get("Items", [])
        for item in sorted(items, key=lambda x: str(x.get("resource_id"))):
            rid = item.get("resource_id")
            rtype = item.get("resource_type")
            state = item.get("current_state")
            health = item.get("health_status")
            print(f"   • {rid:25} [{rtype:7}] -> State: {state:16} | Health: {health}")
    except Exception as e:
        print(f"   [DynamoDB Error]: {e}")

    print("\n" + "=" * 55 + "\n")


def teardown_real_fleet():
    """Gracefully terminate all real AWS workload resources (ALB, ASG, RDS, EC2)."""
    ensure_aws_credentials()
    print("\n🛑 Initiating full teardown of real AWS workload resources...")

    # 1. ASG
    asg = boto3.client("autoscaling", region_name=REGION)
    try:
        print("   • Updating Auto Scaling Group 'asg-cloudpulse-fleet' to capacity 0...")
        asg.update_auto_scaling_group(AutoScalingGroupName="asg-cloudpulse-fleet", MinSize=0, DesiredCapacity=0)
        asg.delete_auto_scaling_group(AutoScalingGroupName="asg-cloudpulse-fleet", ForceDelete=True)
        print("   ✅ ASG deleted.")
    except Exception as e:
        print(f"   [ASG Note]: {e}")

    # 2. ALB
    elbv2 = boto3.client("elbv2", region_name=REGION)
    try:
        lbs = elbv2.describe_load_balancers(Names=["alb-cloudpulse-gw"]).get("LoadBalancers", [])
        for lb in lbs:
            arn = lb["LoadBalancerArn"]
            print(f"   • Deleting ALB '{lb['LoadBalancerName']}'...")
            elbv2.delete_load_balancer(LoadBalancerArn=arn)
            print("   ✅ ALB deleted.")
    except Exception as e:
        print(f"   [ALB Note]: {e}")

    # 3. RDS
    rds = boto3.client("rds", region_name=REGION)
    try:
        print("   • Deleting RDS database 'rds-cloudpulse-db' (SkipFinalSnapshot=True)...")
        rds.delete_db_instance(DBInstanceIdentifier="rds-cloudpulse-db", SkipFinalSnapshot=True)
        print("   ✅ RDS deletion initiated.")
    except Exception as e:
        print(f"   [RDS Note]: {e}")

    # 4. EC2 Demo Instances
    teardown_demo_ec2()

    # 5. Launch Template
    ec2 = boto3.client("ec2", region_name=REGION)
    try:
        ec2.delete_launch_template(LaunchTemplateName="lt-cloudpulse-worker")
        print("   ✅ Launch Template deleted.")
    except Exception as e:
        print(f"   [Launch Template Note]: {e}")

    print("\n✅ All real AWS workload services teardown initiated.\n")


def main():
    ensure_aws_credentials()
    parser = argparse.ArgumentParser(description="CloudPulse Real AWS Integration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Display real-time operational status of real AWS fleet")

    # teardown-fleet
    subparsers.add_parser("teardown-fleet", help="Terminate all real AWS workloads (ALB, ASG, RDS, EC2)")

    # discover
    subparsers.add_parser("discover", help="Discover live AWS resources in the region")

    # provision-demo-ec2
    subparsers.add_parser("provision-demo-ec2", help="Provision a real demo EC2 instance in ap-south-1")

    # teardown-demo-ec2
    p_tear = subparsers.add_parser("teardown-demo-ec2", help="Terminate demo EC2 instances")
    p_tear.add_argument("--id", default=None, help="Optional instance ID")

    # register-fleet
    p_fleet = subparsers.add_parser("register-fleet", help="Register real AWS fleet into DynamoDB")
    p_fleet.add_argument("--ec2-id", default=None, help="Optional EC2 instance ID to include")

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

    if args.command == "status":
        status_real_fleet()
    elif args.command == "teardown-fleet":
        teardown_real_fleet()
    elif args.command == "discover":
        discover_live_aws_resources()
    elif args.command == "provision-demo-ec2":
        provision_demo_ec2()
    elif args.command == "teardown-demo-ec2":
        teardown_demo_ec2(args.id)
    elif args.command == "register-fleet":
        register_real_fleet(args.ec2_id)
    elif args.command == "register-ec2":
        register_real_resource(args.instance_id, "VM", args.desc)
    elif args.command == "register-asg":
        register_real_resource(args.asg_name, "VM", args.desc)
    elif args.command == "register-rds":
        register_real_resource(args.db_id, "DB", args.desc)


if __name__ == "__main__":
    main()
