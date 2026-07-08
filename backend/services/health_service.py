"""health_service — fan out configured resources across health-check providers (feature 021).

Reads the persisted ``health_config`` selection, runs each provider concurrently (boto3
is blocking), and assembles a combined ``ServiceHealthResponse``. A provider that raises
for a resource degrades to an ``unknown`` result rather than failing the whole request.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.schemas import (
    FailureRecord,
    FailuresResponse,
    HealthDetailRequest,
    HealthRun,
    HealthServiceType,
    HealthStatus,
    HealthWindow,
    ServiceHealth,
    ServiceHealthDetail,
    ServiceHealthResponse,
    TimeRange,
)
from backend.plugin_registry import get_cloudwatch_source, get_data_source, get_health_checkers
from backend.repositories import config_repo
from backend.strategies.health_check import HealthCheckStrategy

logger = logging.getLogger(__name__)

_MAX_WORKERS = 8
_MAX_RANGE_DAYS = 31


def _resolve_range(
    window: HealthWindow | None,
    start: datetime | None,
    end: datetime | None,
    now: datetime,
) -> tuple[datetime, datetime, HealthWindow | None]:
    """Resolve the lookback bounds from either a preset window or a custom range."""
    if start is not None or end is not None:
        if start is None or end is None:
            raise ValueError("both start and end are required for a custom range")
        if start >= end:
            raise ValueError("start must be before end")
        if end - start > timedelta(days=_MAX_RANGE_DAYS):
            raise ValueError(f"date range must not exceed {_MAX_RANGE_DAYS} days")
        return start, end, None
    window = window or HealthWindow.H24
    return now - window.delta, now, window


def _lambda_log_group(name: str) -> str:
    """The default CloudWatch log group a Lambda function writes to."""
    return f"/aws/lambda/{name}"


def _selected_ids(health_cfg: dict) -> dict[HealthServiceType, list[str]]:
    """Map each service type to its configured resource ids from health_config."""
    datasync = [t["id"] if isinstance(t, dict) else t for t in health_cfg.get("datasync_tasks", [])]
    return {
        HealthServiceType.GLUE_JOB: list(health_cfg.get("glue_jobs", [])),
        HealthServiceType.GLUE_WORKFLOW: list(health_cfg.get("glue_workflows", [])),
        HealthServiceType.LAMBDA_FUNCTION: list(health_cfg.get("lambda_functions", [])),
        HealthServiceType.DATASYNC_TASK: datasync,
    }


def _datasync_labels(health_cfg: dict) -> dict[str, str]:
    """arn -> friendly name, so a failed DataSync check can still show a label."""
    labels: dict[str, str] = {}
    for t in health_cfg.get("datasync_tasks", []):
        if isinstance(t, dict) and t.get("id"):
            labels[t["id"]] = t.get("label") or t["id"]
    return labels


def check_all(
    db: Session,
    window: HealthWindow | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    profile: str | None = None,
) -> ServiceHealthResponse:
    """Run health checks for one profile's resources over a preset window or custom range.

    ``profile`` selects a named resource set (``None`` uses the first profile). Pass
    ``start``+``end`` for a custom date range; otherwise ``window`` (default 24h) is used.
    A custom range takes precedence over ``window`` when both are supplied.
    """
    generated_at = datetime.now(UTC)
    start, end, window = _resolve_range(window, start, end, generated_at)

    health_cfg = config_repo.get_profile_resources(db, profile) or {}
    profile_name = health_cfg.get("name")
    selected = _selected_ids(health_cfg)

    if not any(selected.values()):
        return ServiceHealthResponse(
            window=window,
            profile=profile_name,
            generated_at=generated_at,
            start=start,
            end=end,
            results=[],
            total_failures=0,
        )

    checkers = get_health_checkers(db)
    ds_labels = _datasync_labels(health_cfg)

    tasks = [
        (service_type, checkers[service_type], ids) for service_type, ids in selected.items() if ids
    ]

    results: list[ServiceHealth] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = [
            pool.submit(_run_checker, st, checker, ids, start, end, ds_labels)
            for st, checker, ids in tasks
        ]
        for future in futures:
            results.extend(future.result())

    total_failures = sum(r.failure_count for r in results)
    return ServiceHealthResponse(
        window=window,
        profile=profile_name,
        generated_at=generated_at,
        start=start,
        end=end,
        results=results,
        total_failures=total_failures,
    )


def get_detail(db: Session, req: HealthDetailRequest) -> ServiceHealthDetail:
    """Run the drill-down history lookup for one configured resource.

    Lambda has no run-list API, so its history is the set of failed invocations found
    in its own CloudWatch log group (the same detector the Fetch Failures button uses);
    Glue and DataSync use their native run APIs via the provider.
    """
    if req.service_type == HealthServiceType.LAMBDA_FUNCTION:
        return _lambda_detail(db, req)
    checker = get_health_checkers(db)[req.service_type]
    try:
        return checker.detail(req.id, req.start, req.end)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully (FR-012)
        logger.warning("health detail failed for %s %s: %s", req.service_type, req.id, exc)
        return ServiceHealthDetail(
            service_type=req.service_type,
            id=req.id,
            label=req.label or req.id,
            start=req.start,
            end=req.end,
            detail=f"detail failed: {exc}",
        )


def _lambda_detail(db: Session, req: HealthDetailRequest) -> ServiceHealthDetail:
    """List a Lambda's failed invocations from its own log group as run rows."""
    source = get_cloudwatch_source(db, [_lambda_log_group(req.id)])
    label = req.label or req.id
    try:
        records = source.fetch_records(req.start, req.end)
    except RuntimeError as exc:
        return ServiceHealthDetail(
            service_type=req.service_type,
            id=req.id,
            label=label,
            start=req.start,
            end=req.end,
            detail=str(exc),
        )
    return ServiceHealthDetail(
        service_type=req.service_type,
        id=req.id,
        label=label,
        start=req.start,
        end=req.end,
        runs=[_record_to_run(r) for r in records],
    )


