"""GlueJobHealthCheck — health of AWS Glue jobs via boto3 (feature 021).

Current status comes from the most recent job run's state; the failure count is the
number of runs that failed/timed out/errored within the lookback window.
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

_FAILED_STATES = {"FAILED", "TIMEOUT", "ERROR"}
_DOWN_STATES = _FAILED_STATES | {"STOPPED"}
_MAX_PAGES = 5
_MAX_WORKERS = 8


class GlueJobHealthCheck(HealthCheckStrategy):
    service_type = HealthServiceType.GLUE_JOB

    def __init__(self, aws_credentials: dict | None = None) -> None:
        self._client = build_client("glue", aws_credentials)

    def discover(self) -> list[HealthResource]:
        names: list[str] = []
        params: dict = {}
        try:
            while True:
                resp = self._client.list_jobs(**params)
                names.extend(resp.get("JobNames", []))
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Glue job discovery failed: {exc}") from exc
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
                detail=f"Glue GetJobRuns failed: {exc}",
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
        latest_state = latest.get("JobRunState", "")
        status = HealthStatus.DOWN if latest_state in _DOWN_STATES else HealthStatus.UP
        failures = sum(
            1
            for r in runs
            if r.get("JobRunState") in _FAILED_STATES and in_window(r.get("StartedOn"), start, end)
        )
        return ServiceHealth(
            service_type=self.service_type,
            id=name,
            label=name,
            status=status,
            failure_count=failures,
            last_activity_ts=latest.get("StartedOn"),
            detail=f"last run {latest_state}",
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
                detail=f"Glue GetJobRuns failed: {exc}",
            )
        history = [
            HealthRun(
                run_id=r.get("Id"),
                status=r.get("JobRunState", ""),
                is_failure=r.get("JobRunState") in _FAILED_STATES,
                started_at=r.get("StartedOn"),
                ended_at=r.get("CompletedOn"),
                detail=r.get("ErrorMessage"),
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
        """Return job runs newest-first, stopping once older than the window."""
        runs: list[dict] = []
        params: dict = {"JobName": name}
        for _ in range(_MAX_PAGES):
            resp = self._client.get_job_runs(**params)
            page = resp.get("JobRuns", [])
            runs.extend(page)
            started = page[-1].get("StartedOn") if page else None
            token = resp.get("NextToken")
            if not token or (started is not None and started < start):
                break
            params["NextToken"] = token
        return runs
