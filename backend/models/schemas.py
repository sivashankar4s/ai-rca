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


# ── GitHub / Source Code Intelligence ─────────────────────────────────────────


class RepoInfo(BaseModel):
    configured: bool
    repo: str | None = None
    owner: str | None = None
    name: str | None = None
    default_branch: str | None = None
    description: str | None = None
    url: str | None = None
    error: str | None = None


class BranchInfo(BaseModel):
    name: str
    sha: str | None = None
    protected: bool = False


class BranchesResponse(BaseModel):
    repo: str
    branches: list[BranchInfo] = []
    error: str | None = None


class PullRequestInfo(BaseModel):
    number: int
    title: str
    state: str
    author: str | None = None
    url: str | None = None
    updated_at: str | None = None
    branch: str | None = None


class PullRequestsResponse(BaseModel):
    repo: str
    pull_requests: list[PullRequestInfo] = []
    error: str | None = None


class CodeReviewFinding(BaseModel):
    severity: str
    category: str
    file: str | None = None
    line: int | None = None
    title: str
    description: str
    recommendation: str | None = None


class CodeReviewResult(BaseModel):
    repo: str
    target: str
    summary: str = ""
    findings: list[CodeReviewFinding] = []
    error: str | None = None


class PostedReviewResult(BaseModel):
    """Response DTO for POST .../review/comments (spec 003-inline-pr-comments)."""

    repo: str = ""
    target: str = ""
    posted: bool = False
    review_url: str | None = None
    inline_comment_count: int = 0
    summary_only_count: int = 0
    verdict: str = "COMMENT"
    error: str | None = None
