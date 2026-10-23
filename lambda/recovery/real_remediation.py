"""Opt-in AWS remediation adapter for a single allowlisted CloudPulse demo resource.

All resource identifiers and commands come from deployment configuration or
constants in this module. Event payloads are never used as AWS targets.
"""
from __future__ import annotations

import os
from typing import Any

import boto3


class RealRemediationError(RuntimeError):
    """Raised when a configured real remediation cannot be safely completed."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RealRemediationError(f"Required real-remediation setting {name} is missing")
    return value


def should_execute_real_remediation(
    resource_id: str,
    environ: dict[str, str] | None = None,
) -> bool:
    """Return true only when the explicit feature flag and exact resource allowlist match."""
    env = os.environ if environ is None else environ
    enabled = env.get("REAL_REMEDIATION_ENABLED", "false").strip().lower() == "true"
    allowed = env.get("REAL_ALLOWED_RESOURCE_ID", "").strip()
    return enabled and bool(allowed) and resource_id == allowed


def _assert_allowed(resource_id: str) -> None:
    allowed = _required("REAL_ALLOWED_RESOURCE_ID")
    if resource_id != allowed:
        raise RealRemediationError(
            f"Resource {resource_id!r} is not the configured real-remediation allowlist target"
        )


def _instance_id() -> str:
    return _required("REAL_EC2_INSTANCE_ID")


def _healthy(elbv2: Any, target_group_arn: str, instance_id: str) -> bool:
    result = elbv2.describe_target_health(
        TargetGroupArn=target_group_arn,
        Targets=[{"Id": instance_id}],
    )
    descriptions = result.get("TargetHealthDescriptions", [])
    return any(
        item.get("Target", {}).get("Id") == instance_id
        and item.get("TargetHealth", {}).get("State") == "healthy"
        for item in descriptions
    )


def _run_ssm_command(instance_id: str, command: str, ssm: Any | None = None) -> str:
    """Run one constant command on the configured, allowlisted instance."""
    client = ssm or boto3.client("ssm")
    response = client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
        TimeoutSeconds=45,
        Comment="CloudPulse allowlisted demo remediation",
    )
    command_id = response["Command"]["CommandId"]
    waiter = client.get_waiter("command_executed")
    waiter.wait(
        CommandId=command_id,
        InstanceId=instance_id,
        WaiterConfig={"Delay": 2, "MaxAttempts": 20},
    )
    invocation = client.get_command_invocation(
        CommandId=command_id,
        InstanceId=instance_id,
    )
    if invocation.get("Status") != "Success":
        raise RealRemediationError(
            f"SSM command ended with status {invocation.get('Status', 'unknown')}"
        )
    return command_id


def execute_real_remediation(
    failure_type: Any,
    resource_id: str,
    *,
    autoscaling: Any | None = None,
    ssm: Any | None = None,
    elbv2: Any | None = None,
) -> str:
    """Execute the fixed AWS action mapped to a failure type."""
    _assert_allowed(resource_id)
    failure = getattr(failure_type, "value", str(failure_type))

    if failure == "HIGH_CPU":
        group_name = _required("REAL_ASG_NAME")
        client = autoscaling or boto3.client("autoscaling")
        groups = client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[group_name]
        ).get("AutoScalingGroups", [])
        if len(groups) != 1 or groups[0].get("AutoScalingGroupName") != group_name:
            raise RealRemediationError("Configured Auto Scaling group was not found uniquely")
        group = groups[0]
        desired = int(group.get("DesiredCapacity", 0))
        maximum = int(group.get("MaxSize", 0))
        if desired >= maximum:
            raise RealRemediationError("Auto Scaling group is already at MaxSize")
        client.set_desired_capacity(
            AutoScalingGroupName=group_name,
            DesiredCapacity=desired + 1,
            HonorCooldown=True,
        )
        return f"Requested bounded ASG scale-out for {group_name}: {desired} to {desired + 1}"

    instance_id = _instance_id()
    if failure == "SERVICE_FAILURE":
        command_id = _run_ssm_command(
            instance_id, "systemctl restart cloudpulse-demo.service && systemctl is-active --quiet cloudpulse-demo.service", ssm
        )
        return f"Restarted cloudpulse-demo.service through SSM command {command_id}"

    if failure == "STORAGE_EXHAUSTION":
        command_id = _run_ssm_command(
            instance_id,
            "find /var/tmp/cloudpulse-demo/cache -xdev -mindepth 1 -maxdepth 1 -type f -mtime +1 -delete",
            ssm,
        )
        return f"Cleaned aged files in the fixed CloudPulse cache path through SSM command {command_id}"

    client = elbv2 or boto3.client("elbv2")
    if failure == "NETWORK_LATENCY":
        rule_arn = _required("REAL_ALB_LISTENER_RULE_ARN")
        target_group_arn = _required("REAL_ALTERNATE_TARGET_GROUP_ARN")
        alternate_instance_id = _required("REAL_ALTERNATE_INSTANCE_ID")
        if alternate_instance_id == instance_id:
            raise RealRemediationError("Alternate target must be different from the primary instance")
        if not _healthy(client, target_group_arn, alternate_instance_id):
            raise RealRemediationError("Configured alternate target is not healthy")
        client.modify_rule(
            RuleArn=rule_arn,
            Actions=[{"Type": "forward", "TargetGroupArn": target_group_arn}],
        )
        return "Routed the configured ALB listener rule to the healthy alternate target group"

    if failure == "SERVICE_DOWNTIME":
        target_group_arn = _required("REAL_FAILOVER_TARGET_GROUP_ARN")
        primary = _required("REAL_PRIMARY_INSTANCE_ID")
        standby = _required("REAL_STANDBY_INSTANCE_ID")
        if primary == standby or instance_id != primary:
            raise RealRemediationError("Failover primary/standby configuration is inconsistent")
        if not _healthy(client, target_group_arn, standby):
            raise RealRemediationError("Configured standby target is not healthy")
        client.deregister_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{"Id": primary}],
        )
        return f"Deregistered primary {primary} after confirming standby {standby} is healthy"

    raise RealRemediationError(f"No real AWS action is defined for failure type {failure!r}")
