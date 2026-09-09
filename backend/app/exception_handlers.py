"""
Global FastAPI exception handlers.

Translates domain exceptions into standardized JSON HTTP responses.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.exceptions import (
    CloudPulseError,
    DatabaseError,
    IncidentNotFoundError,
    InvalidStateTransitionError,
    MetricNotFoundError,
    ResourceNotFoundError,
    SimulationError,
)

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    """Standardized error response body."""

    detail: str
    error_code: str


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain and framework exception handlers onto the FastAPI application."""

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        logger.warning("Resource not found: %s", exc.resource_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(IncidentNotFoundError)
    async def incident_not_found_handler(
        request: Request, exc: IncidentNotFoundError
    ) -> JSONResponse:
        logger.warning("Incident not found: %s", exc.incident_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(MetricNotFoundError)
    async def metric_not_found_handler(request: Request, exc: MetricNotFoundError) -> JSONResponse:
        logger.warning("Metric not found for: %s", exc.resource_id)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_transition_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        logger.warning(
            "Invalid state transition attempted: %s -> %s",
            exc.from_state,
            exc.to_state,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(SimulationError)
    async def simulation_error_handler(request: Request, exc: SimulationError) -> JSONResponse:
        logger.warning("Simulation error: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
        logger.error("Database error: %s", exc.message, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(CloudPulseError)
    async def cloudpulse_error_handler(request: Request, exc: CloudPulseError) -> JSONResponse:
        logger.error("Application error: %s", exc.message, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message, "error_code": exc.error_code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Request validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": str(exc),
                "error_code": "VALIDATION_ERROR",
                "errors": exc.errors(),
            },
        )
