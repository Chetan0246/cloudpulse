"""
Layer 4: AWS Integration Tests
Tests interactions with AWS services (CloudWatch, DynamoDB, SNS, EventBridge) using moto.
"""

import boto3
from botocore.exceptions import ClientError
import pytest

from app.aws.clients import (
    get_cloudwatch_client,
    get_dynamodb_client,
    get_dynamodb_resource,
    get_eventbridge_client,
    get_sns_client,
    reset_client_caches,
)


class TestAwsIntegrationLayer:
    """AWS SDK integration tests with moto."""

    def test_cloudwatch_put_metric_data_integration(self, mock_aws_env: dict):
        """CloudWatch client puts custom metrics with namespace and dimensions."""
        cw = get_cloudwatch_client()
        response = cw.put_metric_data(
            Namespace="CloudPulse",
            MetricData=[
                {
                    "MetricName": "CPUUtilization",
                    "Dimensions": [
                        {"Name": "ResourceId", "Value": "VM-001"},
                        {"Name": "ResourceType", "Value": "VM"},
                    ],
                    "Value": 94.2,
                    "Unit": "Percent",
                }
            ],
        )
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_dynamodb_conditional_expression_integration(self, mock_aws_env: dict):
        """DynamoDB enforces conditional writes correctly using boto3 Table."""
        dynamo = get_dynamodb_resource()
        table = dynamo.Table("cloudpulse-resources-test")

        # Put initial item
        table.put_item(
            Item={"resource_id": "VM-TEST", "current_state": "HEALTHY"}
        )

        # Successful conditional update
        table.update_item(
            Key={"resource_id": "VM-TEST"},
            UpdateExpression="SET current_state = :new_state",
            ConditionExpression="current_state = :expected",
            ExpressionAttributeValues={
                ":new_state": "WARNING",
                ":expected": "HEALTHY",
            },
        )

        item = table.get_item(Key={"resource_id": "VM-TEST"}, ConsistentRead=True)["Item"]
        assert item["current_state"] == "WARNING"

        # Failing conditional update raises ConditionalCheckFailedException
        with pytest.raises(ClientError) as exc_info:
            table.update_item(
                Key={"resource_id": "VM-TEST"},
                UpdateExpression="SET current_state = :new_state",
                ConditionExpression="current_state = :expected",
                ExpressionAttributeValues={
                    ":new_state": "RECOVERED",
                    ":expected": "HEALTHY",  # It is now WARNING, so this must fail
                },
            )
        assert exc_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"

    def test_sns_publish_integration(self, mock_aws_env: dict):
        """SNS client publishes messages to topic successfully."""
        sns = get_sns_client()
        topic_arn = mock_aws_env["topic_arn"]

        res = sns.publish(
            TopicArn=topic_arn,
            Subject="[CloudPulse] Test Alert",
            Message="Test notification payload",
        )
        assert "MessageId" in res
        assert res["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_eventbridge_put_events_integration(self, mock_aws_env: dict):
        """EventBridge client puts custom events to default bus."""
        eb = get_eventbridge_client()
        res = eb.put_events(
            Entries=[
                {
                    "Source": "cloudpulse.simulator",
                    "DetailType": "FailureInjected",
                    "Detail": '{"resourceId": "VM-001", "failureType": "HIGH_CPU"}',
                    "EventBusName": "default",
                }
            ]
        )
        assert res["FailedEntryCount"] == 0
        assert len(res["Entries"]) == 1

    def test_client_caches_and_reset(self):
        """AWS client factories memoize instances and reset properly."""
        c1 = get_cloudwatch_client()
        c2 = get_cloudwatch_client()
        assert c1 is c2

        reset_client_caches()
        c3 = get_cloudwatch_client()
        assert c3 is not c1
