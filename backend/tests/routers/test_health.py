"""Router tests for GET /api/health/services — TestClient with health_service mocked."""

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schemas import (
    FailureRecord,
    FailuresResponse,
    HealthRun,
    HealthServiceType,
    HealthStatus,
    HealthWindow,
    ServiceHealth,
    ServiceHealthDetail,
    ServiceHealthResponse,
    TimeRange,
)

_CLIENT = TestClient(app)
_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)

_RANGE = {"start": "2026-06-29T12:00:00Z", "end": "2026-07-06T12:00:00Z"}


def _response(
    results: list[ServiceHealth], window: HealthWindow | None
) -> ServiceHealthResponse:
    return ServiceHealthResponse(
        window=window,
        generated_at=_NOW,
        start=datetime(2026, 6, 29, 12, tzinfo=UTC),
        end=_NOW,
        results=results,
    )


class TestGetServiceHealth:
    def test_returns_results_and_defaults_to_24h(self) -> None:
        result = ServiceHealth(
            service_type=HealthServiceType.GLUE_JOB,
            id="etl",
            label="etl",
            status=HealthStatus.UP,
            failure_count=2,
        )
        with patch(
            "backend.routers.health.health_service.check_all",
            return_value=_response([result], HealthWindow.H24),
        ) as mock_check:
            resp = _CLIENT.get("/api/health/services")
        assert resp.status_code == 200
        body = resp.json()
        assert body["window"] == "24h"
        assert body["results"][0]["id"] == "etl"
        assert body["results"][0]["failure_count"] == 2
        # Default window is passed through to the service.
        assert mock_check.call_args.args[1] == HealthWindow.H24

    def test_empty_results_when_nothing_configured(self) -> None:
        with patch(
            "backend.routers.health.health_service.check_all",
            return_value=_response([], HealthWindow.H24),
        ):
            resp = _CLIENT.get("/api/health/services")
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_window_query_param_forwarded(self) -> None:
        with patch(
            "backend.routers.health.health_service.check_all",
            return_value=_response([], HealthWindow.D7),
        ) as mock_check:
            resp = _CLIENT.get("/api/health/services?window=7d")
        assert resp.status_code == 200
        assert resp.json()["window"] == "7d"
        assert mock_check.call_args.args[1] == HealthWindow.D7

    def test_invalid_window_returns_422(self) -> None:
        resp = _CLIENT.get("/api/health/services?window=99y")
        assert resp.status_code == 422

    def test_custom_range_forwarded_and_window_ignored(self) -> None:
        with patch(
            "backend.routers.health.health_service.check_all",
            return_value=_response([], None),
        ) as mock_check:
            resp = _CLIENT.get(
                "/api/health/services"
                "?start=2026-06-29T00:00:00Z&end=2026-07-06T23:59:59Z&window=1h"
            )
        assert resp.status_code == 200
        assert resp.json()["window"] is None
        # Custom range wins: window arg passed as None, start/end forwarded.
        assert mock_check.call_args.args[1] is None
        assert mock_check.call_args.args[2] == datetime(2026, 6, 29, 0, 0, tzinfo=UTC)
        assert mock_check.call_args.args[3] == datetime(2026, 7, 6, 23, 59, 59, tzinfo=UTC)

    def test_invalid_custom_range_returns_400(self) -> None:
        # start after end — check_all raises ValueError, mapped to 400 by the app handler.
        resp = _CLIENT.get(
            "/api/health/services?start=2026-07-06T00:00:00Z&end=2026-06-29T00:00:00Z"
        )
        assert resp.status_code == 400

    def test_profile_param_forwarded(self) -> None:
        with patch(
            "backend.routers.health.health_service.check_all",
            return_value=_response([], HealthWindow.H24),
        ) as mock_check:
            resp = _CLIENT.get("/api/health/services?profile=Prod%20ETL")
        assert resp.status_code == 200
        # profile is the 4th positional/keyword arg passed to check_all.
        assert mock_check.call_args.kwargs.get("profile") == "Prod ETL"


class TestGetServiceRuns:
    def test_returns_run_history(self) -> None:
        detail = ServiceHealthDetail(
            service_type=HealthServiceType.GLUE_JOB,
            id="etl",
            label="etl",
            start=datetime(2026, 6, 29, 12, tzinfo=UTC),
            end=_NOW,
            runs=[HealthRun(run_id="r1", status="FAILED", is_failure=True, detail="boom")],
        )
        with patch(
            "backend.routers.health.health_service.get_detail", return_value=detail
        ) as mock_detail:
            resp = _CLIENT.post(
                "/api/health/services/runs",
                json={"service_type": "glue_job", "id": "etl", **_RANGE},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["runs"][0]["run_id"] == "r1"
        assert body["runs"][0]["is_failure"] is True
        assert mock_detail.call_args.args[1].id == "etl"

    def test_invalid_range_returns_422(self) -> None:
        resp = _CLIENT.post(
            "/api/health/services/runs",
            json={
                "service_type": "glue_job",
                "id": "etl",
                "start": "2026-07-06T12:00:00Z",
                "end": "2026-06-29T12:00:00Z",  # end before start
            },
        )
        assert resp.status_code == 422


class TestGetServiceFailures:
    def test_returns_failure_records(self) -> None:
        failures = FailuresResponse(
            total=1,
            time_range=TimeRange.CUSTOM,
            records=[FailureRecord(file_trace_id="req-1", status="FAILED", message="oom")],
        )
        with patch(
            "backend.routers.health.health_service.fetch_failures", return_value=failures
        ):
            resp = _CLIENT.post(
                "/api/health/services/failures",
                json={"service_type": "lambda_function", "id": "fn", **_RANGE},
            )
        assert resp.status_code == 200
        assert resp.json()["records"][0]["message"] == "oom"

    def test_runtime_error_returns_400(self) -> None:
        with patch(
            "backend.routers.health.health_service.fetch_failures",
            side_effect=RuntimeError("CloudWatch not configured"),
        ):
            resp = _CLIENT.post(
                "/api/health/services/failures",
                json={"service_type": "lambda_function", "id": "fn", **_RANGE},
            )
        assert resp.status_code == 400
        assert "CloudWatch" in resp.json()["detail"]
