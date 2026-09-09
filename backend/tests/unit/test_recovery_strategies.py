import pytest
import importlib.util, pathlib

_STRAT_PATH = pathlib.Path(__file__).parents[3] / 'lambda' / 'recovery' / 'strategies.py'
spec = importlib.util.spec_from_file_location('strategies', _STRAT_PATH)
strat_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat_module)

import sys
sys.modules['strategies'] = strat_module

from strategies import dispatch_strategy, MAX_RECOVERY_ATTEMPTS, RecoveryStrategyError, RecoveryStrategy
from app.models.resource import FailureType
from app.models.incident import RecoveryActionType

@pytest.mark.parametrize(
    "failure_type, expected_action_type",
    [
        (FailureType.HIGH_CPU, RecoveryActionType.SCALE_OUT),
        (FailureType.SERVICE_FAILURE, RecoveryActionType.SERVICE_RESTART),
        (FailureType.STORAGE_EXHAUSTION, RecoveryActionType.STORAGE_CLEANUP),
        (FailureType.NETWORK_LATENCY, RecoveryActionType.NETWORK_REROUTE),
        (FailureType.SERVICE_DOWNTIME, RecoveryActionType.FAILOVER),
    ],
)
def test_dispatch_returns_correct_action_type(failure_type, expected_action_type):
    strategy = dispatch_strategy(failure_type)
    assert strategy.recovery_action_type == expected_action_type

@pytest.mark.parametrize(
    "failure_type",
    [
        FailureType.HIGH_CPU,
        FailureType.SERVICE_FAILURE,
        FailureType.STORAGE_EXHAUSTION,
        FailureType.NETWORK_LATENCY,
        FailureType.SERVICE_DOWNTIME,
    ],
)
def test_each_strategy_execute_returns_outcome_and_delta(failure_type):
    strategy = dispatch_strategy(failure_type)
    outcome, delta = strategy.execute("test-id")
    assert isinstance(outcome, str)
    assert len(outcome) > 0
    assert isinstance(delta, dict)
    assert len(delta) > 0

def test_high_cpu_strategy_resets_cpu_to_nominal():
    strategy = dispatch_strategy(FailureType.HIGH_CPU)
    _, delta = strategy.execute("test-id")
    assert delta["cpu_utilization"] == 25.0

def test_service_failure_strategy_resets_latency():
    strategy = dispatch_strategy(FailureType.SERVICE_FAILURE)
    _, delta = strategy.execute("test-id")
    assert delta["network_latency_ms"] == 15.0

def test_storage_exhaustion_strategy_resets_storage():
    strategy = dispatch_strategy(FailureType.STORAGE_EXHAUSTION)
    _, delta = strategy.execute("test-id")
    assert delta["storage_utilization"] == 20.0

def test_network_latency_strategy_resets_latency():
    strategy = dispatch_strategy(FailureType.NETWORK_LATENCY)
    _, delta = strategy.execute("test-id")
    assert delta["network_latency_ms"] == 15.0

def test_service_downtime_strategy_resets_all_metrics():
    strategy = dispatch_strategy(FailureType.SERVICE_DOWNTIME)
    _, delta = strategy.execute("test-id")
    assert "cpu_utilization" in delta
    assert "memory_utilization" in delta
    assert "storage_utilization" in delta
    assert "network_latency_ms" in delta

def test_max_recovery_attempts_is_3():
    assert MAX_RECOVERY_ATTEMPTS == 3

def test_strategy_error_class_is_exception():
    assert issubclass(RecoveryStrategyError, Exception)
