"""Tests for the health-check providers — boto3 clients mocked at the boundary.

No real AWS calls. Covers status mapping, windowed failure counting, discovery, and
per-resource error degradation for Glue jobs, Glue workflows, Lambda, and DataSync.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.config import settings
from backend.models.schemas import FailureRecord, HealthServiceType, HealthStatus
from backend.providers.health_check._aws import build_client, in_window
from backend.providers.health_check.datasync import DataSyncHealthCheck
from backend.providers.health_check.glue_job import GlueJobHealthCheck
from backend.providers.health_check.glue_workflow import GlueWorkflowHealthCheck
from backend.providers.health_check.lambda_fn import LambdaHealthCheck
from backend.strategies.health_check import HealthCheckStrategy

_END = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
_START = _END - timedelta(hours=24)
_IN = _END - timedelta(hours=2)  # inside the window
_OUT = _END - timedelta(days=3)  # before the window


def _client_error(op: str = "Op") -> ClientError:
    return ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, op)


# ── Shared AWS helper ───────────────────────────────────────────────────────────


class TestBuildClient:
    def test_db_credentials_override_env(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_region", "us-east-1")
        monkeypatch.setattr(settings, "aws_access_key_id", "ENV_KEY")
        monkeypatch.setattr(settings, "aws_secret_access_key", "ENV_SECRET")
        with patch("backend.providers.health_check._aws.boto3.client") as mock_client:
            build_client(
                "glue",
                {
                    "access_key_id": "DB_KEY",
                    "secret_access_key": "DB_SECRET",
                    "region": "ap-south-1",
                },
            )
        _, kwargs = mock_client.call_args
        assert kwargs["region_name"] == "ap-south-1"
        assert kwargs["aws_access_key_id"] == "DB_KEY"
        assert kwargs["aws_secret_access_key"] == "DB_SECRET"

    def test_db_creds_do_not_inherit_env_session_token(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_session_token", "STALE_ENV_TOKEN")
        with patch("backend.providers.health_check._aws.boto3.client") as mock_client:
            build_client("lambda", {"access_key_id": "DB_KEY", "secret_access_key": "DB_SECRET"})
        _, kwargs = mock_client.call_args
        assert kwargs["aws_session_token"] is None

    def test_falls_back_to_env_when_no_db_creds(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "aws_region", "eu-west-1")
        monkeypatch.setattr(settings, "aws_access_key_id", "ENV_KEY")
        monkeypatch.setattr(settings, "aws_secret_access_key", "ENV_SECRET")
        monkeypatch.setattr(settings, "aws_session_token", "ENV_TOKEN")
        with patch("backend.providers.health_check._aws.boto3.client") as mock_client:
            build_client("datasync", None)
        _, kwargs = mock_client.call_args
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["aws_access_key_id"] == "ENV_KEY"
        assert kwargs["aws_session_token"] == "ENV_TOKEN"

    def test_in_window_boundaries(self) -> None:
        assert in_window(_IN, _START, _END) is True
        assert in_window(_OUT, _START, _END) is False
        assert in_window(None, _START, _END) is False


# ── Glue job ────────────────────────────────────────────────────────────────────


def _glue_job(client: MagicMock) -> GlueJobHealthCheck:
    with patch("backend.providers.health_check.glue_job.build_client", return_value=client):
        return GlueJobHealthCheck()


class TestGlueJobHealthCheck:
    def test_is_strategy_with_service_type(self) -> None:
        provider = _glue_job(MagicMock())
        assert isinstance(provider, HealthCheckStrategy)
        assert provider.service_type == HealthServiceType.GLUE_JOB

    def test_up_with_windowed_failure_count(self) -> None:
        client = MagicMock()
        client.get_job_runs.return_value = {
            "JobRuns": [
                {"JobRunState": "SUCCEEDED", "StartedOn": _END},
                {"JobRunState": "FAILED", "StartedOn": _IN},
                {"JobRunState": "FAILED", "StartedOn": _OUT},  # outside window
            ]
        }
        [result] = _glue_job(client).check(["etl"], _START, _END)
        assert result.status == HealthStatus.UP
        assert result.failure_count == 1
        assert result.last_activity_ts == _END

    def test_latest_failed_is_down(self) -> None:
        client = MagicMock()
        client.get_job_runs.return_value = {
            "JobRuns": [{"JobRunState": "FAILED", "StartedOn": _IN}]
        }
        [result] = _glue_job(client).check(["etl"], _START, _END)
        assert result.status == HealthStatus.DOWN
        assert result.failure_count == 1

    def test_no_runs_is_unknown(self) -> None:
        client = MagicMock()
        client.get_job_runs.return_value = {"JobRuns": []}
        [result] = _glue_job(client).check(["etl"], _START, _END)
        assert result.status == HealthStatus.UNKNOWN
        assert "no runs" in result.detail

    def test_client_error_is_unknown(self) -> None:
        client = MagicMock()
        client.get_job_runs.side_effect = _client_error("GetJobRuns")
        [result] = _glue_job(client).check(["etl"], _START, _END)
        assert result.status == HealthStatus.UNKNOWN
        assert "failed" in result.detail

    def test_discover_pages_job_names(self) -> None:
        client = MagicMock()
        client.list_jobs.side_effect = [
            {"JobNames": ["a"], "NextToken": "t"},
            {"JobNames": ["b"]},
        ]
        resources = _glue_job(client).discover()
        assert [r.id for r in resources] == ["a", "b"]

    def test_discover_error_raises_runtime(self) -> None:
        client = MagicMock()
        client.list_jobs.side_effect = _client_error("ListJobs")
        with pytest.raises(RuntimeError, match="Glue job discovery failed"):
            _glue_job(client).discover()

    def test_detail_maps_runs_in_window(self) -> None:
        client = MagicMock()
        client.get_job_runs.return_value = {
            "JobRuns": [
                {"Id": "r1", "JobRunState": "SUCCEEDED", "StartedOn": _END, "CompletedOn": _END},
                {"Id": "r2", "JobRunState": "FAILED", "StartedOn": _IN, "ErrorMessage": "boom"},
                {"Id": "r3", "JobRunState": "FAILED", "StartedOn": _OUT},  # outside window
            ]
        }
        detail = _glue_job(client).detail("etl", _START, _END)
        assert [r.run_id for r in detail.runs] == ["r1", "r2"]
        assert detail.runs[1].is_failure is True
        assert detail.runs[1].detail == "boom"

    def test_detail_client_error_sets_detail(self) -> None:
        client = MagicMock()
        client.get_job_runs.side_effect = _client_error("GetJobRuns")
        detail = _glue_job(client).detail("etl", _START, _END)
        assert detail.runs == []
        assert "failed" in detail.detail


# ── Glue workflow ───────────────────────────────────────────────────────────────


def _glue_wf(client: MagicMock) -> GlueWorkflowHealthCheck:
    with patch("backend.providers.health_check.glue_workflow.build_client", return_value=client):
        return GlueWorkflowHealthCheck()


class TestGlueWorkflowHealthCheck:
    def test_service_type(self) -> None:
        assert _glue_wf(MagicMock()).service_type == HealthServiceType.GLUE_WORKFLOW

    def test_error_run_down_and_counted(self) -> None:
        client = MagicMock()
        client.get_workflow_runs.return_value = {
            "Runs": [
                {"Status": "ERROR", "StartedOn": _IN},
                {"Status": "COMPLETED", "StartedOn": _IN, "Statistics": {"FailedActions": 2}},
            ]
        }
        [result] = _glue_wf(client).check(["wf"], _START, _END)
        assert result.status == HealthStatus.DOWN
        # ERROR run + COMPLETED-with-failed-actions run both count.
        assert result.failure_count == 2

    def test_completed_is_up_zero_failures(self) -> None:
        client = MagicMock()
        client.get_workflow_runs.return_value = {
            "Runs": [{"Status": "COMPLETED", "StartedOn": _IN}]
        }
        [result] = _glue_wf(client).check(["wf"], _START, _END)
        assert result.status == HealthStatus.UP
        assert result.failure_count == 0

    def test_discover_lists_workflows(self) -> None:
        client = MagicMock()
        client.list_workflows.return_value = {"Workflows": ["wf1", "wf2"]}
        assert [r.label for r in _glue_wf(client).discover()] == ["wf1", "wf2"]

    def test_detail_maps_runs_with_failure_reasons(self) -> None:
        client = MagicMock()
        client.get_workflow_runs.return_value = {
            "Runs": [
                {"WorkflowRunId": "w1", "Status": "ERROR", "StartedOn": _IN, "ErrorMessage": "bad"},
                {
                    "WorkflowRunId": "w2",
                    "Status": "COMPLETED",
                    "StartedOn": _IN,
                    "Statistics": {"FailedActions": 1},
                },
            ]
        }
        detail = _glue_wf(client).detail("wf", _START, _END)
        assert detail.runs[0].is_failure is True
        assert detail.runs[0].detail == "bad"
        assert detail.runs[1].is_failure is True
        assert "1 failed action" in detail.runs[1].detail


# ── Lambda ──────────────────────────────────────────────────────────────────────


def _lambda(lam: MagicMock) -> LambdaHealthCheck:
    with patch("backend.providers.health_check.lambda_fn.build_client", return_value=lam):
        return LambdaHealthCheck()


def _cw_source(records: list | None = None, error: Exception | None = None) -> MagicMock:
    """A stand-in CloudWatchDataSource whose fetch_records returns records or raises."""
    source = MagicMock()
    if error is not None:
        source.fetch_records.side_effect = error
    else:
        source.fetch_records.return_value = records or []
    return source


def _fail_record(rid: str) -> FailureRecord:
    return FailureRecord(file_trace_id=rid, status="FAILED")


class TestLambdaHealthCheck:
    def test_service_type(self) -> None:
        assert _lambda(MagicMock()).service_type == HealthServiceType.LAMBDA_FUNCTION

    def test_active_counts_failed_invocations_from_logs(self) -> None:
        lam = MagicMock()
        lam.get_function_configuration.return_value = {"State": "Active"}
        provider = _lambda(lam)
        source = _cw_source([_fail_record("r1"), _fail_record("r2"), _fail_record("r3")])
        with patch(
            "backend.providers.health_check.lambda_fn.CloudWatchDataSource", return_value=source
        ) as cw_cls:
            [result] = provider.check(["fn"], _START, _END)
        # Scoped to the function's own log group.
        assert cw_cls.call_args.kwargs["log_groups"] == ["/aws/lambda/fn"]
        assert result.status == HealthStatus.UP
        assert result.failure_count == 3

    def test_inactive_is_down(self) -> None:
        lam = MagicMock()
        lam.get_function_configuration.return_value = {"State": "Inactive"}
        provider = _lambda(lam)
        with patch(
            "backend.providers.health_check.lambda_fn.CloudWatchDataSource",
            return_value=_cw_source([]),
        ):
            [result] = provider.check(["fn"], _START, _END)
        assert result.status == HealthStatus.DOWN
        assert result.failure_count == 0

    def test_count_query_failure_degrades_to_zero(self) -> None:
        lam = MagicMock()
        lam.get_function_configuration.return_value = {"State": "Active"}
        provider = _lambda(lam)
        with patch(
            "backend.providers.health_check.lambda_fn.CloudWatchDataSource",
            return_value=_cw_source(error=RuntimeError("log group does not exist")),
        ):
            [result] = provider.check(["fn"], _START, _END)
        assert result.status == HealthStatus.UP
        assert result.failure_count == 0

    def test_error_is_unknown(self) -> None:
        lam = MagicMock()
        lam.get_function_configuration.side_effect = _client_error("GetFunctionConfiguration")
        [result] = _lambda(lam).check(["fn"], _START, _END)
        assert result.status == HealthStatus.UNKNOWN

    def test_discover_pages_functions(self) -> None:
        lam = MagicMock()
        lam.list_functions.side_effect = [
            {"Functions": [{"FunctionName": "f1"}], "NextMarker": "m"},
            {"Functions": [{"FunctionName": "f2"}]},
        ]
        assert [r.id for r in _lambda(lam).discover()] == ["f1", "f2"]


# ── DataSync ────────────────────────────────────────────────────────────────────

_ARN = "arn:aws:datasync:us-east-1:1:task/task-0abc"


def _datasync(client: MagicMock) -> DataSyncHealthCheck:
    with patch("backend.providers.health_check.datasync.build_client", return_value=client):
        return DataSyncHealthCheck()


class TestDataSyncHealthCheck:
    def test_service_type(self) -> None:
        assert _datasync(MagicMock()).service_type == HealthServiceType.DATASYNC_TASK

    def test_available_counts_only_in_window_errors(self) -> None:
        client = MagicMock()
        client.describe_task.return_value = {"Status": "AVAILABLE", "Name": "s3-to-efs"}
        client.list_task_executions.return_value = {
            "TaskExecutions": [
                {"TaskExecutionArn": f"{_ARN}/exec-1", "Status": "ERROR"},
                {"TaskExecutionArn": f"{_ARN}/exec-2", "Status": "ERROR"},
                {"TaskExecutionArn": f"{_ARN}/exec-3", "Status": "SUCCESS"},
            ]
        }
        client.describe_task_execution.side_effect = [
            {"StartTime": _IN},  # counted
            {"StartTime": _OUT},  # outside window
        ]
        [result] = _datasync(client).check([_ARN], _START, _END)
        assert result.status == HealthStatus.UP
        assert result.label == "s3-to-efs"
        assert result.failure_count == 1

    def test_unavailable_is_down(self) -> None:
        client = MagicMock()
        client.describe_task.return_value = {"Status": "UNAVAILABLE", "Name": "t"}
        client.list_task_executions.return_value = {"TaskExecutions": []}
        [result] = _datasync(client).check([_ARN], _START, _END)
        assert result.status == HealthStatus.DOWN
        assert result.failure_count == 0

    def test_error_is_unknown_keeps_arn_label(self) -> None:
        client = MagicMock()
        client.describe_task.side_effect = _client_error("DescribeTask")
        [result] = _datasync(client).check([_ARN], _START, _END)
        assert result.status == HealthStatus.UNKNOWN
        assert result.label == _ARN

    def test_discover_returns_arn_and_name(self) -> None:
        client = MagicMock()
        client.list_tasks.return_value = {
            "Tasks": [{"TaskArn": _ARN, "Name": "s3-to-efs", "Status": "AVAILABLE"}]
        }
        [resource] = _datasync(client).discover()
        assert resource.id == _ARN
        assert resource.label == "s3-to-efs"

    def test_detail_lists_in_window_executions(self) -> None:
        client = MagicMock()
        client.describe_task.return_value = {"Status": "AVAILABLE", "Name": "s3-to-efs"}
        client.list_task_executions.return_value = {
            "TaskExecutions": [
                {"TaskExecutionArn": f"{_ARN}/exec-1", "Status": "ERROR"},
                {"TaskExecutionArn": f"{_ARN}/exec-2", "Status": "SUCCESS"},
            ]
        }
        client.describe_task_execution.side_effect = [
            {"Status": "ERROR", "StartTime": _IN, "Result": {"ErrorDetail": "perm denied"}},
            {"Status": "SUCCESS", "StartTime": _OUT},  # outside window
        ]
        detail = _datasync(client).detail(_ARN, _START, _END)
        assert detail.label == "s3-to-efs"
        assert [r.run_id for r in detail.runs] == ["exec-1"]
        assert detail.runs[0].is_failure is True
        assert detail.runs[0].detail == "perm denied"

    def test_detail_error_sets_detail(self) -> None:
        client = MagicMock()
        client.describe_task.side_effect = _client_error("DescribeTask")
        detail = _datasync(client).detail(_ARN, _START, _END)
        assert detail.runs == []
        assert "failed" in detail.detail
