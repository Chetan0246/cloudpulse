"""
Unit tests for the API Gateway Lambda handler in lambda/api/handler.py.

Verifies:
- Dynamic stage stripping: requests to /dev/health, /dev/resources, etc.,
  correctly route to FastAPI endpoints instead of returning 404 Not Found.
- Root path handling: requests to /dev and /dev/ return 200 OK.
- $default stage handling without prefix.
- Mangum instance caching per base path.
- Injected failure endpoint routing with stage prefix /dev/simulate/failure.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import uuid
from datetime import UTC, datetime
from typing import Any
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

_HANDLER_PATH = pathlib.Path(__file__).parents[3] / "lambda" / "api" / "handler.py"


def _load_api_handler():
    pytest.importorskip("mangum")
    spec = importlib.util.spec_from_file_location("api_handler", _HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_event(
    path: str, stage: str = "dev", method: str = "GET", body: str | None = None
) -> dict[str, Any]:
    event = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
        },
        "requestContext": {
            "stage": stage,
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
        },
        "isBase64Encoded": False,
    }
    if body is not None:
        event["body"] = body
    return event


def test_api_handler_stage_stripping_health():
    """Verify that GET /dev/health correctly strips /dev and returns 200."""
    api_module = _load_api_handler()
    event = _make_event("/dev/health", stage="dev", method="GET")

    response = api_module.handler(event, MagicMock())
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["status"] == "ok"
    assert data["service"] == "cloudpulse-api"


def test_api_handler_root_path():
    """Verify that GET /dev and /dev/ return 200 OK instead of 404."""
    api_module = _load_api_handler()

    # /dev/
    event_slash = _make_event("/dev/", stage="dev", method="GET")
    resp_slash = api_module.handler(event_slash, MagicMock())
    assert resp_slash["statusCode"] == 200
    data_slash = json.loads(resp_slash["body"])
    assert data_slash["status"] == "ok"

    # /dev
    event_no_slash = _make_event("/dev", stage="dev", method="GET")
    resp_no_slash = api_module.handler(event_no_slash, MagicMock())
    assert resp_no_slash["statusCode"] == 200
    data_no_slash = json.loads(resp_no_slash["body"])
    assert data_no_slash["status"] == "ok"


def test_api_handler_default_stage():
    """Verify that $default stage correctly handles /health without stripping."""
    api_module = _load_api_handler()
    event = _make_event("/health", stage="$default", method="GET")

    response = api_module.handler(event, MagicMock())
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["status"] == "ok"


def test_api_handler_caches_mangum_instances():
    """Verify that Mangum instances are cached in _handlers per base path."""
    api_module = _load_api_handler()
    api_module._handlers.clear()

    event_dev = _make_event("/dev/health", stage="dev")
    api_module.handler(event_dev, MagicMock())
    assert "/dev" in api_module._handlers

    handler_ref = api_module._handlers["/dev"]
    api_module.handler(event_dev, MagicMock())
    assert api_module._handlers["/dev"] is handler_ref


def test_api_handler_simulate_failure_route_matched():
    """Verify that POST /dev/simulate/failure routes to simulate handler, not 404."""
    api_module = _load_api_handler()
    body = json.dumps({"resource_id": "VM-001", "failure_type": "HIGH_CPU"})
    event = _make_event("/dev/simulate/failure", stage="dev", method="POST", body=body)

    sample_res = SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.FAILURE_DETECTED,
        health_status=HealthStatus.CRITICAL,
        cpu_utilization=95.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
    )
    sample_inc = Incident(
        incident_id=str(uuid.uuid4()),
        resource_id="VM-001",
        failure_type=FailureType.HIGH_CPU,
        status=IncidentStatus.OPEN,
        severity=IncidentSeverity.HIGH,
        started_at=datetime.now(UTC),
        state_at_detection=ResourceState.FAILURE_DETECTED,
    )

    with patch("app.routers.simulate.SimulationService") as mock_service_cls:
        mock_instance = mock_service_cls.return_value
        mock_instance.inject_failure.return_value = (
            sample_res,
            sample_inc,
            {"cpu_utilization": 95.0},
        )

        response = api_module.handler(event, MagicMock())
        # Should be 201 Created from inject_failure route, NOT 404 Not Found!
        assert response["statusCode"] == 201
        data = json.loads(response["body"])
        assert "Simulated failure" in data["message"]
        assert data["resource"]["resource_id"] == "VM-001"
