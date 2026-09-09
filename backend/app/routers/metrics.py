"""
/metrics router.

GET  /metrics                          → list reliability metrics snapshots (summaries)
GET  /metrics/{resource_id}            → get latest metric snapshot for a resource
GET  /metrics/{resource_id}/{window_key} → get specific metric snapshot
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.exceptions import MetricNotFoundError
from app.models.reliability_metric import (
    MetricWindowType,
    ReliabilityMetric,
    ReliabilityMetricSummary,
    parse_window_key,
)
from app.services.metric_service import MetricService

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = logging.getLogger(__name__)


def get_metric_service() -> MetricService:
    """FastAPI dependency for MetricService."""
    return MetricService()


@router.get(
    "",
    response_model=list[ReliabilityMetricSummary],
    summary="List reliability metric snapshots",
)
@router.get(
    "/",
    response_model=list[ReliabilityMetricSummary],
    include_in_schema=False,
)
def list_metrics(
    resource_id: str | None = Query(
        None,
        description="Filter by simulated resource ID, e.g. 'VM-001'",
    ),
    window_type: MetricWindowType | None = Query(
        None,
        description="Filter by aggregation window type (DAILY, WEEKLY, CUMULATIVE)",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Maximum number of metric snapshots to return",
    ),
    service: MetricService = Depends(get_metric_service),
) -> list[ReliabilityMetricSummary]:
    """Return pre-computed reliability metric snapshots matching filters."""
    return service.list_metrics(
        resource_id=resource_id,
        window_type=window_type,
        limit=limit,
    )


@router.get(
    "/{resource_id}",
    response_model=ReliabilityMetric,
    summary="Get latest metric snapshot for a resource",
)
def get_latest_metric(
    resource_id: str = Path(
        ...,
        description="Resource identifier, e.g. 'VM-001'",
    ),
    window_type: MetricWindowType = Query(
        MetricWindowType.DAILY,
        description="Window type to query for the latest snapshot (default: DAILY)",
    ),
    service: MetricService = Depends(get_metric_service),
) -> ReliabilityMetric:
    """Return the most recent reliability metric snapshot for a given resource."""
    normalized_id = resource_id.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-]{0,63}", normalized_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid resource_id format: '{resource_id}'",
        )
    metric = service.get_latest_metric(
        resource_id=normalized_id,
        window_type=window_type,
    )
    if metric is None:
        raise MetricNotFoundError(resource_id=normalized_id)
    return metric


@router.get(
    "/{resource_id}/{window_key}",
    response_model=ReliabilityMetric,
    summary="Get specific metric snapshot by resource and window key",
)
def get_metric_by_window(
    resource_id: str = Path(
        ...,
        description="Resource identifier, e.g. 'VM-001'",
    ),
    window_key: str = Path(
        ...,
        description="Window key, e.g. 'DAILY#2026-09-08' or 'CUMULATIVE#ALL'",
    ),
    service: MetricService = Depends(get_metric_service),
) -> ReliabilityMetric:
    """Return an exact reliability metric snapshot by resource ID and window key."""
    normalized_id = resource_id.strip().upper()
    clean_key = window_key.strip()
    try:
        parse_window_key(clean_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return service.get_metric(resource_id=normalized_id, window_key=clean_key)
