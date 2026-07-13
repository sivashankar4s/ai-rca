"""Tests for health_service.check_all — fan-out, window, and partial degradation.

The DB layer and providers are mocked; only the orchestration logic is exercised.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.models.schemas import (
    FailureRecord,
    HealthDetailRequest,
    HealthServiceType,
    HealthStatus,
    HealthWindow,
    ServiceHealth,
    ServiceHealthDetail,
)
from backend.services import health_service

_END = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
_START = _END - timedelta(days=7)


def _detail_req(
    service_type: HealthServiceType, rid: str, label: str | None = None
) -> HealthDetailRequest:
    return HealthDetailRequest(
        service_type=service_type, id=rid, label=label, start=_START, end=_END
    )


def _sh(service_type: HealthServiceType, rid: str) -> ServiceHealth:
    return ServiceHealth(service_type=service_type, id=rid, label=rid, status=HealthStatus.UP)


def test_empty_config_returns_no_results() -> None:
    with patch(
        "backend.services.health_service.config_repo.get_profile_resources",
        return_value={},
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24)
    assert resp.results == []
    assert resp.window == HealthWindow.H24


def test_no_config_row_returns_no_results() -> None:
    with patch(
        "backend.services.health_service.config_repo.get_profile_resources", return_value=None
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H1)
    assert resp.results == []


def test_fans_out_one_result_per_resource() -> None:
    cfg = {"glue_jobs": ["j1"], "lambda_functions": ["f1"]}
    glue = MagicMock()
    glue.check.return_value = [_sh(HealthServiceType.GLUE_JOB, "j1")]
    lam = MagicMock()
    lam.check.return_value = [_sh(HealthServiceType.LAMBDA_FUNCTION, "f1")]
    checkers = {
        HealthServiceType.GLUE_JOB: glue,
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: lam,
        HealthServiceType.DATASYNC_TASK: MagicMock(),
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ),
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24)
    ids = {r.id for r in resp.results}
    assert ids == {"j1", "f1"}


def test_profile_forwarded_and_name_echoed() -> None:
    cfg = {"name": "Prod ETL", "glue_jobs": ["j1"]}
    glue = MagicMock()
    glue.check.return_value = [_sh(HealthServiceType.GLUE_JOB, "j1")]
    checkers = {
        HealthServiceType.GLUE_JOB: glue,
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: MagicMock(),
        HealthServiceType.DATASYNC_TASK: MagicMock(),
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ) as gpr,
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24, profile="Prod ETL")
    assert resp.profile == "Prod ETL"
    assert gpr.call_args.args[1] == "Prod ETL"


def test_custom_range_passed_to_providers_and_echoed() -> None:
    cfg = {"glue_jobs": ["j1"]}
    start = datetime(2026, 6, 1, tzinfo=UTC)
    end = datetime(2026, 6, 8, tzinfo=UTC)
    glue = MagicMock()
    glue.check.return_value = [_sh(HealthServiceType.GLUE_JOB, "j1")]
    checkers = {
        HealthServiceType.GLUE_JOB: glue,
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: MagicMock(),
        HealthServiceType.DATASYNC_TASK: MagicMock(),
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ),
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), None, start, end)
    assert resp.window is None
    assert resp.start == start
    assert resp.end == end
    # The provider receives the exact custom bounds.
    assert glue.check.call_args.args[1] == start
    assert glue.check.call_args.args[2] == end


def test_invalid_custom_range_raises() -> None:
    with pytest.raises(ValueError, match="start must be before end"):
        health_service.check_all(
            MagicMock(),
            None,
            datetime(2026, 6, 8, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
        )


def test_range_over_cap_raises() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        health_service.check_all(
            MagicMock(),
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
        )


def test_total_failures_summed_across_results() -> None:
    cfg = {"glue_jobs": ["j1"], "lambda_functions": ["f1"]}
    glue = MagicMock()
    glue.check.return_value = [
        ServiceHealth(
            service_type=HealthServiceType.GLUE_JOB,
            id="j1",
            label="j1",
            status=HealthStatus.UP,
            failure_count=3,
        )
    ]
    lam = MagicMock()
    lam.check.return_value = [
        ServiceHealth(
            service_type=HealthServiceType.LAMBDA_FUNCTION,
            id="f1",
            label="f1",
            status=HealthStatus.DOWN,
            failure_count=4,
        )
    ]
    checkers = {
        HealthServiceType.GLUE_JOB: glue,
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: lam,
        HealthServiceType.DATASYNC_TASK: MagicMock(),
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ),
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24)
    assert resp.total_failures == 7


def test_empty_config_reports_zero_total_failures() -> None:
    with patch(
        "backend.services.health_service.config_repo.get_profile_resources",
        return_value={},
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24)
    assert resp.total_failures == 0


def test_provider_failure_degrades_to_unknown_others_survive() -> None:
    cfg = {"glue_jobs": ["j1"], "lambda_functions": ["f1"]}
    glue = MagicMock()
    glue.check.side_effect = RuntimeError("boom")
    lam = MagicMock()
    lam.check.return_value = [_sh(HealthServiceType.LAMBDA_FUNCTION, "f1")]
    checkers = {
        HealthServiceType.GLUE_JOB: glue,
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: lam,
        HealthServiceType.DATASYNC_TASK: MagicMock(),
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ),
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.H24)
    by_id = {r.id: r for r in resp.results}
    assert by_id["j1"].status == HealthStatus.UNKNOWN
    assert by_id["f1"].status == HealthStatus.UP


def test_datasync_ids_extracted_and_labelled_on_failure() -> None:
    arn = "arn:aws:datasync:us-east-1:1:task/task-1"
    cfg = {"datasync_tasks": [{"id": arn, "label": "nightly"}]}
    ds = MagicMock()
    ds.check.side_effect = RuntimeError("down")
    checkers = {
        HealthServiceType.GLUE_JOB: MagicMock(),
        HealthServiceType.GLUE_WORKFLOW: MagicMock(),
        HealthServiceType.LAMBDA_FUNCTION: MagicMock(),
        HealthServiceType.DATASYNC_TASK: ds,
    }
    with (
        patch(
            "backend.services.health_service.config_repo.get_profile_resources",
            return_value=cfg,
        ),
        patch("backend.services.health_service.get_health_checkers", return_value=checkers),
    ):
        resp = health_service.check_all(MagicMock(), HealthWindow.D7)
    [result] = resp.results
    assert result.id == arn
    assert result.label == "nightly"
    assert result.status == HealthStatus.UNKNOWN
    # The provider received the bare ARN, not the {id,label} dict.
    ds.check.assert_called_once()
    assert ds.check.call_args.args[0] == [arn]


# ── Drill-down: get_detail + fetch_failures ─────────────────────────────────────


def test_get_detail_dispatches_to_checker() -> None:
    req = _detail_req(HealthServiceType.GLUE_JOB, "j1")
    checker = MagicMock()
    checker.detail.return_value = ServiceHealthDetail(
        service_type=HealthServiceType.GLUE_JOB, id="j1", label="j1", start=_START, end=_END
    )
    checkers = {HealthServiceType.GLUE_JOB: checker}
    with patch("backend.services.health_service.get_health_checkers", return_value=checkers):
        result = health_service.get_detail(MagicMock(), req)
    assert result.id == "j1"
    checker.detail.assert_called_once_with("j1", _START, _END)


def test_get_detail_degrades_on_error() -> None:
    req = _detail_req(HealthServiceType.GLUE_JOB, "j1")
    checker = MagicMock()
    checker.detail.side_effect = RuntimeError("boom")
    checkers = {HealthServiceType.GLUE_JOB: checker}
    with patch("backend.services.health_service.get_health_checkers", return_value=checkers):
        result = health_service.get_detail(MagicMock(), req)
    assert result.runs == []
    assert "detail failed" in result.detail


def test_get_detail_lambda_lists_failed_invocations_from_logs() -> None:
    req = _detail_req(HealthServiceType.LAMBDA_FUNCTION, "fn")
    source = MagicMock()
    source.fetch_records.return_value = [
        FailureRecord(
            file_trace_id="req-1", status="FAILED", message="oom", event_created_ts=_END
        )
    ]
    with patch(
        "backend.services.health_service.get_cloudwatch_source", return_value=source
    ) as gcs:
        result = health_service.get_detail(MagicMock(), req)
    # Scoped to the function's own log group, not the globally-configured groups.
    assert gcs.call_args.args[1] == ["/aws/lambda/fn"]
    assert len(result.runs) == 1
    assert result.runs[0].run_id == "req-1"
    assert result.runs[0].is_failure is True
    assert result.runs[0].detail == "oom"


def test_get_detail_lambda_degrades_when_no_log_group() -> None:
    req = _detail_req(HealthServiceType.LAMBDA_FUNCTION, "fn")
    source = MagicMock()
    source.fetch_records.side_effect = RuntimeError("log group does not exist")
    with patch("backend.services.health_service.get_cloudwatch_source", return_value=source):
        result = health_service.get_detail(MagicMock(), req)
    assert result.runs == []
    assert "log group" in result.detail


def test_fetch_failures_lambda_uses_own_log_group() -> None:
    req = _detail_req(HealthServiceType.LAMBDA_FUNCTION, "fn")
    source = MagicMock()
    source.fetch_records.return_value = [FailureRecord(file_trace_id="abc", status="FAILED")]
    with patch(
        "backend.services.health_service.get_cloudwatch_source", return_value=source
    ) as gcs:
        resp = health_service.fetch_failures(MagicMock(), req)
    assert resp.total == 1
    assert gcs.call_args.args[1] == ["/aws/lambda/fn"]
    # No component filter — the log group already isolates the function.
    source.fetch_records.assert_called_once_with(_START, _END)


def test_fetch_failures_glue_uses_configured_source_and_name() -> None:
    req = _detail_req(HealthServiceType.GLUE_JOB, "etl")
    source = MagicMock()
    source.fetch_records.return_value = []
    with patch("backend.services.health_service.get_data_source", return_value=source) as gds:
        health_service.fetch_failures(MagicMock(), req)
    assert gds.call_args.args[0] == "cloudwatch"
    assert source.fetch_records.call_args.args[2] == "etl"


def test_fetch_failures_datasync_uses_label_as_component() -> None:
    arn = "arn:aws:datasync:us-east-1:1:task/task-1"
    req = _detail_req(HealthServiceType.DATASYNC_TASK, arn, label="nightly")
    source = MagicMock()
    source.fetch_records.return_value = []
    with patch("backend.services.health_service.get_data_source", return_value=source):
        health_service.fetch_failures(MagicMock(), req)
    assert source.fetch_records.call_args.args[2] == "nightly"
