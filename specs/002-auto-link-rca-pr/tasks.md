---

description: "Task list for feature implementation"
---

# Tasks: Auto-Link RCA Cases to GitHub Pull Requests

**Input**: Design documents from `/specs/002-auto-link-rca-pr/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Test tasks ARE included below because Constitution Principle IV
(Test-First Discipline & Coverage Gates) is NON-NEGOTIABLE for this project
(`services/` ≥85%, `repositories/` ≥80% against a real test DB, `routers/`
≥75%).

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Add the persisted column and DTO fields shared by all stories

- [ ] T001 Create an Alembic migration adding a nullable `linked_pr` JSONB
      column to `rca_cases` in `backend/db/migrations/versions/`, per
      `specs/002-auto-link-rca-pr/data-model.md`
- [ ] T002 [P] Add `linked_pr: Mapped[dict | None] = mapped_column(JSONB)` to
      the `RcaCase` model in `backend/db/models.py`
- [ ] T003 [P] Add a `LinkedPullRequest` Pydantic model (`number`, `title`,
      `author`, `state: Literal["open", "merged", "closed"]`, `url`, `branch`,
      `updated_at`) and a `linked_pull_request: LinkedPullRequest | None = None`
      field on `FailureGroup` in `backend/models/schemas.py`, per
      `specs/002-auto-link-rca-pr/data-model.md`

---

## Phase 2: Foundational

**Purpose**: Shared PR-matching and persistence helpers required by all user
stories

**⚠️ CRITICAL**: T004 and T005 MUST exist before any user-story task below

- [ ] T004 Create `backend/services/pr_link_service.py` with:
      - `derive_state(pr: PullRequestInfo) -> Literal["open", "merged", "closed"]`
        (merged if `merged_at`/equivalent is set, else `pr.state`)
      - `score_pull_request(group: FailureGroup, pr: PullRequestInfo) -> int`
        (substring match of `group.component` / error code from
        `group.error_pattern` against `pr.branch`, `pr.title`, and PR body)
      - `find_best_match(group: FailureGroup, pull_requests: list[PullRequestInfo]) -> LinkedPullRequest | None`
        (highest score >0, ties broken by most recent `updated_at`)
      per `specs/002-auto-link-rca-pr/research.md` "PR matching strategy"
- [ ] T005 [P] Add to `backend/repositories/case_repo.py`:
      - `get_linked_pr(db, case_id) -> dict | None`
      - `set_linked_pr(db, case_id, linked_pr: dict | None, activity_type: str, payload: dict) -> None`
        (updates `RcaCase.linked_pr` and calls `add_activity` with the given
        `activity_type` — one of `pr_linked`, `pr_updated`, `pr_unlinked`)
      per `specs/002-auto-link-rca-pr/data-model.md` "Case Activity"

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - See a related pull request on the RCA report (Priority: P1) 🎯 MVP

**Goal**: `POST /api/analyze` attaches a `linked_pull_request` (title, author,
status, url) to failure groups with a matching PR (FR-001–FR-006)

**Independent Test**: Run `specs/002-auto-link-rca-pr/quickstart.md` User
Story 1 steps — analyze a component with a known matching PR and verify
`linked_pull_request` is populated; analyze one with no match and verify it's
absent; unset `GITHUB_REPO` and verify the response is unchanged from
baseline

### Tests for User Story 1

- [ ] T006 [P] [US1] Unit tests for `pr_link_service.find_best_match` and
      `score_pull_request` covering: match via branch name, match via title,
      match via body, and no match (score 0 for all candidates) in
      `backend/tests/services/test_pr_link_service.py`
- [ ] T007 [P] [US1] Contract test: `POST /api/analyze` with a configured repo
      and a PR matching a failure group's component/error returns
      `failure_groups[].linked_pull_request` with `title`, `author`, `state`,
      `url` in `backend/tests/routers/test_analysis_analyze.py`
- [ ] T008 [P] [US1] Contract test: `POST /api/analyze` with `GITHUB_REPO`
      unset returns no `linked_pull_request` field on any failure group and is
      otherwise identical to the pre-feature baseline response, in
      `backend/tests/routers/test_analysis_analyze.py`

### Implementation for User Story 1

- [ ] T009 [US1] In `backend/services/rca_orchestrator.py`, after
      `failure_groups` are built and only when `settings.github_repo` is
      configured, call `github_service.list_pull_requests()` once and, for
      each group, call `pr_link_service.find_best_match(group, pull_requests)`
      and assign the result to `group.linked_pull_request`
- [ ] T010 [US1] Wrap the T009 lookup/matching call in `try/except`, logging a
      warning and leaving `linked_pull_request=None` on every group if it
      raises — per FR-005 and the existing `code_analysis` degradation pattern
      in `backend/agents/code_analysis_agent.py`
- [ ] T011 [US1] In `backend/services/persistence_service.persist_analysis`,
      after `case_repo.create_case_from_group(...)`, if
      `group.linked_pull_request` is set, call
      `case_repo.set_linked_pr(db, case.id, group.linked_pull_request.model_dump(), "pr_linked", {...})`
      (FR-007, FR-009)
- [ ] T012 [P] [US1] Render a "Related Pull Request" badge (title as link,
      author, status) within each failure-group card in `frontend/app.js`,
      with styling added to `frontend/style.css`

**Checkpoint**: User Story 1 is independently functional and testable

---

## Phase 4: User Story 2 - Know whether the related fix has already shipped (Priority: P2)

**Goal**: `linked_pull_request.state` correctly reflects `open`, `merged`, or
`closed`, and the UI distinguishes them (FR-004, User Story 2)

**Independent Test**: Run `specs/002-auto-link-rca-pr/quickstart.md` User
Story 2 steps — analyze with the linked PR open, then merged, then closed, and
verify `linked_pull_request.state` updates accordingly

### Tests for User Story 2

- [ ] T013 [P] [US2] Extend `backend/tests/services/test_pr_link_service.py`
      with `derive_state` cases: `merged_at` set → `"merged"`; `state="closed"`
      with no `merged_at` → `"closed"`; `state="open"` → `"open"`
- [ ] T014 [P] [US2] Extend
      `backend/tests/routers/test_analysis_analyze.py` with fixtures for an
      open, a merged, and a closed PR, asserting
      `linked_pull_request.state` matches in each case

### Implementation for User Story 2

- [ ] T015 [US2] Ensure `backend/services/github_service.list_pull_requests`
      and `PullRequestInfo` (`backend/models/schemas.py`) carry the
      `merged_at` field from the GitHub MCP `list_pull_requests` response so
      `pr_link_service.derive_state` can use it; pass `state="all"` (or both
      `open` and `closed`) when calling `list_pull_requests` from
      `rca_orchestrator` so merged/closed PRs are considered
- [ ] T016 [P] [US2] Add status-pill styling for `open`/`merged`/`closed` to
      the "Related Pull Request" badge in `frontend/style.css` and
      `frontend/app.js`

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Persist the link for recurring cases (Priority: P3)

**Goal**: A case's `linked_pr` is set on first link, retained when no new
candidate is found, updated when a stronger candidate is found, and cleared
when the previously linked PR is no longer resolvable (FR-007–FR-010)

**Independent Test**: Run `specs/002-auto-link-rca-pr/quickstart.md` User
Story 3 steps — link a PR on one analysis, confirm it's retained on a second
analysis with no new candidate, then confirm it's replaced when a stronger
candidate appears, and cleared when the linked PR becomes unresolvable

### Tests for User Story 3

- [ ] T017 [P] [US3] Repository tests for `case_repo.set_linked_pr` /
      `get_linked_pr` covering: first link writes `linked_pr` and a
      `pr_linked` activity row; a second call writes a `pr_updated` activity
      row and updates `linked_pr`; a clearing call (`linked_pr=None`) writes a
      `pr_unlinked` activity row, in
      `backend/tests/repositories/test_case_repo.py`
- [ ] T018 [US3] `persistence_service` test covering three consecutive
      `persist_analysis` calls for the same `(component_name, error_code,
      stage)` signature: (1) sets `linked_pr` to PR A, (2) with no candidate
      found retains PR A, (3) with a stronger-scoring PR B replaces `linked_pr`
      with PR B, in `backend/tests/services/test_persistence_service.py`

### Implementation for User Story 3

- [ ] T019 [US3] In `persistence_service.persist_analysis`, when a failure
      group links to an existing case (recurring signature), compare
      `group.linked_pull_request` (if any) against
      `case_repo.get_linked_pr(db, case.id)` using
      `pr_link_service.score_pull_request`; call `case_repo.set_linked_pr(...,
      "pr_updated", ...)` only if the new candidate scores strictly higher,
      otherwise leave the existing `linked_pr` untouched (FR-008)
- [ ] T020 [US3] In `backend/services/rca_orchestrator.py` (or
      `pr_link_service`), when a case already has a `linked_pr`, check whether
      its `number` is present in the current `list_pull_requests` result; if
      absent and `find_best_match` found no replacement for that group, call
      `case_repo.set_linked_pr(db, case.id, None, "pr_unlinked", {"previous":
      ...})` (FR-010)

**Checkpoint**: All three user stories are independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T021 Run `pytest --cov=backend --cov-fail-under=80` and confirm
      `services/` ≥85%, `repositories/` ≥80% (against the real test DB),
      `routers/` ≥75% for the new/changed `pr_link_service.py`,
      `case_repo.py`, `persistence_service.py`, `rca_orchestrator.py`, and
      `routers/analysis.py` code
- [ ] T022 [P] Run `ruff format` and `ruff check` across the repo and fix any
      issues
- [ ] T023 Run the full `specs/002-auto-link-rca-pr/quickstart.md` (all 3 user
      stories + edge cases) against a configured GitHub repository
- [ ] T024 [P] Update the `README.md` "Roadmap / Planned Enhancements" section
      to move "Auto-link RCA → PR" from planned to implemented, referencing
      `specs/002-auto-link-rca-pr`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T003 defines
  `LinkedPullRequest` used by T004) — BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational; can proceed in
  parallel or in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — no dependency on
  US2/US3
- **User Story 2 (P2)**: Builds on US1's `linked_pull_request` field and
  `pr_link_service`; independently testable once `derive_state`/`merged_at`
  plumbing (T015) is in place
- **User Story 3 (P3)**: Builds on US1's persistence path (T011) and Phase 2's
  `case_repo.set_linked_pr`/`get_linked_pr` (T005); independently testable via
  `persist_analysis`

### Within Each User Story

- Tests (T006-T008, T013-T014, T017-T018) before/alongside implementation
- `pr_link_service` (Phase 2) before orchestrator integration (T009)
- Orchestrator integration (T009-T010) before persistence (T011)
- Persistence (T011) before frontend rendering (T012)

### Parallel Opportunities

- T002, T003 (Setup, different files) in parallel
- T006, T007, T008 (US1 tests, different files) in parallel
- T013, T014 (US2 tests, different files) in parallel
- T017 (US3 repository test) in parallel with T018 (service test, different
  file)
- T022, T024 in Polish can run in parallel with T021/T023

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit tests for pr_link_service in backend/tests/services/test_pr_link_service.py"
Task: "Contract test for /api/analyze with matching PR in backend/tests/routers/test_analysis_analyze.py"
Task: "Contract test for /api/analyze with GITHUB_REPO unset in backend/tests/routers/test_analysis_analyze.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `POST /api/analyze` surfaces `linked_pull_request`
   per FR-001–FR-006, with full test coverage per Principle IV

### Incremental Delivery

1. Setup + Foundational → scaffolding ready
2. User Story 1 → validate independently (MVP)
3. User Story 2 → validate independently (PR status)
4. User Story 3 → validate independently (persistence across recurrence)
5. Polish → confirm coverage gates and run full quickstart

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
- Every bug found during quickstart validation should be fixed with a
  regression test, per Constitution Principle IV
