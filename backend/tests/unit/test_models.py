"""Unit tests for domain models."""
import pytest
from app.models.resource import (
    HealthStatus, Resource, ResourceState, ResourceType, FailureType
)


def test_resource_health_status_healthy():
    r = Resource(resource_id="VM-001", resource_type=ResourceType.VM,
                 cpu_utilization=25.0, memory_utilization=30.0,
                 storage_utilization=20.0, network_latency_ms=15.0)
    assert r.compute_health_status() == HealthStatus.HEALTHY


def test_resource_health_status_degraded_on_high_cpu():
    r = Resource(resource_id="VM-001", resource_type=ResourceType.VM,
                 cpu_utilization=80.0, memory_utilization=30.0,
                 storage_utilization=20.0, network_latency_ms=15.0)
    assert r.compute_health_status() == HealthStatus.DEGRADED


def test_resource_health_status_critical_on_cpu_failure():
    r = Resource(resource_id="VM-001", resource_type=ResourceType.VM,
                 cpu_utilization=95.0, memory_utilization=30.0,
                 storage_utilization=20.0, network_latency_ms=15.0)
    assert r.compute_health_status() == HealthStatus.CRITICAL


def test_resource_health_status_critical_on_storage():
    r = Resource(resource_id="STORAGE-001", resource_type=ResourceType.STORAGE,
                 cpu_utilization=25.0, memory_utilization=30.0,
                 storage_utilization=95.0, network_latency_ms=15.0)
    assert r.compute_health_status() == HealthStatus.CRITICAL


def test_resource_id_uppercased():
    r = Resource(resource_id="vm-001", resource_type=ResourceType.VM)
    assert r.resource_id == "VM-001"


def test_resource_id_empty_raises():
    with pytest.raises(ValueError):
        Resource(resource_id="", resource_type=ResourceType.VM)
