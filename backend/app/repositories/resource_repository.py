"""
DynamoDB repository for virtual resources.

This module is the only place in the application that talks to DynamoDB
for the resources table. It translates between Pydantic models and
DynamoDB item dictionaries.

All methods use strongly consistent reads for state-critical operations.
"""
import logging
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import get_settings
from app.exceptions import ResourceNotFoundError
from app.models.resource import Resource, ResourceSummary, ResourceState

logger = logging.getLogger(__name__)


def _get_table():  # type: ignore[return]
    """Return the DynamoDB Table resource. Lazy-initialized."""
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return dynamodb.Table(settings.dynamodb_resources_table)


def _item_to_resource(item: dict) -> Resource:
    """Deserialize a DynamoDB item into a Resource model."""
    return Resource.model_validate(item)


def _resource_to_item(resource: Resource) -> dict:
    """Serialize a Resource model into a DynamoDB item dict."""
    data = resource.model_dump(mode="json")
    # DynamoDB does not store None values well; remove None fields
    return {k: v for k, v in data.items() if v is not None}


class ResourceRepository:
    """All DynamoDB operations for the resources table."""

    def get(self, resource_id: str) -> Resource:
        """
        Fetch a single resource by ID.

        Uses strongly consistent read to ensure we see the latest state.

        Raises:
            ResourceNotFoundError: If the resource does not exist.
        """
        table = _get_table()
        response = table.get_item(
            Key={"resource_id": resource_id.upper()},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            raise ResourceNotFoundError(resource_id)
        return _item_to_resource(item)

    def list(self) -> list[ResourceSummary]:
        """
        Return all resources as lightweight summaries.

        Uses a full table scan — acceptable since the table has at most
        a few dozen virtual resources.
        """
        table = _get_table()
        response = table.scan()
        items = response.get("Items", [])
        return [ResourceSummary.model_validate(item) for item in items]

    def put(self, resource: Resource) -> None:
        """
        Upsert a resource (create or full overwrite).

        Updates the updated_at timestamp automatically.
        """
        resource = resource.model_copy(
            update={"updated_at": datetime.now(timezone.utc)}
        )
        table = _get_table()
        table.put_item(Item=_resource_to_item(resource))
        logger.info(
            "Resource upserted",
            extra={"resource_id": resource.resource_id, "state": resource.current_state},
        )

    def update_state(
        self,
        resource_id: str,
        new_state: ResourceState,
        condition_state: ResourceState | None = None,
    ) -> Resource:
        """
        Conditionally update resource state in DynamoDB.

        If condition_state is provided, the update only succeeds if the
        current state matches — providing idempotency and preventing
        duplicate recovery actions.

        Returns:
            The updated Resource.

        Raises:
            ResourceNotFoundError: If the resource does not exist.
            ClientError: If the conditional check fails.
        """
        table = _get_table()
        update_kwargs: dict = {
            "Key": {"resource_id": resource_id.upper()},
            "UpdateExpression": "SET current_state = :s, updated_at = :u",
            "ExpressionAttributeValues": {
                ":s": new_state.value,
                ":u": datetime.now(timezone.utc).isoformat(),
            },
            "ReturnValues": "ALL_NEW",
        }
        if condition_state is not None:
            update_kwargs["ConditionExpression"] = "current_state = :cs"
            update_kwargs["ExpressionAttributeValues"][":cs"] = condition_state.value

        try:
            response = table.update_item(**update_kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "State update skipped — condition not met (idempotent)",
                    extra={"resource_id": resource_id, "expected": condition_state},
                )
                return self.get(resource_id)
            raise
        return _item_to_resource(response["Attributes"])
