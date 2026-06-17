# Implementation Plan: Config Page Enhancements

**Branch**: `019-config-page-enhancements` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-config-page-enhancements/spec.md`

## Summary

Add a Config page to the frontend where users can view and update AWS credentials (Access Key ID, Secret Access Key, region) and GitHub MCP settings (repo slug, personal access token). Credentials are stored in a new `app_config` DB table and are never returned in full to the client after initial save — only masked placeholders. A new `routers/config.py` endpoint backed by `repositories/config_repo.py` handles GET/PATCH operations, following the existing layered architecture (Constitution Principle III).

## Technical Context

**Language/Version**: Python 3.13 (backend), ES2022+ vanilla JS (frontend)

**Primary Dependencies**: FastAPI ≥0.111, Pydantic v2, SQLAlchemy 2.x, pydantic-settings, PostgreSQL (psycopg2)

**Storage**: PostgreSQL — new `app_config` table (single-row global config, JSONB columns per integration group)

**Testing**: pytest, FastAPI TestClient, pytest-cov (≥80% overall backend coverage gate)

**Target Platform**: Linux server (self-hosted), single-page frontend served as static files from FastAPI

**Project Type**: Web service (FastAPI backend + vanilla JS SPA frontend)

**Performance Goals**: Config reads/writes are infrequent admin operations — standard synchronous route latency acceptable (<200ms p95 target)

**Constraints**: Secrets MUST NOT be returned in full to client after initial save; masked placeholder only. Real AWS/LLM calls MUST NOT occur in tests (moto/httpx_mock).

**Scale/Scope**: Global config — single set of credentials for the entire deployment. Per-project scoping deferred to `specs/012-multi-project-config`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Type-Safe Modern Python** | PASS | All new code uses built-in generics, `X \| None` unions, f-strings, mandatory type hints on every function |
| **II. YAGNI / No Premature Abstraction** | PASS | No new strategy/provider for config — a single repo with direct JSONB columns is sufficient for one use case |
| **III. Layered Architecture** | PASS | `repositories/config_repo.py` is sole DB access point; router uses `Depends(get_db)`; Pydantic schemas separate from ORM |
| **IV. Test-First / Coverage Gates** | PASS | TDD mandatory: tests written before implementation. Targets: routers ≥75%, repositories ≥80%, overall ≥80% |
| **V. Explicit Configuration** | PASS | `backend/config.py` provides env-var defaults; DB row acts as runtime overlay. No new `os.environ` reads anywhere else |
| **VI. Structured Logging / Error Handling** | PASS | `logging` module only; specific exceptions raised; no ad-hoc error dicts from route handlers |

**Post-design constitution re-check**: All principles satisfied — see Phase 1 artifacts. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/019-config-page-enhancements/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── api.md           ← Phase 1 output
│   └── ui-contract.md   ← Phase 1 output
└── tasks.md             ← /speckit-tasks output (not created here)
```

### Source Code

```text
backend/
├── config.py                               # existing — no changes
├── db/
│   ├── models.py                           # ADD: AppConfig ORM model
│   └── migrations/versions/
│       └── 003_add_app_config.py           # NEW: Alembic migration
├── models/
│   └── schemas.py                          # ADD: AppConfigRead, AwsConfigUpdate, GithubMcpConfigUpdate
├── repositories/
│   └── config_repo.py                      # NEW
├── routers/
│   └── config.py                           # NEW
├── main.py                                 # ADD: include config_router
└── tests/
    ├── repositories/
    │   └── test_config_repo.py             # NEW
    └── routers/
        └── test_config.py                  # NEW

frontend/
├── index.html                              # ADD: Config nav tab + config section markup
├── app.js                                  # ADD: config page load/save handlers
└── style.css                               # ADD: config form styles (reuse CSS custom properties)
```

**Structure Decision**: Web-application layout. The feature adds one router, one repository, and one ORM model — no structural changes to existing modules. Frontend adds one new section to the existing SPA.

## Complexity Tracking

> No constitution violations requiring justification.
