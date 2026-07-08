# Implementation Plan: Service Health Dashboard

**Branch**: `021-service-health-dashboard` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/021-service-health-dashboard/spec.md`

## Summary

Add a new top-level **Health** tab that reports on-demand health for a user-configured
list of AWS Glue jobs, Glue workflows, Lambda functions, and DataSync tasks. Each
resource renders a card showing current up/down status and a failure count over a
selectable lookback window (1h / 24h / 7d), color-coded, with a Refresh action.

Technical approach: a new `HealthCheckStrategy` ABC with one provider per service
(`backend/providers/health_check/`), resolved through `plugin_registry.py` and fanned
out by a `health_service`. A single `GET /api/health/services` endpoint returns the
combined result. Resource selection is persisted in a new `health_config` JSONB column
on the existing single-row `app_config` table, configured via four searchable
multi-select pickers on the Config page (mirroring the existing CloudWatch log-group
picker). AWS credentials reuse the established resolution path (DB `aws_config` first,
env fallback, single source — as in `backend/providers/data_source/cloudwatch.py`).

## Technical Context

**Language/Version**: Python 3.13 (backend), vanilla JS ES2022+ (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy + Alembic, boto3/botocore
(already in `requirements.txt`), pytest + `botocore.stub`/`moto` for tests

**Storage**: PostgreSQL — reuse single-row `app_config` table; add one `health_config`
JSONB column via Alembic migration `007`. No new tables; no health-result persistence.

**Testing**: pytest with per-layer coverage gates (Constitution IV); AWS mocked via
`botocore.stub`/`moto`, routers via FastAPI `TestClient`, repo against the real test DB.

**Target Platform**: Linux server (FastAPI) + single-page browser frontend

**Project Type**: Web application (existing `backend/` + `frontend/` layout)

**Performance Goals**: Health tab returns a definite state for all configured resources
within ~10s (SC-001). Fan-out across resources runs concurrently (bounded thread pool)
since each check is a blocking boto3 call.

**Constraints**: On-demand only — no scheduler, no history, no alerting (FR-013).
Graceful per-resource degradation — one failing lookup never blanks the whole tab (FR-012).

**Scale/Scope**: Tens of configured resources per account (typical). Four service types.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type-Safe, Modern Python** — PASS. All new backend code fully type-hinted; closed
  sets (`HealthStatus`, `HealthWindow`) modelled as `Enum`; cross-boundary data uses
  Pydantic models / dataclasses, never bare dicts.
- **II. Simplicity / YAGNI** — PASS. The `HealthCheckStrategy` ABC + 4 providers is justified
  by 4 concrete implementations of one interface (condition *a*: same shape needed in 2+
  places) and by Principle III's extension-point rule. One reusable frontend multi-select
  picker helper is justified by 4 new pickers. No speculative config, no scheduler, no
  per-card windows, no history — all explicitly out of scope.
- **III. Layered Architecture** — PASS. ABC in `strategies/health_check.py`; concrete
  providers in `providers/health_check/`; selection resolved via `plugin_registry.py`;
  persistence only through `config_repo`; new one-domain router `routers/health.py`;
  every endpoint declares a `response_model`; ORM never exposed (Pydantic schema layer).
- **IV. Test-First & Coverage** — PASS (plan commits to TDD). Contract test per provider
  against the ABC; provider tests mock boto3; service ≥85%, providers ≥70%, router ≥75%,
  repo ≥80% (real test DB); overall `backend/` ≥80%.
- **V. Explicit Configuration & Secrets** — PASS. No `os.environ` reads outside
  `config.py`; credentials via existing `aws_config` resolution; no secrets committed.
- **VI. Structured Logging & Error Handling** — PASS. `logging.getLogger(__name__)`;
  specific exceptions surfaced via FastAPI handlers; per-resource errors captured as an
  `unknown` result with detail rather than swallowed.

**Result**: No violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/021-service-health-dashboard/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (endpoint contracts)
│   ├── health-services.md
│   └── health-config.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── strategies/
│   └── health_check.py            # NEW — HealthCheckStrategy ABC
├── providers/
│   └── health_check/              # NEW package
│       ├── __init__.py
│       ├── glue_job.py            # GlueJobHealthCheck
│       ├── glue_workflow.py       # GlueWorkflowHealthCheck
│       ├── lambda_fn.py           # LambdaHealthCheck
│       └── datasync.py            # DataSyncHealthCheck
├── services/
│   └── health_service.py          # NEW — fan-out + window application
├── routers/
│   ├── health.py                  # NEW — GET /api/health/services
│   └── config.py                  # EDIT — 4 discovery endpoints + PATCH /config/health
├── repositories/config_repo.py    # EDIT — upsert_health_config
├── plugin_registry.py             # EDIT — get_health_checkers(db) + credential wiring
├── models/schemas.py              # EDIT — ServiceHealth, ServiceHealthResponse, HealthStatus,
│                                  #        HealthWindow, HealthConfig{Status,Update},
│                                  #        HealthResource(s)Response
├── db/models.py                   # EDIT — AppConfig.health_config JSONB column
├── db/migrations/versions/
│   └── 007_add_health_config.py   # NEW — add health_config column
└── main.py                        # EDIT — include health_router

backend/tests/
├── providers/test_health_checks.py    # NEW — per-provider + ABC contract tests (boto3 mocked)
├── services/test_health_service.py    # NEW — fan-out, window, partial-failure
├── routers/test_health.py             # NEW — TestClient for /api/health/services
├── routers/test_config.py             # EDIT — discovery + PATCH /config/health
└── repositories/test_config_repo.py   # EDIT — upsert_health_config round-trip

frontend/
├── index.html   # EDIT — nav-health tab, health-view, 4 config pickers
├── app.js       # EDIT — tab wiring, health render, window dropdown, refresh, pickers
└── style.css    # EDIT — health card / status-badge styles (reuse existing CSS vars)
```

**Structure Decision**: Existing web-app layout (`backend/` + `frontend/`). The feature
slots into the established Strategy → Provider → Registry → Service → Router chain and
the single-page frontend, adding one new backend router domain and one new frontend tab.

## Complexity Tracking

> No Constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
