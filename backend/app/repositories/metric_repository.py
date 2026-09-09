"""
DynamoDB repository for reliability metrics.

Translates between domain models (ReliabilityMetric) and DynamoDB items.
Key schema:
- PK: resource_id (String)
- SK: window_key  (String: e.g. DAILY#2026-09-08, CUMULATIVE#ALL)
"""

import logging
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.aws.clients import get_metrics_table
from app.exceptions import DatabaseError, MetricNotFoundError
from app.models.reliability_metric import MetricWindowType, ReliabilityMetric

logger = logging.getLogger(__name__)


class MetricRepository:
    """All DynamoDB operations for the reliability metrics table."""

    def __init__(self, table: Any | None = None) -> None:
        self._table = table

    @property
    def table(self) -> Any:
        if self._table is None:
            self._table = get_metrics_table()
        return self._table

    def get(self, resource_id: str, window_key: str) -> ReliabilityMetric:
        """
        Fetch a single reliability metric snapshot by resource_id and window_key.

        Raises:
            MetricNotFoundError: If the metric record does not exist.
            DatabaseError: If DynamoDB communication fails.
        """
        rid = resource_id.strip().upper()
        try:
            response = self.table.get_item(
                Key={"resource_id": rid, "window_key": window_key.strip()},
                ConsistentRead=True,
            )
        except ClientError as e:
            logger.error(
                "DynamoDB get_item error for metric '%s' / '%s': %s",
                rid,
                window_key,
                e,
            )
            raise DatabaseError(f"Failed to get metric for '{rid}' / '{window_key}': {e}") from e

        item = response.get("Item")
        if not item:
            raise MetricNotFoundError(resource_id=rid, window_key=window_key)
        return ReliabilityMetric.from_dynamodb_item(item)

    def list(
        self,
        resource_id: str | None = None,
        window_type: MetricWindowType | None = None,
        limit: int = 50,
    ) -> list[ReliabilityMetric]:
        """
        List reliability metrics with optional filters.

        If resource_id is specified, queries the partition.
        Otherwise, scans the table.
        """
        try:
            if resource_id:
                rid = resource_id.strip().upper()
                key_condition: Any = (
                    Key("resource_id").eq(rid) & Key("window_key").begins_with(window_type.value)
                    if window_type
                    else Key("resource_id").eq(rid)
                )

                response = self.table.query(
                    KeyConditionExpression=key_condition,
                    ScanIndexForward=False,
                    Limit=limit,
                )
                raw_items = response.get("Items", [])
            else:
                response = self.table.scan()
                raw_items = response.get("Items", [])
                if window_type:
                    raw_items = [i for i in raw_items if i.get("window_type") == window_type.value]
                raw_items.sort(key=lambda x: x.get("computed_at", ""), reverse=True)
                raw_items = raw_items[:limit]

            return [ReliabilityMetric.from_dynamodb_item(item) for item in raw_items]
        except ClientError as e:
            logger.error("DynamoDB error listing metrics: %s", e)
            raise DatabaseError(f"Failed to list metrics: {e}") from e

    def get_latest(
        self,
        resource_id: str,
        window_type: MetricWindowType = MetricWindowType.DAILY,
    ) -> ReliabilityMetric | None:
        """
        Retrieve the latest metric snapshot for a resource and window type.

        Uses descending sort on window_key.
        """
        rid = resource_id.strip().upper()
        try:
            response = self.table.query(
                KeyConditionExpression=Key("resource_id").eq(rid)
                & Key("window_key").begins_with(window_type.value),
                ScanIndexForward=False,
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                return None
            return ReliabilityMetric.from_dynamodb_item(items[0])
        except ClientError as e:
            logger.error("DynamoDB query error in get_latest metric: %s", e)
            raise DatabaseError(f"Failed to query latest metric: {e}") from e

    def put(self, metric: ReliabilityMetric) -> None:
        """Upsert a metric snapshot."""
        try:
            self.table.put_item(Item=metric.to_dynamodb_item())
            logger.info(
                "Metric saved",
                extra={
                    "resource_id": metric.resource_id,
                    "window_key": metric.window_key,
                },
            )
        except ClientError as e:
            logger.error("DynamoDB put_item error for metric: %s", e)
            raise DatabaseError(f"Failed to save metric for '{metric.resource_id}': {e}") from e

    def delete(self, resource_id: str, window_key: str) -> None:
        """Delete a metric snapshot."""
        try:
            self.table.delete_item(
                Key={"resource_id": resource_id.strip().upper(), "window_key": window_key.strip()}
            )
        except ClientError as e:
            logger.error("DynamoDB delete_item error for metric: %s", e)
            raise DatabaseError(f"Failed to delete metric: {e}") from e
