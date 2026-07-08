"""Analysis router — failures fetch, provider describe, and analyze endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.session import get_db
from backend.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    FailureRecord,
    FailuresRequest,
    FailuresResponse,
    ProvidersResponse,
    TimeRange,
)
from backend.plugin_registry import describe_providers, get_data_source, get_log_backend
from backend.repositories.failure_repo import upsert_failure_records
from backend.repositories.project_repo import get_or_create_default_project
from backend.services.rca_service import stream_rca

router = APIRouter(prefix="/api", tags=["analysis"])

_WINDOW: dict[TimeRange, timedelta] = {
    TimeRange.ONE_HOUR: timedelta(hours=1),
    TimeRange.ONE_DAY: timedelta(days=1),
    TimeRange.ONE_WEEK: timedelta(weeks=1),
}


def _matches_trace(record: FailureRecord, trace_id: str) -> bool:
    """True if the record's file_trace_id contains ``trace_id`` (case-insensitive)."""
    return record.file_trace_id is not None and trace_id.lower() in record.file_trace_id.lower()


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers() -> ProvidersResponse:
    """Report available data sources and log backends (T011/FR-005)."""
    return describe_providers()


@router.post("/failures", response_model=FailuresResponse)
async def post_failures(body: FailuresRequest, db: Session = Depends(get_db)) -> FailuresResponse:
    """Fetch FAILED records, persist them, and return the (optionally trace-filtered) set."""
    if body.time_range == TimeRange.CUSTOM:
        start, end = body.start, body.end
    else:
        now = datetime.now(UTC)
        start = now - _WINDOW[body.time_range]
        end = now

    ds = get_data_source(body.data_source, db=db)
    try:
        records = ds.fetch_records(start, end, body.component)
    except RuntimeError as exc:
        # Provider config / backend failure (e.g. CloudWatch not configured) → clean 400.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Persist ALL fetched records under the default project before filtering.
    project = get_or_create_default_project(db)
    upsert_failure_records(db, project.id, records)
    db.commit()

    if body.trace_id:
        records = [r for r in records if _matches_trace(r, body.trace_id)]

    return FailuresResponse(total=len(records), time_range=body.time_range, records=records)


@router.post("/analyze", response_model=AnalyzeResponse)
async def post_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Select log backend for this run and return selection details (T009/FR-002)."""
    get_log_backend(body.log_backend)
    backend_id = body.log_backend or settings.log_analysis_provider
    return AnalyzeResponse(log_backend_used=backend_id, record_count=len(body.records))


@router.post("/analyze/stream")
async def post_analyze_stream(body: AnalyzeRequest) -> StreamingResponse:
    """Stream a combined root-cause analysis of the selected failures token-by-token."""
    if not body.records:
        raise HTTPException(status_code=400, detail="No records selected for analysis.")

    def generate():
        try:
            yield from stream_rca(body.records)
        except RuntimeError as exc:
            yield f"\n\n[analysis error: {exc}]"

    return StreamingResponse(generate(), media_type="text/plain")
