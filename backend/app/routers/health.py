"""
/health router — liveness and readiness probes.

GET  /health        → liveness probe (200 OK)
GET  /health/ready  → readiness probe (checks DynamoDB connectivity)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.repositories.resource_repository import ResourceRepository

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check status response."""

    status: str
    service: str = "cloudpulse-api"


def get_resource_repo() -> ResourceRepository:
    return ResourceRepository()


@router.get("", response_model=HealthResponse, summary="Liveness Probe")
@router.get("/", response_model=HealthResponse, include_in_schema=False)
def liveness() -> HealthResponse:
    """Always returns 200 OK. Used by monitoring to confirm the API is running."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, summary="Readiness Probe")
def readiness(
    repo: ResourceRepository = Depends(get_resource_repo),
) -> HealthResponse:
    """
    Check DynamoDB connectivity by listing resources.

    Returns:
        200 OK if DynamoDB is reachable.

    Raises:
        HTTPException 503 if DynamoDB is unreachable.
    """
    try:
        repo.list()
        return HealthResponse(status="ready")
    except Exception as e:
        logger.error("Readiness check failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DynamoDB unreachable",
        ) from e
