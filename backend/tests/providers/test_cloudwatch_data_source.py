"""Tests for CloudWatchDataSource — boto3 logs client mocked at the boundary.

No real AWS calls, no real network, no real sleeps.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.providers.data_source.cloudwatch import CloudWatchDataSource

_START = datetime(2026, 6, 29, 0, 0, 0)
_END = datetime(2026, 6, 29, 23, 59, 59)

_RID = "792362a0-8f87-5580-8a30-001cb998b40b"
_LOG = "123456789012:/aws/lambda/my-monitoring-fn"
_TS = "2026-06-29 08:59:42.175"
_ERROR_MSG = (
    "[ERROR]\t2026-06-29T08:59:42.175Z\t"
    f"{_RID}\t"
    "[MONITORING] data_builder returned None or empty, skipping monitoring."
)


@pytest.fixture(autouse=True)
def _set_log_groups(monkeypatch):
    """Most tests need a configured log group."""
    monkeypatch.setattr(settings, "cloudwatch_log_groups", ["/aws/lambda/my-monitoring-fn"])
    monkeypatch.setattr(settings, "cloudwatch_query_timeout", 60)


def _row(fields: dict[str, str]) -> list[dict[str, str]]:
    return [{"field": k, "value": v} for k, v in fields.items()]


def _error_row(
    ts: str = _TS,
    message: str = _ERROR_MSG,
    rid: str | None = _RID,
    log: str = _LOG,
    stream: str = "2026/06/29/[$LATEST]abc",
) -> list[dict[str, str]]:
    fields = {"@timestamp": ts, "@message": message, "@log": log, "@logStream": stream}
    if rid is not None:
        fields["@requestId"] = rid
    return _row(fields)


def _report_row(
    message: str,
    max_mem: str | None = None,
    mem_size: str | None = None,
    rid: str = _RID,
    ts: str = _TS,
    log: str = _LOG,
    type_: str = "REPORT",
) -> list[dict[str, str]]:
    fields = {
        "@timestamp": ts,
        "@message": message,
        "@requestId": rid,
        "@log": log,
        "@logStream": "stream-1",
        "@type": type_,
    }
    if max_mem is not None:
        fields["@maxMemoryUsed"] = max_mem
    if mem_size is not None:
        fields["@memorySize"] = mem_size
    return _row(fields)


def _make_ds() -> tuple[CloudWatchDataSource, MagicMock]:
    with patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client:
        client = MagicMock()
        mock_client.return_value = client
        ds = CloudWatchDataSource()
    return ds, client


def _run(ds: CloudWatchDataSource, client: MagicMock, rows: list) -> list:
    client.start_query.return_value = {"queryId": "q-1"}
    client.get_query_results.return_value = {"status": "Complete", "results": rows}
    return ds.fetch_records(_START, _END)


class TestCloudWatchDataSource:
    def test_single_error_line_yields_one_record(self) -> None:
        ds, client = _make_ds()
        records = _run(ds, client, [_error_row()])
        assert len(records) == 1
        r = records[0]
        assert r.file_trace_id == _RID
        assert r.component_name == "my-monitoring-fn"
        assert r.status == "FAILED"
        assert r.message is not None
        assert "data_builder returned None" in r.message
        assert r.event_created_ts == datetime(2026, 6, 29, 8, 59, 42, 175000)
        assert r.raw_payload is not None
        assert r.raw_payload["request_id"] == _RID
        assert r.raw_payload["log_group"] == "/aws/lambda/my-monitoring-fn"
        assert r.raw_payload["log_stream"] == "2026/06/29/[$LATEST]abc"
        assert r.raw_payload["report"] is None
        assert len(r.raw_payload["lines"]) == 1

    def test_multiple_error_lines_consolidated_and_deduped(self) -> None:
        ds, client = _make_ds()
        second = _error_row(
            ts="2026-06-29 08:59:43.000",
            message=(f"[ERROR]\t2026-06-29T08:59:43.000Z\t{_RID}\tSecond distinct failure detail."),
        )
        duplicate = _error_row()  # identical text as the first
        records = _run(ds, client, [_error_row(), second, duplicate])
        assert len(records) == 1
        msg = records[0].message
        # Distinct messages both present, duplicate collapsed (appears once).
        assert "data_builder returned None" in msg
        assert "Second distinct failure detail." in msg
        assert msg.count("data_builder returned None") == 1
        assert len(records[0].raw_payload["lines"]) == 3

    def test_anomalous_report_timeout_yields_record(self) -> None:
        ds, client = _make_ds()
        row = _report_row(
            message=f"RequestId: {_RID} Task timed out after 3.00 seconds",
            type_="platform",
        )
        records = _run(ds, client, [row])
        assert len(records) == 1
        assert "Task timed out" in records[0].message
        # Not a REPORT line -> no report metrics attached.
        assert records[0].raw_payload["report"] is None
        assert "Task timed out" in records[0].raw_payload["failure_reasons"]

    def test_oom_report_yields_record(self) -> None:
        ds, client = _make_ds()
        row = _report_row(
            message=(
                f"REPORT RequestId: {_RID} Duration: 2506.33 ms Billed Duration: "
                "3997 ms Memory Size: 1024 MB Max Memory Used: 1024 MB"
            ),
            max_mem="1073741824",
            mem_size="1073741824",
        )
        records = _run(ds, client, [row])
        assert len(records) == 1
        assert "Out of memory: 1024MB" in records[0].message
        assert records[0].raw_payload["report"] is not None
        assert records[0].raw_payload["report"]["max_memory_used"] == 1073741824

    def test_successful_report_alone_yields_no_record(self) -> None:
        ds, client = _make_ds()
        row = _report_row(
            message=(
                f"REPORT RequestId: {_RID} Duration: 100.0 ms Memory Size: 1024 MB "
                "Max Memory Used: 245 MB"
            ),
            max_mem="256901120",
            mem_size="1073741824",
        )
        records = _run(ds, client, [row])
        assert records == []

    def test_error_indicator_report_yields_record(self) -> None:
        ds, client = _make_ds()
        row = _report_row(
            message=f'REPORT RequestId: {_RID} {{"errorMessage": "boom"}}',
        )
        records = _run(ds, client, [row])
        assert len(records) == 1
        assert "errorMessage" in records[0].message

    def test_to_int_handles_non_numeric_metric(self) -> None:
        ds, client = _make_ds()
        row = _report_row(
            message=f"REPORT RequestId: {_RID} Duration: 100.0 ms",
            max_mem="not-a-number",
            mem_size="1073741824",
        )
        # Non-numeric maxMemoryUsed -> no OOM, no other anomaly -> no record.
        records = _run(ds, client, [row])
        assert records == []

    def test_failed_error_then_successful_report_attaches_metrics(self) -> None:
        ds, client = _make_ds()
        report = _report_row(
            message=(f"REPORT RequestId: {_RID} Duration: 100.0 ms Max Memory Used: 245 MB"),
            max_mem="256901120",
            mem_size="1073741824",
            ts="2026-06-29 08:59:44.000",
        )
        records = _run(ds, client, [_error_row(), report])
        assert len(records) == 1
        assert records[0].raw_payload["report"] is not None
        # Earliest timestamp from the [ERROR] line, not the later REPORT line.
        assert records[0].event_created_ts == datetime(2026, 6, 29, 8, 59, 42, 175000)

    def test_component_filter_included_in_query(self) -> None:
        ds, client = _make_ds()
        client.start_query.return_value = {"queryId": "q-1"}
        client.get_query_results.return_value = {"status": "Complete", "results": []}
        ds.fetch_records(_START, _END, component="my-monitoring-fn")
        query = client.start_query.call_args.kwargs["queryString"]
        assert "filter @log like /my-monitoring-fn/" in query
        assert "sort @timestamp asc" in query
        # log groups and epoch bounds are passed through.
        assert client.start_query.call_args.kwargs["logGroupNames"] == [
            "/aws/lambda/my-monitoring-fn"
        ]
        assert isinstance(client.start_query.call_args.kwargs["startTime"], int)

    def test_empty_results_returns_empty_list(self) -> None:
        ds, client = _make_ds()
        records = _run(ds, client, [])
        assert records == []

    def test_poll_loops_until_complete(self) -> None:
        ds, client = _make_ds()
        client.start_query.return_value = {"queryId": "q-1"}
        client.get_query_results.side_effect = [
            {"status": "Running", "results": []},
            {"status": "Complete", "results": [_error_row()]},
        ]
        with patch("backend.providers.data_source.cloudwatch.time.sleep"):
            records = ds.fetch_records(_START, _END)
        assert len(records) == 1

    def test_failed_status_raises_runtime_error(self) -> None:
        ds, client = _make_ds()
        client.start_query.return_value = {"queryId": "q-1"}
        client.get_query_results.return_value = {"status": "Failed", "results": []}
        with pytest.raises(RuntimeError, match="CloudWatch query failed"):
            ds.fetch_records(_START, _END)

    def test_query_timeout_raises_runtime_error(self, monkeypatch) -> None:
        ds, client = _make_ds()
        monkeypatch.setattr(settings, "cloudwatch_query_timeout", 0)
        client.start_query.return_value = {"queryId": "q-1"}
        client.get_query_results.return_value = {"status": "Running", "results": []}
        with patch(
            "backend.providers.data_source.cloudwatch.time.monotonic",
            side_effect=[0.0, 0.0],
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                ds.fetch_records(_START, _END)

    def test_empty_log_groups_raises_runtime_error(self, monkeypatch) -> None:
        ds, _client = _make_ds()
        monkeypatch.setattr(settings, "cloudwatch_log_groups", [])
        with pytest.raises(RuntimeError, match="log groups to be configured"):
            ds.fetch_records(_START, _END)

    def test_aws_credentials_override_env(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_region", "us-east-1")
        monkeypatch.setattr(settings, "aws_access_key_id", "ENV_KEY")
        monkeypatch.setattr(settings, "aws_secret_access_key", "ENV_SECRET")
        with patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client:
            CloudWatchDataSource(
                aws_credentials={
                    "access_key_id": "DB_KEY",
                    "secret_access_key": "DB_SECRET",
                    "region": "ap-south-1",
                }
            )
        _, kwargs = mock_client.call_args
        assert kwargs["region_name"] == "ap-south-1"
        assert kwargs["aws_access_key_id"] == "DB_KEY"
        assert kwargs["aws_secret_access_key"] == "DB_SECRET"

    def test_db_credentials_do_not_inherit_env_session_token(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_session_token", "STALE_ENV_TOKEN")
        with patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client:
            CloudWatchDataSource(
                aws_credentials={"access_key_id": "DB_KEY", "secret_access_key": "DB_SECRET"}
            )
        _, kwargs = mock_client.call_args
        assert kwargs["aws_session_token"] is None

    def test_db_session_token_is_used(self) -> None:
        with patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client:
            CloudWatchDataSource(
                aws_credentials={
                    "access_key_id": "DB_KEY",
                    "secret_access_key": "DB_SECRET",
                    "session_token": "DB_TOKEN",
                }
            )
        _, kwargs = mock_client.call_args
        assert kwargs["aws_session_token"] == "DB_TOKEN"

    def test_falls_back_to_env_credentials_when_absent(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_session_token", "ENV_TOKEN")
        monkeypatch.setattr(settings, "aws_region", "eu-west-1")
        monkeypatch.setattr(settings, "aws_access_key_id", "ENV_KEY")
        monkeypatch.setattr(settings, "aws_secret_access_key", "ENV_SECRET")
        with patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client:
            CloudWatchDataSource()
        _, kwargs = mock_client.call_args
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["aws_access_key_id"] == "ENV_KEY"
        assert kwargs["aws_secret_access_key"] == "ENV_SECRET"
        assert kwargs["aws_session_token"] == "ENV_TOKEN"

    def test_list_log_groups_returns_names_across_pages(self) -> None:
        ds, client = _make_ds()
        client.describe_log_groups.side_effect = [
            {"logGroups": [{"logGroupName": "/aws/lambda/a"}], "nextToken": "t1"},
            {"logGroups": [{"logGroupName": "/aws/lambda/b"}]},
        ]
        assert ds.list_log_groups("/aws/lambda/") == ["/aws/lambda/a", "/aws/lambda/b"]

    def test_list_log_groups_forwards_prefix(self) -> None:
        ds, client = _make_ds()
        client.describe_log_groups.return_value = {"logGroups": []}
        ds.list_log_groups("/aws-glue/")
        _, kwargs = client.describe_log_groups.call_args
        assert kwargs["logGroupNamePrefix"] == "/aws-glue/"

    def test_list_log_groups_omits_prefix_when_absent(self) -> None:
        ds, client = _make_ds()
        client.describe_log_groups.return_value = {"logGroups": []}
        ds.list_log_groups()
        _, kwargs = client.describe_log_groups.call_args
        assert "logGroupNamePrefix" not in kwargs

    def test_list_log_groups_wraps_client_error(self) -> None:
        ds, client = _make_ds()
        client.describe_log_groups.side_effect = BotoCoreError()
        with pytest.raises(RuntimeError, match="log group discovery failed"):
            ds.list_log_groups()

    def test_row_without_request_id_is_skipped(self) -> None:
        ds, client = _make_ds()
        bad = _row({"@timestamp": _TS, "@message": "[ERROR] no id present here"})
        records = _run(ds, client, [bad, _error_row()])
        assert len(records) == 1
        assert records[0].file_trace_id == _RID

    def test_request_id_parsed_from_message_when_field_absent(self) -> None:
        ds, client = _make_ds()
        # No @requestId field; the UUID is embedded in the [ERROR] message.
        row = _error_row(rid=None)
        records = _run(ds, client, [row])
        assert len(records) == 1
        assert records[0].file_trace_id == _RID

    def test_unparseable_and_empty_timestamps_yield_none(self) -> None:
        ds, client = _make_ds()
        row_empty = _error_row(
            ts="",
            log="",
            message=f"[ERROR]\tx\t{_RID}\tfirst error",
        )
        row_bad = _error_row(
            ts="not-a-date",
            log="",
            message=f"[ERROR]\ty\t{_RID}\tsecond error",
        )
        records = _run(ds, client, [row_empty, row_bad])
        assert len(records) == 1
        assert records[0].event_created_ts is None
        assert records[0].component_name is None
        assert records[0].raw_payload["log_group"] is None

    def test_error_line_without_tab_structure_uses_full_message(self) -> None:
        ds, client = _make_ds()
        row = _error_row(message="[ERROR] inline failure without tab fields")
        records = _run(ds, client, [row])
        assert len(records) == 1
        assert records[0].message == "[ERROR] inline failure without tab fields"

    def test_start_query_boto_error_wrapped(self) -> None:
        ds, client = _make_ds()
        client.start_query.side_effect = BotoCoreError()
        with pytest.raises(RuntimeError, match="CloudWatch query failed"):
            ds.fetch_records(_START, _END)

    def _not_found(self, group: str) -> ClientError:
        return ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": f"Log group '{group}' does not exist for account ID '1'",
                }
            },
            "StartQuery",
        )

    def test_nonexistent_log_group_dropped_and_retried(self, monkeypatch) -> None:
        monkeypatch.setattr(
            settings, "cloudwatch_log_groups", ["/aws/lambda", "/aws/lambda/real-fn"]
        )
        ds, client = _make_ds()
        client.start_query.side_effect = [
            self._not_found("/aws/lambda"),
            {"queryId": "q-1"},
        ]
        client.get_query_results.return_value = {"status": "Complete", "results": []}
        ds.fetch_records(_START, _END)
        # Second call retried with only the valid group.
        assert client.start_query.call_args.kwargs["logGroupNames"] == ["/aws/lambda/real-fn"]

    def test_all_log_groups_missing_raises_clear_error(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "cloudwatch_log_groups", ["/aws/lambda"])
        ds, client = _make_ds()
        client.start_query.side_effect = self._not_found("/aws/lambda")
        with pytest.raises(RuntimeError, match="none of the configured log groups exist"):
            ds.fetch_records(_START, _END)

    def test_non_resource_client_error_still_raises(self) -> None:
        ds, client = _make_ds()
        client.start_query.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "no"}}, "StartQuery"
        )
        with pytest.raises(RuntimeError, match="CloudWatch query failed"):
            ds.fetch_records(_START, _END)

    def test_get_results_boto_error_wrapped(self) -> None:
        ds, client = _make_ds()
        client.start_query.return_value = {"queryId": "q-1"}
        client.get_query_results.side_effect = ClientError(
            {"Error": {"Code": "X", "Message": "y"}}, "GetQueryResults"
        )
        with pytest.raises(RuntimeError, match="CloudWatch query failed"):
            ds.fetch_records(_START, _END)
