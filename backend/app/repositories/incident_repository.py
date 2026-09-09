"""
DynamoDB repository for incident records.

Translates between domain models (Incident) and DynamoDB items.
Supports querying by incident_id, and listing with filters.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError

from app.aws.clients import get_incidents_table
from app.exceptions import DatabaseError, IncidentNotFoundError
from app.models.incident import Incident, IncidentStatus
from app.models.resource import FailureType

logger = logging.getLogger(__name__)


class IncidentRepository:
    """All DynamoDB operations for the incidents table."""

    def __init__(self, table: Any | None = None) -> None:
        self._table = table

    @property
    def table(self) -> Any:
        if self._table is None:
            self._table = get_incidents_table()
        return self._table

    def get(self, incident_id: str) -> Incident:
        """
        Fetch a single incident by ID.

        Uses strongly consistent read.

        Raises:
            IncidentNotFoundError: If the incident does not exist.
            DatabaseError: If DynamoDB communication fails.
        """
        try:
            response = self.table.get_item(
                Key={"incident_id": incident_id.lower()},
                ConsistentRead=True,
            )
        except ClientError as e:
            logger.error("DynamoDB get_item error for incident '%s': %s", incident_id, e)
            raise DatabaseError(f"Failed to get incident '{incident_id}': {e}") from e

        item = response.get("Item")
        if not item:
            raise IncidentNotFoundError(incident_id)
        return Incident.from_dynamodb_item(item)

    def list(
        self,
        resource_id: str | None = None,
        status: IncidentStatus | None = None,
        failure_type: FailureType | None = None,
        limit: int = 50,
    ) -> list[Incident]:
        """
        List incidents with optional filters, sorted newest first.

        Currently uses a full table Scan + in-memory filtering.
        TODO (A-04): When resource_id is provided, Query the ResourceIndex GSI instead of Scan.
        For the academic dataset (< 200 incidents) the Scan cost is negligible.
        """
        try:
            response = self.table.scan()
            raw_items = response.get("Items", [])
        except ClientError as e:
            logger.error("DynamoDB scan error on incidents table: %s", e)
            raise DatabaseError(f"Failed to list incidents: {e}") from e

        items = [Incident.from_dynamodb_item(item) for item in raw_items]

        if resource_id:
            rid = resource_id.strip().upper()
            items = [i for i in items if i.resource_id == rid]
        if status:
            items = [i for i in items if i.status == status]
        if failure_type:
            items = [i for i in items if i.failure_type == failure_type]

        items.sort(key=lambda x: x.detected_at, reverse=True)
        return items[:limit]

    def create(self, incident: Incident) -> Incident:
        """
        Persist a new incident.

        Raises:
            DatabaseError: If an incident with the same ID already exists or write fails.
        """
        try:
            self.table.put_item(
                Item=incident.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(incident_id)",
            )
            logger.info(
                "Incident created",
                extra={
                    "incident_id": incident.incident_id,
                    "resource_id": incident.resource_id,
                },
            )
            return incident
        except ClientError as e:
            logger.error("DynamoDB put_item error for incident '%s': %s", incident.incident_id, e)
            raise DatabaseError(f"Failed to create incident '{incident.incident_id}': {e}") from e

    def update(self, incident: Incident) -> Incident:
        """
        Update an existing incident record with updated_at timestamp.

        Uses ConditionExpression to ensure the incident exists before overwriting.
        NOTE: This is still a full-item overwrite (put_item), not a partial update_item.
        For production, an optimistic-lock version counter would prevent concurrent write races.
        """
        updated = incident.model_copy(update={"updated_at": datetime.now(UTC)})
        try:
            self.table.put_item(
                Item=updated.to_dynamodb_item(),
                # A-10 FIX: Minimum guard — prevent blind writes to non-existent incidents.
                # Does not protect against concurrent overwrite races (would need a version counter).
                ConditionExpression="attribute_exists(incident_id)",
            )
            return updated
        except ClientError as e:
            logger.error(
                "DynamoDB put_item error on incident update '%s': %s", incident.incident_id, e
            )
            raise DatabaseError(f"Failed to update incident '{incident.incident_id}': {e}") from e

    def delete(self, incident_id: str) -> None:
        """Delete an incident by ID."""
        try:
            self.table.delete_item(Key={"incident_id": incident_id.lower()})
        except ClientError as e:
            logger.error("DynamoDB delete_item error for incident '%s': %s", incident_id, e)
            raise DatabaseError(f"Failed to delete incident '{incident_id}': {e}") from e
