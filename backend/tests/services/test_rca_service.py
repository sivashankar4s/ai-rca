"""Tests for the RCA analysis service."""

from unittest.mock import MagicMock, patch

from backend.models.schemas import FailureRecord
from backend.services import rca_service


def _record(**kw) -> FailureRecord:
    return FailureRecord(**kw)


class TestBuildRcaPrompt:
    def test_includes_component_trace_and_message(self) -> None:
        rec = _record(
            file_trace_id="trace-1",
            component_name="dp-monitor",
            error_code="OOM",
            message="Out of memory: 976MB",
        )
        prompt = rca_service.build_rca_prompt([rec])
        assert "dp-monitor" in prompt
        assert "trace-1" in prompt
        assert "Out of memory: 976MB" in prompt
        assert "root cause" in prompt.lower()

    def test_includes_raw_payload_log_lines(self) -> None:
        rec = _record(
            file_trace_id="t",
            raw_payload={"lines": [{"@message": "[ERROR] boom happened"}]},
        )
        prompt = rca_service.build_rca_prompt([rec])
        assert "[ERROR] boom happened" in prompt

    def test_caps_number_of_records(self) -> None:
        recs = [_record(file_trace_id=f"t{i}") for i in range(50)]
        prompt = rca_service.build_rca_prompt(recs)
        # Only the first _MAX_RECORDS are described.
        assert f"{rca_service._MAX_RECORDS} related production failures" in prompt
        assert "### Failure 25" in prompt
        assert "### Failure 26" not in prompt


class TestStreamRca:
    def test_streams_from_llm(self) -> None:
        llm = MagicMock()
        llm.invoke_stream.return_value = iter(["root ", "cause"])
        with patch("backend.services.rca_service.get_llm", return_value=llm):
            chunks = list(rca_service.stream_rca([_record(file_trace_id="t")]))
        assert "".join(chunks) == "root cause"
        llm.invoke_stream.assert_called_once()
