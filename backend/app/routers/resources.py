"""
/resources router.

GET  /resources               → list all virtual resources (lightweight summaries)
GET  /resources/{resource_id} → get full detail for a single resource
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.models.resource import ResourceSummary, SimulatedResource
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["resources"])
logger = logging.getLogger(__name__)


def get_resource_service() -> ResourceService:
    """FastAPI dependency for ResourceService."""
    return ResourceService()


@router.get(
    "",
    response_model=list[ResourceSummary],
    summary="List all virtual resources",
)
@router.get(
    "/",
    response_model=list[ResourceSummary],
    include_in_schema=False,
)
def list_resources(
    service: ResourceService = Depends(get_resource_service),
) -> list[ResourceSummary]:
    """Return all simulated resources as lightweight summaries for dashboard display."""
    return service.list_resources()


@router.get(
    "/{resource_id}",
    response_model=SimulatedResource,
    summary="Get resource details by ID",
)
def get_resource(
    resource_id: str = Path(
        ...,
        description="Unique resource identifier, e.g. 'VM-001'",
        examples=["VM-001", "API-001", "DB-001", "STORAGE-001"],
    ),
    service: ResourceService = Depends(get_resource_service),
) -> SimulatedResource:
    """Return full state and live metrics for a single virtual resource."""
    normalized_id = resource_id.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{0,63}", normalized_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid resource_id format: '{resource_id}'",
        )
    return service.get_resource(normalized_id)
