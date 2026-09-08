"""
/resources router.

GET  /resources             → list all virtual resources (summaries)
GET  /resources/{id}        → get full resource detail
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.exceptions import ResourceNotFoundError
from app.models.resource import Resource, ResourceSummary
from app.repositories.resource_repository import ResourceRepository

router = APIRouter(prefix="/resources", tags=["resources"])
logger = logging.getLogger(__name__)


def get_resource_repo() -> ResourceRepository:
    return ResourceRepository()


@router.get("/", response_model=list[ResourceSummary])
def list_resources(
    repo: ResourceRepository = Depends(get_resource_repo),
) -> list[ResourceSummary]:
    """Return all virtual resources as lightweight summaries."""
    return repo.list()


@router.get("/{resource_id}", response_model=Resource)
def get_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_repo),
) -> Resource:
    """Return full detail for a single virtual resource."""
    try:
        return repo.get(resource_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
