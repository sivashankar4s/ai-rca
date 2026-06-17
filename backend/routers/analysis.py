"""Analysis router — failures fetch, provider describe, and analyze endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from backend.config import settings
from backend.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    FailuresRequest,
    FailuresResponse,
    ProvidersResponse,
    TimeRange,
)
from backend.plugin_registry import describe_providers, get_data_source, get_log_backend

router = APIRouter(prefix="/api", tags=["analysis"])

_WINDOW: dict[TimeRange, timedelta] = {
    TimeRange.ONE_HOUR: timedelta(hours=1),
    TimeRange.ONE_DAY: timedelta(days=1),
    TimeRange.ONE_WEEK: timedelta(weeks=1),
}


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers() -> ProvidersResponse:
    """Report available data sources and log backends (T011/FR-005)."""
    return describe_providers()


@router.post("/failures", response_model=FailuresResponse)
async def post_failures(body: FailuresRequest) -> FailuresResponse:
    """Fetch FAILED records for the requested time window and optional component."""
    if body.time_range == TimeRange.CUSTOM:
        start, end = body.start, body.end
    else:
        now = datetime.now(UTC)
        start = now - _WINDOW[body.time_range]
        end = now

    ds = get_data_source(body.data_source)
    records = ds.fetch_records(start, end, body.component)
    return FailuresResponse(total=len(records), time_range=body.time_range, records=records)


@router.post("/analyze", response_model=AnalyzeResponse)
async def post_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Select log backend for this run and return selection details (T009/FR-002)."""
    get_log_backend(body.log_backend)
    backend_id = body.log_backend or settings.log_analysis_provider
    return AnalyzeResponse(log_backend_used=backend_id, record_count=len(body.records))
