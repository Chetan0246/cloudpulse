"""
/simulate router — manual failure injection for demo and testing.

POST /simulate/inject   → inject a simulated failure on a resource
POST /simulate/heal     → manually trigger recovery on a resource
POST /simulate/reset    → reset resource to HEALTHY (dev/demo use only)
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.exceptions import ResourceNotFoundError, SimulationError
from app.models.resource import FailureType, Resource
from app.repositories.resource_repository import ResourceRepository

router = APIRouter(prefix="/simulate", tags=["simulation"])
logger = logging.getLogger(__name__)


class InjectRequest(BaseModel):
    resource_id: str
    failure_type: FailureType


class SimulateResponse(BaseModel):
    message: str
    resource: Resource


def get_resource_repo() -> ResourceRepository:
    return ResourceRepository()


@router.post("/inject", response_model=SimulateResponse, status_code=status.HTTP_202_ACCEPTED)
def inject_failure(
    request: Annotated[InjectRequest, Body()],
    repo: ResourceRepository = Depends(get_resource_repo),
) -> SimulateResponse:
    """
    Inject a simulated failure on a virtual resource.

    This sets metric values to threshold-breaching levels and updates
    the resource state to FAILURE_DETECTED. The recovery pipeline then
    picks this up via EventBridge.
    """
    # Import here to avoid circular dependency; service layer will be wired in Phase 4
    from app.services.simulation_service import SimulationService  # noqa: PLC0415

    try:
        svc = SimulationService(repo)
        resource = svc.inject_failure(request.resource_id, request.failure_type)
        return SimulateResponse(
            message=f"Failure '{request.failure_type}' injected on '{request.resource_id}'",
            resource=resource,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SimulationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post("/reset/{resource_id}", response_model=SimulateResponse)
def reset_resource(
    resource_id: str,
    repo: ResourceRepository = Depends(get_resource_repo),
) -> SimulateResponse:
    """
    Reset a resource to HEALTHY state with nominal metrics.
    Intended for demo/development use only.
    """
    from app.services.simulation_service import SimulationService  # noqa: PLC0415

    try:
        svc = SimulationService(repo)
        resource = svc.reset_resource(resource_id)
        return SimulateResponse(message=f"Resource '{resource_id}' reset to HEALTHY", resource=resource)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
