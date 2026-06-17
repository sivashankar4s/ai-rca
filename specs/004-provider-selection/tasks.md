---
description: "Task list for feature implementation"
status: done
---

# Tasks: Per-Run Provider Selection

**Input**: Design documents from `/specs/004-provider-selection/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Test tasks ARE included because Constitution Principle IV (Test-First
Discipline & Coverage Gates) is NON-NEGOTIABLE: `routers/` ≥75% (via FastAPI
`TestClient`), `providers/` ≥70%, overall backend ≥80%.

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Schemas the endpoints depend on

- [ ] T001 [P] Add `data_source: Literal["athena","postgres"] | None = None` to
      `FailuresRequest` in `backend/models/schemas.py`, per data-model.md
- [ ] T002 [P] Add `ProviderOption` (`id`, `label`, `is_default`) and
      `ProvidersResponse` (`data_sources`, `log_backends`) Pydantic models to
      `backend/models/schemas.py`, per data-model.md

---

## Phase 2: Foundational

**Purpose**: A single place that reports available providers + defaults, reused by the
endpoint and tests

**⚠️ CRITICAL**: T003 MUST exist before the US3 endpoint task

- [ ] T003 Add a small `describe_providers() -> ProvidersResponse` helper (in
      `backend/plugin_registry.py` or a thin `routers/analysis.py` local) that builds
      the lists from the registry's known data-source/log-backend keys intersected with
      configuration, marking `is_default` from `settings.*_provider` (and the
      `local_data_file` short-circuit for the data source), per research.md Decision 4

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Choose the data source for a fetch (Priority: P1) 🎯 MVP

**Goal**: The fetch request carries a per-run data-source override that is forwarded to
`get_data_source(override=...)`; stored history is selectable; unknown/unavailable
selections fail loudly (FR-001, FR-003, FR-004, FR-007, FR-008, FR-010)

**Independent Test**: Run quickstart.md User Story 1 — fetch from stored history and
from the default source and confirm the source actually used.

### Tests for User Story 1

- [ ] T004 [P] [US1] Router test in `backend/tests/routers/test_analysis.py`
      (`TestClient`, registry mocked at the DI boundary): `POST /api/failures` with
      `data_source: "postgres"` forwards `override="postgres"` to `get_data_source`; with
      the field absent, no override is forwarded (default path)
- [ ] T005 [P] [US1] Router test: `POST /api/failures` with `data_source` naming an
      unavailable provider returns HTTP 400 and fetches nothing; a value outside the
      `Literal` returns HTTP 422 (request validation)

### Implementation for User Story 1

- [ ] T006 [US1] In `backend/routers/analysis.py`, read `request.data_source` and pass
      it as `get_data_source(override=request.data_source)`; ensure `None` preserves the
      current default behavior, per contracts/api.md
- [ ] T007 [US1] Ensure an unknown selection surfaces as a clear error: the registry's
      existing `ValueError` for an unknown key is translated by a FastAPI exception
      handler to HTTP 400 (add/confirm the handler); a selected-but-unreachable source
      propagates a message naming the source, with no fallback (FR-007), per research.md
      Decision 5

**Checkpoint**: User Story 1 is independently functional — the MVP

---

## Phase 4: User Story 2 - Choose the log backend for an analysis (Priority: P2)

**Goal**: The analyze UI sends the existing `log_backend` override; default behavior is
unchanged when unset (FR-002, FR-003, FR-010)

**Independent Test**: Run quickstart.md User Story 2 — analyze with a non-default
backend and confirm the queries/deep-links target it.

### Tests for User Story 2

- [ ] T008 [P] [US2] Router test in `backend/tests/routers/test_analysis.py`: `POST
      /api/analyze` with `log_backend: "grafana_loki"` forwards `override="grafana_loki"`
      to `get_log_backend`; absent → default path (no override)

### Implementation for User Story 2

- [ ] T009 [US2] Confirm/forward `request.log_backend` into
      `get_log_backend(override=...)` in `backend/routers/analysis.py` (the override
      parameter already exists in the registry); no contract change

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Discover availability + neutral identity (Priority: P3)

**Goal**: `GET /api/providers` reports real availability; the frontend populates its
selectors from it and uses neutral branding (FR-005, FR-006, FR-009)

**Independent Test**: Run quickstart.md User Story 3 — verify the selector reflects only
configured providers and the header is vendor-neutral.

### Tests for User Story 3

- [ ] T010 [P] [US3] Router test in `backend/tests/routers/test_analysis.py`: `GET
      /api/providers` returns 200 with `data_sources`/`log_backends`, each having exactly
      one `is_default: true`, and lists only configured providers (assert an unconfigured
      provider is absent)

### Implementation for User Story 3

- [ ] T011 [US3] Add `GET /api/providers` to `backend/routers/analysis.py` with
      `response_model=ProvidersResponse`, delegating to `describe_providers()` (T003),
      per contracts/api.md
- [ ] T012 [US3] In `frontend/index.html` + `frontend/app.js`: on load, call
      `/api/providers`; render a **Source** selector by the time-range controls and a
      **Log Backend** selector in the analyze step, each defaulted from `is_default`;
      send the chosen `data_source` / `log_backend` on fetch/analyze; attach listeners
      via `addEventListener` (no inline `onclick`)
- [ ] T013 [P] [US3] In `frontend/index.html`, replace the vendor-specific header
      tagline with a provider-neutral one (FR-009); add minimal selector styling to
      `frontend/style.css` reusing existing CSS custom properties

**Checkpoint**: All three user stories are independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T014 Run `pytest --cov=backend --cov-fail-under=80`; confirm `routers/analysis.py`
      ≥75% and the existing `PostgresDataSource` test still passes
- [ ] T015 [P] Run `ruff format` and `ruff check`; fix any issues
- [ ] T016 Run the full `specs/004-provider-selection/quickstart.md` (US1–US3 + edge
      cases) against a live default source and a populated stored history
- [ ] T017 [P] Update `README.md` to note per-run source/log-backend selection and the
      neutral tagline; update `ENGINEERING_OPS_COPILOT_VISION.md` §5/§8 to mark this
      Phase 1 slice implemented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T003 returns the T002 models) — BLOCKS US3
- **User Stories (Phase 3-5)**: US1 and US2 depend only on Setup; US3 depends on
  Foundational. Recommended order P1 → P2 → P3
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Needs only the `FailuresRequest.data_source` field (T001).
  Delivers the MVP.
- **User Story 2 (P2)**: Reuses the existing `log_backend` override; independent of US1.
- **User Story 3 (P3)**: Needs the describe helper (T003) + response models (T002).

### Parallel Opportunities

- T001, T002 (Setup, same file `schemas.py` — coordinate; mark [P] across files only)
- T004, T005 (US1 router tests) parallel with T008 (US2) and T010 (US3) — all in
  `test_analysis.py`, so sequence edits to that file; `[P]` denotes independence from
  non-test tasks
- T013 (branding/CSS) parallel with backend tasks

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (at least T001)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: a fetch can target stored history vs. the default source per
   run, with unknown selections rejected, router coverage ≥75%

### Incremental Delivery

1. Setup → schemas ready
2. US1 → per-run data-source selection (MVP)
3. US2 → per-run log-backend selection
4. US3 → `/api/providers` + selectors + neutral branding
5. Polish → coverage gates, lint, quickstart, docs

---

## Notes

- This feature reuses existing registry overrides and the existing `PostgresDataSource`;
  it adds no new strategy, provider, or persistence (Principle II)
- The override is request-scoped and never written back to `settings` (Principle V)
- Unknown/unavailable selections fail loudly; never silently substitute (Principle VI)
- Commit after each task or logical group; every bug found during quickstart gets a
  regression test (Principle IV)
