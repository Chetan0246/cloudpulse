import importlib.util
import pathlib
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.resource import (
    FailureType,
    HealthStatus,
    ResourceState,
    ResourceType,
    SimulatedResource,
)


def _make_resource(
    resource_id: str,
    failure_type: FailureType,
    resource_type: ResourceType = ResourceType.VM,
) -> SimulatedResource:
    """Build a realistic resource in FAILURE_DETECTED for handler tests."""
    return SimulatedResource(
        resource_id=resource_id,
        resource_type=resource_type,
        current_state=ResourceState.FAILURE_DETECTED,
        health_status=HealthStatus.CRITICAL,
        active_failure_type=failure_type,
    )


def _mock_resource_repo(resource: SimulatedResource, extra_state_updates: int = 1):
    """Repository double whose first transition returns RECOVERY_INITIATED."""
    initial_transition = resource.model_copy(
        update={"current_state": ResourceState.RECOVERY_INITIATED}
    )
    repo = MagicMock()
    repo.get.return_value = resource
    repo.update_state.side_effect = [initial_transition] + [None] * extra_state_updates
    return repo


def _load_recovery_handler():
    # 2. Load strategies
    _strat_path = pathlib.Path(__file__).parents[3] / "lambda" / "recovery" / "strategies.py"
    spec = importlib.util.spec_from_file_location("strategies", _strat_path)
    strat_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(strat_module)
    sys.modules["strategies"] = strat_module

    # 3. Load handler
    _handler_path = pathlib.Path(__file__).parents[3] / "lambda" / "recovery" / "handler.py"
    spec_h = importlib.util.spec_from_file_location("handler", _handler_path)
    handler_module = importlib.util.module_from_spec(spec_h)
    spec_h.loader.exec_module(handler_module)

    return handler_module


@pytest.fixture(autouse=True)
def mock_dependencies():
    with (
        patch("app.services.monitoring_service.MonitoringService") as mock_ms,
        patch("boto3.client") as mock_boto,
    ):
        yield mock_ms, mock_boto


def test_successful_recovery_high_cpu():
    h = _load_recovery_handler()

    resource = _make_resource("VM-001", FailureType.HIGH_CPU)
    mock_resource_repo = _mock_resource_repo(resource, extra_state_updates=1)

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
    }

    with patch("boto3.client"):
        result = h.handler(event, {})

    assert result["statusCode"] == 200
    persisted = mock_resource_repo.put.call_args.args[0]
    assert persisted.current_state == ResourceState.RECOVERED
    mock_incident_repo.create.assert_called_once()
    mock_incident_repo.update.assert_not_called()


def test_successful_recovery_service_failure():
    h = _load_recovery_handler()
    resource = _make_resource("API-001", FailureType.SERVICE_FAILURE, ResourceType.API)
    mock_resource_repo = _mock_resource_repo(resource)
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "API-001", "failureType": "SERVICE_FAILURE"},
    }
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200


def test_successful_recovery_storage_exhaustion():
    h = _load_recovery_handler()
    resource = _make_resource("DB-001", FailureType.STORAGE_EXHAUSTION, ResourceType.DB)
    mock_resource_repo = _mock_resource_repo(resource)
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "DB-001", "failureType": "STORAGE_EXHAUSTION"},
    }
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200


def test_successful_recovery_network_latency():
    h = _load_recovery_handler()
    resource = _make_resource("API-001", FailureType.NETWORK_LATENCY, ResourceType.API)
    mock_resource_repo = _mock_resource_repo(resource)
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "API-001", "failureType": "NETWORK_LATENCY"},
    }
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200


def test_successful_recovery_service_downtime():
    h = _load_recovery_handler()
    resource = _make_resource("VM-001", FailureType.SERVICE_DOWNTIME)
    mock_resource_repo = _mock_resource_repo(resource)
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "SERVICE_DOWNTIME"},
    }
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200


def test_duplicate_event_is_idempotent():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.RECOVERY_INITIATED
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.return_value = mock_resource
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock()

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
    }
    result = h.handler(event, {})
    assert result["statusCode"] == 200
    assert result["body"] == "Already recovering"
    mock_resource_repo.update_state.assert_not_called()


