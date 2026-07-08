"""Health dashboard router — on-demand health of configured AWS services (feature 021)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.schemas import (
    FailuresResponse,
    HealthDetailRequest,
    HealthWindow,
    ServiceHealthDetail,
    ServiceHealthResponse,
)
from ..services import health_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/services", response_model=ServiceHealthResponse)
async def get_service_health(
    window: HealthWindow = HealthWindow.H24,
    start: datetime | None = None,
    end: datetime | None = None,
    profile: str | None = None,
    db: Session = Depends(get_db),
) -> ServiceHealthResponse:
    """Return status + failure counts for a profile's resources.

    ``profile`` selects the named resource set (defaults to the first). A custom
    ``start``/``end`` date range takes precedence over the ``window`` preset.
    """
    if start is not None or end is not None:
        return health_service.check_all(db, None, start, end, profile)
    return health_service.check_all(db, window, profile=profile)


@router.post("/services/runs", response_model=ServiceHealthDetail)
async def get_service_runs(
    body: HealthDetailRequest, db: Session = Depends(get_db)
) -> ServiceHealthDetail:
    """Return run history (or Lambda metric buckets) for one resource over a date range."""
    return health_service.get_detail(db, body)


@router.post("/services/failures", response_model=FailuresResponse)
async def get_service_failures(
    body: HealthDetailRequest, db: Session = Depends(get_db)
) -> FailuresResponse:
    """Fetch failure reasons for one resource from CloudWatch Logs Insights on demand."""
    try:
        return health_service.fetch_failures(db, body)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
