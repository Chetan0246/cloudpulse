"""
Unit tests for the Simulator Lambda handler helpers.

Coverage:
- _jitter(): bounds, always-within-range, clamping
- _compute_state(): health → state mapping for each metric threshold
- _publish_metrics(): publishes exactly 5 metrics, includes ServiceHealth,
  uses single API call, correct dimensions and units
- handler(): skips RECOVERY_INITIATED/IN_PROGRESS resources (race guard)
- handler(): handles empty resource list gracefully
- Metric alignment: simulator and MonitoringService produce matching metric sets

All AWS calls are mocked via unittest.mock — no real AWS resources needed.

NOTE: The lambda/ directory cannot be imported with `from lambda.simulator import ...`
because `lambda` is a Python keyword. All access to the simulator handler code
is done via importlib.util.spec_from_file_location().
"""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── Shared path constant ──────────────────────────────────────────────────────

_HANDLER_PATH = pathlib.Path(__file__).parents[3] / "lambda" / "simulator" / "handler.py"


# ── Module loader helper ──────────────────────────────────────────────────────

def _load_simulator_handler():
    """
    Load the simulator handler module with all app.* imports stubbed out.

    The simulator handler does sys.path.insert(0, "/opt/python") and then
    imports from app.*. In tests, the backend/app package is already on
    sys.path via conftest.py, so we only need to satisfy the stubs that
    differ between the Lambda runtime and the test environment.

    Returns the loaded module object for direct function access.
    """
    spec = importlib.util.spec_from_file_location("_simulator_handler", _HANDLER_PATH)
    assert spec and spec.loader

    from app.models.resource import (
        CPU_FAILURE_THRESHOLD,
        CPU_WARNING_THRESHOLD,
        MEMORY_FAILURE_THRESHOLD,
        MEMORY_WARNING_THRESHOLD,
        NETWORK_LATENCY_FAILURE_MS,
        NETWORK_LATENCY_WARNING_MS,
        STORAGE_FAILURE_THRESHOLD,
        STORAGE_WARNING_THRESHOLD,
        HealthStatus,
        ResourceState,
        SimulatedResource,
    )
    from app.services.monitoring_service import compute_service_health

    stub_resource_mod = MagicMock()
    stub_resource_mod.CPU_FAILURE_THRESHOLD = CPU_FAILURE_THRESHOLD
    stub_resource_mod.CPU_WARNING_THRESHOLD = CPU_WARNING_THRESHOLD
    stub_resource_mod.MEMORY_FAILURE_THRESHOLD = MEMORY_FAILURE_THRESHOLD
    stub_resource_mod.MEMORY_WARNING_THRESHOLD = MEMORY_WARNING_THRESHOLD
    stub_resource_mod.STORAGE_FAILURE_THRESHOLD = STORAGE_FAILURE_THRESHOLD
    stub_resource_mod.STORAGE_WARNING_THRESHOLD = STORAGE_WARNING_THRESHOLD
    stub_resource_mod.NETWORK_LATENCY_FAILURE_MS = NETWORK_LATENCY_FAILURE_MS
    stub_resource_mod.NETWORK_LATENCY_WARNING_MS = NETWORK_LATENCY_WARNING_MS
    stub_resource_mod.HealthStatus = HealthStatus
    stub_resource_mod.ResourceState = ResourceState
    stub_resource_mod.Resource = SimulatedResource

    monitoring_stub = MagicMock()
    monitoring_stub.compute_service_health = compute_service_health

    config_stub = MagicMock()
    config_stub.get_settings.return_value = MagicMock(
        log_level="DEBUG",
        aws_region="us-east-1",
        cloudwatch_namespace="CloudPulse",
    )

    with patch.dict(
        "sys.modules",
        {
            "app.config": config_stub,
            "app.logging_config": MagicMock(),
            "app.models.resource": stub_resource_mod,
            "app.repositories.resource_repository": MagicMock(),
            "app.services.monitoring_service": monitoring_stub,
        },
    ):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_resource(
    resource_id: str = "VM-001",
    cpu: float = 25.0,
    memory: float = 30.0,
    storage: float = 20.0,
    latency: float = 15.0,
    state: str = "HEALTHY",
) -> Any:
    """Return a SimulatedResource configured with the given metric values."""
    from app.models.resource import (
        HealthStatus,
        ResourceState,
        ResourceType,
        SimulatedResource,
    )

    state_enum = ResourceState(state)
    health = HealthStatus.HEALTHY
    if state_enum in (
        ResourceState.FAILURE_DETECTED,
        ResourceState.RECOVERY_INITIATED,
        ResourceState.RECOVERY_IN_PROGRESS,
    ):
        health = HealthStatus.CRITICAL

    return SimulatedResource(
        resource_id=resource_id,
        resource_type=ResourceType.VM,
        cpu_utilization=cpu,
        memory_utilization=memory,
        storage_utilization=storage,
        network_latency_ms=latency,
        current_state=state_enum,
        health_status=health,
        last_heartbeat=datetime.now(timezone.utc),
    )


