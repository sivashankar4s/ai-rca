"""Tests for AthenaDataSource — all AWS calls stubbed via botocore.Stubber."""

from datetime import datetime
from unittest.mock import patch

import pytest
from botocore.stub import Stubber

from backend.providers.data_source.athena import AthenaDataSource

_START = datetime(2026, 6, 16, 0, 0, 0)
_END = datetime(2026, 6, 16, 23, 59, 59)

_QUERY_ID = "test-query-id-001"

# Minimal Athena API response shapes
_START_RESPONSE = {"QueryExecutionId": _QUERY_ID}

_STATUS_SUCCEEDED = {
    "QueryExecution": {
        "QueryExecutionId": _QUERY_ID,
        "Status": {"State": "SUCCEEDED"},
    }
}

_RESULTS_ONE_ROW = {
    "ResultSet": {
        "Rows": [
            # Header row
            {
                "Data": [
                    {"VarCharValue": "application_name"},
                    {"VarCharValue": "component_name"},
                    {"VarCharValue": "custom_key1"},
                    {"VarCharValue": "custom_key2"},
                    {"VarCharValue": "custom_key3"},
                    {"VarCharValue": "event_created_timestamp"},
                    {"VarCharValue": "event_inserted_timestamp"},
                    {"VarCharValue": "organization"},
                    {"VarCharValue": "status"},
                    {"VarCharValue": "event_data"},
                ]
            },
            # Data row
            {
                "Data": [
                    {"VarCharValue": "db11224"},
                    {"VarCharValue": "dp-lz-s3-event-processor"},
                    {"VarCharValue": "trace-abc"},
                    {"VarCharValue": "voice_abc.raw"},
                    {"VarCharValue": "dev-abc"},
                    {"VarCharValue": "2026-06-16 09:13:09.152000"},
                    {"VarCharValue": "2026-06-16 09:14:17.519000"},
                    {"VarCharValue": "db11224"},
                    {"VarCharValue": "FAILED"},
                    {"VarCharValue": '{"stage":"lz-processor","error_code":"S3_PUT_FAILED"}'},
                ]
            },
        ],
        "ResultSetMetadata": {"ColumnInfo": []},
    }
}

_RESULTS_EMPTY = {
    "ResultSet": {
        "Rows": [
            {
                "Data": [
                    {"VarCharValue": "application_name"},
                    {"VarCharValue": "component_name"},
                    {"VarCharValue": "custom_key1"},
                    {"VarCharValue": "custom_key2"},
                    {"VarCharValue": "custom_key3"},
                    {"VarCharValue": "event_created_timestamp"},
                    {"VarCharValue": "event_inserted_timestamp"},
                    {"VarCharValue": "organization"},
                    {"VarCharValue": "status"},
                    {"VarCharValue": "event_data"},
                ]
            }
        ],
        "ResultSetMetadata": {"ColumnInfo": []},
    }
}


def _make_ds() -> tuple[AthenaDataSource, Stubber]:
    ds = AthenaDataSource()
    stubber = Stubber(ds._client)
    return ds, stubber


