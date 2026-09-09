"""
AWS client factory module.
"""

from app.aws.clients import (
    get_cloudwatch_client,
    get_dynamodb_client,
    get_dynamodb_resource,
    get_eventbridge_client,
    get_incidents_table,
    get_metrics_table,
    get_resources_table,
    get_sns_client,
    reset_client_caches,
)

__all__ = [
    "get_dynamodb_resource",
    "get_dynamodb_client",
    "get_cloudwatch_client",
    "get_eventbridge_client",
    "get_sns_client",
    "get_resources_table",
    "get_incidents_table",
    "get_metrics_table",
    "reset_client_caches",
]
