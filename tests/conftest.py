"""
Root pytest configuration and shared fixtures for the CloudPulse test suite.
Provides comprehensive mocked AWS infrastructure using moto.
"""

import json
import os
import pathlib
import sys
from collections.abc import Generator
from typing import Any

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# Ensure project directories are on Python path
ROOT_DIR = pathlib.Path(__file__).parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
LAMBDA_RECOVERY_DIR = ROOT_DIR / "lambda" / "recovery"
LAMBDA_SIMULATOR_DIR = ROOT_DIR / "lambda" / "simulator"

for d in (BACKEND_DIR, LAMBDA_RECOVERY_DIR, LAMBDA_SIMULATOR_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

# Environment variables for testing
os.environ["DYNAMODB_RESOURCES_TABLE"] = "cloudpulse-resources-test"
os.environ["DYNAMODB_INCIDENTS_TABLE"] = "cloudpulse-incidents-test"
os.environ["DYNAMODB_METRICS_TABLE"] = "cloudpulse-metrics-test"
os.environ["CLOUDWATCH_NAMESPACE"] = "CloudPulse"
os.environ["EVENTBRIDGE_BUS_NAME"] = "default"
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:cloudpulse-notifications-test"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(autouse=True)
def reset_system_caches() -> Generator[None, None, None]:
    """Clear lru_caches and client singletons between all tests."""
    from app.aws.clients import reset_client_caches
    from app.config import get_settings

    get_settings.cache_clear()
    reset_client_caches()
    yield
    get_settings.cache_clear()
    reset_client_caches()


@pytest.fixture(scope="function")
def mock_aws_env(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, Any], None, None]:
    """
    Initialize complete mocked AWS environment:
    - DynamoDB tables (Resources, Incidents, Metrics)
    - CloudWatch client
    - SNS Topic
    - EventBridge bus
    """
    monkeypatch.setenv("DYNAMODB_RESOURCES_TABLE", "cloudpulse-resources-test")
    monkeypatch.setenv("DYNAMODB_INCIDENTS_TABLE", "cloudpulse-incidents-test")
    monkeypatch.setenv("DYNAMODB_METRICS_TABLE", "cloudpulse-metrics-test")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:cloudpulse-notifications-test")

    from app.aws.clients import reset_client_caches
    from app.config import get_settings

    get_settings.cache_clear()
    reset_client_caches()

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        sns = boto3.client("sns", region_name="us-east-1")

        # 1. Resources table
        res_table = dynamodb.create_table(
            TableName="cloudpulse-resources-test",
            KeySchema=[{"AttributeName": "resource_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "resource_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        res_table.wait_until_exists()

        # 2. Incidents table
        inc_table = dynamodb.create_table(
            TableName="cloudpulse-incidents-test",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "incident_id", "AttributeType": "S"},
                {"AttributeName": "resource_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "ResourceIndex",
                    "KeySchema": [{"AttributeName": "resource_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        inc_table.wait_until_exists()

        # 3. Metrics table
        met_table = dynamodb.create_table(
            TableName="cloudpulse-metrics-test",
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
        met_table.wait_until_exists()

        # 4. SNS Topic
        topic_res = sns.create_topic(Name="cloudpulse-notifications-test")
        topic_arn = topic_res["TopicArn"]
        os.environ["SNS_TOPIC_ARN"] = topic_arn

        yield {
            "dynamodb": dynamodb,
            "resources_table": res_table,
            "incidents_table": inc_table,
            "metrics_table": met_table,
            "sns": sns,
            "topic_arn": topic_arn,
        }


@pytest.fixture
def seed_fleet(mock_aws_env: dict[str, Any]) -> list[dict[str, Any]]:
    """Seed the 4 virtual resources into the mocked DynamoDB resources table."""
    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "seed_resources.json"
    with open(fixture_path, encoding="utf-8") as f:
        items = json.load(f)

    from app.models.resource import SimulatedResource
    from app.repositories.resource_repository import ResourceRepository

    repo = ResourceRepository()
    seeded = []
    for raw in items:
        resource = SimulatedResource.model_validate(raw)
        repo.put(resource)
        seeded.append(raw)
    return seeded


@pytest.fixture
def scenarios_matrix() -> list[dict[str, Any]]:
    """Load scenarios definition matrix for FS-01 to FS-05."""
    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "scenarios.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    return data["scenarios"]


@pytest.fixture
def client(mock_aws_env: dict[str, Any]) -> Generator[TestClient, None, None]:
    """FastAPI TestClient connected to mocked AWS infrastructure."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def event_factory():
    """Helper factory for generating CloudWatch and Simulator EventBridge events."""

    def _create_alarm_event(alarm_name: str, resource_id: str, state_value: str = "ALARM") -> dict[str, Any]:
        return {
            "version": "0",
            "id": "test-event-id",
            "source": "aws.cloudwatch",
            "account": "123456789012",
            "time": "2026-09-09T12:00:00Z",
            "region": "us-east-1",
            "detail-type": "CloudWatch Alarm State Change",
            "detail": {
                "alarmName": alarm_name,
                "state": {
                    "value": state_value,
                    "reason": f"Threshold crossed for {resource_id}",
                    "timestamp": "2026-09-09T12:00:00.000+0000",
                },
                "previousState": {
                    "value": "OK",
                    "timestamp": "2026-09-09T11:58:00.000+0000",
                },
                "configuration": {
                    "metrics": [
                        {
                            "metricStat": {
                                "metric": {
                                    "namespace": "CloudPulse",
                                    "name": "CPUUtilization",
                                    "dimensions": {"ResourceId": resource_id},
                                }
                            }
                        }
                    ]
                },
            },
        }

    def _create_inject_event(resource_id: str, failure_type: str) -> dict[str, Any]:
        return {
            "version": "0",
            "id": "test-inject-id",
            "source": "cloudpulse.simulator",
            "account": "123456789012",
            "time": "2026-09-09T12:00:00Z",
            "region": "us-east-1",
            "detail-type": "FailureInjected",
            "detail": {
                "resourceId": resource_id,
                "failureType": failure_type,
            },
        }

    return {
        "alarm": _create_alarm_event,
        "inject": _create_inject_event,
    }
