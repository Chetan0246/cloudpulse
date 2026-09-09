"""
/simulate router — failure simulation engine and recovery/reset API.

Endpoints:
- POST /simulate/failure      → inject a simulated failure scenario
- POST /simulate/reset/{id}   → manually recover/reset a simulated resource
- POST /simulate/reset        → manually recover/reset a simulated resource (via body)
- POST /simulate/recover      → alias for manual recovery
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.incident import Incident, IncidentSeverity
from app.models.resource import FailureType, SimulatedResource
from app.services.simulation_service import (
    SCENARIO_CODE_MAP,
    SCENARIO_NAME_MAP,
    SimulationService,
)

router = APIRouter(prefix="/simulate", tags=["simulation"])
logger = logging.getLogger(__name__)

_SCENARIO_INPUT_MAP = {
    "FS-01": FailureType.HIGH_CPU,
    "FS-02": FailureType.SERVICE_FAILURE,
    "FS-03": FailureType.STORAGE_EXHAUSTION,
    "FS-04": FailureType.NETWORK_LATENCY,
    "FS-05": FailureType.SERVICE_DOWNTIME,
}


class SimulateFailureRequest(BaseModel):
    """Request payload to inject a simulated failure scenario."""

    model_config = ConfigDict(populate_by_name=True)

    resource_id: str = Field(
        ...,
        alias="resourceId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$",
        description="Unique identifier of the resource, e.g. 'VM-001'",
        examples=["VM-001", "API-001", "DB-001", "STORAGE-001"],
    )
    failure_type: FailureType = Field(
        ...,
        alias="failureType",
        description="Failure scenario enum or code: HIGH_CPU, FS-01, SERVICE_FAILURE, FS-02, etc.",
        examples=["HIGH_CPU", "FS-01"],
    )
    severity: IncidentSeverity | None = Field(
        default=None,
        description="Optional severity level override (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional failure parameters and metric overrides (e.g. {'cpu': 98.0})",
    )

    @field_validator("failure_type", mode="before")
    @classmethod
    def parse_failure_type(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in _SCENARIO_INPUT_MAP:
                return _SCENARIO_INPUT_MAP[v_upper]
            for code, ftype in _SCENARIO_INPUT_MAP.items():
                if v_upper.startswith(code):
                    return ftype
            return v_upper
        return v


class SimulateFailureResponse(BaseModel):
    """Response returned upon successful simulated failure injection."""

    message: str
    scenario_id: str
    scenario_name: str
    resource: SimulatedResource
    incident: Incident
    metrics_emitted: dict[str, float]


class SimulateResetRequest(BaseModel):
    """Optional request payload for manual resource reset."""

    model_config = ConfigDict(populate_by_name=True)

    resource_id: str = Field(
        ...,
        alias="resourceId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$",
        description="Identifier of the resource to reset",
        examples=["VM-001"],
    )


class SimulateResetResponse(BaseModel):
    """Response returned upon manual resource recovery/reset."""

    message: str
    resource: SimulatedResource
    resolved_incidents: list[str] = Field(default_factory=list)


def get_simulation_service() -> SimulationService:
    """FastAPI dependency for SimulationService."""
    return SimulationService()


@router.post(
    "/failure",
    response_model=SimulateFailureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inject a simulated failure scenario",
)
def inject_failure(
    request: Annotated[SimulateFailureRequest, Body()],
    service: SimulationService = Depends(get_simulation_service),
) -> SimulateFailureResponse:
    """
    Inject a deterministic failure scenario (FS-01 to FS-05) on a simulated resource.

    Steps executed:
    1. Validates the virtual resource exists and is in a valid state (HEALTHY or WARNING).
    2. Updates its simulated state to FAILURE_DETECTED (CRITICAL health).
    3. Records fault metrics deterministically (with optional parameter overrides).
    4. Emits custom CloudWatch metric data points for alarms.
    5. Creates an Incident record in DynamoDB.
    6. Returns the updated resource, created incident, and emitted metrics.
    """
    resource, incident, emitted = service.inject_failure(
        resource_id=request.resource_id,
        failure_type=request.failure_type,
        severity=request.severity,
        parameters=request.parameters,
    )

    scenario_code = SCENARIO_CODE_MAP[request.failure_type]
    scenario_name = SCENARIO_NAME_MAP[request.failure_type]

    return SimulateFailureResponse(
        message=(
            f"Simulated failure '{scenario_name}' successfully injected on "
            f"'{resource.resource_id}'"
        ),
        scenario_id=scenario_code,
        scenario_name=scenario_name,
        resource=resource,
        incident=incident,
        metrics_emitted=emitted,
    )


@router.post(
    "/inject",
    response_model=SimulateFailureResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def inject_failure_alias(
    request: Annotated[SimulateFailureRequest, Body()],
    service: SimulationService = Depends(get_simulation_service),
) -> SimulateFailureResponse:
    """Backward-compatible alias for /simulate/failure."""
    return inject_failure(request=request, service=service)


@router.post(
    "/reset/{resource_id}",
    response_model=SimulateResetResponse,
    summary="Manually reset/recover a simulated resource by path ID",
)
def reset_resource_by_path(
    resource_id: str = Path(
        ...,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-]{0,63}$",
        description="Unique resource identifier, e.g. 'VM-001'",
    ),
    service: SimulationService = Depends(get_simulation_service),
) -> SimulateResetResponse:
    """
    Manually recover and reset a resource to HEALTHY state with nominal metrics.
    Resolves any active OPEN or RECOVERING incidents for the resource.
    """
    resource, resolved_incidents = service.reset_resource(resource_id)
    return SimulateResetResponse(
        message=f"Resource '{resource.resource_id}' successfully reset to HEALTHY",
        resource=resource,
        resolved_incidents=resolved_incidents,
    )


@router.post(
    "/reset",
    response_model=SimulateResetResponse,
    summary="Manually reset/recover a simulated resource by body",
)
def reset_resource_by_body(
    request: Annotated[SimulateResetRequest, Body()],
    service: SimulationService = Depends(get_simulation_service),
) -> SimulateResetResponse:
    """Manually reset a resource via request body."""
    return reset_resource_by_path(resource_id=request.resource_id, service=service)


@router.post(
    "/recover",
    response_model=SimulateResetResponse,
    summary="Alias to manually recover a simulated resource",
)
def recover_resource(
    request: Annotated[SimulateResetRequest, Body()],
    service: SimulationService = Depends(get_simulation_service),
) -> SimulateResetResponse:
    """Alias for manual recovery/reset."""
    return reset_resource_by_path(resource_id=request.resource_id, service=service)
