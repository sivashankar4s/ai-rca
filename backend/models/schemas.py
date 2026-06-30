"""Pydantic v2 request/response DTOs for the AI-RCA API.

All structured data that crosses a function boundary more than once MUST use
a Pydantic model (Constitution Principle I). No bare dicts in API handlers.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


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
    message: str | None = None
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
    data_source: Literal["athena", "postgres"] | None = None

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


# ── App Configuration ──────────────────────────────────────────────────────────

MASK_SENTINEL = "••••••••"


class AwsConfigStatus(BaseModel):
    configured: bool
    access_key_id: str | None = None
    secret_access_key: str | None = None
    region: str | None = None


class GithubMcpConfigStatus(BaseModel):
    configured: bool
    repo: str | None = None
    token: str | None = None
    default_branch: str | None = None


class AppConfigRead(BaseModel):
    aws: AwsConfigStatus
    github_mcp: GithubMcpConfigStatus


class AwsConfigUpdate(BaseModel):
    access_key_id: str
    secret_access_key: str
    region: str | None = None

    @field_validator("access_key_id")
    @classmethod
    def _access_key_id_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("access_key_id must not be empty")
        return v.strip()

    @field_validator("secret_access_key")
    @classmethod
    def _secret_nonempty_unless_sentinel(cls, v: str) -> str:
        if v != MASK_SENTINEL and not v.strip():
            raise ValueError("secret_access_key must not be empty")
        return v


class GithubMcpConfigUpdate(BaseModel):
    repo: str
    token: str
    default_branch: str | None = None

    @field_validator("repo")
    @classmethod
    def _repo_format(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("repo must not be empty")
        parts = stripped.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("repo must be in owner/repo format")
        return stripped

    @field_validator("token")
    @classmethod
    def _token_nonempty_unless_sentinel(cls, v: str) -> str:
        if v != MASK_SENTINEL and not v.strip():
            raise ValueError("token must not be empty")
        return v


class ConfigSaveResult(BaseModel):
    success: bool
    message: str
    updated_at: datetime | None = None


class ProviderOption(BaseModel):
    """One selectable provider returned by GET /api/providers."""

    id: str
    label: str
    is_default: bool


class ProvidersResponse(BaseModel):
    """Response body for GET /api/providers (FR-005)."""

    data_sources: list[ProviderOption]
    log_backends: list[ProviderOption]


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze (FR-002)."""

    records: list[FailureRecord]
    time_range: TimeRange
    log_backend: Literal["cloudwatch", "grafana_loki"] | None = None


class AnalyzeResponse(BaseModel):
    """Response body for POST /api/analyze."""

    log_backend_used: str
    record_count: int


