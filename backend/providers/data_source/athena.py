"""AthenaDataSource — queries failure records from Amazon Athena via boto3."""

import json
import logging
import time
from datetime import datetime

import boto3

from backend.config import settings
from backend.models.schemas import FailureRecord
from backend.strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1  # seconds between status polls


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_event_data(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _rows_to_records(rows: list[dict]) -> list[FailureRecord]:
    """Convert Athena result rows (header + data) to FailureRecord list."""
    if len(rows) <= 1:
        return []
    headers = [c.get("VarCharValue", "") for c in rows[0]["Data"]]
    results: list[FailureRecord] = []
    for row in rows[1:]:
        cells = [c.get("VarCharValue", "") for c in row["Data"]]
        r = dict(zip(headers, cells))
        event = _parse_event_data(r.get("event_data"))
        results.append(
            FailureRecord(
                application_name=r.get("application_name") or None,
                component_name=r.get("component_name") or None,
                organization=r.get("organization") or None,
                file_trace_id=r.get("custom_key1") or None,
                file_name=r.get("custom_key2") or None,
                device_id=r.get("custom_key3") or None,
                error_code=event.get("error_code"),
                stage=event.get("stage"),
                status=r.get("status") or None,
                event_created_ts=_parse_ts(r.get("event_created_timestamp")),
                event_inserted_ts=_parse_ts(r.get("event_inserted_timestamp")),
                raw_payload=r,
            )
        )
    return results


class AthenaDataSource(DataSourceStrategy):
    """Queries FAILED records from Amazon Athena for a given datetime window."""

    def __init__(
        self, database: str | None = None, table: str | None = None
    ) -> None:
        # ``None`` means "fall back to env settings" — the registry injects the
        # effective config (DB app_config row, env fallback) when available.
        self._database = database or settings.athena_database
        self._table = table or settings.athena_table
        self._client = boto3.client(
            "athena",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
        )

    def _build_sql(self, start: datetime, end: datetime, component: str | None) -> str:
        start_s = start.strftime("%Y-%m-%d %H:%M:%S")
        end_s = end.strftime("%Y-%m-%d %H:%M:%S")
        component_clause = (
            f" AND component_name = '{component.replace(chr(39), chr(39) * 2)}'"
            if component
            else ""
        )
        return (
            f"SELECT application_name, component_name, custom_key1, custom_key2,"
            f" custom_key3, event_created_timestamp, event_inserted_timestamp,"
            f" organization, status, event_data"
            f" FROM {self._database}.{self._table}"
            f" WHERE status = 'FAILED'"
            f" AND event_created_timestamp"
            f" BETWEEN TIMESTAMP '{start_s}' AND TIMESTAMP '{end_s}'"
            f"{component_clause}"
        )

    def _start_query(self, sql: str) -> str:
        resp = self._client.start_query_execution(
            QueryString=sql,
            ResultConfiguration={
                "OutputLocation": f"s3://{settings.athena_output_bucket}/query-results/"
            },
        )
        return resp["QueryExecutionId"]

    def _poll(self, query_id: str) -> None:
        while True:
            resp = self._client.get_query_execution(QueryExecutionId=query_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                return
            if state in ("FAILED", "CANCELLED"):
                reason = resp["QueryExecution"]["Status"].get("StateChangeReason", "")
                raise RuntimeError(f"Athena query failed: {reason}")
            time.sleep(_POLL_INTERVAL)

    def fetch_records(
        self,
        start: datetime,
        end: datetime,
        component: str | None = None,
    ) -> list[FailureRecord]:
        sql = self._build_sql(start, end, component)
        logger.info("AthenaDataSource: executing query component=%s", component or "<all>")
        query_id = self._start_query(sql)
        self._poll(query_id)
        resp = self._client.get_query_results(QueryExecutionId=query_id)
        rows = resp["ResultSet"]["Rows"]
        records = _rows_to_records(rows)
        logger.info("AthenaDataSource: returned %d records", len(records))
        return records
