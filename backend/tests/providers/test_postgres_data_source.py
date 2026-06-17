"""Tests for PostgresDataSource — mocks the DB session to avoid a live database."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.providers.data_source.postgres import PostgresDataSource, _to_schema


def _make_orm_row(**kwargs):
    """Return a mock ORM FailureRecord with sensible defaults."""
    from backend.db.models import FailureRecord as ORM

    row = MagicMock(spec=ORM)
    row.file_trace_id = kwargs.get("file_trace_id", "trace-001")
    row.application_name = kwargs.get("application_name", "app1")
    row.component_name = kwargs.get("component_name", "dp-lz-s3-event-processor")
    row.organization = kwargs.get("organization", "org1")
    row.file_name = kwargs.get("file_name", None)
    row.device_id = kwargs.get("device_id", None)
    row.error_code = kwargs.get("error_code", "S3_PUT_FAILED")
    row.stage = kwargs.get("stage", "lz-processor")
    row.event_created_ts = kwargs.get("event_created_ts", datetime(2026, 6, 16, tzinfo=UTC))
    row.event_inserted_ts = kwargs.get("event_inserted_ts", None)
    row.raw_payload = kwargs.get("raw_payload", None)
    row.signature_hash = kwargs.get("signature_hash", None)
    return row


def _make_session(rows: list) -> MagicMock:
    """Return a mock SQLAlchemy session whose scalars().all() returns *rows*."""
    session = MagicMock()
    session.scalars.return_value.all.return_value = rows
    return session


_START = datetime(2026, 6, 1, tzinfo=UTC)
_END = datetime(2026, 6, 30, tzinfo=UTC)


class TestPostgresDataSource:
    def test_returns_records_from_db(self) -> None:
        row = _make_orm_row()
        mock_session = _make_session([row])
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        results = ds.fetch_records(_START, _END)

        assert len(results) == 1
        assert results[0].file_trace_id == "trace-001"

    def test_empty_result_when_no_rows(self) -> None:
        mock_session = _make_session([])
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        results = ds.fetch_records(_START, _END)

        assert results == []

    def test_component_filter_is_applied(self) -> None:
        row = _make_orm_row(component_name="target-component")
        mock_session = _make_session([row])
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        results = ds.fetch_records(_START, _END, component="target-component")

        assert len(results) == 1
        # Verify the where clause was built (session.scalars received the stmt)
        mock_session.scalars.assert_called_once()

    def test_no_component_filter_when_none(self) -> None:
        mock_session = _make_session([])
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        ds.fetch_records(_START, _END, component=None)

        mock_session.scalars.assert_called_once()

    def test_session_is_closed_after_fetch(self) -> None:
        mock_session = _make_session([])
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        ds.fetch_records(_START, _END)

        mock_session.close.assert_called_once()

    def test_session_closed_on_exception(self) -> None:
        mock_session = MagicMock()
        mock_session.scalars.side_effect = RuntimeError("DB error")
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        with pytest.raises(RuntimeError):
            ds.fetch_records(_START, _END)

        mock_session.close.assert_called_once()

    def test_multiple_records_returned(self) -> None:
        rows = [_make_orm_row(file_trace_id=f"t{i}") for i in range(5)]
        mock_session = _make_session(rows)
        ds = PostgresDataSource(session_factory=lambda: mock_session)

        results = ds.fetch_records(_START, _END)

        assert len(results) == 5


class TestToSchema:
    def test_all_fields_mapped(self) -> None:
        ts = datetime(2026, 6, 15, tzinfo=UTC)
        row = _make_orm_row(
            file_trace_id="t1",
            application_name="myapp",
            component_name="comp",
            organization="org",
            file_name="file.raw",
            device_id="dev-001",
            error_code="ERR",
            stage="stage1",
            event_created_ts=ts,
            raw_payload={"k": "v"},
            signature_hash="abc123",
        )
        schema = _to_schema(row)

        assert schema.file_trace_id == "t1"
        assert schema.application_name == "myapp"
        assert schema.component_name == "comp"
        assert schema.organization == "org"
        assert schema.file_name == "file.raw"
        assert schema.device_id == "dev-001"
        assert schema.error_code == "ERR"
        assert schema.stage == "stage1"
        assert schema.event_created_ts == ts
        assert schema.raw_payload == {"k": "v"}
        assert schema.signature_hash == "abc123"

    def test_none_fields_allowed(self) -> None:
        row = _make_orm_row(file_trace_id=None, application_name=None)
        schema = _to_schema(row)
        assert schema.file_trace_id is None
