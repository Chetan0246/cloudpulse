import pytest
from unittest.mock import MagicMock, patch
import json
import importlib.util, pathlib
import sys
import uuid
from datetime import datetime, timezone

from app.models.resource import FailureType, ResourceState, HealthStatus
from app.models.incident import Incident, IncidentStatus, IncidentSeverity

def _load_recovery_handler():
    # 2. Load strategies
    _STRAT_PATH = pathlib.Path(__file__).parents[3] / 'lambda' / 'recovery' / 'strategies.py'
    spec = importlib.util.spec_from_file_location('strategies', _STRAT_PATH)
    strat_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(strat_module)
    sys.modules['strategies'] = strat_module

    # 3. Load handler
    _HANDLER_PATH = pathlib.Path(__file__).parents[3] / 'lambda' / 'recovery' / 'handler.py'
    spec_h = importlib.util.spec_from_file_location('handler', _HANDLER_PATH)
    handler_module = importlib.util.module_from_spec(spec_h)
    spec_h.loader.exec_module(handler_module)
    
    return handler_module

@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('app.services.monitoring_service.MonitoringService') as mock_ms, \
         patch('boto3.client') as mock_boto:
        yield mock_ms, mock_boto

def test_successful_recovery_high_cpu():
    h = _load_recovery_handler()
    
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated_mock_resource"
    
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {
        "source": "cloudpulse.simulator",
        "detail": {
            "resourceId": "VM-001",
            "failureType": "HIGH_CPU"
        }
    }
    
    with patch("boto3.client") as mock_boto:
        result = h.handler(event, {})
    
    assert result["statusCode"] == 200
    mock_resource_repo.put.assert_called_once_with("updated_mock_resource")
    mock_incident_repo.create.assert_called_once()
    mock_incident_repo.update.assert_not_called()

def test_successful_recovery_service_failure():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated_mock_resource"
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "API-001", "failureType": "SERVICE_FAILURE"}}
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200

def test_successful_recovery_storage_exhaustion():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated_mock_resource"
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "DB-001", "failureType": "STORAGE_EXHAUSTION"}}
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200

def test_successful_recovery_network_latency():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated_mock_resource"
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "API-001", "failureType": "NETWORK_LATENCY"}}
    with patch("boto3.client"):
        result = h.handler(event, {})
    assert result["statusCode"] == 200

def test_successful_recovery_service_downtime():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated_mock_resource"
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "SERVICE_DOWNTIME"}}
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
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
    result = h.handler(event, {})
    assert result["statusCode"] == 200
    assert result["body"] == "Already recovering"
    mock_resource_repo.update_state.assert_not_called()

def test_failed_recovery_transitions_to_recovery_failed():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED

    mock_resource_repo = MagicMock()
    mock_resource_repo.get.return_value = mock_resource
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None, None]

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    # Patch dispatch_strategy in the handler module's namespace
    from strategies import RecoveryStrategyError as RSE

    def mock_dispatch(failure_type):
        raise RSE("forced failure")

    with patch.object(h, "dispatch_strategy", mock_dispatch):
        event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
        with patch("boto3.client"):
            result = h.handler(event, {})

    assert result["statusCode"] == 500
    # Last update_state call should set resource to RECOVERY_FAILED
    last_call = mock_resource_repo.update_state.call_args_list[-1]
    assert last_call.args[1] == ResourceState.RECOVERY_FAILED

def test_invalid_event_returns_400():
    h = _load_recovery_handler()
    event = {"source": "unknown"}
    result = h.handler(event, {})
    assert result["statusCode"] == 400

def test_unknown_failure_type_in_alarm_name():
    h = _load_recovery_handler()
    event = {
        "source": "aws.cloudwatch",
        "detail": {
            "alarmName": "cloudpulse-VM-001-UNKNOWN_FAILURE"
        }
    }
    result = h.handler(event, {})
    assert result["statusCode"] == 400

def test_resource_metrics_reset_after_recovery():
    h = _load_recovery_handler()
    
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    def mock_copy(**kwargs):
        assert kwargs["update"]["cpu_utilization"] == 25.0
        return "updated"
    mock_resource.model_copy.side_effect = mock_copy
    
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
    
    with patch("boto3.client"):
        h.handler(event, {})
    mock_resource_repo.put.assert_called_with("updated")

def test_existing_incident_is_reused():
    h = _load_recovery_handler()
    
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated"
    
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    
    existing_incident = Incident(
        incident_id=str(uuid.uuid4()),
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RECOVERING,
        state_at_detection=ResourceState.FAILURE_DETECTED,
        recovery_attempts=0,
        recovery_actions=[]
    )
    
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = [existing_incident]
    
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
    
    with patch("boto3.client"):
        h.handler(event, {})
        
    mock_incident_repo.create.assert_not_called()
    mock_incident_repo.update.assert_called_once()

def test_sns_success_notification():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_resource.model_copy.return_value = "updated"
    
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED
    
    mock_resource_repo = MagicMock()
    mock_resource_repo.get.side_effect = [mock_resource, mock_resource]
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None]
    
    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []
    
    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)
    
    event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
    
    mock_boto_client = MagicMock()
    mock_sns = MagicMock()
    mock_boto_client.return_value = mock_sns
    
    with patch("boto3.client", mock_boto_client):
        h.handler(event, {})
        
    called_kwargs = mock_sns.publish.call_args.kwargs
    assert "[CloudPulse] RECOVERED" in called_kwargs["Subject"]


def test_sns_failure_notification():
    h = _load_recovery_handler()
    mock_resource = MagicMock()
    mock_resource.current_state = ResourceState.FAILURE_DETECTED
    mock_updated_resource_init = MagicMock()
    mock_updated_resource_init.current_state = ResourceState.RECOVERY_INITIATED

    mock_resource_repo = MagicMock()
    mock_resource_repo.get.return_value = mock_resource
    mock_resource_repo.update_state.side_effect = [mock_updated_resource_init, None, None]

    mock_incident_repo = MagicMock()
    mock_incident_repo.list.return_value = []

    h.ResourceRepository = MagicMock(return_value=mock_resource_repo)
    h.IncidentRepository = MagicMock(return_value=mock_incident_repo)

    from strategies import RecoveryStrategyError as RSE

    def mock_dispatch(failure_type):
        raise RSE("forced failure for SNS test")

    mock_boto_client = MagicMock()
    mock_sns = MagicMock()
    mock_boto_client.return_value = mock_sns

    with patch.object(h, "dispatch_strategy", mock_dispatch):
        event = {"source": "cloudpulse.simulator", "detail": {"resourceId": "VM-001", "failureType": "HIGH_CPU"}}
        with patch("boto3.client", mock_boto_client):
            result = h.handler(event, {})

    assert result["statusCode"] == 500
    called_kwargs = mock_sns.publish.call_args.kwargs
    assert "[CloudPulse] RECOVERY FAILED" in called_kwargs["Subject"]

