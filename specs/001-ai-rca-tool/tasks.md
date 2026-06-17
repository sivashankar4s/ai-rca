---
description: "Task list for feature implementation"
status: done
---

# Tasks: AI-Powered RCA Tool for Production Incidents

**Input**: Design documents from `/specs/001-ai-rca-tool/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Context**: This is a **from-scratch TDD build**. The `backend/` and `frontend/`
trees are intentionally deleted in the working tree; this feature rebuilds the whole
application from the design documents above. `plan.md`, `data-model.md`, and
`contracts/api.md` describe the **target** architecture (the prior implementation in git
`HEAD` may be used as reference only). Tasks follow Red-Green-Refactor: write the failing
test, then the implementation, per Constitution Principle IV.

**Tests**: Test tasks are MANDATORY and come first — Constitution Principle IV
(Test-First Discipline & Coverage Gates) is NON-NEGOTIABLE. Per-layer targets:
`services/` ≥85%, `repositories/` ≥80% (real test DB, not mocked SQL), `providers/`
≥70% (AWS/HTTP/LLM mocked via `botocore.stub`/`responses`/`httpx_mock` — never real
calls), `routers/` ≥75% (FastAPI `TestClient`, mocking at the DI boundary), overall
`backend/` ≥80% via `pytest --cov=backend --cov-fail-under=80`.

**Organization**: Tasks are grouped by user story so each story is independently
implementable and testable. **US1 is the MVP** and can ship before US2/US3 are built.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Bootable FastAPI skeleton + test/lint harness that every story builds on

- [ ] T001 Create `backend/__init__.py` and `backend/config.py` — `pydantic-settings`
      `Settings` with provider selectors and safe defaults so the app boots with no
      `.env`: `data_source_provider` (default `"local_file"`), `local_data_file`
      (default `"./sample_failures.json"`), `log_analysis_provider`, `llm_provider`,
      `database_url`, and `github_*` placeholders, per `plan.md` Technical Context and
      Constitution Principle V
- [ ] T002 Create `backend/main.py` — FastAPI app, CORS middleware, static mount for
      `frontend/`, router includes, and `GET /api/health` → `{"status": "ok"}`
- [ ] T003 [P] Create `requirements-dev.txt` (`pytest`, `pytest-cov`, `ruff`, `httpx`,
      `responses`/`httpx_mock`, `moto`/`botocore` stub deps) and extend
      `pyproject.toml` `[tool.pytest.ini_options]` with `--cov=backend` options;
      `.coverage-thresholds.json` (100% gate) already exists as the threshold source
- [ ] T004 [P] Create `backend/tests/__init__.py`, `backend/tests/conftest.py`
      (a `TestClient` fixture, and a real test-DB fixture that provisions a separate
      test database via Alembic for repository tests), and
      `backend/tests/test_health.py` asserting `GET /api/health` returns 200
- [ ] T005 [P] Create `sample_failures.json` at repo root — realistic records (schema per
      `README.md`) spanning multiple components and timestamps, including non-`FAILED`
      rows, to exercise filtering

**Checkpoint**: `uvicorn backend.main:app` boots; `pytest` + `ruff` run clean

---

## Phase 2: Foundational (BLOCKING)

**Purpose**: Shared strategy interfaces, registry, core schemas, and DB base used by
all stories

**⚠️ CRITICAL**: Phase 2 MUST complete before ANY user-story phase

- [ ] T006 Create strategy ABCs: `backend/strategies/__init__.py`,
      `backend/strategies/data_source.py` (`DataSourceStrategy.fetch_records(...) ->
      list[FailureRecord]`), `backend/strategies/llm.py` (`LLMStrategy`),
      `backend/strategies/log_analysis.py` (`LogAnalysisStrategy`), per Constitution
      Principle III
- [ ] T007 Create core DTOs in `backend/models/schemas.py`: `TimeRange(str, Enum)`
      (`1h|1d|1w|custom`), `EventData`, `FailureRecord`, `FailuresRequest`
      (`time_range`, `component?`, `start?`, `end?`, `data_source?`), `FailuresResponse`
      (`total`, `time_range`, `records`), with a `custom`-range validator, per
      `data-model.md`
- [ ] T008 Create the DB base: `backend/db/__init__.py`, `backend/db/session.py`
      (engine, `SessionLocal`, `get_db`), `backend/db/models.py` (Declarative base +
      `Project` ORM model), `alembic.ini` + `backend/db/migrations/` (env + initial
      migration creating `projects`), and `backend/repositories/__init__.py` +
      `backend/repositories/project_repo.py` (`get_or_create_default_project`), per
      `data-model.md` and Constitution Principle III
- [ ] T009 Create `backend/plugin_registry.py` with `get_data_source(override: str |
      None = None)` (`match` on `local_data_file` short-circuit / `data_source_provider`;
      `ValueError` on unknown key); `get_llm` / `get_log_backend` added in US2

**Checkpoint**: Foundation ready — user-story implementation can begin

---

## Phase 3: User Story 1 - Find failed records without manual queries (Priority: P1) 🎯 MVP

**Goal**: `POST /api/failures` retrieves, filters, paginates, persists (dedup), and
returns failed records; the UI renders them with cross-page selection
(FR-001–FR-004, FR-012)

**Independent Test**: `quickstart.md` "Validate User Story 1" against
`LOCAL_DATA_FILE=./sample_failures.json` — fetch by time range/component and confirm the
returned/displayed records, pagination, and selection.

### Tests for User Story 1 (write first — RED)

- [ ] T010 [P] [US1] Provider test `backend/tests/providers/test_local_file_data_source.py`:
      `LocalFileDataSource` returns only `FAILED` records within the window; `component`
      filter narrows; out-of-window and non-`FAILED` rows excluded (≥70%)
- [ ] T011 [P] [US1] Provider test `backend/tests/providers/test_athena_data_source.py`:
      `AthenaDataSource` query construction + row parsing via `botocore.stub`
      (`StartQueryExecution` → `GetQueryResults`); never a real AWS call (≥70%)
- [ ] T012 [P] [US1] Registry test `backend/tests/test_plugin_registry.py`:
      `get_data_source` returns `LocalFileDataSource` under `local_data_file`, `athena`
      under override, and raises `ValueError` on an unknown key
- [ ] T013 [P] [US1] Repository test `backend/tests/repositories/test_failure_repo.py`
      (real test DB): upsert dedup by `(project_id, file_trace_id)` — persisting the same
      record twice creates no duplicate (FR-012, SC-005) (≥80%)
- [ ] T014 [P] [US1] Router test `backend/tests/routers/test_analysis.py` (`TestClient`,
      data source mocked at DI boundary): `POST /api/failures` returns matching records
      for a time range (FR-001), narrows by `component` (FR-002), and returns
      `total: 0`, `records: []` for a no-match window (edge case) — not a 5xx

### Implementation for User Story 1 (GREEN)

- [ ] T015 [P] [US1] `backend/providers/data_source/__init__.py` +
      `backend/providers/__init__.py` + `backend/providers/data_source/local_file.py`
      (`LocalFileDataSource`: load JSON, parse `event_data`, filter FAILED/window/component)
- [ ] T016 [P] [US1] `backend/providers/data_source/athena.py` (`AthenaDataSource` via
      boto3: build Presto SQL, run query, parse rows → `FailureRecord`)
- [ ] T017 [US1] Wire `get_data_source` arms in `backend/plugin_registry.py` for
      `local_file` and `athena`
- [ ] T018 [US1] `backend/db/models.py` `FailureRecord` ORM (fields per `data-model.md`;
      unique `(project_id, file_trace_id)`) + Alembic migration for `failure_records`
- [ ] T019 [US1] `backend/repositories/failure_repo.py` — upsert dedup by
      `(project_id, file_trace_id)`; called to persist every fetched record (FR-012)
- [ ] T020 [US1] `backend/routers/analysis.py` — `POST /api/failures`
      (`response_model=FailuresResponse`): resolve window from `time_range`/custom dates,
      `get_data_source(override=request.data_source)`, persist via `failure_repo`, return
      records; include the router in `backend/main.py`; clean empty state
- [ ] T021 [US1] Frontend `frontend/index.html` + `frontend/app.js` + `frontend/style.css`:
      time-range controls + optional component, Fetch, paginated table with page-size
      selector, selection state keyed by `file_trace_id` that persists across pages
      (FR-003), select-all across all matches (FR-004), "No failures found" empty state;
      listeners via `addEventListener` (no inline `onclick`)

**Checkpoint**: US1 is an independently shippable MVP — fetch, display, paginate, select

---

## Phase 4: User Story 2 - Get an AI-generated root cause analysis (Priority: P2)

**Goal**: `POST /api/analyze` runs the 5-step pipeline (summarize → log queries →
execute → group/RCA → executive summary), returns failure groups + deep-links +
optional related code changes, and degrades gracefully when the log backend or repo is
unavailable (FR-005–FR-011, FR-015–FR-017)

**Independent Test**: `quickstart.md` "Validate User Story 2" — select records, analyze,
and confirm `failure_groups`, `summary`, log deep-links, and `code_analysis` behavior.

### Tests for User Story 2 (write first — RED)

- [ ] T022 [P] [US2] Router test (`test_analysis.py`): `POST /api/analyze` with
      `records: []` is rejected before the pipeline runs (FR-005)
- [ ] T023 [P] [US2] Service test `backend/tests/services/test_rca_orchestrator.py`: the
      5-step pipeline with `LLMStrategy` + `LogAnalysisStrategy` mocked — asserts
      grouping, summary, and per-group fields (≥85%)
- [ ] T024 [P] [US2] Provider test `backend/tests/providers/test_log_analysis.py`:
      `CloudWatchLogBackend` + `GrafanaLokiBackend` query generation and deep-link URL
      construction (≥70%)
- [ ] T025 [P] [US2] Provider test `backend/tests/providers/test_navify_llm.py`:
      `NavifyLLMProvider` request/response parsing via `responses`/`httpx_mock` (≥70%)
- [ ] T026 [P] [US2] Agent test `backend/tests/agents/test_code_analysis_agent.py` (MCP
      client mocked): `code_analysis.items` on success; `code_analysis.error` populated
      on lookup failure; `null` when `GITHUB_REPO` unset (FR-015/FR-016)
- [ ] T027 [US2] Router test (`test_analysis.py`) FR-016: with the log backend raising,
      `POST /api/analyze` still returns `failure_groups`/`summary`, with empty
      `cw_log_url`/`log_samples` for the affected group (SC-006)

### Implementation for User Story 2 (GREEN)

- [ ] T028 [US2] Analyze DTOs in `backend/models/schemas.py`: `AnalyzeRequest`
      (validator: ≥1 record — FR-005), `AnalyzeResponse`, `FailureGroup`,
      `CodeAnalysisResult`, `ConfigResponse`/`ConfigUpdateRequest`, per `data-model.md`
- [ ] T029 [US2] `backend/providers/llm/__init__.py` +
      `backend/providers/llm/navify.py` (`NavifyLLMProvider`) + `get_llm` arm in
      `plugin_registry.py`
- [ ] T030 [US2] `backend/providers/log_analysis/__init__.py` +
      `cloudwatch.py` + `grafana_loki.py` + `get_log_backend(override)` arm in
      `plugin_registry.py`
- [ ] T031 [US2] `backend/mcp/__init__.py` + `backend/mcp/client.py` (stdio
      github-mcp-server client) + `backend/agents/__init__.py` +
      `backend/agents/code_analysis_agent.py` (FR-015/FR-016)
- [ ] T032 [US2] `backend/services/__init__.py` +
      `backend/services/rca_orchestrator.py` — 5-step provider-agnostic pipeline; each
      external step (log backend, code analysis) wrapped so its failure is caught and
      surfaced inline, never aborting the response (FR-016, Principle VI)
- [ ] T033 [US2] Endpoints in `backend/routers/analysis.py`: `POST /api/analyze`
      (`response_model=AnalyzeResponse`), `GET`/`POST /api/config` (FR-017, secrets as
      `*_set` flags), `GET /api/models`
- [ ] T034 [US2] Frontend Step 2: select → Analyze, render failure groups with one-click
      log deep-links, executive summary, and the related-code-changes card (handles
      `code_analysis: null` and `code_analysis.error`)

**Checkpoint**: US1 + US2 both independently functional

---

## Phase 5: User Story 3 - Automatically detect recurring issues (Priority: P3)

**Goal**: Root-cause signatures create a new case the first time and link/flag an
existing case as recurring (with a `case_activity` entry) on repeat; repeated fetches
never duplicate failure records (FR-013, FR-014; re-verify FR-012)

**Independent Test**: `quickstart.md` "Validate User Story 3" — analyze the same
signature twice; confirm the second run reuses the case, sets `status = recurring`, and
appends a `case_activity` row.

### Tests for User Story 3 (write first — RED)

- [ ] T035 [P] [US3] Service test `backend/tests/services/test_signature_service.py`:
      signature hash derived stably from `component_name` + `error_code` + `stage`
      (FR-013) (≥85%)
- [ ] T036 [P] [US3] Repository test
      `backend/tests/repositories/test_signature_repo.py` (real DB): new
      `RootCauseSignature` for an unseen signature; match increments `occurrence_count` /
      `last_seen` (≥80%)
- [ ] T037 [P] [US3] Repository test `backend/tests/repositories/test_case_repo.py`
      (real DB): new `RcaCase` with `status = new`; on repeat signature, existing case
      linked, `status = recurring`, `case_activity` row appended (FR-014) (≥80%)
- [ ] T038 [US3] Service test
      `backend/tests/services/test_persistence_service.py`: persist an `AnalyzeResponse`
      with a new signature (→ new case `status = new`), then a second with the same
      `(component, error, stage)` (→ same case reused, `status = recurring`, activity
      recorded)
- [ ] T039 [US3] Repository test (extend `test_failure_repo.py`): persisting the same
      fetched batch twice does not duplicate `failure_records` (FR-012, SC-005)

### Implementation for User Story 3 (GREEN)

- [ ] T040 [US3] ORM models in `backend/db/models.py`: `RootCauseSignature`, `RcaCase`,
      `CaseFailureRecord`, `CaseActivity`, `CaseSignatureLink` (per `data-model.md`) +
      Alembic migration
- [ ] T041 [US3] `backend/services/signature_service.py` — signature hashing/matching
      (FR-013)
- [ ] T042 [US3] `backend/repositories/signature_repo.py` +
      `backend/repositories/case_repo.py`
- [ ] T043 [US3] `backend/services/persistence_service.py` — on each analysis, create or
      link cases by signature, flag recurrence, append `case_activity`; wire into the
      `POST /api/analyze` flow (FR-014)

**Checkpoint**: All three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T044 Run `pytest --cov=backend --cov-fail-under=80`; confirm per-layer targets
      (`services/` ≥85%, `repositories/` ≥80%, `providers/` ≥70%, `routers/` ≥75%);
      close any gaps
- [ ] T045 [P] Run `ruff format` and `ruff check`; fix all issues
- [ ] T046 Run the full `specs/001-ai-rca-tool/quickstart.md` (US1–US3 + edge cases)
      against the docker-compose Postgres instance (US2/US3) and `LOCAL_DATA_FILE` (US1)
- [ ] T047 [P] Update `README.md` (note the rebuilt 001 baseline) and reconcile any spec
      discrepancies found during implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3-5)**: Depend on Foundational; then priority order P1 → P2 → P3.
  US1 ships without US2/US3. US2 and US3 each extend the shared `routers/analysis.py`,
  `models/schemas.py`, and `db/models.py`, so build them after US1.
- **Polish (Phase 6)**: After all desired stories

### User Story Dependencies

- **US1 (P1)**: Needs only Foundational. Delivers the MVP (fetch + persist + display).
- **US2 (P2)**: Adds the LLM/log providers, MCP agent, orchestrator, and analyze
  endpoint. Independent of US3.
- **US3 (P3)**: Adds signatures + cases + recurrence persistence; consumes the analysis
  output from US2, so build after US2.

### Within Each User Story

- Tests (RED) before implementation (GREEN); commit after each task or logical group
- Sequential where tasks touch the same file (`schemas.py`, `analysis.py`, `db/models.py`)

### Parallel Opportunities

- T003, T004, T005 (Setup, different files)
- T010–T014 (US1 tests, different files)
- T015, T016 (US1 providers, different files)
- T022–T026 (US2 tests, different files)
- T035–T037 (US3 tests, different files)
- T045, T047 (Polish) alongside T044/T046

---

## Parallel Example: User Story 1

```bash
# Launch the US1 tests together (different files):
Task: "Provider test for LocalFileDataSource in backend/tests/providers/test_local_file_data_source.py"
Task: "Provider test for AthenaDataSource (botocore.stub) in backend/tests/providers/test_athena_data_source.py"
Task: "Registry test in backend/tests/test_plugin_registry.py"
Task: "Repository dedup test in backend/tests/repositories/test_failure_repo.py"
Task: "Router test for POST /api/failures in backend/tests/routers/test_analysis.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `POST /api/failures` fetches/persists/dedups per
   FR-001–FR-004/FR-012, the UI paginates and preserves selection, and coverage meets
   Principle IV — this is a shippable slice

### Incremental Delivery

1. Setup + Foundational → bootable skeleton + shared base
2. US1 → fetch + persist + display (MVP)
3. US2 → AI analysis pipeline + config
4. US3 → recurring-case detection
5. Polish → coverage gate, lint, full quickstart, docs

---

## Notes

- Build from the design docs (`plan.md`, `data-model.md`, `contracts/api.md`); the prior
  `HEAD` implementation is reference only
- TDD is mandatory: write the failing test first, then implement (Principle IV)
- Tests never make real AWS/LLM/GitHub calls — mock at the provider/DI boundary
- Repository tests run against a real test DB (Principle IV), not mocked SQL
- [P] = different files, no dependencies; [Story] maps a task to its user story
- Commit after each task or logical group; every bug found gets a regression test
