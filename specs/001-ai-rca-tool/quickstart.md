# Quickstart: AI-Powered RCA Tool for Production Incidents

Validates the user stories in `spec.md` end-to-end. See `LOCAL_SETUP.md` for
full environment setup details.

## Prerequisites

- Python 3.13 environment with `requirements-dev.txt` installed
- Local Postgres running (`docker compose up -d`) with migrations applied
  (`alembic upgrade head`)
- `.env` configured; for a quick check without AWS, set
  `LOCAL_DATA_FILE=./sample_failures.json`

## Run the app

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

## Validate User Story 1 — Find failed records (P1)

1. In the UI, select time range "Last 1 hour" (or another range covered by
   `sample_failures.json`), leave component filter blank.
2. **Expected**: A paginated table of `FAILED` records appears (FR-001,
   FR-003).
3. Repeat with a specific `component_name` from the sample data.
4. **Expected**: Only records for that component are returned (FR-002).
5. Change page size and navigate pages after selecting some rows.
6. **Expected**: Selections persist across page changes (FR-003).

Equivalent API check:

```bash
curl -X POST http://localhost:8000/api/failures \
  -H "Content-Type: application/json" \
  -d '{"time_range": "1h"}'
```

## Validate User Story 2 — AI-generated root cause analysis (P2)

1. From the Step 1 table, select one or more failure records (or "select all").
2. Click "Analyze".
3. **Expected**: Response includes `failure_groups` with `root_cause`,
   `failure_category`, `impact_count`, `immediate_action`, `likely_fix`,
   `escalation_path`, `cw_log_url`, and an overall `summary` (FR-006–FR-011).
4. Click a failure group's log link.
5. **Expected**: Opens the configured log backend (CloudWatch or Grafana)
   pre-filtered to the relevant query/time window (FR-010).
6. If `GITHUB_REPO` is configured, confirm the response includes
   `code_analysis.items` (FR-015); if not configured, confirm `code_analysis`
   is `null` and the rest of the response is unaffected.

Equivalent API check:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"time_range": "1h", "records": ["...from /api/failures response..."]}'
```

## Validate User Story 3 — Recurring issue detection (P3)

1. Run the analysis from User Story 2 once. Note one of the returned
   `failure_groups[].error_pattern` / `component`.
2. Inspect the `rca_cases` table — a new row with `status = new` should exist
   for that signature.
3. Re-fetch the same time range via `/api/failures`.
4. **Expected**: `failure_records` row count for that range does not increase
   (no duplicates) — verifies FR-012/SC-005.
5. Run `/api/analyze` again on a failure batch with the same
   `(component_name, error_code, stage)` signature.
6. **Expected**: The existing `rca_cases` row is reused, its `status` becomes
   `recurring`, and a new `case_activity` row records the recurrence
   (FR-014).

## Validate edge cases

- Time range/component with no matches → UI shows an empty state, `total: 0`,
  `records: []` (no error).
- `/api/analyze` called with `records: []` → request is rejected before the
  pipeline runs (FR-005).
- Misconfigured/unreachable log backend → `/api/analyze` still returns
  `failure_groups` and `summary`; affected `cw_log_url`/`log_samples` are
  empty (FR-016, SC-006).
- `GITHUB_REPO` set but `GITHUB_TOKEN`/MCP server unavailable →
  `code_analysis.error` is populated; rest of response unaffected (FR-016,
  SC-006).

## Run automated tests

```bash
pytest --cov=backend --cov-fail-under=80
ruff format --check .
ruff check .
```
