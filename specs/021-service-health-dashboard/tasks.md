---
description: "Task list for Service Health Dashboard implementation"
---

# Tasks: Service Health Dashboard

**Input**: Design documents from `specs/021-service-health-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — Constitution IV (Test-First Discipline) is NON-NEGOTIABLE for this
project, so every phase writes tests first (they MUST fail before implementation).

**Organization**: Tasks grouped by user story (US1, US2, US3) for independent delivery.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish have no story label)
- Exact file paths included in each task

## Coverage targets (Constitution IV)

services ≥85% · providers ≥70% · routers ≥75% · repositories ≥80% (real test DB) ·
overall `backend/` ≥80% (`pytest --cov=backend --cov-fail-under=80`). AWS mocked via
`botocore.stub`/`moto` — never real AWS calls in tests.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package scaffolding.

- [X] T001 [P] Create the health-check provider package with `backend/providers/health_check/__init__.py`
- [X] T002 [P] Add empty test module stubs: `backend/tests/providers/test_health_checks.py`, `backend/tests/services/test_health_service.py`, `backend/tests/routers/test_health.py` (imports + `pytest` collection only)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared schema, persistence column, and the strategy contract that ALL user
stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `health_config` JSONB column to `AppConfig` in `backend/db/models.py` and create Alembic migration `backend/db/migrations/versions/007_add_health_config.py` (`down_revision = "006_add_athena_config"`, mirror `006_add_athena_config.py`)
- [X] T004 [P] Add health enums and transient API models to `backend/models/schemas.py`: `HealthStatus` (up/down/unknown), `HealthWindow` (1h/24h/7d, each carrying a `timedelta`), `HealthServiceType` (glue_job/glue_workflow/lambda_function/datasync_task), `ServiceHealth`, `ServiceHealthResponse`, `HealthResource`, `HealthResourcesResponse` (per data-model.md)
- [X] T005 Define the `HealthCheckStrategy` ABC in `backend/strategies/health_check.py` with `service_type` class attr, `check(ids, start, end) -> list[ServiceHealth]`, and `discover() -> list[HealthResource]` (depends on T004 for types)

**Checkpoint**: Schema, storage column, and strategy contract exist — user stories can begin.

---

## Phase 3: User Story 1 - View health of configured services on demand (Priority: P1) 🎯 MVP

**Goal**: The Health tab shows one status card per configured resource (current up/down +
failure count) via `GET /api/health/services`, color-coded, with a Refresh action.

**Independent Test**: Seed `app_config.health_config` with one resource of each type, open
the Health tab (or call the endpoint), and confirm each resource returns a card with a
definite status (up/down/unknown) and a failure count; a resource whose latest run FAILED
shows a non-green/down state.

### Tests for User Story 1 (write first, must FAIL) ⚠️

- [X] T006 [P] [US1] Provider unit + ABC contract tests in `backend/tests/providers/test_health_checks.py`: each provider implements `HealthCheckStrategy`; `check()` maps Glue/Lambda/DataSync boto3 responses (mocked via `botocore.stub`) to correct `status`/`failure_count`; AWS error on one resource → `ServiceHealth(status=UNKNOWN, detail=...)`
- [X] T007 [P] [US1] Service tests in `backend/tests/services/test_health_service.py`: fan-out returns one `ServiceHealth` per configured resource; empty `health_config` → `[]`; one provider raising → that resource `unknown`, others still present (FR-012)
- [X] T008 [P] [US1] Router tests in `backend/tests/routers/test_health.py` (FastAPI `TestClient`, service mocked at DI boundary): `GET /api/health/services` returns `ServiceHealthResponse`; no config → `results == []` with `200`; response echoes requested window

### Implementation for User Story 1

- [X] T009 [P] [US1] Implement `GlueJobHealthCheck` in `backend/providers/health_check/glue_job.py` (`glue:GetJobRuns`; current = latest run state, failures = FAILED/TIMEOUT/ERROR runs within window; `discover()` = `glue:ListJobs`) per research §1
- [X] T010 [P] [US1] Implement `GlueWorkflowHealthCheck` in `backend/providers/health_check/glue_workflow.py` (`glue:GetWorkflowRuns`; failed run `Status=ERROR` / `Statistics.FailedActions>0`; `discover()` = `glue:ListWorkflows`)
- [X] T011 [P] [US1] Implement `LambdaHealthCheck` in `backend/providers/health_check/lambda_fn.py` (current = `GetFunctionConfiguration.State==Active`; failures = `cloudwatch:GetMetricStatistics` AWS/Lambda `Errors` Sum over window; `discover()` = `lambda:ListFunctions`)
- [X] T012 [P] [US1] Implement `DataSyncHealthCheck` in `backend/providers/health_check/datasync.py` (current = task `AVAILABLE`; failures = `ListTaskExecutions` + `DescribeTaskExecution` ERROR within window; `discover()` = `datasync:ListTasks` returning `{id: arn, label: name}`)
- [X] T013 [US1] Add `get_health_checkers(db) -> list[HealthCheckStrategy]` to `backend/plugin_registry.py`, resolving AWS credentials from `aws_config` (DB first, env fallback, single source — reuse the `_build_cloudwatch_source` pattern) and instantiating the four providers (depends on T009–T012)
- [X] T014 [US1] Implement `health_service.check_all(db, window)` in `backend/services/health_service.py`: read `health_config`, build (type, id) work list, fan out over providers with a bounded `concurrent.futures.ThreadPoolExecutor`, catch per-future exceptions → `unknown`, return `ServiceHealthResponse` (depends on T005, T013)
- [X] T015 [US1] Implement `GET /api/health/services` in `backend/routers/health.py` (query `window: HealthWindow = HealthWindow.H24`, `response_model=ServiceHealthResponse`, `db` via `Depends(get_db)`) per contracts/health-services.md (depends on T014)
- [X] T016 [US1] Register `health_router` in `backend/main.py` (`app.include_router(health_router)`) — verify no clash with the existing liveness `GET /api/health`
- [X] T017 [US1] Frontend Health tab: add `nav-health` button + `health-view` container in `frontend/index.html`; in `frontend/app.js` wire `_activateTab`, fetch `/api/health/services`, render one card per result (status badge + failure count + detail) and a Refresh button; add card/badge styles reusing existing CSS custom properties in `frontend/style.css`

**Checkpoint**: Health tab renders live status cards from configured resources — MVP usable.

---

## Phase 4: User Story 2 - Choose the failure lookback window (Priority: P2)

**Goal**: A window control (1h/24h/7d) on the Health tab recomputes failure counts for the
selected window without a page reload.

**Independent Test**: With a resource that has failures spread across time, switch the
window between 1h/24h/7d and confirm the failure count changes to reflect only that window.

### Tests for User Story 2 (write first, must FAIL) ⚠️

- [X] T018 [P] [US2] Window-scoping tests in `backend/tests/providers/test_health_checks.py` and `backend/tests/services/test_health_service.py`: failures with timestamps inside vs. outside `[start, end]` are counted/excluded correctly for each provider; `HealthWindow` → `timedelta` mapping verified

### Implementation for User Story 2

- [X] T019 [US2] Add the window `<select>` (1h/24h/7d, default 24h) to the Health tab in `frontend/index.html`, and in `frontend/app.js` re-issue `GET /api/health/services?window=...` on change and on Refresh (backend already accepts `window` from US1)

**Checkpoint**: Failure counts respond to the selected window; US1 + US2 both work.

---

## Phase 5: User Story 3 - Configure which resources are monitored (Priority: P1)

**Goal**: Config-page pickers discover Glue jobs/workflows, Lambda functions, and DataSync
tasks from AWS, let the operator multi-select and save, and persist the selection.

**Independent Test**: On the Config page, open each picker, search, select resources, save,
reload → selections persist (via `GET /api/config` → `health`) and drive the Health tab.

### Tests for User Story 3 (write first, must FAIL) ⚠️

- [X] T020 [P] [US3] Repository tests in `backend/tests/repositories/test_config_repo.py` (real test DB): `upsert_health_config` writes all four lists, allows empty lists, and re-save overwrites; `get_app_config` round-trips `health_config`
- [X] T021 [P] [US3] Router tests in `backend/tests/routers/test_config.py`: each discovery endpoint returns `{resources: [...]}` on success and `400` on AWS error (discovery mocked); `PATCH /api/config/health` persists and round-trips via `GET /api/config`

### Implementation for User Story 3

- [X] T022 [P] [US3] Add `HealthConfigStatus`, `HealthConfigUpdate` to `backend/models/schemas.py` and a `health: HealthConfigStatus` field to `AppConfigRead` (whitespace-stripping list validators, empty allowed) per data-model.md
- [X] T023 [US3] Add `upsert_health_config(db, data)` to `backend/repositories/config_repo.py` and `_build_health_status(...)` to `backend/routers/config.py`, wiring `health` into the `GET /api/config` response (depends on T022, T003)
- [X] T024 [US3] Add the four discovery endpoints (`GET /api/config/health/glue-jobs|glue-workflows|lambda-functions|datasync-tasks`, each `response_model=HealthResourcesResponse`, calling the matching provider's `discover()` via `get_health_checkers`) and `PATCH /api/config/health` (`response_model=ConfigSaveResult`) to `backend/routers/config.py` per contracts/health-config.md (depends on T013, T022, T023)
- [X] T025 [US3] Frontend Config pickers: add four searchable multi-select pickers (Glue Jobs, Glue Workflows, Lambda Functions, DataSync Tasks) to `frontend/index.html`; implement one reusable picker helper (fetch URL + storage key) in `frontend/app.js` that populates from the discovery endpoints and saves via `PATCH /api/config/health`; style with existing CSS vars in `frontend/style.css` (leave the existing CloudWatch picker untouched)

**Checkpoint**: Operator can discover, select, and persist monitored resources end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T026 [P] Run `ruff format` and `ruff check` (line length 100, `F/E/I/UP`) on all new/changed files; fix findings
- [X] T027 Run `pytest --cov=backend --cov-fail-under=80` and confirm per-layer targets (services ≥85%, providers ≥70%, routers ≥75%, repositories ≥80%) are met
- [X] T028 Execute the `specs/021-service-health-dashboard/quickstart.md` validation scenarios (1–6) against a running instance
- [X] T029 [P] Update `.env.example`/`README.md` only if new env fallbacks are introduced (none expected — credentials reuse `aws_config`); otherwise skip

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: depends on Foundational. The MVP.
- **User Story 2 (Phase 4)**: depends on Foundational; builds on US1's endpoint (window
  param already supported) — only adds the UI control + window tests.
- **User Story 3 (Phase 5)**: depends on Foundational; reuses US1's `get_health_checkers`
  (T013) for discovery. Otherwise independently testable (discovery mocked in tests).
- **Polish (Phase 6)**: after all desired stories.

### Key task-level dependencies

- T005 → T004 (ABC imports schemas)
- T013 → T009–T012 (registry builds the providers)
- T014 → T005, T013 · T015 → T014 · T016 → T015
- T023 → T022, T003 · T024 → T013, T022, T023

### Within each user story

- Tests written first and FAIL before implementation (Constitution IV).
- Providers → registry → service → endpoint → frontend.

### Parallel Opportunities

- Setup: T001, T002 in parallel.
- Foundational: T004 parallel with T003; T005 after T004.
- US1 tests: T006, T007, T008 in parallel. US1 providers: T009–T012 in parallel.
- US3: T020, T021 in parallel; T022 parallel with them.

---

## Parallel Example: User Story 1

```bash
# Tests first (parallel):
Task: "Provider + ABC contract tests in backend/tests/providers/test_health_checks.py"
Task: "Service fan-out tests in backend/tests/services/test_health_service.py"
Task: "Router tests in backend/tests/routers/test_health.py"

# Then the four providers (parallel):
Task: "GlueJobHealthCheck in backend/providers/health_check/glue_job.py"
Task: "GlueWorkflowHealthCheck in backend/providers/health_check/glue_workflow.py"
Task: "LambdaHealthCheck in backend/providers/health_check/lambda_fn.py"
Task: "DataSyncHealthCheck in backend/providers/health_check/datasync.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & validate** the
   Health tab against seeded config → demo.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → live health cards (MVP).
3. US3 → self-service configuration of monitored resources.
4. US2 → selectable lookback window.
   (US3 before US2 is a reasonable delivery order since configuration unlocks real data;
   both remain independently testable.)

---

## Notes

- [P] = different files, no incomplete dependencies.
- Verify each test fails before implementing; commit after each task or logical group.
- Reuse the CloudWatch credential/discovery patterns; do not modify the existing
  CloudWatch picker (surgical change, Constitution II/III).
- No background polling, history, or alerting — on-demand only (FR-013).
