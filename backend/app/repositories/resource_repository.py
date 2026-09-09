"""
DynamoDB repository for virtual resources.

Translates between domain models (SimulatedResource) and DynamoDB items.
All methods use strongly consistent reads for state-critical operations.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from app.aws.clients import get_resources_table
from app.exceptions import DatabaseError, ResourceNotFoundError
from app.models.resource import ResourceState, SimulatedResource

logger = logging.getLogger(__name__)


class ResourceRepository:
    """All DynamoDB operations for the resources table."""

    def __init__(self, table: Any | None = None) -> None:
        self._table = table

    @property
    def table(self) -> Any:
        if self._table is None:
            self._table = get_resources_table()
        return self._table

    def get(self, resource_id: str) -> SimulatedResource:
        """
        Fetch a single resource by ID.

        Uses strongly consistent read.

        Raises:
            ResourceNotFoundError: If the resource does not exist.
            DatabaseError: If DynamoDB communication fails.
        """
        try:
            response = self.table.get_item(
                Key={"resource_id": resource_id.upper()},
                ConsistentRead=True,
            )
        except ClientError as e:
            logger.error("DynamoDB get_item error for resource '%s': %s", resource_id, e)
            raise DatabaseError(f"Failed to get resource '{resource_id}': {e}") from e

        item = response.get("Item")
        if not item:
            raise ResourceNotFoundError(resource_id)
        return SimulatedResource.from_dynamodb_item(item)

    def list(self) -> list[SimulatedResource]:
        """
        Return all resources.

        Uses a full table scan — acceptable because the table has bounded
        size (≤20 virtual resources).
        """
        try:
            response = self.table.scan()
            items = response.get("Items", [])
            return [SimulatedResource.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error("DynamoDB scan error on resources table: %s", e)
            raise DatabaseError(f"Failed to list resources: {e}") from e

    def put(self, resource: SimulatedResource) -> None:
        """
        Upsert a resource (create or full overwrite).

        Updates the updated_at timestamp automatically.
        """
        updated_resource = resource.model_copy(update={"updated_at": datetime.now(UTC)})
        try:
            self.table.put_item(Item=updated_resource.to_dynamodb_item())
            logger.info(
                "Resource upserted",
                extra={
                    "resource_id": updated_resource.resource_id,
                    "state": updated_resource.current_state.value,
                },
            )
        except ClientError as e:
            logger.error(
                "DynamoDB put_item error for resource '%s': %s",
                resource.resource_id,
                e,
            )
            raise DatabaseError(f"Failed to put resource '{resource.resource_id}': {e}") from e

    def update_state(
        self,
        resource_id: str,
        new_state: ResourceState,
        condition_state: ResourceState | None = None,
    ) -> SimulatedResource:
        """
        Conditionally update resource state in DynamoDB.

        If condition_state is provided, the update only succeeds if the
        current state matches — providing idempotency and preventing
        duplicate recovery actions.

        Returns:
            The updated SimulatedResource.

        Raises:
            ResourceNotFoundError: If the resource does not exist.
            DatabaseError: If DynamoDB communication fails.
        """
        update_kwargs: dict[str, Any] = {
            "Key": {"resource_id": resource_id.upper()},
            "UpdateExpression": "SET current_state = :s, updated_at = :u",
            "ExpressionAttributeValues": {
                ":s": new_state.value,
                ":u": datetime.now(UTC).isoformat(),
            },
            "ReturnValues": "ALL_NEW",
        }
        if condition_state is not None:
            update_kwargs["ConditionExpression"] = "current_state = :cs"
            update_kwargs["ExpressionAttributeValues"][":cs"] = condition_state.value

        try:
            response = self.table.update_item(**update_kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "State update skipped — condition not met (idempotent)",
                    extra={"resource_id": resource_id, "expected": condition_state},
                )
                return self.get(resource_id)
            logger.error("DynamoDB update_item error for resource '%s': %s", resource_id, e)
            raise DatabaseError(f"Failed to update state for resource '{resource_id}': {e}") from e

        attributes = response.get("Attributes")
        if not attributes:
            return self.get(resource_id)
        return SimulatedResource.from_dynamodb_item(attributes)

    def delete(self, resource_id: str) -> None:
        """Delete a resource by ID."""
        try:
            self.table.delete_item(Key={"resource_id": resource_id.upper()})
        except ClientError as e:
            logger.error("DynamoDB delete_item error for resource '%s': %s", resource_id, e)
            raise DatabaseError(f"Failed to delete resource '{resource_id}': {e}") from e
