"""Unit tests for AWS client factory."""

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


def test_aws_clients_cached():
    c1 = get_dynamodb_client()
    c2 = get_dynamodb_client()
    assert c1 is c2

    r1 = get_dynamodb_resource()
    r2 = get_dynamodb_resource()
    assert r1 is r2

    cw1 = get_cloudwatch_client()
    cw2 = get_cloudwatch_client()
    assert cw1 is cw2

    eb1 = get_eventbridge_client()
    eb2 = get_eventbridge_client()
    assert eb1 is eb2

    sns1 = get_sns_client()
    sns2 = get_sns_client()
    assert sns1 is sns2


def test_reset_client_caches():
    c1 = get_dynamodb_client()
    reset_client_caches()
    c2 = get_dynamodb_client()
    assert c1 is not c2


def test_get_tables_helper(mock_all_tables):
    res_table = get_resources_table()
    assert res_table.name == "test-resources"

    inc_table = get_incidents_table()
    assert inc_table.name == "test-incidents"

    met_table = get_metrics_table()
    assert met_table.name == "test-metrics"
