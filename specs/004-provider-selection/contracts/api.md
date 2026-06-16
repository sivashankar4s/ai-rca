# API Contracts: Per-Run Provider Selection

One new endpoint is added and two existing endpoints gain an optional override field.
No endpoints are removed. All live in `backend/routers/analysis.py`.

## `GET /api/providers` (NEW)

Reports the data sources and log backends currently available, with the default for
each, so the UI can populate its selectors from real availability. Read-only; no I/O
beyond inspecting configuration. Satisfies FR-005/FR-006.

**Response** (`ProvidersResponse`, HTTP 200):

```json
{
  "data_sources": [
    { "id": "athena",   "label": "Amazon Athena",            "is_default": true },
    { "id": "postgres", "label": "Stored history (Postgres)", "is_default": false }
  ],
  "log_backends": [
    { "id": "cloudwatch",   "label": "CloudWatch Logs Insights", "is_default": true },
    { "id": "grafana_loki", "label": "Grafana Loki",             "is_default": false }
  ]
}
```

**Behavioral contract**:
- Only configured/available providers are listed (FR-006); an unconfigured provider does
  not appear.
- Exactly one option per kind has `is_default = true`, matching the configured default.
- When `local_data_file` mode is active, the data-source default reflects the local-file
  short-circuit.

## `POST /api/failures` (MODIFIED — optional `data_source`)

The existing fetch endpoint accepts an optional per-run data-source override.

**Request body** (`FailuresRequest`, new field shown):

```json
{
  "time_range": "1d",
  "component": "dp-lz-s3-event-processor",
  "data_source": "postgres"
}
```

**Behavioral contract**:
- `data_source` absent/`null` → the configured default source is used; results are
  identical to today (FR-001/FR-010).
- `data_source: "postgres"` → records are read from the stored failure history for the
  same window/component, with no live external data-source call (FR-004/SC-002).
- `data_source` naming a provider that is not available → HTTP 400 with a clear message;
  nothing is fetched (FR-008). A value outside the supported set is rejected by request
  validation (HTTP 422).
- A selected-but-unreachable source → the run fails with a message naming the selected
  source; no silent fallback to the default (FR-007).
- The response shape (`FailuresResponse`) is unchanged.

## `POST /api/analyze` (UNCHANGED contract — existing `log_backend` override)

The analyze endpoint already accepts `log_backend` (`"cloudwatch" | "grafana_loki"`).
This feature wires the UI selector to it; the contract is unchanged.

**Behavioral contract** (restated for completeness):
- `log_backend` absent/`null` → configured default backend (FR-002/FR-010).
- `log_backend` set → that backend is used for query generation and deep-links for this
  run only (FR-002/FR-003).
- Unknown/unavailable backend → clear error; no substitution (FR-007/FR-008).

## Unchanged endpoints (for reference)

- `GET /api/config` / `POST /api/config` — runtime config read/update; unchanged.
- `GET /api/models` — LLM model list proxy; unchanged.
- `GET /api/health` — unchanged.
