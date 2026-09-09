"""
Layer 7: Recovery Tests
Tests recovery strategy dispatcher, action execution, and state transitions.
"""

from unittest.mock import MagicMock
import pytest

from app.models.incident import RecoveryActionType
from app.models.resource import FailureType, HealthStatus, ResourceState
from app.repositories.incident_repository import IncidentRepository
from app.repositories.resource_repository import ResourceRepository
from handler import handler
from strategies import MAX_RECOVERY_ATTEMPTS, RecoveryStrategyError, dispatch_strategy


class TestRecoveryLayer:
    """Recovery strategy execution and state machine tests."""

    @pytest.mark.parametrize(
        "failure_type,expected_action",
        [
            (FailureType.HIGH_CPU, RecoveryActionType.SCALE_OUT),
            (FailureType.SERVICE_FAILURE, RecoveryActionType.SERVICE_RESTART),
            (FailureType.STORAGE_EXHAUSTION, RecoveryActionType.STORAGE_CLEANUP),
            (FailureType.NETWORK_LATENCY, RecoveryActionType.NETWORK_REROUTE),
            (FailureType.SERVICE_DOWNTIME, RecoveryActionType.FAILOVER),
        ],
    )
    def test_strategy_dispatcher_maps_correct_actions(
        self, failure_type: FailureType, expected_action: RecoveryActionType
    ):
        """Every failure scenario maps to its dedicated recovery action type."""
        strategy = dispatch_strategy(failure_type)
        assert strategy.recovery_action_type == expected_action
        assert strategy.failure_type == failure_type

        # Verify execution produces delta and message
        outcome_msg, delta = strategy.execute("VM-001")
        assert isinstance(outcome_msg, str) and len(outcome_msg) > 0
        assert isinstance(delta, dict) and len(delta) > 0

    def test_recovery_lambda_execution_success(
        self, seed_fleet: list, event_factory: dict
    ):
        """Recovery Lambda processes alarm event and transitions resource to RECOVERED."""
        res_repo = ResourceRepository()
        inc_repo = IncidentRepository()

        # 1. Put resource into FAILURE_DETECTED
        res = res_repo.get("VM-001")
        res_repo.put(
            res.model_copy(
                update={
                    "current_state": ResourceState.FAILURE_DETECTED,
                    "health_status": HealthStatus.CRITICAL,
                    "active_failure_type": FailureType.HIGH_CPU,
                    "cpu_utilization": 95.0,
                }
            )
        )

        event = event_factory["alarm"](
            alarm_name="cloudpulse-VM-001-HIGH_CPU",
            resource_id="VM-001",
        )

        result = handler(event, context=MagicMock())
        assert result["statusCode"] == 200

        # Verify resource recovered
        recovered_res = res_repo.get("VM-001")
        assert recovered_res.current_state == ResourceState.RECOVERED
        assert recovered_res.health_status == HealthStatus.HEALTHY
        assert recovered_res.cpu_utilization == 25.0

        # Verify incident resolved
        incidents = inc_repo.list(resource_id="VM-001")
        assert len(incidents) >= 1
        resolved_inc = incidents[0]
        assert resolved_inc.status.value == "RESOLVED"
        assert resolved_inc.recovery_action == "SCALE_OUT"
        assert resolved_inc.duration_seconds is not None

    def test_idempotency_pre_read_gate(
        self, seed_fleet: list, event_factory: dict
    ):
        """If resource is already in RECOVERY_IN_PROGRESS or RECOVERED, handler exits cleanly."""
        res_repo = ResourceRepository()
        res = res_repo.get("VM-001")
        res_repo.put(
            res.model_copy(
                update={
                    "current_state": ResourceState.RECOVERY_IN_PROGRESS,
                    "health_status": HealthStatus.CRITICAL,
                }
            )
        )

        event = event_factory["alarm"](
            alarm_name="cloudpulse-VM-001-HIGH_CPU",
            resource_id="VM-001",
        )
        result = handler(event, context=MagicMock())
        assert result["statusCode"] == 200
        assert result["body"] == "Already recovering"
