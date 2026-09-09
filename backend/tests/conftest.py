"""
pytest configuration and shared fixtures for CloudPulse backend unit tests.

All AWS calls are mocked using moto — no real AWS account is needed.
"""

import os
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# ── Force test environment before any app imports ──────────────────────────────
os.environ["DYNAMODB_RESOURCES_TABLE"] = "test-resources"
os.environ["DYNAMODB_INCIDENTS_TABLE"] = "test-incidents"
os.environ["DYNAMODB_METRICS_TABLE"] = "test-metrics"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"


@pytest.fixture(autouse=True)
def reset_caches() -> Generator[None, None, None]:
    """Clear lru caches and settings between tests."""
    from app.aws.clients import reset_client_caches
    from app.config import get_settings

    get_settings.cache_clear()
    reset_client_caches()
    yield
    get_settings.cache_clear()
    reset_client_caches()


@pytest.fixture(scope="function")
def aws_credentials() -> None:
    """Mocked AWS credentials for moto."""


@pytest.fixture(scope="function")
def dynamodb_resources_table(aws_credentials: None) -> Generator[Any, None, None]:
    """Create a mocked DynamoDB resources table for each test."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-resources",
            KeySchema=[{"AttributeName": "resource_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "resource_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture(scope="function")
def dynamodb_incidents_table(aws_credentials: None) -> Generator[Any, None, None]:
    """Create a mocked DynamoDB incidents table for each test."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-incidents",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "incident_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture(scope="function")
def dynamodb_metrics_table(aws_credentials: None) -> Generator[Any, None, None]:
    """Create a mocked DynamoDB metrics table for each test."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-metrics",
            KeySchema=[
                {"AttributeName": "resource_id", "KeyType": "HASH"},
                {"AttributeName": "window_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "resource_id", "AttributeType": "S"},
                {"AttributeName": "window_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield table


@pytest.fixture(scope="function")
def mock_all_tables(
    aws_credentials: None,
) -> Generator[dict[str, Any], None, None]:
    """Create all three mocked DynamoDB tables within a single mock_aws context."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        resources_tbl = dynamodb.create_table(
            TableName="test-resources",
            KeySchema=[{"AttributeName": "resource_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "resource_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        incidents_tbl = dynamodb.create_table(
            TableName="test-incidents",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "incident_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        metrics_tbl = dynamodb.create_table(
            TableName="test-metrics",
            KeySchema=[
                {"AttributeName": "resource_id", "KeyType": "HASH"},
                {"AttributeName": "window_key", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "resource_id", "AttributeType": "S"},
                {"AttributeName": "window_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        resources_tbl.wait_until_exists()
        incidents_tbl.wait_until_exists()
        metrics_tbl.wait_until_exists()

        yield {
            "resources": resources_tbl,
            "incidents": incidents_tbl,
            "metrics": metrics_tbl,
        }


@pytest.fixture(scope="function")
def client(mock_all_tables: dict[str, Any]) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with all DynamoDB tables mocked."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def seed_resource() -> Any:
    """Return a sample healthy VM-001 resource."""
    from app.models.resource import (
        HealthStatus,
        ResourceState,
        ResourceType,
        SimulatedResource,
    )

    return SimulatedResource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        cpu_utilization=25.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
        health_status=HealthStatus.HEALTHY,
        last_heartbeat=datetime.now(UTC),
    )
