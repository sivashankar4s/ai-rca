"""Pydantic v2 request/response DTOs for the AI-RCA API.

All structured data that crosses a function boundary more than once MUST use
a Pydantic model (Constitution Principle I). No bare dicts in API handlers.
"""

from datetime import datetime, timedelta
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
    data_source: Literal["athena", "postgres", "cloudwatch"] | None = None
    trace_id: str | None = None

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
    session_token: str | None = None
    region: str | None = None


class GithubMcpConfigStatus(BaseModel):
    configured: bool
    repo: str | None = None
    token: str | None = None
    default_branch: str | None = None


class CloudWatchConfigStatus(BaseModel):
    configured: bool
    log_groups: list[str] = []
    query_timeout: int | None = None


class AthenaConfigStatus(BaseModel):
    configured: bool
    database: str | None = None
    table: str | None = None


class AppConfigRead(BaseModel):
    aws: AwsConfigStatus
    github_mcp: GithubMcpConfigStatus
    cloudwatch: CloudWatchConfigStatus
    athena: AthenaConfigStatus
    health: "HealthConfigStatus"


class AwsConfigUpdate(BaseModel):
    access_key_id: str
    secret_access_key: str
    session_token: str | None = None
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


class CloudWatchConfigUpdate(BaseModel):
    log_groups: list[str]
    query_timeout: int | None = None

    @field_validator("log_groups")
    @classmethod
    def _log_groups_nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [g.strip() for g in v if g.strip()]
        if not cleaned:
            raise ValueError("at least one log group is required")
        return cleaned

    @field_validator("query_timeout")
    @classmethod
    def _timeout_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("query_timeout must be a positive number of seconds")
        return v


class AthenaConfigUpdate(BaseModel):
    database: str
    table: str

    @field_validator("database", "table")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class CloudWatchLogGroupsResponse(BaseModel):
    """Log groups discovered from AWS for the CloudWatch config picker."""

    log_groups: list[str]


# ── Service Health Dashboard (feature 021) ──────────────────────────────────────


class HealthStatus(StrEnum):
    """Current state of a monitored resource."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class HealthWindow(StrEnum):
    """Failure-count lookback window offered on the Health tab."""

    H1 = "1h"
    H24 = "24h"
    D7 = "7d"

    @property
    def delta(self) -> timedelta:
        return {
            HealthWindow.H1: timedelta(hours=1),
            HealthWindow.H24: timedelta(hours=24),
            HealthWindow.D7: timedelta(days=7),
        }[self]


class HealthServiceType(StrEnum):
    """The AWS service types the dashboard checks."""

    GLUE_JOB = "glue_job"
    GLUE_WORKFLOW = "glue_workflow"
    LAMBDA_FUNCTION = "lambda_function"
    DATASYNC_TASK = "datasync_task"


class ServiceHealth(BaseModel):
    """Computed health of one monitored resource at check time (transient)."""

    service_type: HealthServiceType
    id: str
    label: str
    status: HealthStatus
    failure_count: int = 0
    last_activity_ts: datetime | None = None
    detail: str | None = None

    @field_validator("failure_count")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("failure_count must be >= 0")
        return v


class ServiceHealthResponse(BaseModel):
    """Response body for GET /api/health/services.

    ``window`` is the preset used, or ``None`` for a custom date range. ``start``/``end``
    are the actual lookback bounds the failure counts were computed over.
    """

    window: HealthWindow | None = None
    profile: str | None = None
    generated_at: datetime
    start: datetime
    end: datetime
    results: list[ServiceHealth]
    total_failures: int = 0


# ── Drill-down: per-resource run history + failure reasons ──────────────────────

_MAX_DETAIL_DAYS = 31


class HealthRun(BaseModel):
    """A single run/execution of a Glue job, Glue workflow, or DataSync task."""

    run_id: str | None = None
    status: str
    is_failure: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None
    detail: str | None = None


class ServiceHealthDetail(BaseModel):
    """Drill-down run history for one resource over a selected date range.

    ``runs`` holds native runs for Glue jobs/workflows and DataSync tasks, and failed
    invocations (from CloudWatch Logs) for Lambda. ``detail`` carries an explanation
    when the lookup degraded or found nothing.
    """

    service_type: HealthServiceType
    id: str
    label: str
    start: datetime
    end: datetime
    runs: list[HealthRun] = []
    detail: str | None = None


class HealthDetailRequest(BaseModel):
    """Request body for the drill-down runs + fetch-failures endpoints."""

    service_type: HealthServiceType
    id: str
    label: str | None = None
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _valid_range(self) -> "HealthDetailRequest":
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if self.end - self.start > timedelta(days=_MAX_DETAIL_DAYS):
            raise ValueError(f"date range must not exceed {_MAX_DETAIL_DAYS} days")
        return self


class HealthResource(BaseModel):
    """One selectable resource returned by a discovery endpoint / stored on save."""

    id: str
    label: str


class HealthResourcesResponse(BaseModel):
    """Response body for the Config-page health discovery endpoints."""

    resources: list[HealthResource]


class HealthConfigStatus(BaseModel):
    """Persisted selection of monitored resources (read side)."""

    configured: bool
    glue_jobs: list[str] = []
    glue_workflows: list[str] = []
    lambda_functions: list[str] = []
    datasync_tasks: list[HealthResource] = []


def _clean_names(v: list[str]) -> list[str]:
    return [s.strip() for s in v if s.strip()]


class HealthConfigUpdate(BaseModel):
    """PATCH /api/config/health body — all lists optional, empty allowed."""

    glue_jobs: list[str] = []
    glue_workflows: list[str] = []
    lambda_functions: list[str] = []
    datasync_tasks: list[HealthResource] = []

    @field_validator("glue_jobs", "glue_workflows", "lambda_functions")
    @classmethod
    def _strip_names(cls, v: list[str]) -> list[str]:
        return _clean_names(v)


# ── Health profiles — named sets of monitored resources ─────────────────────────


def _clean_profile_name(v: str) -> str:
    name = v.strip()
    if not name:
        raise ValueError("profile name must not be empty")
    if len(name) > 64:
        raise ValueError("profile name must be 64 characters or fewer")
    return name


class HealthProfile(BaseModel):
    """One named set of monitored resources (read side)."""

    name: str
    glue_jobs: list[str] = []
    glue_workflows: list[str] = []
    lambda_functions: list[str] = []
    datasync_tasks: list[HealthResource] = []


class HealthProfilesResponse(BaseModel):
    """Response body for GET /api/config/health/profiles."""

    profiles: list[HealthProfile]


class HealthProfileCreate(BaseModel):
    """POST /api/config/health/profiles — create a new (empty) profile."""

    name: str

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        return _clean_profile_name(v)


class HealthProfileUpdate(BaseModel):
    """PATCH /api/config/health/profiles — replace one profile's resources."""

    name: str
    glue_jobs: list[str] = []
    glue_workflows: list[str] = []
    lambda_functions: list[str] = []
    datasync_tasks: list[HealthResource] = []

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        return _clean_profile_name(v)

    @field_validator("glue_jobs", "glue_workflows", "lambda_functions")
    @classmethod
    def _strip_names(cls, v: list[str]) -> list[str]:
        return _clean_names(v)


class HealthProfileRename(BaseModel):
    """POST /api/config/health/profiles/rename — rename an existing profile."""

    name: str
    new_name: str

    @field_validator("name", "new_name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        return _clean_profile_name(v)


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