# ── _jitter tests ─────────────────────────────────────────────────────────────


class TestJitter:
    """_jitter() is a pure random-walk function with clamping."""

    @pytest.fixture(autouse=True)
    def module(self) -> None:
        self.h = _load_simulator_handler()

    def test_value_stays_within_default_bounds(self) -> None:
        """_jitter must never produce a value outside [min_val, max_val]."""
        for _ in range(500):
            result = self.h._jitter(50.0, 20.0, min_val=0.0, max_val=100.0)
            assert 0.0 <= result <= 100.0

    def test_value_rounded_to_two_decimal_places(self) -> None:
        result = self.h._jitter(50.0, 5.0)
        assert result == round(result, 2)

    def test_clamp_at_lower_bound(self) -> None:
        """Extreme negative delta must clamp to min_val."""
        result = self.h._jitter(0.0, 200.0, min_val=0.0, max_val=100.0)
        assert result >= 0.0

    def test_clamp_at_upper_bound(self) -> None:
        """Extreme positive delta must clamp to max_val."""
        result = self.h._jitter(100.0, 200.0, min_val=0.0, max_val=100.0)
        assert result <= 100.0

    def test_custom_max_val_for_latency(self) -> None:
        """Network latency uses max_val=5000 in the handler."""
        for _ in range(200):
            result = self.h._jitter(50.0, 50.0, min_val=0.0, max_val=5000.0)
            assert 0.0 <= result <= 5000.0


# ── _compute_state tests ──────────────────────────────────────────────────────


class TestComputeState:
    """_compute_state() maps metric thresholds to ResourceState + HealthStatus."""

    @pytest.fixture(autouse=True)
    def module(self) -> None:
        self.h = _load_simulator_handler()

    def test_healthy_resource_stays_healthy(self) -> None:
        from app.models.resource import HealthStatus, ResourceState

        resource = _make_resource(cpu=25.0, memory=30.0, storage=20.0, latency=15.0)
        state, health = self.h._compute_state(resource)
        assert state == ResourceState.HEALTHY
        assert health == HealthStatus.HEALTHY

    def test_high_cpu_gives_failure_detected(self) -> None:
        from app.models.resource import HealthStatus, ResourceState

        resource = _make_resource(cpu=92.0, memory=60.0, storage=20.0, latency=50.0)
        state, health = self.h._compute_state(resource)
        assert state == ResourceState.FAILURE_DETECTED
        assert health == HealthStatus.CRITICAL

    def test_warning_level_cpu_gives_warning(self) -> None:
        from app.models.resource import HealthStatus, ResourceState

        # 78% is between warning threshold (75) and failure threshold (85)
        resource = _make_resource(cpu=78.0, memory=30.0, storage=20.0, latency=15.0)
        state, health = self.h._compute_state(resource)
        assert state == ResourceState.WARNING
        assert health == HealthStatus.DEGRADED

    def test_high_latency_gives_failure_detected(self) -> None:
        from app.models.resource import HealthStatus, ResourceState

        resource = _make_resource(cpu=20.0, memory=25.0, storage=15.0, latency=750.0)
        state, health = self.h._compute_state(resource)
        assert state == ResourceState.FAILURE_DETECTED
        assert health == HealthStatus.CRITICAL

    def test_high_storage_gives_failure_detected(self) -> None:
        from app.models.resource import HealthStatus, ResourceState

        resource = _make_resource(cpu=30.0, memory=40.0, storage=96.0, latency=50.0)
        state, health = self.h._compute_state(resource)
        assert state == ResourceState.FAILURE_DETECTED
        assert health == HealthStatus.CRITICAL


# ── _publish_metrics tests ────────────────────────────────────────────────────


