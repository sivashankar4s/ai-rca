"""DataSyncHealthCheck — health of AWS DataSync tasks via boto3 (feature 021).

Current status is the task's ``Status`` (AVAILABLE = up); the failure count is the
number of task executions that ended in ``ERROR`` within the lookback window.
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

_MAX_DESCRIBES = 25
_MAX_WORKERS = 8


class DataSyncHealthCheck(HealthCheckStrategy):
    service_type = HealthServiceType.DATASYNC_TASK

    def __init__(self, aws_credentials: dict | None = None) -> None:
        self._client = build_client("datasync", aws_credentials)

    def discover(self) -> list[HealthResource]:
        resources: list[HealthResource] = []
        params: dict = {}
        try:
            while True:
                resp = self._client.list_tasks(**params)
                for t in resp.get("Tasks", []):
                    arn = t["TaskArn"]
                    resources.append(HealthResource(id=arn, label=t.get("Name") or arn))
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"DataSync discovery failed: {exc}") from exc
        return resources

    def check(self, ids: list[str], start: datetime, end: datetime) -> list[ServiceHealth]:
        if len(ids) <= 1:
            return [self._check_one(arn, start, end) for arn in ids]
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(ids))) as pool:
            return list(pool.map(self._check_one, ids, repeat(start), repeat(end)))

    def _check_one(self, arn: str, start: datetime, end: datetime) -> ServiceHealth:
        try:
            task = self._client.describe_task(TaskArn=arn)
            label = task.get("Name") or arn
            status = HealthStatus.UP if task.get("Status") == "AVAILABLE" else HealthStatus.DOWN
            failures = self._error_count(arn, start, end)
        except (BotoCoreError, ClientError) as exc:
            return ServiceHealth(
                service_type=self.service_type,
                id=arn,
                label=arn,
                status=HealthStatus.UNKNOWN,
                detail=f"DataSync check failed: {exc}",
            )
        return ServiceHealth(
            service_type=self.service_type,
            id=arn,
            label=label,
            status=status,
            failure_count=failures,
            detail=f"Status={task.get('Status')}",
        )

    def detail(self, resource_id: str, start: datetime, end: datetime) -> ServiceHealthDetail:
        try:
            task = self._client.describe_task(TaskArn=resource_id)
            label = task.get("Name") or resource_id
            runs = self._collect_executions(resource_id, start, end)
        except (BotoCoreError, ClientError) as exc:
            return ServiceHealthDetail(
                service_type=self.service_type,
                id=resource_id,
                label=resource_id,
                start=start,
                end=end,
                detail=f"DataSync detail failed: {exc}",
            )
        return ServiceHealthDetail(
            service_type=self.service_type,
            id=resource_id,
            label=label,
            start=start,
            end=end,
            runs=runs,
        )

    def _collect_executions(self, arn: str, start: datetime, end: datetime) -> list[HealthRun]:
        resp = self._client.list_task_executions(TaskArn=arn)
        runs: list[HealthRun] = []
        executions = resp.get("TaskExecutions", [])[:_MAX_DESCRIBES]
        infos = self._describe_task_executions([ex["TaskExecutionArn"] for ex in executions])
        for ex, info in zip(executions, infos, strict=False):
            exec_arn = ex["TaskExecutionArn"]
            started = info.get("StartTime")
            if not in_window(started, start, end):
                continue
            status = info.get("Status") or ex.get("Status") or ""
            result = info.get("Result") or {}
            reason = result.get("ErrorDetail") or result.get("ErrorCode")
            runs.append(
                HealthRun(
                    run_id=exec_arn.rsplit("/", 1)[-1],
                    status=status,
                    is_failure=status == "ERROR",
                    started_at=started,
                    detail=reason,
                )
            )
        return runs

    def _error_count(self, arn: str, start: datetime, end: datetime) -> int:
        resp = self._client.list_task_executions(TaskArn=arn)
        error_arns = [
            ex["TaskExecutionArn"]
            for ex in resp.get("TaskExecutions", [])[:_MAX_DESCRIBES]
            if ex.get("Status") == "ERROR"
        ]
        return sum(
            1
            for detail in self._describe_task_executions(error_arns)
            if in_window(detail.get("StartTime"), start, end)
        )

    def _describe_task_executions(self, execution_arns: list[str]) -> list[dict]:
        if len(execution_arns) <= 1:
            return [self._describe_task_execution(arn) for arn in execution_arns]
        with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(execution_arns))) as pool:
            return list(pool.map(self._describe_task_execution, execution_arns))

    def _describe_task_execution(self, execution_arn: str) -> dict:
        return self._client.describe_task_execution(TaskExecutionArn=execution_arn)
