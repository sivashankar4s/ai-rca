"""RCA analysis service — builds one combined root-cause prompt from the selected
failures and streams the LLM's analysis back token-by-token."""

from collections.abc import Iterator

from backend.models.schemas import FailureRecord
from backend.plugin_registry import get_llm

_MAX_RECORDS = 25
_MAX_LINES_PER_RECORD = 15


def _payload_lines(payload: dict | None) -> list[str]:
    """Extract raw log-line messages from a record's raw_payload (CloudWatch shape)."""
    if not isinstance(payload, dict):
        return []
    lines = payload.get("lines")
    if not isinstance(lines, list):
        return []
    out: list[str] = []
    for line in lines[:_MAX_LINES_PER_RECORD]:
        if isinstance(line, dict):
            msg = line.get("@message") or line.get("message")
            if msg:
                out.append(str(msg).strip())
    return out


def _record_block(index: int, record: FailureRecord) -> str:
    parts = [f"### Failure {index}"]
    if record.component_name:
        parts.append(f"Component: {record.component_name}")
    if record.file_trace_id:
        parts.append(f"Trace ID: {record.file_trace_id}")
    if record.error_code:
        parts.append(f"Error code: {record.error_code}")
    if record.message:
        parts.append(f"Message: {record.message}")
    lines = _payload_lines(record.raw_payload)
    if lines:
        parts.append("Log lines:\n" + "\n".join(lines))
    return "\n".join(parts)


def build_rca_prompt(records: list[FailureRecord]) -> str:
    """Build a single combined root-cause-analysis prompt for all selected failures."""
    selected = records[:_MAX_RECORDS]
    blocks = "\n\n".join(_record_block(i, r) for i, r in enumerate(selected, 1))
    return (
        "You are an experienced SRE performing root cause analysis. Below are "
        f"{len(selected)} related production failures. Identify the most likely shared "
        "root cause(s), explain your reasoning from the evidence, and recommend concrete "
        "remediation steps. Be concise and specific.\n\n"
        f"{blocks}"
    )


def stream_rca(records: list[FailureRecord]) -> Iterator[str]:
    """Yield the combined root-cause analysis for the given failures as it is generated."""
    prompt = build_rca_prompt(records)
    yield from get_llm().invoke_stream(prompt)
