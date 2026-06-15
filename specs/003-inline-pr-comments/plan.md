# Implementation Plan: Inline PR Review Comments

**Branch**: `003-inline-pr-comments` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-inline-pr-comments/spec.md`

## Summary

Add a user-invoked action that posts the findings of a completed AI code review
onto the corresponding GitHub pull request as a single native review. Each finding
that carries a resolvable file + line becomes an inline comment anchored to the new
side of the diff; findings without a location are folded into the review summary so
nothing is dropped. The submitted review uses a neutral `COMMENT` verdict (never
blocks the PR). The flow reuses the existing GitHub MCP integration
(`backend/mcp/client.py`) and the existing review pipeline
(`backend/services/code_review_service.py`) — no new persistence, no new
strategy/provider, no new configuration.

Technical approach: a new `POST /api/github/pull-requests/{number}/review/comments`
endpoint accepts the review result the client already has on screen (`findings` +
`summary`) and a new `post_review_to_pull_request(...)` service function drives the
three-step MCP review-write flow (create pending review → add inline comments →
submit as COMMENT), with cleanup of the pending review on partial failure.

## Technical Context

**Language/Version**: Python 3.13 (backend), ES2022+ vanilla JS (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, the GitHub MCP client
(`backend/mcp/client.py` → `github-mcp-server` over stdio), configured LLM via
`plugin_registry.get_llm()` (already used by the existing review)

**Storage**: N/A — this feature persists nothing. Posted reviews live only on
GitHub; the API response is transient (per spec Key Entities and the confirmed
"no DB persistence" decision).

**Testing**: pytest + FastAPI `TestClient`, mocking at the MCP boundary
(`call_github_tool`) and the DI boundary; never real GitHub/LLM calls in tests.

**Target Platform**: Linux/Windows server (FastAPI + uvicorn), browser SPA.

**Project Type**: Web application (FastAPI backend + vanilla-JS frontend).

**Performance Goals**: Interactive — one create call, N inline-comment calls (one
per anchored finding), one submit call against the GitHub MCP server. Bounded by the
number of findings (tens, not thousands).

**Constraints**: The github-mcp-server is launched WITHOUT `--read-only`
(`backend/config.py: github_mcp_command` default `github-mcp-server stdio`) so the
`pull_requests` write toolset is available; `GITHUB_TOKEN` must carry the `repo`
(write) scope. A single repo is configured at a time (`GITHUB_REPO`).

**Scale/Scope**: One new endpoint, one new service function, two new Pydantic
schemas, one frontend action + styling. Single configured repository.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type-Safe, Modern Python** — PASS. New service function and schemas are fully
  type-hinted; request/response cross boundaries as Pydantic v2 models, not bare
  dicts. `Any` only at the raw MCP-response boundary.
- **II. Simplicity / YAGNI** — PASS. Reuses `code_review_service`, `mcp/client.py`,
  and existing config. No new persistence/table, no new strategy/provider, no new
  config flag. The request body reuses the existing `CodeReviewResult` model rather
  than introducing a near-duplicate (decision recorded in research.md).
- **III. Layered Architecture** — PASS. New endpoint added to the existing
  per-domain `routers/github.py`; business logic stays in
  `services/code_review_service.py`; all GitHub access goes through the existing MCP
  client. No DB → no repository needed. The endpoint declares a `response_model`; no
  ORM model is exposed. No scattered provider `if` branching.
- **IV. Test-First & Coverage Gates (NON-NEGOTIABLE)** — PASS (plan commits to it).
  New service logic covered ≥85% by extending
  `backend/tests/services/test_code_review_service.py` (mocking `call_github_tool` to
  assert the create → comment → submit sequence, summary folding, the empty-findings
  short-circuit, and partial-failure cleanup); the new endpoint covered ≥75% via a
  new `backend/tests/routers/test_github.py` using `TestClient`.
- **V. Explicit Configuration** — PASS. Reuses `settings.github_repo` /
  `settings.github_token` / `settings.github_mcp_command` from `backend/config.py`;
  no new env reads elsewhere, no new global config.
- **VI. Structured Logging & Explicit Error Handling** — PASS. Uses
  `logging.getLogger(__name__)`; returns a result object with a clear `error` on
  failure (consistent with the existing `CodeReviewResult` degradation pattern);
  attempts to delete the pending review on partial failure rather than swallowing the
  error or stranding it.

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-inline-pr-comments/
├── plan.md              # This file (/speckit-plan command output)
├── spec.md              # Feature specification (/speckit-specify)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

```text
backend/
├── routers/
│   └── github.py                 # MODIFIED — add POST .../review/comments endpoint
├── services/
│   └── code_review_service.py    # MODIFIED — add post_review_to_pull_request()
├── models/
│   └── schemas.py                # MODIFIED — add PostedReviewResult (+ reuse CodeReviewResult as request body)
├── mcp/
│   └── client.py                 # REUSED, unchanged — call_github_tool()
├── config.py                     # REUSED, unchanged — github_* settings
└── tests/
    ├── services/
    │   └── test_code_review_service.py   # MODIFIED — post-flow unit tests
    └── routers/
        └── test_github.py                # NEW — endpoint contract test (TestClient)

frontend/
├── app.js                        # MODIFIED — "Post to PR" action + confirm + result display
└── style.css                     # MODIFIED — button / posted-state styling (reuse existing CSS vars)
```

**Structure Decision**: Web application layout (existing). The feature is a thin
extension of the current Source Code Intelligence area: one new write endpoint in
the existing `routers/github.py`, the posting orchestration in the existing
`services/code_review_service.py`, and one new button + result display in the single
`frontend/app.js`. No new top-level directories.

## Complexity Tracking

> No constitution violations — table intentionally empty.
