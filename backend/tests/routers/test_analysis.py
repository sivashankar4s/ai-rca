"""Tests for the analysis router — POST /api/failures, POST /api/analyze, GET /api/providers."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.db.session import get_db
from backend.main import app
from backend.models.schemas import FailureRecord

_CLIENT = TestClient(app)

_DEFAULT_PROJECT_ID = uuid.uuid4()

_FAKE_RECORD = FailureRecord(
    file_trace_id="trace-001",
    application_name="app1",
    component_name="dp-lz-s3-event-processor",
    organization="org1",
    error_code="S3_PUT_FAILED",
    stage="lz-processor",
    status="FAILED",
    event_created_ts=datetime(2026, 6, 16, 9, 13, 9, tzinfo=UTC),
)


def _mock_ds(records: list[FailureRecord] | None = None) -> MagicMock:
    """Return a mock DataSourceStrategy whose fetch_records returns ``records``."""
    mock = MagicMock()
    mock.fetch_records.return_value = records if records is not None else [_FAKE_RECORD]
    return mock


def _fake_get_db() -> Iterator[MagicMock]:
    yield MagicMock()


@pytest.fixture(autouse=True)
def _db_mocks() -> Iterator[tuple[MagicMock, MagicMock]]:
    """Override get_db and stub the persistence repos so router tests never touch a real DB."""
    app.dependency_overrides[get_db] = _fake_get_db
    with (
        patch(
            "backend.routers.analysis.get_or_create_default_project",
            return_value=MagicMock(id=_DEFAULT_PROJECT_ID),
        ) as get_project,
        patch("backend.routers.analysis.upsert_failure_records") as upsert,
    ):
        yield get_project, upsert
    app.dependency_overrides.clear()


class TestPostFailures:
    def test_returns_200_with_response_shape(self) -> None:
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds()):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["time_range"] == "1d"
        assert body["total"] == 1
        assert isinstance(body["records"], list)
        assert len(body["records"]) == 1

    def test_1h_time_range_window(self) -> None:
        """1h time_range must pass start ~ now-1h, end ~ now to fetch_records."""
        mock_ds = _mock_ds([])
        before = datetime.now(UTC)
        with patch("backend.routers.analysis.get_data_source", return_value=mock_ds):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1h"})
        after = datetime.now(UTC)
        assert resp.status_code == 200
        start, end = mock_ds.fetch_records.call_args[0][:2]
        assert before - timedelta(hours=1, seconds=5) <= start <= after - timedelta(hours=1)
        assert before <= end <= after + timedelta(seconds=5)

    def test_1w_time_range_window(self) -> None:
        """1w time_range must span approximately 7 days."""
        mock_ds = _mock_ds([])
        with patch("backend.routers.analysis.get_data_source", return_value=mock_ds):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1w"})
        assert resp.status_code == 200
        start, end = mock_ds.fetch_records.call_args[0][:2]
        delta = end - start
        assert timedelta(days=6, hours=23) <= delta <= timedelta(days=7, seconds=5)

    def test_custom_time_range_uses_provided_dates(self) -> None:
        """CUSTOM time_range passes the request's start/end to fetch_records."""
        mock_ds = _mock_ds([])
        payload = {
            "time_range": "custom",
            "start": "2026-06-10T00:00:00Z",
            "end": "2026-06-16T23:59:59Z",
        }
        with patch("backend.routers.analysis.get_data_source", return_value=mock_ds):
            resp = _CLIENT.post("/api/failures", json=payload)
        assert resp.status_code == 200
        start, end = mock_ds.fetch_records.call_args[0][:2]
        assert start.year == 2026 and start.month == 6 and start.day == 10
        assert end.year == 2026 and end.month == 6 and end.day == 16

    def test_custom_missing_start_end_returns_422(self) -> None:
        resp = _CLIENT.post("/api/failures", json={"time_range": "custom"})
        assert resp.status_code == 422

    def test_component_filter_passed_to_fetch_records(self) -> None:
        mock_ds = _mock_ds([])
        payload = {"time_range": "1d", "component": "dp-fhir-transformer"}
        with patch("backend.routers.analysis.get_data_source", return_value=mock_ds):
            resp = _CLIENT.post("/api/failures", json=payload)
        assert resp.status_code == 200
        _, _, component = mock_ds.fetch_records.call_args[0]
        assert component == "dp-fhir-transformer"

    # T004 — data_source override forwarding
    def test_data_source_athena_forwarded_to_factory(self) -> None:
        """data_source='athena' is forwarded to get_data_source."""
        mock_ds = _mock_ds([])
        with patch(
            "backend.routers.analysis.get_data_source", return_value=mock_ds
        ) as mock_factory:
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "data_source": "athena"})
        assert resp.status_code == 200
        mock_factory.assert_called_once_with("athena")

    def test_data_source_postgres_forwarded_to_factory(self) -> None:
        """data_source='postgres' is forwarded to get_data_source (T004)."""
        mock_ds = _mock_ds([])
        with patch(
            "backend.routers.analysis.get_data_source", return_value=mock_ds
        ) as mock_factory:
            resp = _CLIENT.post(
                "/api/failures", json={"time_range": "1d", "data_source": "postgres"}
            )
        assert resp.status_code == 200
        mock_factory.assert_called_once_with("postgres")

    def test_no_data_source_passes_none_to_factory(self) -> None:
        """When data_source is omitted, get_data_source(None) is called."""
        mock_ds = _mock_ds([])
        with patch(
            "backend.routers.analysis.get_data_source", return_value=mock_ds
        ) as mock_factory:
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.status_code == 200
        mock_factory.assert_called_once_with(None)

    # T005 — rejection of invalid / unavailable selections
    def test_unknown_data_source_literal_returns_422(self) -> None:
        """A value outside Literal['athena','postgres'] is rejected by Pydantic (T005)."""
        resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "data_source": "mysql"})
        assert resp.status_code == 422

    def test_unavailable_data_source_returns_400(self) -> None:
        """When the registry raises ValueError, the router returns 400 (T005/T007)."""
        with patch(
            "backend.routers.analysis.get_data_source",
            side_effect=ValueError("Unknown data_source_provider: 'athena'"),
        ):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "data_source": "athena"})
        assert resp.status_code == 400
        assert "athena" in resp.json()["detail"]

    def test_total_matches_record_count(self) -> None:
        records = [_FAKE_RECORD, _FAKE_RECORD, _FAKE_RECORD]
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds(records)):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.json()["total"] == 3
        assert len(resp.json()["records"]) == 3

    def test_invalid_time_range_returns_422(self) -> None:
        resp = _CLIENT.post("/api/failures", json={"time_range": "2h"})
        assert resp.status_code == 422

    def test_fetched_records_are_persisted(
        self, _db_mocks: tuple[MagicMock, MagicMock]
    ) -> None:
        get_project, upsert = _db_mocks
        records = [_FAKE_RECORD]
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds(records)):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.status_code == 200
        get_project.assert_called_once()
        upsert.assert_called_once()
        args = upsert.call_args[0]
        assert args[1] == _DEFAULT_PROJECT_ID
        assert args[2] == records

    def test_trace_id_filters_response_but_persists_all(
        self, _db_mocks: tuple[MagicMock, MagicMock]
    ) -> None:
        _, upsert = _db_mocks
        r1 = FailureRecord(file_trace_id="trace-001", status="FAILED")
        r2 = FailureRecord(file_trace_id="trace-XYZ", status="FAILED")
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds([r1, r2])):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "trace_id": "001"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["records"][0]["file_trace_id"] == "trace-001"
        assert upsert.call_args[0][2] == [r1, r2]  # all persisted, pre-filter

    def test_trace_id_match_is_case_insensitive(self) -> None:
        r1 = FailureRecord(file_trace_id="trace-001")
        r2 = FailureRecord(file_trace_id="trace-XYZ")
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds([r1, r2])):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "trace_id": "TRACE"})
        assert resp.json()["total"] == 2

    def test_trace_id_no_match_returns_empty(self) -> None:
        r1 = FailureRecord(file_trace_id="trace-001")
        r2 = FailureRecord(file_trace_id=None)
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds([r1, r2])):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d", "trace_id": "zzz"})
        assert resp.json()["total"] == 0
        assert resp.json()["records"] == []


