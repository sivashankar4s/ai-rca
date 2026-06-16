# Implementation Plan: AI-Powered RCA Tool for Production Incidents

**Branch**: `001-ai-rca-tool` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ai-rca-tool/spec.md`

## Summary

Provide a two-step workflow — fetch failed records for a time window/component,
then run an AI-driven pipeline that summarizes failures, queries the log
backend, groups failures by root cause, and produces an executive summary with
log deep-links and (optionally) related code changes. Every fetched record and
every analysis result is persisted so recurring root-cause signatures are
automatically linked to existing CRM-style cases.

This plan describes the **target architecture** for feature 001, rebuilt from
scratch (the `backend/`/`frontend/` trees are intentionally deleted in the working
tree; git `HEAD` is reference only): `backend/services/rca_orchestrator.py`
orchestrates three pluggable strategy interfaces (`DataSourceStrategy`, `LLMStrategy`,
`LogAnalysisStrategy`) selected via `backend/plugin_registry.py`, with persistence
through `backend/repositories/*` into PostgreSQL, and an optional GitHub-MCP-backed
code analysis agent. The build follows `tasks.md` (from-scratch, TDD, MVP-first by user
story); `data-model.md` and `contracts/api.md` define the schema and endpoints.

## Technical Context

**Language/Version**: Python 3.13 (backend), vanilla JavaScript ES2022+ (frontend)

**Primary Dependencies**: FastAPI ≥0.111, Pydantic v2, SQLAlchemy 2.0, Alembic,
boto3 (Athena / CloudWatch Logs Insights), Navify Enrichment API client
(OpenAI-compatible LLM), Grafana Loki HTTP API, official `github-mcp-server`
over stdio (`backend/mcp/client.py`)

**Storage**: PostgreSQL 16 (CRM tables: `projects`, `failure_records`,
`rca_cases`, `case_failure_records`, `case_activity`, `root_cause_signatures`,
`case_signature_links`)

**Testing**: pytest, pytest-cov (`--cov=backend --cov-fail-under=80`), ruff
(format + lint)

**Target Platform**: Linux server (FastAPI/uvicorn) with PostgreSQL via Docker
Compose for local dev; browser-based single-page frontend

**Project Type**: Web application (FastAPI backend + vanilla-JS frontend)

**Performance Goals**: Failure retrieval responds within ~10s for a selected
time window (SC-001); a full analysis (summarize → log queries → grouping →
executive summary) completes within ~2 minutes for a selected batch (SC-002)

**Constraints**: Data source, LLM, and log backend are pluggable providers
selected at runtime via `.env` / `plugin_registry.py` (Athena or local file;
CloudWatch Logs Insights or Grafana Loki; Navify LLM); log-backend and
code-repository lookups must fail independently without aborting the overall
analysis (FR-016)

**Scale/Scope**: Single configured project per deployment today (multi-project
CRM model is tracked separately in `CRM_PLAN.md` and is out of scope for this
baseline)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type-Safe, Modern Python** — PASS. Existing `backend/` code uses Python
  3.13 syntax, type hints throughout `services/`, `repositories/`,
  `strategies/`, and Pydantic v2 models in `models/schemas.py`.
- **II. Simplicity / No Premature Abstraction** — PASS. This plan documents the
  existing strategy/provider abstractions, which are justified by 2+ concrete
  implementations each (Athena/local-file data sources; CloudWatch/Loki log
  backends). No new abstractions are introduced.
- **III. Layered Architecture via Strategy/Provider/Repository** — PASS.
  Orchestration lives in `services/rca_orchestrator.py`, persistence in
  `repositories/*_repo.py`, provider selection in `plugin_registry.py`, and
  `routers/analysis.py` declares `response_model`s for every endpoint per
  `models/schemas.py`.
- **IV. Test-First Discipline & Coverage Gates** — PASS (baseline). Existing
  `backend/tests/` suite covers services/repositories/providers/routers; no new
  code is introduced by this plan. Any gaps found during Phase 1 review will be
  tracked as follow-up tasks rather than blocking this baseline.
- **V. Explicit Configuration & Secrets Management** — PASS. Configuration
  flows through `backend/config.py` (pydantic-settings); per-project config in
  `projects.data_source_cfg` / `log_backend_cfg` / `llm_cfg` (JSONB).
- **VI. Structured Logging & Explicit Error Handling** — PASS. Log-backend and
  code-analysis failures are caught and surfaced inline (FR-016) rather than
  failing the whole request, per existing `rca_orchestrator` behavior.

No violations — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-rca-tool/
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
├── main.py                       # FastAPI app, middleware, static serving
├── config.py                     # Pydantic settings from .env
├── plugin_registry.py            # Selects providers based on settings
├── strategies/                   # Abstract provider interfaces
│   ├── data_source.py            # DataSourceStrategy
│   ├── llm.py                    # LLMStrategy
│   └── log_analysis.py           # LogAnalysisStrategy
├── providers/
│   ├── data_source/{athena,local_file}.py
│   ├── llm/navify.py
│   └── log_analysis/{cloudwatch,grafana_loki}.py
├── agents/
│   └── code_analysis_agent.py    # GitHub MCP related-code-changes lookup
├── mcp/
│   └── client.py                 # stdio client for github-mcp-server
├── models/schemas.py             # Pydantic request/response DTOs
├── routers/analysis.py           # /api/failures, /api/analyze, /api/config, etc.
├── services/
│   ├── rca_orchestrator.py       # 5-step pipeline (provider-agnostic)
│   ├── signature_service.py      # Root-cause signature hashing/matching
│   └── persistence_service.py    # Persists results to CRM tables
├── repositories/{project,failure,signature,case}_repo.py
├── db/{models.py,session.py,migrations/}
└── tests/

frontend/
├── index.html                    # Single-page app shell
├── app.js                        # Two-step UI logic + pagination
└── style.css                     # Dark theme
```

**Structure Decision**: This baseline reuses the existing web-application
layout above (FastAPI backend + vanilla-JS frontend, Option 2 from the
template). No new top-level directories are introduced.

## Complexity Tracking

*No constitution violations — table not required.*
