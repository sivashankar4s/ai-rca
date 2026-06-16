# Quickstart: Per-Run Provider Selection

Validates the user stories in `spec.md` end-to-end. Builds on the existing two-step
fetch/analyze flow and the already-persisted failure history.

## Prerequisites

- Baseline app running (`uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`).
- Postgres reachable and migrated (`alembic upgrade head`); at least one earlier fetch
  has persisted some `failure_records` rows for a known window.
- A working live data source (Athena, or `LOCAL_DATA_FILE` for local dev) as the
  configured default.
- For US2: two log backends configured (CloudWatch and Grafana Loki) so both appear.

## Validate User Story 1 — Choose the data source for a fetch (P1)

1. Load the app. **Expected**: a **Source** selector appears next to the time-range
   controls, listing the configured default and "Stored history (Postgres)", with the
   default pre-selected (FR-001).
2. Select **Stored history (Postgres)** and fetch over a window with recorded failures.
   **Expected**: results come from `failure_records` for that window/component; no live
   data-source call is made (FR-004/SC-002).
3. Switch back to the default source and fetch. **Expected**: live records return; the
   server-wide default is unchanged for a second browser/user (FR-003).

## Validate User Story 2 — Choose the log backend for an analysis (P2)

1. In the analyze step, confirm a **Log Backend** selector lists both backends with the
   default pre-selected (FR-002).
2. Select the non-default backend and run an analysis. **Expected**: generated queries
   and the deep-link target that backend for this run (FR-002/FR-003).
3. Run an analysis without changing the selector. **Expected**: the configured default
   backend is used — identical to today (FR-010).

## Validate User Story 3 — Discover availability + neutral identity (P3)

1. Configure only one data source (e.g. unset Postgres/Athena so only one remains) and
   reload. **Expected**: the Source selector offers only that one option (FR-006).
2. Configure a second source and reload. **Expected**: the new option appears with no
   code change (FR-006/SC-003).
3. Read the header. **Expected**: a provider-neutral tagline; no named-vendor claim
   (FR-009/SC-005).

## Validate edge cases

- **Unavailable selection**: POST `/api/failures` with `data_source` set to a provider
  that is not configured. **Expected**: HTTP 400 with a clear message; nothing fetched
  (FR-008). A value outside the supported set returns HTTP 422.
- **Selected source unreachable**: select a source whose backing system is down and
  fetch. **Expected**: the run fails naming the selected source; no silent fallback
  (FR-007).
- **Empty history window**: fetch from stored history for a window with no rows.
  **Expected**: an empty result set, not an error.
- **Single provider**: with one provider configured, confirm the selector still renders
  and the run behaves as the environment-pinned default does.

## Confirm `GET /api/providers`

```bash
curl -s localhost:8000/api/providers | jq
```

**Expected**: `data_sources` and `log_backends` arrays, each with exactly one
`is_default: true`, listing only available providers.

## Run automated tests

```bash
pytest --cov=backend --cov-fail-under=80
ruff format --check .
ruff check .
```

Coverage targets for the changed code: `routers/analysis.py` ≥75%; the existing
`PostgresDataSource` provider test (≥70%) continues to pass.
