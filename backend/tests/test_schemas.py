"""Tests for core Pydantic DTOs in backend/models/schemas.py (RED phase for WU2)."""

from datetime import UTC

import pytest
from pydantic import ValidationError

from backend.models.schemas import (
    FailureRecord,
    FailuresRequest,
    FailuresResponse,
    TimeRange,
)


class TestTimeRange:
    def test_all_enum_values(self) -> None:
        assert TimeRange.ONE_HOUR.value == "1h"
        assert TimeRange.ONE_DAY.value == "1d"
        assert TimeRange.ONE_WEEK.value == "1w"
        assert TimeRange.CUSTOM.value == "custom"

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FailuresRequest(time_range="2h")  # type: ignore[arg-type]


class TestFailuresRequest:
    def test_minimal_valid(self) -> None:
        req = FailuresRequest(time_range=TimeRange.ONE_HOUR)
        assert req.time_range == TimeRange.ONE_HOUR
        assert req.component is None
        assert req.start is None
        assert req.end is None
        assert req.data_source is None

    def test_custom_range_requires_start_and_end(self) -> None:
        with pytest.raises(ValidationError, match="start.*end|custom"):
            FailuresRequest(time_range=TimeRange.CUSTOM)

    def test_custom_range_valid_with_both_dates(self) -> None:
        from datetime import datetime

        start = datetime(2026, 6, 1, tzinfo=UTC)
        end = datetime(2026, 6, 2, tzinfo=UTC)
        req = FailuresRequest(time_range=TimeRange.CUSTOM, start=start, end=end)
        assert req.start == start
        assert req.end == end

    def test_non_custom_range_ignores_dates(self) -> None:
        from datetime import datetime

        req = FailuresRequest(
            time_range=TimeRange.ONE_DAY,
            start=datetime(2026, 6, 1, tzinfo=UTC),
        )
        assert req.time_range == TimeRange.ONE_DAY

    def test_component_filter(self) -> None:
        req = FailuresRequest(time_range=TimeRange.ONE_HOUR, component="dp-lz-s3-event-processor")
        assert req.component == "dp-lz-s3-event-processor"


class TestFailureRecord:
    def test_minimal_construction(self) -> None:
        rec = FailureRecord(file_trace_id="trace-001")
        assert rec.file_trace_id == "trace-001"
        assert rec.application_name is None
        assert rec.component_name is None
        assert rec.status is None

    def test_full_construction(self) -> None:
        rec = FailureRecord(
            file_trace_id="trace-001",
            application_name="db11224",
            component_name="dp-lz-s3-event-processor",
            organization="db11224",
            file_name="voice.raw",
            device_id="dev-001",
            error_code="S3_PUT_FAILED",
            stage="lz-processor",
            status="FAILED",
        )
        assert rec.component_name == "dp-lz-s3-event-processor"
        assert rec.error_code == "S3_PUT_FAILED"

    def test_message_defaults_to_none(self) -> None:
        assert FailureRecord(file_trace_id="t").message is None

    def test_message_can_be_set(self) -> None:
        assert FailureRecord(message="boom").message == "boom"


class TestFailuresResponse:
    def test_construction(self) -> None:
        resp = FailuresResponse(
            total=2,
            time_range=TimeRange.ONE_HOUR,
            records=[
                FailureRecord(file_trace_id="t1"),
                FailureRecord(file_trace_id="t2"),
            ],
        )
        assert resp.total == 2
        assert len(resp.records) == 2

    def test_empty_records(self) -> None:
        resp = FailuresResponse(total=0, time_range=TimeRange.ONE_DAY, records=[])
        assert resp.total == 0
        assert resp.records == []


class TestStrategyABCs:
    """Verify the three strategy ABCs cannot be instantiated directly."""

    def test_data_source_strategy_is_abstract(self) -> None:
        from backend.strategies.data_source import DataSourceStrategy

        with pytest.raises(TypeError):
            DataSourceStrategy()  # type: ignore[abstract]

    def test_llm_strategy_is_abstract(self) -> None:
        from backend.strategies.llm import LLMStrategy

        with pytest.raises(TypeError):
            LLMStrategy()  # type: ignore[abstract]

    def test_log_analysis_strategy_is_abstract(self) -> None:
        from backend.strategies.log_analysis import LogAnalysisStrategy

        with pytest.raises(TypeError):
            LogAnalysisStrategy()  # type: ignore[abstract]

    def test_data_source_strategy_contract(self) -> None:
        """Concrete subclass must implement fetch_records."""
        from datetime import datetime

        from backend.strategies.data_source import DataSourceStrategy

        class ConcreteDS(DataSourceStrategy):
            def fetch_records(
                self,
                start: datetime,
                end: datetime,
                component: str | None = None,
            ) -> list[FailureRecord]:
                return []

        ds = ConcreteDS()
        result = ds.fetch_records(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 2, tzinfo=UTC),
        )
        assert result == []
