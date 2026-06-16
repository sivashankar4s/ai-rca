# Data Model: Per-Run Provider Selection

This feature introduces **no persisted entities** — nothing new is written to Postgres.
It adds one request field and two response DTOs, and reuses the existing
`FailureRecord` shape returned by every data source. All models live in
`backend/models/schemas.py` (Pydantic v2).

## FailuresRequest (existing — one field added)

The Step-1 fetch request. One optional override field is added.

| Field | Type | Notes |
|---|---|---|
| `time_range` | TimeRange enum | existing |
| `component` | str \| null | existing optional component filter |
| `start` / `end` | datetime \| null | existing custom-range fields |
| `data_source` | `Literal["athena","postgres"] \| null` | **NEW** — per-run source override; `null` = configured default (FR-001/FR-010) |

## AnalyzeRequest (existing — reused unchanged)

The Step-2 analyze request already carries the per-run log-backend override; no change.

| Field | Type | Notes |
|---|---|---|
| `time_range` | TimeRange enum | existing |
| `records` | list[FailureRecord] | existing |
| `log_backend` | `Literal["cloudwatch","grafana_loki"] \| null` | existing — per-run backend override (FR-002) |

## ProviderOption (NEW — response DTO)

One selectable provider, reported by `GET /api/providers`.

| Field | Type | Notes |
|---|---|---|
| `id` | str | Stable identifier used as the override value (e.g. `athena`, `postgres`, `cloudwatch`, `grafana_loki`) |
| `label` | str | Human-readable name for the selector (e.g. "Amazon Athena", "Stored history (Postgres)") |
| `is_default` | bool | `true` for the provider that is the configured default for its kind |

## ProvidersResponse (NEW — response DTO)

Returned by `GET /api/providers`; declared as the endpoint `response_model`.

| Field | Type | Notes |
|---|---|---|
| `data_sources` | list[ProviderOption] | Available data sources; exactly one has `is_default = true` |
| `log_backends` | list[ProviderOption] | Available log backends; exactly one has `is_default = true` |

**Rules**:
- Only currently-available providers appear (FR-006). Availability = the provider key is
  known to the registry AND its configuration is present.
- When `local_data_file` mode is active, the data-source list reflects that the local
  file is the effective default (the registry short-circuits to it).
- Exactly one option per kind has `is_default = true`, matching `settings.*_provider`.

## FailureRecord (existing — reused unchanged)

Every data source — Athena, local file, and the stored-history Postgres source — returns
the same `FailureRecord` shape. The stored-history source returns the records previously
persisted for the requested window/component; the caller cannot tell the records came
from history rather than a live fetch except that no live system was queried (SC-002).

## Relationship to the existing flow

```
GET  /api/providers            -> ProvidersResponse        (NEW; populates the selectors)
POST /api/failures  (FailuresRequest.data_source)          -> uses get_data_source(override)
POST /api/analyze   (AnalyzeRequest.log_backend)           -> uses get_log_backend(override)
```

No state is shared between calls beyond what already exists; the override is request-
scoped and never written back to `settings`.
