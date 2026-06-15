---
description: "Task list for feature implementation"
---

# Tasks: Inline PR Review Comments

**Input**: Design documents from `/specs/003-inline-pr-comments/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Test tasks ARE included because Constitution Principle IV (Test-First
Discipline & Coverage Gates) is NON-NEGOTIABLE: `services/` ≥85%, `routers/` ≥75%
(via FastAPI `TestClient`), overall backend ≥80%.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Shared DTO and test scaffolding used by all stories

- [ ] T001 [P] Add the `PostedReviewResult` Pydantic model (`repo`, `target`,
      `posted`, `review_url`, `inline_comment_count`, `summary_only_count`,
      `verdict`, `error`) to `backend/models/schemas.py`, per
      `specs/003-inline-pr-comments/data-model.md`
- [ ] T002 [P] Create the new router test package file
      `backend/tests/routers/__init__.py` (empty) so endpoint tests can live under
      `backend/tests/routers/`

---

## Phase 2: Foundational

**Purpose**: Shared posting helpers + the service entry point all stories build on

**⚠️ CRITICAL**: T003 and T004 MUST exist before any user-story task below

- [ ] T003 Add helpers to `backend/services/code_review_service.py`:
      `_is_anchorable(finding) -> bool` (true when `finding.file` is non-empty and
      `finding.line` is a positive int) and `_format_comment_body(finding) -> str`
      (renders severity, category, title, description, recommendation as readable
      Markdown), per `specs/003-inline-pr-comments/research.md` Decisions 1 & 4
- [ ] T004 Add `post_review_to_pull_request(number: int, review: CodeReviewResult)
      -> PostedReviewResult` to `backend/services/code_review_service.py` with the
      repo/token guard (reuse `parse_repo(settings.github_repo)` + `settings.github_token`
      checks exactly as `review_pull_request` does) returning a
      `PostedReviewResult(posted=False, error=...)` when unconfigured; otherwise
      delegating to the flow implemented in later phases

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Post AI findings onto the pull request (Priority: P1) 🎯 MVP

**Goal**: A single "Post to PR" action creates one GitHub review on the PR with each
anchorable finding as an inline comment + the summary as the review body, and returns
a link (FR-001–FR-003, FR-008, FR-009, FR-011, FR-012)

**Independent Test**: Run `specs/003-inline-pr-comments/quickstart.md` User Story 1 —
review a PR with at least one file/line finding, click "Post to PR", and confirm one
review with the expected inline comments + summary appears on GitHub and the app shows
its link.

### Tests for User Story 1

- [ ] T005 [P] [US1] Unit test in `backend/tests/services/test_code_review_service.py`:
      with `call_github_tool` patched, a successful post asserts the call sequence
      `pull_request_review_write(method="create")` → `add_comment_to_pending_review`
      (once per anchorable finding) → `pull_request_review_write(method="submit",
      event="COMMENT")`, and that the returned `PostedReviewResult` has `posted=True`,
      correct `inline_comment_count`, `verdict="COMMENT"`, and a `review_url`
- [ ] T006 [P] [US1] Contract test in `backend/tests/routers/test_github.py` using
      FastAPI `TestClient`: `POST /api/github/pull-requests/42/review/comments` with a
      `CodeReviewResult` body returns 200 and a `PostedReviewResult` with `posted=True`
      (service mocked at the router boundary)

### Implementation for User Story 1

- [ ] T007 [US1] Implement the happy-path flow in
      `backend/services/code_review_service.py`: short-circuit with `posted=False` +
      "nothing to post" when `review.findings` is empty (no MCP calls — FR-008);
      otherwise create the pending review, call `add_comment_to_pending_review`
      (`subjectType="line"`, `side="RIGHT"`) for each anchorable finding using
      `_format_comment_body`, submit with `event="COMMENT"` and the summary body, and
      capture `review_url` from the submit response (fallback to the PR URL) — per
      `specs/003-inline-pr-comments/research.md` Decisions 1, 6
- [ ] T008 [US1] Add `POST /api/github/pull-requests/{number}/review/comments` to
      `backend/routers/github.py` with `response_model=PostedReviewResult`, accepting a
      `CodeReviewResult` request body and delegating to
      `code_review_service.post_review_to_pull_request(number, body)`, per
      `specs/003-inline-pr-comments/contracts/api.md`
- [ ] T009 [US1] In `frontend/app.js` add a "Post to PR" button to the PR review
      result panel (PR reviews only), wired via `addEventListener`, that shows a
      confirmation dialog (always — re-posting creates a new review, FR-009), POSTs the
      displayed `CodeReviewResult` to the new endpoint, and renders the returned
      `review_url` + counts; add button/result styling to `frontend/style.css` reusing
      existing CSS custom properties

**Checkpoint**: User Story 1 is independently functional — the MVP

---

## Phase 4: User Story 2 - Non-anchorable findings still reach the PR (Priority: P2)

**Goal**: Findings without a resolvable file/line are folded into the review summary
body rather than dropped (FR-004, SC-002)

**Independent Test**: Run `specs/003-inline-pr-comments/quickstart.md` User Story 2 —
post a review containing both anchorable and non-anchorable findings and confirm the
non-anchorable ones appear in the review summary while `inline_comment_count +
summary_only_count` equals the total findings.

### Tests for User Story 2

- [ ] T010 [P] [US2] Unit tests in
      `backend/tests/services/test_code_review_service.py`: (a) a mixed findings list
      yields correct `inline_comment_count` and `summary_only_count` and the
      non-anchorable finding text appears in the submitted review body; (b) an
      all-non-anchorable list still submits a review with zero inline comments and all
      findings in the body

### Implementation for User Story 2

- [ ] T011 [US2] In `backend/services/code_review_service.py`, build the submit body
      by combining `review.summary` with a clearly labeled section listing each
      non-anchorable finding (via `_format_comment_body`), and set `summary_only_count`
      accordingly so `inline_comment_count + summary_only_count` == number of input
      findings, per `specs/003-inline-pr-comments/research.md` Decision 4

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Safe, transparent failures (Priority: P3)

**Goal**: Misconfiguration, lost write access, closed PRs, and mid-post failures
produce a clear error and never leave a stranded/partial review; displayed findings
are untouched (FR-006, FR-010, FR-012)

**Independent Test**: Run `specs/003-inline-pr-comments/quickstart.md` User Story 3 —
attempt to post with write access unavailable and with the MCP server unreachable, and
confirm `posted=false` with an actionable error and no partial review on the PR.

### Tests for User Story 3

- [ ] T012 [P] [US3] Unit tests in
      `backend/tests/services/test_code_review_service.py`: (a) repo/token not
      configured → `posted=False` with explanatory `error` and **no** `call_github_tool`
      invocation; (b) a finding-bearing post where `add_comment_to_pending_review` (or
      submit) raises → the service calls `pull_request_review_write(method="delete")`
      to remove the pending review and returns `posted=False` with the error
- [ ] T013 [P] [US3] Contract test in `backend/tests/routers/test_github.py`: posting
      with an empty `findings` body and with `GITHUB_REPO` unset each return 200 with
      `posted=False` and a populated `error`

### Implementation for User Story 3

- [ ] T014 [US3] In `backend/services/code_review_service.py`, wrap the MCP
      create/comment/submit flow in `try/except`: on failure after the pending review
      is created, best-effort call `pull_request_review_write(method="delete", ...)`,
      log via `logger.warning`, and return `PostedReviewResult(posted=False,
      error=str(exc))` — never swallow silently (Principle VI), per
      `specs/003-inline-pr-comments/research.md` Decision 5
- [ ] T015 [US3] In `frontend/app.js`, render the error state when `posted` is false
      (show the `error` message) and ensure a failed post leaves the displayed findings
      panel unchanged (FR-012)

**Checkpoint**: All three user stories are independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T016 Run `pytest --cov=backend --cov-fail-under=80` and confirm the new/changed
      code meets gates: `code_review_service.py` ≥85% and `routers/github.py` ≥75%
- [ ] T017 [P] Run `ruff format` and `ruff check` across the repo and fix any issues
- [ ] T018 Run the full `specs/003-inline-pr-comments/quickstart.md` (US1–US3 + edge
      cases) against a configured GitHub repo with a write-scoped token
- [ ] T019 [P] Update the `README.md` "Roadmap / Planned Enhancements" section to move
      "Inline PR review comments" from planned to implemented, referencing
      `specs/003-inline-pr-comments`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T004 returns the T001 `PostedReviewResult`)
  — BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational; then proceed in priority
  order (P1 → P2 → P3). US2 and US3 extend the US1 flow in the same service function.
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Needs only Foundational. Delivers the MVP.
- **User Story 2 (P2)**: Extends US1's submit-body construction (summary folding);
  build after US1's flow exists.
- **User Story 3 (P3)**: Wraps US1's flow with cleanup/error handling and the
  config guard from Foundational; build after US1.

### Within Each User Story

- Tests (T005/T006, T010, T012/T013) are written alongside/before implementation
- Service flow (T007) before the endpoint (T008) before the frontend (T009)
- T007 → T011 → T014 all edit `code_review_service.py` and are therefore sequential

### Parallel Opportunities

- T001, T002 (Setup, different files) in parallel
- T005 (service test) and T006 (router test) in parallel — different files
- T012 (service test) and T013 (router test) in parallel — different files
- T017, T019 in Polish can run in parallel with T016/T018
- Note: T005, T010, T012 all touch `test_code_review_service.py`, so they are NOT
  parallel with each other; their `[P]` marks parallelism with the router-test task in
  the same phase only

---

## Parallel Example: User Story 1

```bash
# Launch the two US1 tests together (different files):
Task: "Service unit test for the post flow in backend/tests/services/test_code_review_service.py"
Task: "Router contract test for POST .../review/comments in backend/tests/routers/test_github.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: a reviewer can post AI findings onto a PR as one COMMENT
   review with inline comments and a link, per FR-001–FR-003/FR-008/FR-009/FR-011,
   with service ≥85% and router ≥75% coverage

### Incremental Delivery

1. Setup + Foundational → scaffolding ready
2. User Story 1 → validate independently (MVP)
3. User Story 2 → validate independently (non-anchorable findings folded into summary)
4. User Story 3 → validate independently (safe/transparent failures)
5. Polish → confirm coverage gates, lint, run quickstart, update README

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to a specific user story for traceability
- This feature persists nothing — no migrations, no repository, no DB tests
- Tests mock at the MCP boundary (`backend.services.code_review_service.call_github_tool`)
  and never make real GitHub/LLM calls (Principle IV)
- Commit after each task or logical group; every bug found during quickstart gets a
  regression test (Principle IV)
