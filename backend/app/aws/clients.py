"""
AWS client and resource factory.

Provides cached, lazily-initialized boto3 clients and resources for:
- DynamoDB (ServiceResource and Client)
- CloudWatch
- EventBridge
- SNS

All client initializations read settings dynamically or allow overriding
for testing (e.g. endpoint_url for local DynamoDB or moto mocks).
"""

from functools import lru_cache
from typing import Any

import boto3

from app.config import get_settings


@lru_cache
def get_dynamodb_resource(
    region_name: str | None = None,
    endpoint_url: str | None = None,
) -> Any:
    """Return a cached boto3 DynamoDB ServiceResource."""
    settings = get_settings()
    region = region_name or settings.aws_region
    endpoint = endpoint_url or settings.dynamodb_endpoint_url
    return boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint)


@lru_cache
def get_dynamodb_client(
    region_name: str | None = None,
    endpoint_url: str | None = None,
) -> Any:
    """Return a cached boto3 DynamoDB Client."""
    settings = get_settings()
    region = region_name or settings.aws_region
    endpoint = endpoint_url or settings.dynamodb_endpoint_url
    return boto3.client("dynamodb", region_name=region, endpoint_url=endpoint)


@lru_cache
def get_cloudwatch_client(region_name: str | None = None) -> Any:
    """Return a cached boto3 CloudWatch Client."""
    settings = get_settings()
    region = region_name or settings.aws_region
    return boto3.client("cloudwatch", region_name=region)


@lru_cache
def get_eventbridge_client(region_name: str | None = None) -> Any:
    """Return a cached boto3 EventBridge Client."""
    settings = get_settings()
    region = region_name or settings.aws_region
    return boto3.client("events", region_name=region)


@lru_cache
def get_sns_client(region_name: str | None = None) -> Any:
    """Return a cached boto3 SNS Client."""
    settings = get_settings()
    region = region_name or settings.aws_region
    return boto3.client("sns", region_name=region)


def get_resources_table() -> Any:
    """Return the DynamoDB Table resource for resources."""
    settings = get_settings()
    dynamodb = get_dynamodb_resource(settings.aws_region, settings.dynamodb_endpoint_url)
    return dynamodb.Table(settings.dynamodb_resources_table)


def get_incidents_table() -> Any:
    """Return the DynamoDB Table resource for incidents."""
    settings = get_settings()
    dynamodb = get_dynamodb_resource(settings.aws_region, settings.dynamodb_endpoint_url)
    return dynamodb.Table(settings.dynamodb_incidents_table)


def get_metrics_table() -> Any:
    """Return the DynamoDB Table resource for reliability metrics."""
    settings = get_settings()
    dynamodb = get_dynamodb_resource(settings.aws_region, settings.dynamodb_endpoint_url)
    return dynamodb.Table(settings.dynamodb_metrics_table)


def reset_client_caches() -> None:
    """Clear lru_caches for boto3 clients. Useful between unit tests."""
    get_dynamodb_resource.cache_clear()
    get_dynamodb_client.cache_clear()
    get_cloudwatch_client.cache_clear()
    get_eventbridge_client.cache_clear()
    get_sns_client.cache_clear()
