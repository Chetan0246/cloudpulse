"""
pytest configuration and shared fixtures for CloudPulse backend unit tests.

All AWS calls are mocked using moto — no real AWS account is needed
to run these tests.
"""
import os

import boto3
import pytest
from moto import mock_aws

# ── Force test environment before any app imports ──────────────────────────────
os.environ["DYNAMODB_RESOURCES_TABLE"] = "test-resources"
os.environ["DYNAMODB_INCIDENTS_TABLE"] = "test-incidents"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS credentials for moto."""
    # Already set in module-level os.environ above


@pytest.fixture(scope="function")
def dynamodb_resources_table(aws_credentials):
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
def dynamodb_incidents_table(aws_credentials):
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
def seed_resource():
    """Return a sample healthy VM-001 resource."""
    from datetime import datetime, timezone
    from app.models.resource import HealthStatus, Resource, ResourceState, ResourceType

    return Resource(
        resource_id="VM-001",
        resource_type=ResourceType.VM,
        current_state=ResourceState.HEALTHY,
        cpu_utilization=25.0,
        memory_utilization=30.0,
        storage_utilization=20.0,
        network_latency_ms=15.0,
        health_status=HealthStatus.HEALTHY,
        last_heartbeat=datetime.now(timezone.utc),
    )