class TestAthenaDataSource:
    def test_fetch_records_returns_parsed_failure_record(self) -> None:
        ds, stubber = _make_ds()
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_ONE_ROW)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        r = records[0]
        assert r.application_name == "db11224"
        assert r.component_name == "dp-lz-s3-event-processor"
        assert r.file_trace_id == "trace-abc"
        assert r.error_code == "S3_PUT_FAILED"
        assert r.stage == "lz-processor"
        assert r.status == "FAILED"

    def test_fetch_records_with_component_filter(self) -> None:
        ds, stubber = _make_ds()
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_ONE_ROW)

            records = ds.fetch_records(_START, _END, component="dp-lz-s3-event-processor")

        assert len(records) == 1

    def test_fetch_records_empty_result(self) -> None:
        ds, stubber = _make_ds()
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_EMPTY)

            records = ds.fetch_records(_START, _END)

        assert records == []

    def test_query_polls_until_succeeded(self) -> None:
        ds, stubber = _make_ds()
        status_running = {
            "QueryExecution": {
                "QueryExecutionId": _QUERY_ID,
                "Status": {"State": "RUNNING"},
            }
        }
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", status_running)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_EMPTY)

            with patch("time.sleep"):  # don't actually sleep in tests
                records = ds.fetch_records(_START, _END)

        assert records == []

    def test_query_failure_raises_runtime_error(self) -> None:
        ds, stubber = _make_ds()
        status_failed = {
            "QueryExecution": {
                "QueryExecutionId": _QUERY_ID,
                "Status": {"State": "FAILED", "StateChangeReason": "Syntax error"},
            }
        }
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", status_failed)

            with pytest.raises(RuntimeError, match="Athena query failed"):
                ds.fetch_records(_START, _END)

    def test_sql_contains_date_range(self) -> None:
        """Verify the SQL built for a date-range window contains the timestamps."""
        ds, stubber = _make_ds()
        captured_sql: list[str] = []

        original_start = ds._start_query

        def capturing_start(sql: str) -> str:
            captured_sql.append(sql)
            return original_start(sql)

        ds._start_query = capturing_start

        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_EMPTY)
            ds.fetch_records(_START, _END)

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        assert "2026-06-16" in sql
        assert "FAILED" in sql

    def test_raw_payload_is_populated(self) -> None:
        ds, stubber = _make_ds()
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", _RESULTS_ONE_ROW)

            records = ds.fetch_records(_START, _END)

        assert records[0].raw_payload is not None

    def _make_single_row_result(self, event_created_ts: str = "", event_data: str = "") -> dict:
        return {
            "ResultSet": {
                "Rows": [
                    {
                        "Data": [
                            {"VarCharValue": "application_name"},
                            {"VarCharValue": "component_name"},
                            {"VarCharValue": "custom_key1"},
                            {"VarCharValue": "custom_key2"},
                            {"VarCharValue": "custom_key3"},
                            {"VarCharValue": "event_created_timestamp"},
                            {"VarCharValue": "event_inserted_timestamp"},
                            {"VarCharValue": "organization"},
                            {"VarCharValue": "status"},
                            {"VarCharValue": "event_data"},
                        ]
                    },
                    {
                        "Data": [
                            {"VarCharValue": "app"},
                            {"VarCharValue": "comp"},
                            {"VarCharValue": "trace-x"},
                            {"VarCharValue": "f.raw"},
                            {"VarCharValue": "dev-x"},
                            {"VarCharValue": event_created_ts},
                            {"VarCharValue": ""},
                            {"VarCharValue": "org"},
                            {"VarCharValue": "FAILED"},
                            {"VarCharValue": event_data},
                        ]
                    },
                ],
                "ResultSetMetadata": {"ColumnInfo": []},
            }
        }

    def test_empty_timestamp_results_in_none_event_created_ts(self) -> None:
        """A row with an empty-string timestamp produces event_created_ts=None."""
        ds, stubber = _make_ds()
        result = self._make_single_row_result(event_created_ts="")
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", result)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        assert records[0].event_created_ts is None

    def test_no_microseconds_timestamp_is_parsed(self) -> None:
        """A timestamp without microseconds parses via the second format."""
        ds, stubber = _make_ds()
        result = self._make_single_row_result(event_created_ts="2026-06-16 10:00:00")
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", result)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        assert records[0].event_created_ts is not None

    def test_unparseable_timestamp_results_in_none(self) -> None:
        """A completely invalid timestamp string produces event_created_ts=None."""
        ds, stubber = _make_ds()
        result = self._make_single_row_result(event_created_ts="not-a-date")
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", result)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        assert records[0].event_created_ts is None

    def test_empty_event_data_yields_no_error_code(self) -> None:
        """An empty-string event_data produces error_code=None and stage=None."""
        ds, stubber = _make_ds()
        result = self._make_single_row_result(event_data="")
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", result)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        assert records[0].error_code is None

    def test_malformed_event_data_yields_no_error_code(self) -> None:
        """A non-JSON event_data string is silently ignored."""
        ds, stubber = _make_ds()
        result = self._make_single_row_result(event_data="not{{json")
        with stubber:
            stubber.add_response("start_query_execution", _START_RESPONSE)
            stubber.add_response("get_query_execution", _STATUS_SUCCEEDED)
            stubber.add_response("get_query_results", result)

            records = ds.fetch_records(_START, _END)

        assert len(records) == 1
        assert records[0].error_code is None
