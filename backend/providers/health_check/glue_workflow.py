"""GlueWorkflowHealthCheck — health of AWS Glue workflows via boto3 (feature 021).

Current status comes from the most recent workflow run; the failure count is the number
of workflow runs that errored (or had failed actions) within the lookback window.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import repeat

from botocore.exceptions import BotoCoreError, ClientError

from backend.models.schemas import (
    HealthResource,
    HealthRun,
    HealthServiceType,
    HealthStatus,
    ServiceHealth,
    ServiceHealthDetail,
)
from backend.providers.health_check._aws import build_client, in_window
from backend.strategies.health_check import HealthCheckStrategy

logger = logging.getLogger(__name__)

_DOWN_STATES = {"ERROR", "STOPPED"}
_MAX_PAGES = 5
_MAX_WORKERS = 8


class GlueWorkflowHealthCheck(HealthCheckStrategy):
    service_type = HealthServiceType.GLUE_WORKFLOW

    def __init__(self, aws_credentials: dict | None = None) -> None:
        self._client = build_client("glue", aws_credentials)

    def discover(self) -> list[HealthResource]:
        names: list[str] = []
        params: dict = {}
        try:
            while True:
                resp = self._client.list_workflows(**params)
                names.extend(resp.get("Workflows", []))
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Glue workflow discovery failed: {exc}") from exc
        return [HealthResource(id=n, label=n) for n in names]

    def check(self, ids: list[str], start: datetime, end: datetime) -> list[ServiceHealth]:
        if len(ids) <= 1:
            return [self._check_one(name, start, end) for name in ids]
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(ids))) as pool:
            return list(pool.map(self._check_one, ids, repeat(start), repeat(end)))

    def _check_one(self, name: str, start: datetime, end: datetime) -> ServiceHealth:
        try:
            runs = self._collect_runs(name, start)
        except (BotoCoreError, ClientError) as exc:
            return ServiceHealth(
                service_type=self.service_type,
                id=name,
                label=name,
                status=HealthStatus.UNKNOWN,
                detail=f"Glue GetWorkflowRuns failed: {exc}",
            )
        if not runs:
            return ServiceHealth(
                service_type=self.service_type,
                id=name,
                label=name,
                status=HealthStatus.UNKNOWN,
                detail="no runs found",
            )
        latest = runs[0]
        latest_status = latest.get("Status", "")
        status = HealthStatus.DOWN if latest_status in _DOWN_STATES else HealthStatus.UP
        failures = sum(
            1 for r in runs if _is_failed(r) and in_window(r.get("StartedOn"), start, end)
        )
        return ServiceHealth(
            service_type=self.service_type,
            id=name,
            label=name,
            status=status,
            failure_count=failures,
            last_activity_ts=latest.get("StartedOn"),
            detail=f"last run {latest_status}",
        )

    def detail(self, resource_id: str, start: datetime, end: datetime) -> ServiceHealthDetail:
        try:
            runs = self._collect_runs(resource_id, start)
        except (BotoCoreError, ClientError) as exc:
            return ServiceHealthDetail(
                service_type=self.service_type,
                id=resource_id,
                label=resource_id,
                start=start,
                end=end,
                detail=f"Glue GetWorkflowRuns failed: {exc}",
            )
        history = [
            HealthRun(
                run_id=r.get("WorkflowRunId"),
                status=r.get("Status", ""),
                is_failure=_is_failed(r),
                started_at=r.get("StartedOn"),
                ended_at=r.get("CompletedOn"),
                detail=_failure_detail(r),
            )
            for r in runs
            if in_window(r.get("StartedOn"), start, end)
        ]
        return ServiceHealthDetail(
            service_type=self.service_type,
            id=resource_id,
            label=resource_id,
            start=start,
            end=end,
            runs=history,
        )

    def _collect_runs(self, name: str, start: datetime) -> list[dict]:
        runs: list[dict] = []
        params: dict = {"Name": name}
        for _ in range(_MAX_PAGES):
            resp = self._client.get_workflow_runs(**params)
            page = resp.get("Runs", [])
            runs.extend(page)
            started = page[-1].get("StartedOn") if page else None
            token = resp.get("NextToken")
            if not token or (started is not None and started < start):
                break
            params["NextToken"] = token
        return runs


def _is_failed(run: dict) -> bool:
    if run.get("Status") == "ERROR":
        return True
    stats = run.get("Statistics") or {}
    return int(stats.get("FailedActions", 0)) > 0


def _failure_detail(run: dict) -> str | None:
    """Human-readable failure summary for a workflow run, or None when it succeeded."""
    if run.get("Status") == "ERROR":
        return run.get("ErrorMessage") or "run errored"
    failed = int((run.get("Statistics") or {}).get("FailedActions", 0))
    return f"{failed} failed action(s)" if failed > 0 else None
