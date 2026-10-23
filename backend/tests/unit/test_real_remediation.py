import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import pytest

_MODULE_PATH = pathlib.Path(__file__).parents[3] / "lambda" / "recovery" / "real_remediation.py"
_spec = importlib.util.spec_from_file_location("real_remediation", _MODULE_PATH)
real = importlib.util.module_from_spec(_spec)
sys.modules["real_remediation"] = real
_spec.loader.exec_module(real)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    values = {
        "REAL_ALLOWED_RESOURCE_ID": "VM-001",
        "REAL_EC2_INSTANCE_ID": "i-primary",
        "REAL_ASG_NAME": "cloudpulse-demo",
        "REAL_ALB_LISTENER_RULE_ARN": "arn:rule/demo",
        "REAL_ALTERNATE_TARGET_GROUP_ARN": "arn:tg/alternate",
        "REAL_FAILOVER_TARGET_GROUP_ARN": "arn:tg/failover",
        "REAL_PRIMARY_INSTANCE_ID": "i-primary",
        "REAL_STANDBY_INSTANCE_ID": "i-standby",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_resource_allowlist_rejects_event_resource():
    with pytest.raises(real.RealRemediationError, match="not the configured"):
        real.execute_real_remediation("SERVICE_FAILURE", "API-001")


def test_high_cpu_increases_only_named_asg_by_one():
    class AutoScaling:
        def __init__(self):
            self.calls = []

        def describe_auto_scaling_groups(self, **kwargs):
            self.calls.append(("describe", kwargs))
            return {"AutoScalingGroups": [{
                "AutoScalingGroupName": "cloudpulse-demo",
                "DesiredCapacity": 1,
                "MaxSize": 2,
            }]}

        def set_desired_capacity(self, **kwargs):
            self.calls.append(("set", kwargs))

    client = AutoScaling()
    outcome = real.execute_real_remediation("HIGH_CPU", "VM-001", autoscaling=client)
    assert "1 to 2" in outcome
    assert client.calls[-1] == ("set", {
        "AutoScalingGroupName": "cloudpulse-demo",
        "DesiredCapacity": 2,
        "HonorCooldown": True,
    })


def test_high_cpu_refuses_to_exceed_asg_maximum():
    class AutoScaling:
        def describe_auto_scaling_groups(self, **kwargs):
            return {"AutoScalingGroups": [{
                "AutoScalingGroupName": "cloudpulse-demo",
                "DesiredCapacity": 2,
                "MaxSize": 2,
            }]}

        def set_desired_capacity(self, **kwargs):
            raise AssertionError("must not scale above MaxSize")

    with pytest.raises(real.RealRemediationError, match="MaxSize"):
        real.execute_real_remediation("HIGH_CPU", "VM-001", autoscaling=AutoScaling())


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("SERVICE_FAILURE", "systemctl restart cloudpulse-demo.service"),
        ("STORAGE_EXHAUSTION", "/var/tmp/cloudpulse-demo/cache"),
    ],
)
def test_ssm_strategy_uses_constant_safe_command(monkeypatch, failure, expected):
    calls = []

    def fake_ssm(instance_id, command, ssm=None):
        calls.append((instance_id, command))
        return "cmd-123"

    monkeypatch.setattr(real, "_run_ssm_command", fake_ssm)
    outcome = real.execute_real_remediation(failure, "VM-001")
    assert calls[0][0] == "i-primary"
    assert expected in calls[0][1]
    assert "cmd-123" in outcome


def test_network_reroute_requires_healthy_target_and_changes_only_configured_rule():
    class Elbv2:
        def __init__(self):
            self.changed = None

        def describe_target_health(self, **kwargs):
            return {"TargetHealthDescriptions": [{
                "Target": {"Id": "i-primary"},
                "TargetHealth": {"State": "healthy"},
            }]}

        def describe_rules(self, **kwargs):
            return {"Rules": [{
                "RuleArn": "arn:rule/demo",
                "Actions": [{"Type": "forward", "TargetGroupArn": "arn:tg/old"}],
            }]}

        def modify_rule(self, **kwargs):
            self.changed = kwargs

    client = Elbv2()
    real.execute_real_remediation("NETWORK_LATENCY", "VM-001", elbv2=client)
    assert client.changed == {
        "RuleArn": "arn:rule/demo",
        "Actions": [{"Type": "forward", "TargetGroupArn": "arn:tg/alternate"}],
    }


def test_network_reroute_refuses_unhealthy_alternate():
    class Elbv2:
        def describe_target_health(self, **kwargs):
            return {"TargetHealthDescriptions": []}

        def modify_rule(self, **kwargs):
            raise AssertionError("must not change rule")

    with pytest.raises(real.RealRemediationError, match="not healthy"):
        real.execute_real_remediation("NETWORK_LATENCY", "VM-001", elbv2=Elbv2())


def test_failover_checks_standby_before_deregistering_primary():
    class Elbv2:
        def __init__(self):
            self.deregistered = None

        def describe_target_health(self, **kwargs):
            assert kwargs["Targets"] == [{"Id": "i-standby"}]
            return {"TargetHealthDescriptions": [{
                "Target": {"Id": "i-standby"},
                "TargetHealth": {"State": "healthy"},
            }]}

        def deregister_targets(self, **kwargs):
            self.deregistered = kwargs

    client = Elbv2()
    real.execute_real_remediation("SERVICE_DOWNTIME", "VM-001", elbv2=client)
    assert client.deregistered == {
        "TargetGroupArn": "arn:tg/failover",
        "Targets": [{"Id": "i-primary"}],
    }


def test_failover_never_deregisters_when_standby_is_unhealthy():
    class Elbv2:
        def describe_target_health(self, **kwargs):
            return {"TargetHealthDescriptions": []}

        def deregister_targets(self, **kwargs):
            raise AssertionError("must not deregister primary")

    with pytest.raises(real.RealRemediationError, match="standby target is not healthy"):
        real.execute_real_remediation("SERVICE_DOWNTIME", "VM-001", elbv2=Elbv2())
