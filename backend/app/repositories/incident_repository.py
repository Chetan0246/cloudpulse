"""
DynamoDB repository for incident records.
"""
import logging
from datetime import datetime, timezone

import boto3

from app.config import get_settings
from app.exceptions import IncidentNotFoundError
from app.models.incident import Incident, IncidentStatus, IncidentSummary

logger = logging.getLogger(__name__)


def _get_table():  # type: ignore[return]
    settings = get_settings()
    dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return dynamodb.Table(settings.dynamodb_incidents_table)


class IncidentRepository:
    """All DynamoDB operations for the incidents table."""

    def get(self, incident_id: str) -> Incident:
        table = _get_table()
        response = table.get_item(
            Key={"incident_id": incident_id},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            raise IncidentNotFoundError(incident_id)
        return Incident.model_validate(item)

    def list(
        self,
        resource_id: str | None = None,
        status: IncidentStatus | None = None,
        limit: int = 50,
    ) -> list[IncidentSummary]:
        """
        List incidents with optional filters.

        Full table scan is acceptable for academic scale.
        """
        table = _get_table()
        response = table.scan()
        items = response.get("Items", [])

        if resource_id:
            items = [i for i in items if i.get("resource_id") == resource_id]
        if status:
            items = [i for i in items if i.get("status") == status.value]

        items.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
        return [IncidentSummary.model_validate(i) for i in items[:limit]]

    def create(self, incident: Incident) -> Incident:
        """Persist a new incident. Raises if incident_id already exists."""
        table = _get_table()
        table.put_item(
            Item=incident.model_dump(mode="json", exclude_none=True),
            ConditionExpression="attribute_not_exists(incident_id)",
        )
        logger.info(
            "Incident created",
            extra={"incident_id": incident.incident_id, "resource_id": incident.resource_id},
        )
        return incident

    def update(self, incident: Incident) -> Incident:
        """Full overwrite of an existing incident record."""
        table = _get_table()
        table.put_item(Item=incident.model_dump(mode="json", exclude_none=True))
        return incident
