"""
/incidents router.

GET  /incidents               → list incidents with optional filters
GET  /incidents/{incident_id} → get full detail for a single incident
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.models.incident import IncidentDetail, IncidentStatus, IncidentSummary
from app.models.resource import FailureType
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = logging.getLogger(__name__)

_UUID_V4_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def get_incident_service() -> IncidentService:
    """FastAPI dependency for IncidentService."""
    return IncidentService()


@router.get(
    "",
    response_model=list[IncidentSummary],
    summary="List incidents with optional filters",
)
@router.get(
    "/",
    response_model=list[IncidentSummary],
    include_in_schema=False,
)
def list_incidents(
    resource_id: str | None = Query(
        None,
        description="Filter by simulated resource ID, e.g. 'VM-001'",
    ),
    status_filter: IncidentStatus | None = Query(
        None,
        alias="status",
        description="Filter by incident lifecycle status (OPEN, RECOVERING, RESOLVED, ESCALATED)",
    ),
    failure_type: FailureType | None = Query(
        None,
        description="Filter by failure type",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of incidents to return",
    ),
    service: IncidentService = Depends(get_incident_service),
) -> list[IncidentSummary]:
    """List incidents ordered newest first, with optional filtering."""
    return service.list_incidents(
        resource_id=resource_id,
        status=status_filter,
        failure_type=failure_type,
        limit=limit,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetail,
    summary="Get incident detail by ID",
)
def get_incident(
    incident_id: str = Path(
        ...,
        description="UUID v4 incident identifier",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    ),
    service: IncidentService = Depends(get_incident_service),
) -> IncidentDetail:
    """Return complete details for a single incident including embedded recovery actions."""
    clean_id = incident_id.strip()
    if not _UUID_V4_REGEX.match(clean_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid incident_id format (must be UUID v4): '{incident_id}'",
        )
    return service.get_incident(clean_id.lower())
