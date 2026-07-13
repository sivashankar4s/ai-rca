# Phase 1 Data Model: Service Health Dashboard

## Enums

### `HealthStatus` (str, Enum)
| Member | Value | Meaning |
|--------|-------|---------|
| `UP` | `up` | Resource currently healthy/active |
| `DOWN` | `down` | Resource currently failed/inactive/unavailable |
| `UNKNOWN` | `unknown` | State could not be determined (error, not found, no permission) |

### `HealthWindow` (str, Enum)
| Member | Value | `timedelta` |
|--------|-------|-------------|
| `H1` | `1h` | 1 hour |
| `H24` | `24h` | 24 hours (default) |
| `D7` | `7d` | 7 days |

### `HealthServiceType` (str, Enum)
`glue_job`, `glue_workflow`, `lambda_function`, `datasync_task`.

## Transient models (API I/O — not persisted)

### `ServiceHealth`
Computed health of one resource at check time.

| Field | Type | Notes |
|-------|------|-------|
| `service_type` | `HealthServiceType` | Which service |
| `id` | `str` | Stored identifier (name; ARN for DataSync) |
| `label` | `str` | Human-readable name shown on the card |
| `status` | `HealthStatus` | up / down / unknown |
| `failure_count` | `int` | Failures within the selected window (≥ 0) |
| `last_activity_ts` | `datetime \| None` | Last run/execution time when available |
| `detail` | `str \| None` | Reason for down/unknown, or last-run summary |

**Validation**: `failure_count ≥ 0`. A `DOWN`/`UNKNOWN` result SHOULD carry a `detail`.

### `ServiceHealthResponse`
| Field | Type | Notes |
|-------|------|-------|
| `window` | `HealthWindow` | Echo of the applied window |
| `generated_at` | `datetime` | When the checks ran |
| `results` | `list[ServiceHealth]` | One per configured resource |

### `HealthResource` / `HealthResourcesResponse`
Discovery payload for the Config pickers.

| `HealthResource` field | Type | Notes |
|------------------------|------|-------|
| `id` | `str` | Value persisted on save (name, or ARN for DataSync) |
| `label` | `str` | Display name |

`HealthResourcesResponse`: `{ resources: list[HealthResource] }`.

## Config models (persisted in `app_config.health_config`)

### `HealthConfigStatus` (read)
| Field | Type | Notes |
|-------|------|-------|
| `configured` | `bool` | True if any resource selected across all types |
| `glue_jobs` | `list[str]` | Selected job names |
| `glue_workflows` | `list[str]` | Selected workflow names |
| `lambda_functions` | `list[str]` | Selected function names |
| `datasync_tasks` | `list[HealthResource]` | Selected `{id: arn, label: name}` |

### `HealthConfigUpdate` (write, PATCH body)
Same four lists. All optional-list fields default to `[]`. No `field_validator`
requiring non-empty (an operator may clear a service type). Whitespace-only entries
are stripped. Added to `AppConfigRead` as a new `health` field.

## Persistence

### `AppConfig.health_config` (new JSONB column)
```json
{
  "glue_jobs": ["etl-daily", "etl-hourly"],
  "glue_workflows": ["nightly-pipeline"],
  "lambda_functions": ["ingest-fn", "notify-fn"],
  "datasync_tasks": [{"arn": "arn:aws:datasync:...:task/task-0abc", "name": "s3-to-efs"}]
}
```
- Migration `007_add_health_config` (`down_revision = 006_add_athena_config`) adds the
  nullable column, mirroring `006_add_athena_config`.
- `config_repo.upsert_health_config(db, data)` writes the four lists. No mask sentinel
  (identifiers are not secrets).

## Strategy contract

### `HealthCheckStrategy` (ABC — `backend/strategies/health_check.py`)
```
service_type: HealthServiceType            # class attribute

def check(self, ids: list[str], start: datetime, end: datetime) -> list[ServiceHealth]:
    """Return one ServiceHealth per requested id; window = [start, end]."""

def discover(self) -> list[HealthResource]:
    """List available resources of this type for the config picker."""
```
Each provider (`GlueJobHealthCheck`, `GlueWorkflowHealthCheck`, `LambdaHealthCheck`,
`DataSyncHealthCheck`) implements both, wraps its boto3 client, and catches AWS errors
per-resource → `ServiceHealth(status=UNKNOWN, detail=...)`. A provider-level failure in
`discover()` raises `RuntimeError` (surfaced as HTTP 400 by the router, like the
CloudWatch discovery endpoint).

## Relationships / flow

```
Config page pickers ──PATCH /api/config/health──▶ config_repo.upsert_health_config
                                                          │
                                                   app_config.health_config (JSONB)
                                                          │
Health tab ──GET /api/health/services?window──▶ health_service.check_all(db, window)
                                                          │ reads health_config + aws_config
                                                          ▼
                            plugin_registry.get_health_checkers(db) → 4 providers
                                                          │ ThreadPoolExecutor fan-out
                                                          ▼
                                     list[ServiceHealth] ─▶ ServiceHealthResponse
```
