"""CloudWatchDataSource — failure records from CloudWatch Logs Insights via boto3.

Reads plain-text AWS Lambda logs, detects failing invocations (``[ERROR]`` lines,
``Task timed out`` / OOM / error-indicator ``REPORT`` lines), consolidates every
line of one invocation by its Lambda RequestId, and returns one ``FailureRecord``
per failing RequestId. The RequestId is stored in ``file_trace_id``.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.models.schemas import FailureRecord
from backend.strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1  # seconds between Logs Insights status polls
_QUERY_LIMIT = 10000
_TERMINAL_FAILURE_STATES = ("Failed", "Cancelled", "Timeout")

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _row_dict(row: list[dict[str, str]]) -> dict[str, str]:
    return {item["field"]: item.get("value", "") for item in row}


def _request_id(rd: dict[str, str]) -> str | None:
    rid = rd.get("@requestId")
    if rid:
        return rid
    match = _UUID_RE.search(rd.get("@message", ""))
    return match.group(0) if match else None


def _component_from_log(log: str) -> str | None:
    if not log:
        return None
    return log.rsplit("/", 1)[-1] or None


def _log_group_from_log(log: str) -> str | None:
    if not log:
        return None
    return log.split(":", 1)[-1]


def _error_text(message: str) -> str:
    parts = message.split("\t")
    if len(parts) >= 4 and parts[0].strip() == "[ERROR]":
        return "\t".join(parts[3:]).strip()
    return message.strip()


def _anomaly_reason(message: str, max_mem: int | None, mem_size: int | None) -> str | None:
    """Synthesised failure reason for a non-``[ERROR]`` line, or None if benign."""
    if "Task timed out" in message:
        return "Task timed out"
    if max_mem is not None and mem_size is not None and max_mem >= mem_size:
        return f"Out of memory: {mem_size // (1024 * 1024)}MB"
    if "errorMessage" in message or "Error" in message:
        return message
    return None


def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


@dataclass
class _Group:
    """Accumulated state for a single Lambda RequestId."""

    request_id: str
    component: str | None = None
    log_group: str | None = None
    log_stream: str | None = None
    earliest_ts: datetime | None = None
    has_failure: bool = False
    report: dict | None = None
    error_texts: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    rows: list[dict[str, str]] = field(default_factory=list)


def _build_record(group: _Group) -> FailureRecord:
    error_texts = _ordered_unique(group.error_texts)
    reasons = _ordered_unique(group.failure_reasons)
    message = "\n".join(error_texts + reasons)
    raw_payload: dict = {
        "request_id": group.request_id,
        "log_group": group.log_group,
        "log_stream": group.log_stream,
        "report": group.report,
        "lines": group.rows,
        "failure_reasons": reasons,
    }
    return FailureRecord(
        file_trace_id=group.request_id,
        component_name=group.component,
        message=message,
        status="FAILED",
        event_created_ts=group.earliest_ts,
        raw_payload=raw_payload,
    )


def _rows_to_records(results: list) -> list[FailureRecord]:
    groups: dict[str, _Group] = {}
    skipped = 0
    for row in results:
        rd = _row_dict(row)
        rid = _request_id(rd)
        if rid is None:
            skipped += 1
            logger.warning("CloudWatchDataSource: skipping row with no resolvable RequestId")
            continue
        group = groups.get(rid)
        if group is None:
            group = _Group(request_id=rid)
            groups[rid] = group
        group.rows.append(rd)

        log = rd.get("@log", "")
        if group.component is None:
            group.component = _component_from_log(log)
        if group.log_group is None:
            group.log_group = _log_group_from_log(log)
        if group.log_stream is None:
            group.log_stream = rd.get("@logStream") or None

        ts = _parse_ts(rd.get("@timestamp"))
        if ts is not None and (group.earliest_ts is None or ts < group.earliest_ts):
            group.earliest_ts = ts

        message = rd.get("@message", "")
        max_mem = _to_int(rd.get("@maxMemoryUsed"))
        mem_size = _to_int(rd.get("@memorySize"))
        if "[ERROR]" in message:
            group.has_failure = True
            group.error_texts.append(_error_text(message))
        else:
            reason = _anomaly_reason(message, max_mem, mem_size)
            if reason is not None:
                group.has_failure = True
                group.failure_reasons.append(reason)

        if rd.get("@type") == "REPORT":
            group.report = {
                "max_memory_used": max_mem,
                "memory_size": mem_size,
                "message": message,
            }

    logger.info("CloudWatchDataSource: skipped %d rows without RequestId", skipped)
    return [_build_record(g) for g in groups.values() if g.has_failure]


class CloudWatchDataSource(DataSourceStrategy):
    """Queries failing Lambda invocations from CloudWatch Logs Insights."""

    def __init__(
        self,
        log_groups: list[str] | None = None,
        query_timeout: int | None = None,
        aws_credentials: dict | None = None,
    ) -> None:
        # ``None`` means "fall back to env settings" — the registry injects the
        # effective config (DB app_config row, env fallback) when available. AWS
        # credentials come from the Config page (DB ``aws_config``) when present,
        # falling back to env settings otherwise.
        self._log_groups = log_groups
        self._query_timeout = query_timeout
        creds = aws_credentials or {}
        self._client = boto3.client(
            "logs",
            region_name=creds.get("region") or settings.aws_region,
            aws_access_key_id=creds.get("access_key_id") or settings.aws_access_key_id or None,
            aws_secret_access_key=(
                creds.get("secret_access_key") or settings.aws_secret_access_key or None
            ),
            aws_session_token=settings.aws_session_token or None,
        )

    @property
    def _effective_log_groups(self) -> list[str]:
        return self._log_groups if self._log_groups is not None else settings.cloudwatch_log_groups

    @property
    def _effective_timeout(self) -> int:
        if self._query_timeout is not None:
            return self._query_timeout
        return settings.cloudwatch_query_timeout

    def _build_query(self, component: str | None) -> str:
        query = (
            "fields @timestamp, @message, @requestId, @log, @logStream, @type, "
            "@maxMemoryUsed, @memorySize "
            "| filter @message like /\\[ERROR\\]/ or @message like /Task timed out/ "
            'or @type = "REPORT"'
        )
        if component:
            query += f" | filter @log like /{component}/"
        query += f" | sort @timestamp asc | limit {_QUERY_LIMIT}"
        return query

    def _start(self, query: str, start: datetime, end: datetime) -> str:
        try:
            resp = self._client.start_query(
                logGroupNames=self._effective_log_groups,
                startTime=int(start.timestamp()),
                endTime=int(end.timestamp()),
                queryString=query,
                limit=_QUERY_LIMIT,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"CloudWatch query failed: {exc}") from exc
        return resp["queryId"]

    def _get_results(self, query_id: str) -> dict:
        try:
            return self._client.get_query_results(queryId=query_id)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"CloudWatch query failed: {exc}") from exc

    def _poll(self, query_id: str) -> list:
        timeout = self._effective_timeout
        deadline = time.monotonic() + timeout
        while True:
            result = self._get_results(query_id)
            status = result["status"]
            if status == "Complete":
                return result["results"]
            if status in _TERMINAL_FAILURE_STATES:
                raise RuntimeError(f"CloudWatch query failed: status={status}")
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"CloudWatch query failed: query timed out after {timeout}s"
                )
            time.sleep(_POLL_INTERVAL)

    def fetch_records(
        self,
        start: datetime,
        end: datetime,
        component: str | None = None,
    ) -> list[FailureRecord]:
        if not self._effective_log_groups:
            raise RuntimeError(
                "CloudWatch data source requires log groups to be configured "
                "(set them on the Config page or via CLOUDWATCH_LOG_GROUPS)"
            )
        query = self._build_query(component)
        logger.info("CloudWatchDataSource: executing query component=%s", component or "<all>")
        query_id = self._start(query, start, end)
        results = self._poll(query_id)
        records = _rows_to_records(results)
        logger.info("CloudWatchDataSource: returned %d records", len(records))
        return records