class TestPostAnalyze:
    """T008 — log_backend override forwarded to get_log_backend."""

    def test_log_backend_override_forwarded(self) -> None:
        """data_source='grafana_loki' is forwarded to get_log_backend."""
        with patch("backend.routers.analysis.get_log_backend", return_value=MagicMock()) as mock_lb:
            resp = _CLIENT.post(
                "/api/analyze",
                json={"time_range": "1d", "records": [], "log_backend": "grafana_loki"},
            )
        assert resp.status_code == 200
        mock_lb.assert_called_once_with("grafana_loki")

    def test_no_log_backend_uses_default_path(self) -> None:
        """Absent log_backend → get_log_backend(None) (default path)."""
        with patch("backend.routers.analysis.get_log_backend", return_value=MagicMock()) as mock_lb:
            resp = _CLIENT.post(
                "/api/analyze",
                json={"time_range": "1d", "records": []},
            )
        assert resp.status_code == 200
        mock_lb.assert_called_once_with(None)

    def test_response_includes_log_backend_used(self) -> None:
        with patch("backend.routers.analysis.get_log_backend", return_value=MagicMock()):
            resp = _CLIENT.post(
                "/api/analyze",
                json={"time_range": "1d", "records": [], "log_backend": "cloudwatch"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["log_backend_used"] == "cloudwatch"
        assert body["record_count"] == 0

    def test_unknown_log_backend_literal_returns_422(self) -> None:
        resp = _CLIENT.post(
            "/api/analyze",
            json={"time_range": "1d", "records": [], "log_backend": "splunk"},
        )
        assert resp.status_code == 422

    def test_record_count_reflects_input(self) -> None:
        records = [{"file_trace_id": f"t{i}"} for i in range(3)]
        with patch("backend.routers.analysis.get_log_backend", return_value=MagicMock()):
            resp = _CLIENT.post(
                "/api/analyze",
                json={"time_range": "1d", "records": records},
            )
        assert resp.status_code == 200
        assert resp.json()["record_count"] == 3


class TestGetProviders:
    """T010 — GET /api/providers returns real availability."""

    def test_returns_200_with_expected_shape(self) -> None:
        resp = _CLIENT.get("/api/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert "data_sources" in body
        assert "log_backends" in body
        assert isinstance(body["data_sources"], list)
        assert isinstance(body["log_backends"], list)

    def test_exactly_one_data_source_default(self) -> None:
        resp = _CLIENT.get("/api/providers")
        data_sources = resp.json()["data_sources"]
        defaults = [ds for ds in data_sources if ds["is_default"]]
        assert len(defaults) == 1

    def test_exactly_one_log_backend_default(self) -> None:
        resp = _CLIENT.get("/api/providers")
        log_backends = resp.json()["log_backends"]
        defaults = [lb for lb in log_backends if lb["is_default"]]
        assert len(defaults) == 1

    def test_data_sources_contain_athena_and_postgres(self) -> None:
        resp = _CLIENT.get("/api/providers")
        ids = {ds["id"] for ds in resp.json()["data_sources"]}
        assert "athena" in ids
        assert "postgres" in ids

    def test_log_backends_contain_cloudwatch_and_grafana_loki(self) -> None:
        resp = _CLIENT.get("/api/providers")
        ids = {lb["id"] for lb in resp.json()["log_backends"]}
        assert "cloudwatch" in ids
        assert "grafana_loki" in ids

    def test_default_reflects_settings(self) -> None:
        """The default data source matches settings.data_source_provider."""
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "athena"
            mock_settings.log_analysis_provider = "cloudwatch"
            resp = _CLIENT.get("/api/providers")
        body = resp.json()
        athena = next(ds for ds in body["data_sources"] if ds["id"] == "athena")
        assert athena["is_default"] is True
        postgres = next(ds for ds in body["data_sources"] if ds["id"] == "postgres")
        assert postgres["is_default"] is False
