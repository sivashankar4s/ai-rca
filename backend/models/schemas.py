from pydantic import BaseModel, field_validator
from typing import Optional, List, Any, Literal
from enum import Enum
import json as _json


DataSourceProvider = Literal["athena", "postgres"]
LogBackendProvider = Literal["cloudwatch", "grafana_loki"]


class TimeRange(str, Enum):
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class EventData(BaseModel):
    """Parsed contents of the event_data JSON column."""
    file_trace_id: Optional[str] = None
    region_name: Optional[str] = None
    object_type: Optional[str] = None
    status: Optional[str] = None
    timestamp: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: Optional[int] = None
    stage: Optional[str] = None
    tenant_alias: Optional[str] = None
    fhir_org_id: Optional[str] = None
    file_name: Optional[str] = None
    device_id: Optional[str] = None


class FailureRecord(BaseModel):
    application_name: Optional[str] = None
    component_name: Optional[str] = None
    custom_key1: Optional[str] = None   # file_trace_id
    custom_key2: Optional[str] = None   # file_name
    custom_key3: Optional[str] = None   # device_id
    event_created_timestamp: Optional[str] = None
    event_inserted_timestamp: Optional[str] = None
    organization: Optional[str] = None
    status: str = "FAILED"
    event_data: Optional[EventData] = None

    @field_validator("event_data", mode="before")
    @classmethod
    def parse_event_data(cls, v: Any) -> Any:
        """Accept either a JSON string or a dict/None."""
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except (_json.JSONDecodeError, ValueError):
                return None
        return v


# ── Step 1 ────────────────────────────────────────────────────────────────────
class FailuresRequest(BaseModel):
    time_range: Optional[TimeRange] = TimeRange.ONE_HOUR
    start_date: Optional[str] = None   # ISO local datetime e.g. "2026-05-12T10:00"
    end_date: Optional[str] = None     # ISO local datetime e.g. "2026-05-12T12:00"
    component: Optional[str] = None
    failure_only: bool = True          # True → filter WHERE status = 'FAILED'
    data_source: Optional[DataSourceProvider] = None  # overrides DATA_SOURCE_PROVIDER for this request


class FailuresResponse(BaseModel):
    total: int
    time_range: str
    records: List[FailureRecord]


# ── Step 2 ────────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    time_range: Optional[TimeRange] = TimeRange.ONE_HOUR
    start_date: Optional[str] = None   # ISO local datetime e.g. "2026-05-12T10:00"
    end_date: Optional[str] = None     # ISO local datetime e.g. "2026-05-12T12:00"
    records: List[FailureRecord]
    log_backend: Optional[LogBackendProvider] = None  # overrides LOG_ANALYSIS_PROVIDER for this request


class FailureGroup(BaseModel):
    group_id: str
    component: str
    error_pattern: str
    root_cause: str
    failure_category: str
    impact_count: int
    # Developer-focused fields
    immediate_action: Optional[str] = None   # exact next step a dev should take right now
    likely_fix: Optional[str] = None         # code/config change that likely resolves it
    affected_files: List[str] = []           # service/config files likely involved
    escalation_path: Optional[str] = None    # who/what team to escalate to if fix doesn't work
    records: List[FailureRecord] = []
    log_samples: List[str] = []
    cw_log_url: Optional[str] = None


class CodeChangeItem(BaseModel):
    type: str               # "commit" | "pull_request"
    title: str
    author: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None


class CodeAnalysisResult(BaseModel):
    repo: str
    items: List[CodeChangeItem] = []
    error: Optional[str] = None


class BranchInfo(BaseModel):
    name: str
    sha: Optional[str] = None
    protected: bool = False


class BranchesResponse(BaseModel):
    repo: str
    branches: List[BranchInfo] = []
    error: Optional[str] = None


class PullRequestInfo(BaseModel):
    number: int
    title: str
    state: str
    author: Optional[str] = None
    url: Optional[str] = None
    updated_at: Optional[str] = None
    branch: Optional[str] = None


class PullRequestsResponse(BaseModel):
    repo: str
    pull_requests: List[PullRequestInfo] = []
    error: Optional[str] = None


class CodeReviewFinding(BaseModel):
    severity: str            # "critical" | "high" | "medium" | "low" | "info"
    category: str            # "security" | "sql_injection" | "bug" | "code_quality" | "performance" | "style" | "suggestion"
    file: Optional[str] = None
    line: Optional[int] = None
    title: str
    description: str
    recommendation: Optional[str] = None


class CodeReviewResult(BaseModel):
    repo: str
    target: str
    summary: str = ""
    findings: List[CodeReviewFinding] = []
    error: Optional[str] = None


class RepoInfo(BaseModel):
    configured: bool
    repo: Optional[str] = None
    owner: Optional[str] = None
    name: Optional[str] = None
    default_branch: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class AnalyzeResponse(BaseModel):
    total_failures: int
    time_range: str
    analyzed_at: str
    failure_groups: List[FailureGroup]
    summary: str
    code_analysis: Optional[CodeAnalysisResult] = None


# ── Config ────────────────────────────────────────────────────────────────────
class ConfigUpdateRequest(BaseModel):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: Optional[str] = None
    athena_database: Optional[str] = None
    athena_table: Optional[str] = None
    llm_model: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    grafana_loki_url: Optional[str] = None
    grafana_api_key: Optional[str] = None
    grafana_datasource_uid: Optional[str] = None
    github_repo: Optional[str] = None
    github_token: Optional[str] = None
    github_mcp_command: Optional[str] = None


class ProviderOption(BaseModel):
    id: str
    label: str


class ProvidersResponse(BaseModel):
    data_sources: List[ProviderOption]
    log_backends: List[ProviderOption]
    defaults: dict[str, str]


class ConfigResponse(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key_set: bool
    aws_session_token_set: bool
    aws_region: str
    athena_database: str
    athena_table: str
    llm_model: str
    llm_base_url: str
    llm_provider: str
    anthropic_api_key_set: bool
    grafana_loki_url: str
    grafana_api_key_set: bool
    grafana_datasource_uid: str
    database_url_masked: str
    database_connected: bool
    github_repo: str
    github_token_set: bool
    github_mcp_command: str
