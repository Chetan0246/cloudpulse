"""
/health router — liveness and readiness checks.

GET  /health        → liveness (always returns 200 if Lambda is running)
GET  /health/ready  → readiness (checks DynamoDB connectivity)
"""
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    service: str = "cloudpulse-api"


@router.get("/", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Always returns 200. Used by monitoring to confirm Lambda is alive."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def readiness() -> HealthResponse:
    """Check DynamoDB connectivity. Returns 503 if unhealthy."""
    try:
        from app.repositories.resource_repository import ResourceRepository  # noqa: PLC0415

        ResourceRepository().list()
        return HealthResponse(status="ready")
    except Exception as e:
        logger.exception("Readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DynamoDB unreachable",
        ) from e
