# Implementation Plan: Auto-Link RCA Cases to GitHub Pull Requests

**Branch**: `002-auto-link-rca-pr` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-auto-link-rca-pr/spec.md`

## Summary

Extend the existing `/api/analyze` pipeline so that, after grouping failures
and building the RCA case, the system searches the configured GitHub
repository for a pull request that likely addresses each failure group's
component/error (by branch name, title, description), attaches the
best-matching PR (title, author, status, URL) to the failure group in the
response, and persists it on the linked `RcaCase` so it survives across
recurring analyses. The search reuses the existing GitHub MCP integration
(`backend/services/github_service.list_pull_requests`,
`backend/mcp/client.call_github_tool`) and fails open per FR-005/FR-006 —
exactly like the existing `code_analysis` block.

## Technical Context

**Language/Version**: Python 3.13 (backend), vanilla JavaScript ES2022+
(frontend, to render the new "Related Pull Request" badge)

**Primary Dependencies**: Existing `github-mcp-server` integration
(`backend/mcp/client.py`, `backend/services/github_service.py`); no new
external dependencies

**Storage**: PostgreSQL 16 — add a `linked_pr` JSONB column to `rca_cases`
(new Alembic migration); reuse `case_activity` for link/update history

**Testing**: pytest, pytest-cov (existing coverage gates), ruff

**Target Platform**: Same as baseline (FastAPI/uvicorn backend, browser SPA
frontend)

**Project Type**: Web application (extends existing `backend/` + `frontend/`)

**Performance Goals**: PR matching MUST NOT materially extend
`/api/analyze` latency beyond the ~2-minute baseline (spec 001 SC-002) — a
single `list_pull_requests` call per analysis is reused across all failure
groups rather than one call per group

**Constraints**: Reuses `GITHUB_REPO`/`GITHUB_TOKEN`/`GITHUB_MCP_COMMAND`
config (no new settings); PR search failures MUST NOT fail the overall
`/api/analyze` response (FR-005); feature MUST be a no-op when no repository
is configured (FR-006)

**Scale/Scope**: Single configured repository per deployment, matching the
baseline's existing code-analysis scope (spec 001 Assumptions)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type-Safe, Modern Python** — PASS. New matching logic and the
  `LinkedPullRequest` Pydantic model will use Python 3.13 type hints and
  `X | None` unions, consistent with `backend/models/schemas.py`.
- **II. Simplicity / No Premature Abstraction** — PASS. PR matching is added
  as a single new function/module (`backend/services/pr_link_service.py`)
  reusing the existing `github_service.list_pull_requests` and
  `mcp.client.call_github_tool` — no new strategy/provider ABC, since GitHub
  is the only configured code-repository integration (per spec Assumptions:
  cross-repo search is out of scope).
- **III. Layered Architecture via Strategy/Provider/Repository** — PASS.
  Matching logic lives in `services/`, persistence of `linked_pr` and
  `case_activity` entries goes through `repositories/case_repo.py`
  (no direct `db.session` access from services), and `routers/analysis.py`'s
  `response_model` (`AnalyzeResponse` → `FailureGroup`) is extended with an
  optional `linked_pull_request` field.
- **IV. Test-First Discipline & Coverage Gates** — Plan includes test tasks for
  the new service (≥85%), the `case_repo` persistence changes (≥80% against a
  real test DB), and the router contract (≥75%), per Principle IV.
- **V. Explicit Configuration & Secrets Management** — PASS. No new
  configuration is introduced; existing `settings.github_repo` /
  `settings.github_token` are reused via `backend/config.py`.
- **VI. Structured Logging & Explicit Error Handling** — PASS. PR-search
  failures are caught and logged (`logger.warning`, matching the existing
  pattern in `code_analysis_agent.py`), surfaced as an absence of
  `linked_pull_request` rather than raised.

No violations — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/002-auto-link-rca-pr/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── services/
│   ├── pr_link_service.py        # NEW: match failure group -> best PR, build LinkedPullRequest
│   ├── rca_orchestrator.py        # MODIFIED: call pr_link_service after grouping, attach to FailureGroup
│   └── persistence_service.py     # MODIFIED: persist linked_pr on RcaCase + case_activity entry
├── repositories/
│   └── case_repo.py               # MODIFIED: read/update RcaCase.linked_pr, append activity
├── models/
│   └── schemas.py                 # MODIFIED: add LinkedPullRequest, FailureGroup.linked_pull_request
├── db/
│   ├── models.py                  # MODIFIED: RcaCase.linked_pr (JSONB, nullable)
│   └── migrations/versions/       # NEW: migration adding rca_cases.linked_pr
└── tests/
    ├── services/test_pr_link_service.py      # NEW
    ├── repositories/test_case_repo.py        # MODIFIED (or NEW if not present from 001)
    └── routers/test_analysis_analyze.py      # MODIFIED (or NEW if not present from 001)

frontend/
├── app.js                          # MODIFIED: render "Related Pull Request" badge per failure group
└── style.css                       # MODIFIED: badge styling (open/merged/closed)
```

**Structure Decision**: Extends the existing web-application layout from
baseline 001 — no new top-level directories. All changes are additive
(new column, new optional response field, new service module).

## Complexity Tracking

*No constitution violations — table not required.*
