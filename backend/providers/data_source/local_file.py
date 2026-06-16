"""LocalFileDataSource — reads failure records from a JSON file (dev/CI use)."""

import json
import logging
from datetime import datetime
from pathlib import Path

from backend.models.schemas import FailureRecord
from backend.strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)


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


def _to_failure_record(row: dict) -> FailureRecord:
    event = _parse_event_data(row.get("event_data"))
    return FailureRecord(
        application_name=row.get("application_name"),
        component_name=row.get("component_name"),
        organization=row.get("organization"),
        file_trace_id=row.get("custom_key1"),
        file_name=row.get("custom_key2"),
        device_id=row.get("custom_key3"),
        error_code=event.get("error_code"),
        stage=event.get("stage"),
        status=row.get("status"),
        event_created_ts=_parse_ts(row.get("event_created_timestamp")),
        event_inserted_ts=_parse_ts(row.get("event_inserted_timestamp")),
        raw_payload=row,
    )


class LocalFileDataSource(DataSourceStrategy):
    """Loads FAILED records from a local JSON file, filtering by time window."""

    def __init__(self, path: str) -> None:
        self._path = path

    def fetch_records(
        self,
        start: datetime,
        end: datetime,
        component: str | None = None,
    ) -> list[FailureRecord]:
        try:
            raw = Path(self._path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeError(f"LOCAL_DATA_FILE not found: {self._path}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LOCAL_DATA_FILE is not valid JSON: {exc}") from exc

        rows: list[dict] = data if isinstance(data, list) else data.get("records", [])

        results: list[FailureRecord] = []
        for row in rows:
            if row.get("status") != "FAILED":
                continue
            ts = _parse_ts(row.get("event_created_timestamp"))
            if ts is None or not (start <= ts <= end):
                continue
            if component is not None and row.get("component_name") != component:
                continue
            results.append(_to_failure_record(row))

        logger.info(
            "LocalFileDataSource: returned %d records (component=%s)",
            len(results),
            component or "<all>",
        )
        return results
