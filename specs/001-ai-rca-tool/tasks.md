---

description: "Task list for feature implementation"
---

# Tasks: AI-Powered RCA Tool for Production Incidents

**Input**: Design documents from `/specs/001-ai-rca-tool/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Context**: This feature documents the **existing, already-implemented** RCA
pipeline as baseline 001 (see plan.md Summary). The functional code already
exists in `backend/` and `frontend/`. The tasks below therefore focus on:
(a) validating each user story against the running system via
`quickstart.md`, and (b) closing test-coverage gaps required by Constitution
Principle IV (services ≥85%, repositories ≥80% against a real test DB,
providers ≥70%, routers ≥75%) so the baseline is verifiably compliant before
new features build on it.

**Tests**: Test tasks ARE included below because Constitution Principle IV
(Test-First Discipline & Coverage Gates) is NON-NEGOTIABLE for this project.

**Organization**: Tasks are grouped by user story to enable independent
validation of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Confirm the local environment runs the existing baseline before
validating/extending it

- [ ] T001 Follow `LOCAL_SETUP.md` to install dependencies, configure `.env`
      (with `LOCAL_DATA_FILE=./sample_failures.json` for a no-AWS check), start
      Postgres via `docker compose up -d`, and apply migrations with
      `alembic upgrade head`
- [ ] T002 [P] Run `ruff format --check .` and `ruff check .` from the repo
      root and confirm both pass against the current `backend/` code
- [ ] T003 [P] Run `pytest --cov=backend` from the repo root and record the
      current per-module coverage as the starting baseline (no `--cov-fail-under`
      yet, for reference only)

---

## Phase 2: Foundational

**Purpose**: Establish the test scaffolding required by Constitution Principle
IV before story-level coverage tasks can run

**⚠️ CRITICAL**: T004 and T005 MUST exist before any repository/router tests in
later phases can be written

- [ ] T004 Create `backend/tests/repositories/__init__.py` and a pytest fixture
      in `backend/tests/conftest.py` that provisions a real test database
      (separate test schema/DB via Alembic) for repository tests, per
      Constitution Principle IV ("repositories ≥80% against a real test DB, not
      mocked SQL")
- [ ] T005 Create `backend/tests/routers/__init__.py` and a pytest fixture in
      `backend/tests/conftest.py` providing a FastAPI `TestClient` with
      provider dependencies overridden at the DI boundary (per Constitution
      Principle III/IV)

**Checkpoint**: Test scaffolding ready — user story validation/coverage tasks
can now proceed

---

## Phase 3: User Story 1 - Find failed records without manual queries (Priority: P1) 🎯 MVP

**Goal**: Confirm `POST /api/failures` correctly retrieves, filters, paginates,
and deduplicates failed records (FR-001–FR-003, FR-012)

**Independent Test**: Run the User Story 1 steps in `quickstart.md` against
`LOCAL_DATA_FILE=./sample_failures.json` and verify the returned records match
the chosen time range/component filter

### Tests for User Story 1

- [ ] T006 [P] [US1] Contract test for `POST /api/failures` (time range,
      component filter, default `failure_only=true`) per
      `specs/001-ai-rca-tool/contracts/api.md` in
      `backend/tests/routers/test_analysis_failures.py`
- [ ] T007 [P] [US1] Repository test for `FailureRecord` upsert/dedup by
      `(project_id, file_trace_id)` — fetching the same time range twice MUST
      NOT create duplicate rows (FR-012, SC-005) in
      `backend/tests/repositories/test_failure_repo.py`
- [ ] T008 [P] [US1] Provider test for `LocalFileDataSource` time-range and
      component filtering against `sample_failures.json` in
      `backend/tests/providers/test_local_file_data_source.py`

### Implementation for User Story 1

- [ ] T009 [US1] Run `specs/001-ai-rca-tool/quickstart.md` "Validate User Story
      1" steps end-to-end (UI + `curl` check against `POST /api/failures`);
      fix any discrepancy found between `spec.md` FR-001–FR-003 and the
      behavior of `backend/routers/analysis.py` / `backend/services/rca_orchestrator.py`
- [ ] T010 [US1] If T006–T008 reveal gaps (e.g. missing dedup, missing
      component filter), fix in
      `backend/repositories/failure_repo.py` and/or
      `backend/providers/data_source/local_file.py` / `athena.py`

**Checkpoint**: User Story 1 is validated and covered independently of US2/US3

---

## Phase 4: User Story 2 - Get an AI-generated root cause analysis (Priority: P2)

**Goal**: Confirm `POST /api/analyze` produces grouped root causes, an
executive summary, log deep-links, and optional related-code-changes, and
degrades gracefully when the log backend or code repository is unavailable
(FR-004–FR-011, FR-015, FR-016)

**Independent Test**: Run the User Story 2 steps in `quickstart.md` — select
failure records, call `POST /api/analyze`, and verify `failure_groups`,
`summary`, log deep-links, and `code_analysis` behavior

### Tests for User Story 2

- [ ] T011 [P] [US2] Contract test for `POST /api/analyze` success path
      (non-empty `failure_groups` with required fields, `summary` present, at
      least one `cw_log_url`) per `specs/001-ai-rca-tool/contracts/api.md` in
      `backend/tests/routers/test_analysis_analyze.py`
- [ ] T012 [P] [US2] Contract test for `POST /api/analyze` with `records: []`
      returning a validation error before the pipeline runs (FR-005) in
      `backend/tests/routers/test_analysis_analyze.py`
- [ ] T013 [P] [US2] Service test for `rca_orchestrator`'s 5-step pipeline
      (summarize → log queries → execute → group/RCA → executive summary)
      with `LLMStrategy` and `LogAnalysisStrategy` mocked, in
      `backend/tests/services/test_rca_orchestrator.py`
- [ ] T014 [P] [US2] Provider tests for `CloudWatchLogBackend` and
      `GrafanaLokiBackend` query generation and deep-link URL construction in
      `backend/tests/providers/test_log_analysis.py`
- [ ] T015 [US2] Test for FR-016 (log-backend path): when the configured log
      backend raises/returns no results, `POST /api/analyze` still returns
      `failure_groups`/`summary`, with empty `cw_log_url`/`log_samples` for the
      affected group, in `backend/tests/routers/test_analysis_analyze.py`
- [ ] T016 [US2] Test for FR-015/FR-016 (code-analysis path): `code_analysis`
      is `null` when `GITHUB_REPO` unset; `code_analysis.error` is populated
      (response still 200 with `failure_groups`/`summary` intact) when
      `GITHUB_REPO` is set but the MCP server is unreachable — extend
      `backend/tests/agents/test_code_analysis_agent.py` and
      `backend/tests/routers/test_analysis_analyze.py`

### Implementation for User Story 2

- [ ] T017 [US2] Run `specs/001-ai-rca-tool/quickstart.md` "Validate User Story
      2" steps end-to-end; fix any discrepancy found between `spec.md`
      FR-004–FR-011/FR-015/FR-016 and `backend/services/rca_orchestrator.py`,
      `backend/providers/log_analysis/*`, or `backend/agents/code_analysis_agent.py`
- [ ] T018 [US2] If T011–T016 reveal gaps in graceful degradation (FR-016),
      add/adjust try/except handling per Constitution Principle VI in
      `backend/services/rca_orchestrator.py` and
      `backend/agents/code_analysis_agent.py` so failures are caught and
      surfaced inline rather than raised

**Checkpoint**: User Stories 1 AND 2 are both validated and covered
independently

---

## Phase 5: User Story 3 - Automatically detect recurring issues (Priority: P3)

**Goal**: Confirm root-cause signatures correctly create new cases or flag
existing cases as recurring with an activity-log entry, and that repeated
fetches do not duplicate failure records (FR-012–FR-014)

**Independent Test**: Run the User Story 3 steps in `quickstart.md` — analyze
the same failure signature twice and verify the second run links to the
existing `rca_cases` row, sets `status = recurring`, and adds a
`case_activity` entry

### Tests for User Story 3

- [ ] T019 [P] [US3] Repository tests for `signature_repo` — creating a new
      `RootCauseSignature` for an unseen `(component_name, error_code, stage)`
      and matching an existing one, incrementing `occurrence_count` /
      `last_seen`, in `backend/tests/repositories/test_signature_repo.py`
- [ ] T020 [P] [US3] Repository tests for `case_repo` — creating a new
      `RcaCase` with `status = new` for a first-seen signature, and linking an
      existing case + appending a `case_activity` row + setting
      `status = recurring` for a repeated signature, in
      `backend/tests/repositories/test_case_repo.py`
- [ ] T021 [US3] Extend `backend/tests/services/test_persistence_service.py`
      with an end-to-end case: persist an `AnalyzeResponse` with a new
      signature (expect new `RcaCase`, `status = new`), then persist a second
      `AnalyzeResponse` with the same `(component_name, error_code, stage)`
      (expect the same case reused, `status = recurring`, new
      `case_activity` row recorded)
- [ ] T022 [US3] Extend `backend/tests/repositories/test_failure_repo.py` with
      a test that fetching the same time range twice via persistence does not
      duplicate `failure_records` rows (FR-012, SC-005)

### Implementation for User Story 3

- [ ] T023 [US3] Run `specs/001-ai-rca-tool/quickstart.md` "Validate User Story
      3" steps end-to-end against the local Postgres instance; fix any
      discrepancy found between `spec.md` FR-013/FR-014 and
      `backend/services/signature_service.py` /
      `backend/services/persistence_service.py` /
      `backend/repositories/{signature,case}_repo.py`

**Checkpoint**: All three user stories are validated and covered independently

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the baseline meets project-wide quality gates after all
stories are validated

- [ ] T024 Run `pytest --cov=backend --cov-fail-under=80` and confirm
      per-layer targets from Constitution Principle IV are met (`services/`
      ≥85%, `repositories/` ≥80%, `providers/` ≥70%, `routers/` ≥75%);
      address any remaining gaps
- [ ] T025 [P] Run `ruff format` and `ruff check` across the repo and fix any
      remaining issues
- [ ] T026 Run the full `specs/001-ai-rca-tool/quickstart.md` (all 3 user
      stories + edge cases) against the docker-compose Postgres instance with
      a real or local-file data source
- [ ] T027 [P] Reconcile any discrepancies found during T009/T017/T023 between
      `README.md` / `CRM_PLAN.md` and the behavior documented in
      `specs/001-ai-rca-tool/spec.md`, `data-model.md`, and `contracts/api.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS repository
  and router test tasks in all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion;
  stories can then proceed in parallel or in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — no dependency on US2/US3
- **User Story 2 (P2)**: Can start after Foundational — independently testable;
  shares `backend/tests/routers/` scaffolding with US1 (T005)
- **User Story 3 (P3)**: Can start after Foundational — independently testable;
  shares `backend/tests/repositories/` scaffolding with US1 (T004)

### Within Each User Story

- Tests (T006-T008, T011-T016, T019-T022) before fixes (T010, T018, T023)
- Quickstart validation (T009, T017, T023) can run alongside writing tests
- Story complete before moving to the next priority if working sequentially

### Parallel Opportunities

- T002, T003 can run in parallel during Setup
- T006, T007, T008 (US1 tests, different files) can run in parallel
- T011-T014 (US2 tests, different files) can run in parallel
- T019, T020 (US3 repository tests, different files) can run in parallel
- T025, T027 in Polish can run in parallel with T024/T026

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for POST /api/failures in backend/tests/routers/test_analysis_failures.py"
Task: "Repository test for FailureRecord dedup in backend/tests/repositories/test_failure_repo.py"
Task: "Provider test for LocalFileDataSource filtering in backend/tests/providers/test_local_file_data_source.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `POST /api/failures` behaves per FR-001–FR-003/FR-012
   and is covered by tests meeting Principle IV targets

### Incremental Delivery

1. Setup + Foundational → scaffolding ready
2. User Story 1 → validate independently (MVP)
3. User Story 2 → validate independently
4. User Story 3 → validate independently
5. Polish → confirm coverage gates and run full quickstart

---

## Notes

- This baseline contains **no new feature code** — tasks close test-coverage
  gaps and validate existing behavior against `spec.md`. Any bug found during
  validation (T009, T010, T017, T018, T023) should be fixed as a small,
  targeted change with a regression test, per Constitution Principle IV.
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