class TestPublishMetrics:
    """_publish_metrics() must publish exactly 5 metrics in a single API call."""

    @pytest.fixture(autouse=True)
    def module(self) -> None:
        self.h = _load_simulator_handler()

    def test_publishes_exactly_five_metrics(self) -> None:
        """All 5 metrics must be included in a single batched API call."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        mock_cw.put_metric_data.assert_called_once()
        kwargs = mock_cw.put_metric_data.call_args[1]
        assert kwargs["Namespace"] == "CloudPulse"
        assert len(kwargs["MetricData"]) == 5

    def test_includes_service_health_metric(self) -> None:
        """ServiceHealth must be one of the published metrics."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        metric_names = {m["MetricName"] for m in kwargs["MetricData"]}
        assert "ServiceHealth" in metric_names

    def test_all_expected_metric_names_present(self) -> None:
        """Verify exact metric names match the documented CloudPulse namespace."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        metric_names = {m["MetricName"] for m in kwargs["MetricData"]}
        expected = {
            "CPUUtilization",
            "MemoryUtilization",
            "StorageUtilization",
            "NetworkLatency",
            "ServiceHealth",
        }
        assert metric_names == expected

    def test_dimensions_contain_resource_id_and_type(self) -> None:
        """Each metric must carry ResourceId and ResourceType dimensions."""
        from app.models.resource import ResourceType

        mock_cw = MagicMock()
        resource = _make_resource(resource_id="DB-001")
        resource = resource.model_copy(update={"resource_type": ResourceType.DB})

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        for dp in kwargs["MetricData"]:
            dim_map = {d["Name"]: d["Value"] for d in dp["Dimensions"]}
            assert dim_map.get("ResourceId") == "DB-001"
            assert dim_map.get("ResourceType") == "DB"

    def test_service_health_unit_is_none(self) -> None:
        """ServiceHealth is a dimensionless score — Unit must be 'None'."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        sh = next(m for m in kwargs["MetricData"] if m["MetricName"] == "ServiceHealth")
        assert sh["Unit"] == "None"

    def test_cpu_utilization_unit_is_percent(self) -> None:
        mock_cw = MagicMock()
        resource = _make_resource(cpu=42.5)

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        cpu = next(m for m in kwargs["MetricData"] if m["MetricName"] == "CPUUtilization")
        assert cpu["Unit"] == "Percent"
        assert cpu["Value"] == 42.5

    def test_network_latency_unit_is_milliseconds(self) -> None:
        mock_cw = MagicMock()
        resource = _make_resource(latency=980.0)

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        nl = next(m for m in kwargs["MetricData"] if m["MetricName"] == "NetworkLatency")
        assert nl["Unit"] == "Milliseconds"
        assert nl["Value"] == 980.0

    def test_timestamp_is_present_on_all_data_points(self) -> None:
        """Every data point must include a Timestamp for CloudWatch accuracy."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        for dp in kwargs["MetricData"]:
            assert "Timestamp" in dp, f"Missing Timestamp in {dp['MetricName']}"

    def test_service_health_value_in_valid_range_healthy(self) -> None:
        """ServiceHealth for a healthy resource must be in [0.0, 100.0]."""
        mock_cw = MagicMock()
        resource = _make_resource()

        self.h._publish_metrics(resource, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        sh = next(m for m in kwargs["MetricData"] if m["MetricName"] == "ServiceHealth")
        assert 0.0 <= sh["Value"] <= 100.0

    def test_service_health_value_in_valid_range_failure(self) -> None:
        """ServiceHealth for a failing resource must still be in [0.0, 100.0]."""
        mock_cw = MagicMock()
        resource_fail = _make_resource(
            cpu=92.0, memory=60.0, storage=20.0, latency=50.0, state="FAILURE_DETECTED"
        )

        self.h._publish_metrics(resource_fail, mock_cw, "CloudPulse")

        kwargs = mock_cw.put_metric_data.call_args[1]
        sh = next(m for m in kwargs["MetricData"] if m["MetricName"] == "ServiceHealth")
        assert 0.0 <= sh["Value"] <= 100.0


# ── Metric alignment test ──────────────────────────────────────────────────────


class TestMetricAlignment:
    """
    Critical regression guard: verify that the simulator and MonitoringService
    publish the exact same set of metric names.

    Previously the simulator published 4 metrics while MonitoringService
    published 5 (missing ServiceHealth). This test catches that regression.
    """

    def test_simulator_and_monitoring_service_publish_same_metric_names(self) -> None:
        """Both publishing paths must produce identical CloudWatch metric name sets."""
        from app.models.resource import (
            HealthStatus,
            ResourceState,
            ResourceType,
            SimulatedResource,
        )
        from app.services.monitoring_service import MonitoringService

        resource = SimulatedResource(
            resource_id="VM-001",
            resource_type=ResourceType.VM,
            cpu_utilization=25.0,
            memory_utilization=30.0,
            storage_utilization=20.0,
            network_latency_ms=15.0,
            current_state=ResourceState.HEALTHY,
            health_status=HealthStatus.HEALTHY,
        )

        # Get metric names from MonitoringService
        mock_cw_ms = MagicMock()
        svc = MonitoringService(cloudwatch_client=mock_cw_ms)
        with patch("app.services.monitoring_service.get_settings") as ms:
            ms.return_value.cloudwatch_namespace = "CloudPulse"
            svc.publish_resource_metrics(resource)

        ms_names = {
            m["MetricName"]
            for m in mock_cw_ms.put_metric_data.call_args[1]["MetricData"]
        }

        # Get metric names from simulator _publish_metrics
        sim_module = _load_simulator_handler()
        mock_cw_sim = MagicMock()
        sim_module._publish_metrics(resource, mock_cw_sim, "CloudPulse")
        sim_names = {
            m["MetricName"]
            for m in mock_cw_sim.put_metric_data.call_args[1]["MetricData"]
        }

        assert ms_names == sim_names, (
            f"Metric name mismatch between simulator and MonitoringService!\n"
            f"  Simulator publishes:         {sorted(sim_names)}\n"
            f"  MonitoringService publishes: {sorted(ms_names)}\n"
            f"  Missing from simulator:      {ms_names - sim_names}\n"
            f"  Extra in simulator:          {sim_names - ms_names}"
        )


# ── Recovery skip guard tests ─────────────────────────────────────────────────


class TestHandlerRecoverySkip:
    """
    The simulator handler must skip resources in RECOVERY_INITIATED or
    RECOVERY_IN_PROGRESS state to prevent heartbeat jitter from corrupting
    metrics mid-recovery.

    Without this guard, a random walk could push metrics back below alarm
    thresholds while a recovery is in flight, causing ALARM → OK transition
    and disrupting the demo.
    """

    def _make_handler_module_with_repo(self, resource, mock_cw):
        """Load handler module with a mock repo returning the given resource."""
        spec = importlib.util.spec_from_file_location(
            f"_sim_skip_{resource.resource_id}", _HANDLER_PATH
        )
        assert spec and spec.loader

        from app.models.resource import (
            CPU_FAILURE_THRESHOLD,
            CPU_WARNING_THRESHOLD,
            MEMORY_FAILURE_THRESHOLD,
            MEMORY_WARNING_THRESHOLD,
            NETWORK_LATENCY_FAILURE_MS,
            NETWORK_LATENCY_WARNING_MS,
            STORAGE_FAILURE_THRESHOLD,
            STORAGE_WARNING_THRESHOLD,
            HealthStatus,
            ResourceState,
            SimulatedResource,
        )
        from app.services.monitoring_service import compute_service_health

        stub_res = MagicMock()
        stub_res.CPU_FAILURE_THRESHOLD = CPU_FAILURE_THRESHOLD
        stub_res.CPU_WARNING_THRESHOLD = CPU_WARNING_THRESHOLD
        stub_res.MEMORY_FAILURE_THRESHOLD = MEMORY_FAILURE_THRESHOLD
        stub_res.MEMORY_WARNING_THRESHOLD = MEMORY_WARNING_THRESHOLD
        stub_res.STORAGE_FAILURE_THRESHOLD = STORAGE_FAILURE_THRESHOLD
        stub_res.STORAGE_WARNING_THRESHOLD = STORAGE_WARNING_THRESHOLD
        stub_res.NETWORK_LATENCY_FAILURE_MS = NETWORK_LATENCY_FAILURE_MS
        stub_res.NETWORK_LATENCY_WARNING_MS = NETWORK_LATENCY_WARNING_MS
        stub_res.HealthStatus = HealthStatus
        stub_res.ResourceState = ResourceState
        stub_res.Resource = SimulatedResource

        monitoring_stub = MagicMock()
        monitoring_stub.compute_service_health = compute_service_health

        mock_repo = MagicMock()
        mock_repo.list.return_value = [resource]
        mock_repo.get.return_value = resource

        repo_stub = MagicMock()
        repo_stub.ResourceRepository.return_value = mock_repo

        config_stub = MagicMock()
        config_stub.get_settings.return_value = MagicMock(
            log_level="DEBUG",
            aws_region="us-east-1",
            cloudwatch_namespace="CloudPulse",
        )

        with patch.dict(
            "sys.modules",
            {
                "app.config": config_stub,
                "app.logging_config": MagicMock(),
                "app.models.resource": stub_res,
                "app.repositories.resource_repository": repo_stub,
                "app.services.monitoring_service": monitoring_stub,
            },
        ):
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module, mock_cw

    def test_recovery_initiated_resource_is_skipped(self) -> None:
        """Resources in RECOVERY_INITIATED must not have metrics re-published."""
        from app.models.resource import ResourceState

        resource = _make_resource(resource_id="VM-001", state="RECOVERY_INITIATED")
        mock_cw = MagicMock()

        module, _ = self._make_handler_module_with_repo(resource, mock_cw)

        with patch("boto3.client", return_value=mock_cw):
            result = module.handler({}, MagicMock())

        mock_cw.put_metric_data.assert_not_called()
        assert result["statusCode"] == 200

    def test_recovery_in_progress_resource_is_skipped(self) -> None:
        """Resources in RECOVERY_IN_PROGRESS must not have metrics published."""
        from app.models.resource import ResourceState

        resource = _make_resource(resource_id="API-001", state="RECOVERY_IN_PROGRESS")
        mock_cw = MagicMock()

        module, _ = self._make_handler_module_with_repo(resource, mock_cw)

        with patch("boto3.client", return_value=mock_cw):
            result = module.handler({}, MagicMock())

        mock_cw.put_metric_data.assert_not_called()
        assert result["statusCode"] == 200

    def test_empty_resource_list_returns_early(self) -> None:
        """Handler returns gracefully when no resources exist in DynamoDB."""
        spec = importlib.util.spec_from_file_location("_sim_empty_test", _HANDLER_PATH)
        assert spec and spec.loader

        from app.models.resource import (
            CPU_FAILURE_THRESHOLD,
            CPU_WARNING_THRESHOLD,
            MEMORY_FAILURE_THRESHOLD,
            MEMORY_WARNING_THRESHOLD,
            NETWORK_LATENCY_FAILURE_MS,
            NETWORK_LATENCY_WARNING_MS,
            STORAGE_FAILURE_THRESHOLD,
            STORAGE_WARNING_THRESHOLD,
            HealthStatus,
            ResourceState,
            SimulatedResource,
        )
        from app.services.monitoring_service import compute_service_health

        stub_res = MagicMock()
        stub_res.CPU_FAILURE_THRESHOLD = CPU_FAILURE_THRESHOLD
        stub_res.CPU_WARNING_THRESHOLD = CPU_WARNING_THRESHOLD
        stub_res.MEMORY_FAILURE_THRESHOLD = MEMORY_FAILURE_THRESHOLD
        stub_res.MEMORY_WARNING_THRESHOLD = MEMORY_WARNING_THRESHOLD
        stub_res.STORAGE_FAILURE_THRESHOLD = STORAGE_FAILURE_THRESHOLD
        stub_res.STORAGE_WARNING_THRESHOLD = STORAGE_WARNING_THRESHOLD
        stub_res.NETWORK_LATENCY_FAILURE_MS = NETWORK_LATENCY_FAILURE_MS
        stub_res.NETWORK_LATENCY_WARNING_MS = NETWORK_LATENCY_WARNING_MS
        stub_res.HealthStatus = HealthStatus
        stub_res.ResourceState = ResourceState
        stub_res.Resource = SimulatedResource

        monitoring_stub = MagicMock()
        monitoring_stub.compute_service_health = compute_service_health

        mock_repo = MagicMock()
        mock_repo.list.return_value = []

        repo_stub = MagicMock()
        repo_stub.ResourceRepository.return_value = mock_repo

        config_stub = MagicMock()
        config_stub.get_settings.return_value = MagicMock(
            log_level="DEBUG",
            aws_region="us-east-1",
            cloudwatch_namespace="CloudPulse",
        )

        with patch.dict(
            "sys.modules",
            {
                "app.config": config_stub,
                "app.logging_config": MagicMock(),
                "app.models.resource": stub_res,
                "app.repositories.resource_repository": repo_stub,
                "app.services.monitoring_service": monitoring_stub,
            },
        ):
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]

        mock_cw = MagicMock()
        with patch("boto3.client", return_value=mock_cw):
            result = module.handler({}, MagicMock())

        assert result["statusCode"] == 200
        assert "No resources" in result["body"]