def _record_to_run(record: FailureRecord) -> HealthRun:
    """Map a CloudWatch failure record to a run row (one per failed invocation)."""
    return HealthRun(
        run_id=record.file_trace_id,
        status="FAILED",
        is_failure=True,
        started_at=record.event_created_ts,
        detail=record.message,
    )


def fetch_failures(db: Session, req: HealthDetailRequest) -> FailuresResponse:
    """Pull failure reasons for one resource from CloudWatch Logs Insights on demand.

    Lambda is scoped to its own ``/aws/lambda/<name>`` log group; Glue and DataSync use
    the configured CloudWatch log groups, narrowed to the resource by name (its friendly
    label for DataSync, whose id is an ARN).
    """
    if req.service_type == HealthServiceType.LAMBDA_FUNCTION:
        source = get_cloudwatch_source(db, [_lambda_log_group(req.id)])
        records = source.fetch_records(req.start, req.end)
    else:
        source = get_data_source("cloudwatch", db=db)
        records = source.fetch_records(req.start, req.end, _failure_component(req))
    return FailuresResponse(total=len(records), time_range=TimeRange.CUSTOM, records=records)


def _failure_component(req: HealthDetailRequest) -> str:
    """CloudWatch log filter for a non-Lambda resource — the name, or the label for ARNs."""
    if req.service_type == HealthServiceType.DATASYNC_TASK:
        return req.label or req.id
    return req.id


def _run_checker(
    service_type: HealthServiceType,
    checker: HealthCheckStrategy,
    ids: list[str],
    start: datetime,
    end: datetime,
    ds_labels: dict[str, str],
) -> list[ServiceHealth]:
    """Run one provider; on an unexpected error, emit an ``unknown`` per requested id."""
    try:
        return checker.check(ids, start, end)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully (FR-012)
        logger.warning("health check failed for %s: %s", service_type, exc)
        return [
            ServiceHealth(
                service_type=service_type,
                id=rid,
                label=ds_labels.get(rid, rid),
                status=HealthStatus.UNKNOWN,
                detail=f"check failed: {exc}",
            )
            for rid in ids
        ]
