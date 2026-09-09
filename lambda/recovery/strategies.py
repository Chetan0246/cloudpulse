from dataclasses import dataclass

from app.models.incident import RecoveryActionType
from app.models.resource import FailureType

class RecoveryStrategyError(Exception):
    pass

MAX_RECOVERY_ATTEMPTS = 3

@dataclass
class RecoveryStrategy:
    failure_type: FailureType
    recovery_action_type: RecoveryActionType
    description: str
    simulated_duration_seconds: float

    def execute(self, resource_id: str) -> tuple[str, dict]:
        if self.failure_type == FailureType.HIGH_CPU:
            metrics_delta = {"cpu_utilization": 25.0, "memory_utilization": 30.0}
        elif self.failure_type == FailureType.SERVICE_FAILURE:
            metrics_delta = {"network_latency_ms": 15.0, "cpu_utilization": 25.0}
        elif self.failure_type == FailureType.STORAGE_EXHAUSTION:
            metrics_delta = {"storage_utilization": 20.0}
        elif self.failure_type == FailureType.NETWORK_LATENCY:
            metrics_delta = {"network_latency_ms": 15.0}
        elif self.failure_type == FailureType.SERVICE_DOWNTIME:
            metrics_delta = {
                "cpu_utilization": 25.0,
                "memory_utilization": 30.0,
                "storage_utilization": 20.0,
                "network_latency_ms": 15.0,
            }
        else:
            raise RecoveryStrategyError(f"Unknown failure type {self.failure_type}")
        
        return (self.description, metrics_delta)

def dispatch_strategy(failure_type: FailureType) -> RecoveryStrategy:
    strategies = {
        FailureType.HIGH_CPU: RecoveryStrategy(
            failure_type=FailureType.HIGH_CPU,
            recovery_action_type=RecoveryActionType.SCALE_OUT,
            description="Simulated scale-out: increased virtual CPU allocation",
            simulated_duration_seconds=3.0,
        ),
        FailureType.SERVICE_FAILURE: RecoveryStrategy(
            failure_type=FailureType.SERVICE_FAILURE,
            recovery_action_type=RecoveryActionType.SERVICE_RESTART,
            description="Simulated service restart: health check resumed",
            simulated_duration_seconds=5.0,
        ),
        FailureType.STORAGE_EXHAUSTION: RecoveryStrategy(
            failure_type=FailureType.STORAGE_EXHAUSTION,
            recovery_action_type=RecoveryActionType.STORAGE_CLEANUP,
            description="Simulated storage cleanup: freed 30% capacity",
            simulated_duration_seconds=4.0,
        ),
        FailureType.NETWORK_LATENCY: RecoveryStrategy(
            failure_type=FailureType.NETWORK_LATENCY,
            recovery_action_type=RecoveryActionType.NETWORK_REROUTE,
            description="Simulated traffic reroute: alternate path active",
            simulated_duration_seconds=2.0,
        ),
        FailureType.SERVICE_DOWNTIME: RecoveryStrategy(
            failure_type=FailureType.SERVICE_DOWNTIME,
            recovery_action_type=RecoveryActionType.FAILOVER,
            description="Simulated failover: standby instance promoted",
            simulated_duration_seconds=6.0,
        ),
    }
    
    if failure_type not in strategies:
        raise RecoveryStrategyError(f"No strategy for failure type {failure_type}")
        
    return strategies[failure_type]
