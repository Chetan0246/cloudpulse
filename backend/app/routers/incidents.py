"""
/incidents router.

GET  /incidents             → list incidents (filterable by resource_id, status)
GET  /incidents/{id}        → get full incident detail
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.exceptions import IncidentNotFoundError
from app.models.incident import Incident, IncidentStatus, IncidentSummary
from app.repositories.incident_repository import IncidentRepository

router = APIRouter(prefix="/incidents", tags=["incidents"])
logger = logging.getLogger(__name__)


def get_incident_repo() -> IncidentRepository:
    return IncidentRepository()


@router.get("/", response_model=list[IncidentSummary])
def list_incidents(
    resource_id: str | None = Query(None),
    status_filter: IncidentStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    repo: IncidentRepository = Depends(get_incident_repo),
) -> list[IncidentSummary]:
    """List incidents with optional filters."""
    return repo.list(resource_id=resource_id, status=status_filter, limit=limit)


@router.get("/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: str,
    repo: IncidentRepository = Depends(get_incident_repo),
) -> Incident:
    """Return full detail for a single incident."""
    try:
        return repo.get(incident_id)
    except IncidentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
