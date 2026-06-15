# API Contracts: AI-Powered RCA Tool for Production Incidents

These contracts describe the existing FastAPI endpoints in
`backend/routers/analysis.py` that satisfy the functional requirements in
`spec.md`. All endpoints declare a `response_model` from
`backend/models/schemas.py` per Constitution Principle III.

## `POST /api/failures`

Satisfies FR-001, FR-002, FR-003, FR-012.

**Request** (`FailuresRequest`):

```json
{
  "time_range": "1h",
  "start_date": null,
  "end_date": null,
  "component": "dp-lz-s3-event-processor",
  "failure_only": true,
  "data_source": null
}
```

**Response** (`FailuresResponse`):

```json
{
  "total": 47,
  "time_range": "1h",
  "records": [ { "...": "FailureRecord" } ]
}
```

## `POST /api/analyze`

Satisfies FR-004–FR-011, FR-013–FR-016.

**Request** (`AnalyzeRequest`):

```json
{
  "time_range": "1h",
  "records": [ "...selected FailureRecord objects from /api/failures..." ],
  "log_backend": null
}
```

- MUST contain at least one record (FR-005); a router-level validation error is
  returned otherwise.

**Response** (`AnalyzeResponse`):

```json
{
  "total_failures": 12,
  "time_range": "1h",
  "analyzed_at": "2026-06-15T10:30:00+00:00",
  "summary": "12 failures across 2 components...",
  "failure_groups": [
    {
      "group_id": "grp-1",
      "component": "dp-lz-s3-event-processor",
      "error_pattern": "S3_PUT_FAILED on lz-processor stage",
      "root_cause": "...",
      "failure_category": "Configuration",
      "impact_count": 10,
      "immediate_action": "...",
      "likely_fix": "...",
      "affected_files": ["..."],
      "escalation_path": "...",
      "cw_log_url": "https://...",
      "records": ["..."],
      "log_samples": ["..."]
    }
  ],
  "code_analysis": {
    "repo": "owner/repo",
    "items": [
      { "type": "commit", "title": "...", "author": "...", "date": "...", "url": "..." }
    ],
    "error": null
  }
}
```

- `code_analysis` is `null` when `GITHUB_REPO` is not configured (FR-015).
- `code_analysis.error` is set (non-null) when the repo is configured but the
  lookup fails; `failure_groups`/`summary` are still populated (FR-016).
- A failure group's `cw_log_url` and `log_samples` MAY be empty if the
  configured log backend is unreachable, without failing the response
  (FR-016).

## `GET /api/config` / `POST /api/config`

Satisfies FR-017.

- `GET` returns `ConfigResponse` — current runtime provider configuration with
  secrets represented as `*_set: bool` flags, never raw secret values.
- `POST` accepts `ConfigUpdateRequest` (partial) and updates in-memory runtime
  configuration; does not persist to `.env`.

## `GET /api/models`

Proxies the configured LLM provider's `/v1/models` endpoint for the
Configuration UI.

## `GET /api/health`

Returns `{"status": "ok"}` — used for deployment health checks.