def test_failed_recovery_transitions_to_recovery_failed():
    h = _load_recovery_handler()
    resource = _make_resource("VM-001", FailureType.HIGH_CPU)
    mock_resource_repo = _mock_resource_repo(resource, extra_state_updates=2)

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    # Patch dispatch_strategy in the handler module's namespace
    from strategies import RecoveryStrategyError as StrategyError

    def mock_dispatch(failure_type):
        raise StrategyError("forced failure")

    with patch.object(h, "dispatch_strategy", mock_dispatch):
        event = {
            "source": "cloudpulse.simulator",
            "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
        }
        with patch("boto3.client"):
            with pytest.raises(RuntimeError, match="Recovery failed after 1 attempt"):
                h.handler(event, {})

    # Last update_state call should set resource to RECOVERY_FAILED
    last_call = mock_resource_repo.update_state.call_args_list[-1]
    assert last_call.args[1] == ResourceState.RECOVERY_FAILED


def test_invalid_event_raises_for_dlq():
    """A-06 fix: Unparseable event raises ValueError so Lambda retry policy and DLQ engage."""
    import pytest

    h = _load_recovery_handler()
    event = {"source": "unknown"}
    with pytest.raises(ValueError, match="Cannot parse event"):
        h.handler(event, {})


def test_unknown_failure_type_in_alarm_name():
    """A-06 fix: Unknown alarm suffix raises ValueError — routed to DLQ, not silently swallowed."""
    import pytest

    h = _load_recovery_handler()
    event = {
        "source": "aws.cloudwatch",
        "detail": {"alarmName": "cloudpulse-VM-001-UNKNOWN_FAILURE"},
    }
    with pytest.raises(ValueError, match="Cannot parse event"):
        h.handler(event, {})


def test_resource_metrics_reset_after_recovery():
    h = _load_recovery_handler()

    resource = _make_resource(
        "VM-001",
        FailureType.HIGH_CPU,
    ).model_copy(
        update={
            "cpu_utilization": 95.0,
            "memory_utilization": 90.0,
        }
    )
    mock_resource_repo = _mock_resource_repo(resource)

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
    }

    with patch("boto3.client"):
        h.handler(event, {})

    persisted = mock_resource_repo.put.call_args.args[0]
    assert persisted.cpu_utilization == 25.0
    assert persisted.current_state == ResourceState.RECOVERED


def test_existing_incident_is_reused():
    h = _load_recovery_handler()

    resource = _make_resource("VM-001", FailureType.HIGH_CPU)
    mock_resource_repo = _mock_resource_repo(resource)

    existing_incident = Incident(
        incident_id=str(uuid.uuid4()),
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RECOVERING,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        recovery_attempts=0,
        recovery_actions=[],
    )

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = [existing_incident]

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
    }

    with patch("boto3.client"):
        h.handler(event, {})

    mock_incident_repo.create.assert_not_called()
    mock_incident_repo.update.assert_called_once()


def test_sns_success_notification():
    h = _load_recovery_handler()
    resource = _make_resource("VM-001", FailureType.HIGH_CPU)
    mock_resource_repo = _mock_resource_repo(resource)

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    event = {
        "source": "cloudpulse.simulator",
        "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
    }

    mock_boto_client = MagicMock()
    mock_sns = MagicMock()
    mock_boto_client.return_value = mock_sns

    with patch("boto3.client", mock_boto_client):
        h.handler(event, {})

    called_kwargs = mock_sns.publish.call_args.kwargs
    assert "[CloudPulse] RECOVERED" in called_kwargs["Subject"]


def test_sns_failure_notification():
    h = _load_recovery_handler()
    resource = _make_resource("VM-001", FailureType.HIGH_CPU)
    mock_resource_repo = _mock_resource_repo(resource, extra_state_updates=2)

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    from strategies import RecoveryStrategyError as StrategyError

    def mock_dispatch(failure_type):
        raise StrategyError("forced failure for SNS test")

    mock_boto_client = MagicMock()
    mock_sns = MagicMock()
    mock_boto_client.return_value = mock_sns

    with patch.object(h, "dispatch_strategy", mock_dispatch):
        event = {
            "source": "cloudpulse.simulator",
            "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"},
        }
        with patch("boto3.client", mock_boto_client):
            with pytest.raises(RuntimeError):
                h.handler(event, {})

    called_kwargs = mock_sns.publish.call_args.kwargs
    assert "[CloudPulse] RECOVERY FAILED" in called_kwargs["Subject"]
