"""Pydantic v2 request/response DTOs for the AI-RCA API.

All structured data that crosses a function boundary more than once MUST use
a Pydantic model (Constitution Principle I). No bare dicts in API handlers.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, model_validator


class TimeRange(StrEnum):
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    CUSTOM = "custom"


class EventData(BaseModel):
    stage: str | None = None
    error_code: str | None = None
    object_type: str | None = None
    retry_count: int | None = None
    fhir_org_id: str | None = None


class FailureRecord(BaseModel):
    """A single failed production event (spec Key Entity: Failure Record)."""

    file_trace_id: str | None = None
    application_name: str | None = None
    component_name: str | None = None
    organization: str | None = None
    file_name: str | None = None
    device_id: str | None = None
    error_code: str | None = None
    stage: str | None = None
    status: str | None = None
    event_created_ts: datetime | None = None
    event_inserted_ts: datetime | None = None
    raw_payload: dict | None = None
    signature_hash: str | None = None


class FailuresRequest(BaseModel):
    """Request body for POST /api/failures (FR-001, FR-002)."""

    time_range: TimeRange
    component: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    data_source: str | None = None

    @model_validator(mode="after")
    def _require_dates_for_custom(self) -> "FailuresRequest":
        if self.time_range == TimeRange.CUSTOM and (self.start is None or self.end is None):
            raise ValueError("start and end are required when time_range is 'custom'")
        return self


class FailuresResponse(BaseModel):
    """Response body for POST /api/failures."""

    total: int
    time_range: TimeRange
    records: list[FailureRecord]
