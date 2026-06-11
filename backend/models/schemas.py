from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from enum import Enum
import json as _json


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


class AnalyzeResponse(BaseModel):
    total_failures: int
    time_range: str
    analyzed_at: str
    failure_groups: List[FailureGroup]
    summary: str


# ── Config ────────────────────────────────────────────────────────────────────
class ConfigUpdateRequest(BaseModel):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    aws_region: Optional[str] = None
    athena_database: Optional[str] = None
    athena_table: Optional[str] = None
    llm_model: Optional[str] = None


class ConfigResponse(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key_set: bool
    aws_session_token_set: bool
    aws_region: str
    athena_database: str
    athena_table: str
    llm_model: str
    llm_base_url: str
