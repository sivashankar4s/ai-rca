"""Tests for POST /api/failures — router-level integration tests using TestClient."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schemas import FailureRecord

_CLIENT = TestClient(app)

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

    def test_data_source_field_selects_provider(self) -> None:
        """data_source field is forwarded to get_data_source."""
        mock_ds = _mock_ds([])
        with patch(
            "backend.routers.analysis.get_data_source", return_value=mock_ds
        ) as mock_factory:
            resp = _CLIENT.post(
                "/api/failures", json={"time_range": "1d", "data_source": "athena"}
            )
        assert resp.status_code == 200
        mock_factory.assert_called_once_with("athena")

    def test_total_matches_record_count(self) -> None:
        records = [_FAKE_RECORD, _FAKE_RECORD, _FAKE_RECORD]
        with patch("backend.routers.analysis.get_data_source", return_value=_mock_ds(records)):
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.json()["total"] == 3
        assert len(resp.json()["records"]) == 3

    def test_no_data_source_field_passes_none_to_factory(self) -> None:
        """When data_source is omitted, get_data_source(None) is called."""
        mock_ds = _mock_ds([])
        with patch(
            "backend.routers.analysis.get_data_source", return_value=mock_ds
        ) as mock_factory:
            resp = _CLIENT.post("/api/failures", json={"time_range": "1d"})
        assert resp.status_code == 200
        mock_factory.assert_called_once_with(None)

    def test_invalid_time_range_returns_422(self) -> None:
        resp = _CLIENT.post("/api/failures", json={"time_range": "2h"})
        assert resp.status_code == 422
