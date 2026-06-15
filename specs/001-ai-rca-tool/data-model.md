# Data Model: AI-Powered RCA Tool for Production Incidents

Entities below map the Key Entities from `spec.md` to the existing
implementation (`backend/db/models.py` for persisted entities,
`backend/models/schemas.py` for API DTOs). No schema changes are introduced by
this baseline.

## Project

Represents a monitored application/tenant and owns its provider configuration.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | string | Unique |
| `data_source_cfg` | JSON | Data-source provider config |
| `log_backend_cfg` | JSON | Log-backend provider config |
| `llm_cfg` | JSON \| null | LLM provider config |
| `is_active` | bool | |

## Failure Record

A single failed event from a production pipeline (spec Key Entity: *Failure
Record*).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | FK → Project |
| `application_name` | string \| null | Tenant/application identifier |
| `component_name` | string \| null | Pipeline component |
| `organization` | string \| null | |
| `file_trace_id` | string \| null | Dedup key (from `custom_key1`) |
| `file_name` | string \| null | (`custom_key2`) |
| `device_id` | string \| null | (`custom_key3`) |
| `error_code` | string \| null | Parsed from `event_data` |
| `stage` | string \| null | Parsed from `event_data` |
| `event_created_ts` / `event_inserted_ts` | datetime \| null | |
| `raw_payload` | JSON | Full original record |
| `signature_hash` | string | Derived from component/error/stage |

**Validation / rules**:
- Upserted by `(project_id, file_trace_id)` — re-fetching the same time range
  MUST NOT create duplicates (FR-012, SC-005).
- `signature_hash` is computed at persistence time (FR-013).

## Root-Cause Signature

A recognized failure pattern derived from `component_name` + `error_code` +
`stage` (spec Key Entity: *Root-Cause Signature*).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID \| null | `null` = global/cross-project pattern |
| `signature_hash` | string | Unique per `(project_id, signature_hash)` |
| `component_name`, `error_code`, `stage` | string \| null | Pattern fields |
| `root_cause`, `fix_notes`, `failure_category` | string | Knowledge-base content |
| `occurrence_count` | int | Incremented on each match |
| `first_seen` / `last_seen` | datetime | |

## RCA Case

A persistent record tracking a root-cause signature over time (spec Key
Entity: *RCA Case*).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | FK → Project |
| `status` | enum | `new \| triaged \| analyzing \| analyzed \| assigned \| resolved \| recurring` |
| `component_name`, `error_pattern`, `root_cause`, `failure_category` | string | From the latest matching Failure Group |
| `immediate_action`, `likely_fix`, `escalation_path`, `summary` | string \| null | |
| `affected_files` | JSON (list) | |
| `impact_count` | int | Sum of affected records |
| `cw_log_url` | string \| null | Deep-link to logs |

**State transitions**:
- New signature → case created with `status = new`.
- Recognized signature → existing case linked, `status = recurring`, and a
  `case_activity` entry of type `signature_match`/recurrence is appended
  (FR-014).

## Case Failure Record (link table)

Many-to-many association between `RcaCase` and `FailureRecord` (`case_id`,
`failure_record_id`).

## Case Activity

Timeline entries for a case — status changes, comments, analysis runs,
signature matches.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `case_id` | UUID | FK → RcaCase |
| `activity_type` | string | e.g. `analysis_run`, `signature_match` |
| `payload` | JSON \| null | |
| `created_by` | string \| null | |
| `created_at` | datetime | |

## Case Signature Link (link table)

Many-to-many association between `RcaCase` and `RootCauseSignature`, with
`matched_at` timestamp.

## Failure Group (API DTO, not persisted as its own table)

A cluster of failure records sharing a root cause (spec Key Entity: *Failure
Group*), returned by `/api/analyze` and used to populate `RcaCase` +
`CaseActivity` on persistence.

| Field | Type | Notes |
|---|---|---|
| `group_id` | string | Per-response identifier |
| `component`, `error_pattern`, `root_cause`, `failure_category` | string | |
| `impact_count` | int | |
| `immediate_action`, `likely_fix`, `escalation_path` | string \| null | |
| `affected_files` | list[string] | |
| `records` | list[FailureRecord] | |
| `log_samples` | list[string] | |
| `cw_log_url` | string \| null | |

## Related Code Change (API DTO, not persisted)

A commit or pull request associated with the affected component (spec Key
Entity: *Related Code Change*), returned as `CodeAnalysisResult.items`.

| Field | Type | Notes |
|---|---|---|
| `type` | `"commit" \| "pull_request"` | |
| `title`, `author`, `date`, `url` | string \| null | |

`CodeAnalysisResult.error` carries an inline error message when the lookup
fails (FR-016), without failing the overall `/api/analyze` response.
