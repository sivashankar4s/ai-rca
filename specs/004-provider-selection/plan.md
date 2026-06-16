# Implementation Plan: Per-Run Provider Selection

**Branch**: `004-provider-selection` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-provider-selection/spec.md`

## Summary

Let the user pick the data source and log backend per run from the UI, surface the
stored failure history as a selectable data source, expose the available providers to
the frontend, and make the header vendor-neutral. A large part of the plumbing already
exists: `plugin_registry.get_data_source(override)` and `get_log_backend(override)`
already accept a per-run override, and a `PostgresDataSource` provider already
implements `DataSourceStrategy` against the `failure_records` table. The remaining work
is therefore thin: (1) carry the operator's choice from the request body into those
existing override parameters, (2) add a read-only `GET /api/providers` endpoint that
reports the available data sources / log backends and their defaults, and (3) add the
two selectors plus neutral branding to the single-page frontend.

Technical approach: add an optional `data_source` field to `FailuresRequest` (the
`log_backend` override already exists on `AnalyzeRequest`), thread it through
`routers/analysis.py` into `plugin_registry.get_data_source(override=...)`; add
`GET /api/providers` returning a `ProvidersResponse` built from the registry's known
provider keys and the configured defaults; reject unknown selections at the registry
boundary (already raises `ValueError`) translated to a clear HTTP error. No new
strategy, no new persistence, no new global configuration.

## Technical Context

**Language/Version**: Python 3.13 (backend), ES2022+ vanilla JS (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (the existing
`PostgresDataSource` reads `failure_records` via the repository layer), existing
`plugin_registry` selection.

**Storage**: No new storage. The stored-history source reads existing
`failure_records` rows through the existing repository; this feature writes nothing new.

**Testing**: pytest + FastAPI `TestClient`. Router tests mock at the DI boundary;
registry/selection tested directly; `PostgresDataSource` already has provider tests
(`backend/tests/providers/test_postgres_data_source.py`) against a real test DB.

**Target Platform**: Linux/Windows server (FastAPI + uvicorn), browser SPA.

**Project Type**: Web application (FastAPI backend + vanilla-JS frontend).

**Performance Goals**: Interactive. `GET /api/providers` is an in-memory describe call
(no I/O). A stored-history fetch is one indexed query over `failure_records`.

**Constraints**: Selection is global to the single configured project (per-project
selection is feature 012, out of scope). Overrides layer on top of `.env` defaults;
defaults are unchanged. `local_data_file` mode continues to short-circuit data-source
selection exactly as today.

**Scale/Scope**: One new request field, one new endpoint, one new response schema, two
frontend selectors + a header copy change. No new provider (Postgres already exists).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type-Safe, Modern Python** — PASS. New `ProvidersResponse` / `ProviderOption`
  are Pydantic v2 models; the `data_source` field is `Literal[...] | None`; selection
  uses the existing `match`/`case` in `plugin_registry`.
- **II. Simplicity / YAGNI** — PASS. Reuses the override parameters and
  `PostgresDataSource` that already exist; adds nothing speculative. `GET /api/providers`
  derives its list from the registry's existing known keys + config defaults rather than
  a new registry abstraction.
- **III. Layered Architecture** — PASS. Selection stays in `plugin_registry`; routers
  obtain the strategy via the registry and pass the override through; no `if provider ==`
  branching leaks into services; the new endpoint declares a `response_model`; the
  stored-history source reads through the existing repository, not `db.session`.
- **IV. Test-First & Coverage Gates (NON-NEGOTIABLE)** — PASS (plan commits to it).
  `routers/analysis.py` ≥75% via `TestClient` (override forwarded; unknown selection
  rejected; `GET /api/providers` shape); `plugin_registry` selection covered for the
  override and unknown-key paths; the existing `PostgresDataSource` contract test is
  retained. Overall backend ≥80%.
- **V. Explicit Configuration** — PASS. Defaults still come only from `backend/config.py`;
  the override is request-scoped and never written back to settings.
- **VI. Structured Logging & Explicit Error Handling** — PASS. An unknown selection
  raises `ValueError` at the registry boundary, translated by a FastAPI handler to a
  clear 400; no ad-hoc error dicts; the run fails loudly rather than substituting a
  provider (FR-007/FR-008).

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-provider-selection/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── routers/
│   └── analysis.py                # MODIFIED — forward data_source override; add GET /api/providers
├── models/
│   └── schemas.py                 # MODIFIED — add data_source to FailuresRequest; add ProvidersResponse / ProviderOption
├── plugin_registry.py             # REUSED — get_data_source(override) / get_log_backend(override) already exist
├── providers/data_source/
│   └── postgres.py                # REUSED, already exists — PostgresDataSource
├── config.py                      # REUSED, unchanged — *_provider defaults
└── tests/
    ├── routers/
    │   └── test_analysis.py       # MODIFIED/NEW — override forwarding, unknown selection, /api/providers
    └── providers/
        └── test_postgres_data_source.py   # REUSED — existing provider contract test

frontend/
├── index.html                     # MODIFIED — Source + Log Backend selectors; neutral header tagline
├── app.js                         # MODIFIED — load /api/providers; send data_source/log_backend; populate selectors
└── style.css                      # MODIFIED — selector styling (reuse existing CSS vars)
```

**Structure Decision**: Web application layout (existing). This is a thin extension of
the existing fetch/analyze area — one request field, one describe endpoint, two
selectors — sitting on top of provider-selection machinery that already exists.

## Complexity Tracking

> No constitution violations — table intentionally empty.
