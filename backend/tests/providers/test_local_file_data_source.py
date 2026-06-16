"""Tests for LocalFileDataSource — no real file I/O except sample_failures.json."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.providers.data_source.local_file import LocalFileDataSource

# sample_failures.json spans 2026-06-10 through 2026-06-16
_WINDOW_START = datetime(2026, 6, 16, 0, 0, 0, tzinfo=datetime.now().astimezone().tzinfo)
_WINDOW_END = datetime(2026, 6, 16, 23, 59, 59, tzinfo=datetime.now().astimezone().tzinfo)

# Naive datetimes (no tz) that bracket all sample records
_NAIVE_START = datetime(2026, 6, 16, 0, 0, 0)
_NAIVE_END = datetime(2026, 6, 16, 23, 59, 59)

SAMPLE_PATH = str(Path(__file__).parents[3] / "sample_failures.json")


class TestLocalFileDataSource:
    def test_returns_only_failed_records(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert all(r.status == "FAILED" for r in records)

    def test_excludes_success_and_completed_rows(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        statuses = {r.status for r in records}
        assert "SUCCESS" not in statuses
        assert "COMPLETED" not in statuses

    def test_filters_by_time_window(self) -> None:
        # Only records from 2026-06-16 — sample has records on other dates too
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(records) > 0
        for r in records:
            assert r.event_created_ts is not None
            assert _NAIVE_START <= r.event_created_ts.replace(tzinfo=None) <= _NAIVE_END

    def test_excludes_out_of_window_records(self) -> None:
        # Narrow to a 1-second window that matches no records
        narrow_start = datetime(2026, 6, 13, 0, 0, 0)
        narrow_end = datetime(2026, 6, 13, 0, 0, 1)
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(narrow_start, narrow_end)
        assert records == []

    def test_component_filter_narrows_results(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        all_records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        filtered = ds.fetch_records(
            _NAIVE_START, _NAIVE_END, component="dp-lz-s3-event-processor"
        )
        assert len(filtered) < len(all_records)
        assert all(r.component_name == "dp-lz-s3-event-processor" for r in filtered)

    def test_component_filter_none_returns_all_components(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        components = {r.component_name for r in records}
        assert len(components) > 1

    def test_parses_event_data_fields(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(records) > 0
        # At least some records should have error_code and stage populated
        with_error = [r for r in records if r.error_code is not None]
        assert len(with_error) > 0
        with_stage = [r for r in records if r.stage is not None]
        assert len(with_stage) > 0

    def test_maps_custom_key_fields(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(records) > 0
        r = records[0]
        assert r.file_trace_id is not None  # from custom_key1

    def test_raw_payload_preserved(self) -> None:
        ds = LocalFileDataSource(SAMPLE_PATH)
        records = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(records) > 0
        assert records[0].raw_payload is not None

    def test_file_not_found_raises_runtime_error(self) -> None:
        ds = LocalFileDataSource("/nonexistent/path/failures.json")
        with pytest.raises(RuntimeError, match="not found"):
            ds.fetch_records(_NAIVE_START, _NAIVE_END)

    def test_invalid_json_raises_runtime_error(self, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json", encoding="utf-8")
        ds = LocalFileDataSource(str(bad))
        with pytest.raises(RuntimeError, match="not valid JSON"):
            ds.fetch_records(_NAIVE_START, _NAIVE_END)

    def test_malformed_event_data_string_is_handled(self, tmp_path) -> None:
        """A record with a non-JSON event_data string should still be returned."""
        records = [
            {
                "application_name": "app",
                "component_name": "comp",
                "custom_key1": "trace-bad",
                "custom_key2": "file.raw",
                "custom_key3": "dev-001",
                "event_created_timestamp": "2026-06-16 10:00:00.000000",
                "event_inserted_timestamp": "2026-06-16 10:00:01.000000",
                "organization": "org",
                "status": "FAILED",
                "event_data": "not-json{{",
            }
        ]
        f = tmp_path / "records.json"
        f.write_text(json.dumps(records), encoding="utf-8")
        ds = LocalFileDataSource(str(f))
        result = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(result) == 1
        assert result[0].error_code is None
        assert result[0].stage is None

    def test_null_timestamp_record_is_excluded(self, tmp_path) -> None:
        """FAILED record with null event_created_timestamp is silently skipped."""
        records = [
            {
                "application_name": "app",
                "component_name": "comp",
                "custom_key1": "trace-null-ts",
                "status": "FAILED",
                "event_created_timestamp": None,
                "event_data": None,
            }
        ]
        f = tmp_path / "records.json"
        f.write_text(json.dumps(records), encoding="utf-8")
        ds = LocalFileDataSource(str(f))
        result = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert result == []

    def test_no_microseconds_timestamp_is_parsed(self, tmp_path) -> None:
        """Timestamp without microseconds (second format) parses correctly."""
        records = [
            {
                "application_name": "app",
                "component_name": "comp",
                "custom_key1": "trace-no-us",
                "status": "FAILED",
                "event_created_timestamp": "2026-06-16 10:00:00",
                "event_data": None,
            }
        ]
        f = tmp_path / "records.json"
        f.write_text(json.dumps(records), encoding="utf-8")
        ds = LocalFileDataSource(str(f))
        result = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert len(result) == 1
        assert result[0].event_created_ts is not None

    def test_unparseable_timestamp_record_is_excluded(self, tmp_path) -> None:
        """FAILED record with a completely invalid timestamp string is skipped."""
        records = [
            {
                "application_name": "app",
                "component_name": "comp",
                "custom_key1": "trace-bad-ts",
                "status": "FAILED",
                "event_created_timestamp": "not-a-date",
                "event_data": None,
            }
        ]
        f = tmp_path / "records.json"
        f.write_text(json.dumps(records), encoding="utf-8")
        ds = LocalFileDataSource(str(f))
        result = ds.fetch_records(_NAIVE_START, _NAIVE_END)
        assert result == []
