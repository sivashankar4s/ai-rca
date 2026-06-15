<!--
Sync Impact Report
- Version change: [TEMPLATE] -> 1.0.0
- Modified principles: n/a (initial ratification)
- Added sections: Core Principles (I-VI), Technology & Architecture Constraints,
  Development Workflow & Quality Gates, Governance
- Removed sections: none
- Templates requiring updates:
  - .specify/templates/plan-template.md ✅ (Constitution Check gates align with
    principles II, III, IV below)
  - .specify/templates/spec-template.md ✅ (no constitution-specific references
    requiring change)
  - .specify/templates/tasks-template.md ✅ (testing/task categorization aligns
    with principle IV)
  - .specify/templates/commands/*.md ✅ (no agent-specific renames required)
- Follow-up TODOs:
  - TODO(RATIFICATION_DATE): original adoption date predates this constitution;
    set to date of this ratification per project decision.
-->

# AI-RCA Constitution

## Core Principles

### I. Type-Safe, Modern Python
All backend code targets Python 3.13 and MUST use modern syntax: built-in generics
(`list[str]`, `dict[str, Any]`), `X | None` / `X | Y` unions, `match`/`case` for
provider-selection logic, and f-strings exclusively. Type hints (parameters and
return types) are MANDATORY on every function in `backend/`; `Any` is permitted
only at true I/O boundaries (raw Athena rows, raw LLM text prior to parsing).
Structured data crossing a function boundary more than once MUST use a dataclass
or Pydantic v2 model — never a bare `dict`.

**Rationale**: Type hints and modern syntax catch integration bugs before runtime
and keep an LLM-assisted codebase navigable as multiple providers/strategies are
added.

### II. Simplicity and No Premature Abstraction (YAGNI)
Three similar lines of code beat a new helper, base class, or config flag. A
shared module/strategy/provider/repository MAY be extracted only when (a) the
same logic or markup is needed in 2+ places, or (b) it implements a designated
extension point already described in `PLUGIN_STRATEGY_PLAN.md` or `CRM_PLAN.md`.
Generic "framework" code for a single current use case, feature toggles for
hypothetical future requirements, and pass-through wrapper classes are PROHIBITED.
Dead code (unused functions/files, commented-out blocks, duplicate
implementations) MUST be deleted, not retained "just in case".

**Rationale**: This project evolves rapidly via AI-assisted iteration; speculative
abstractions accumulate faster than they pay off and make specs/plans harder to
verify against actual code.

### III. Layered Architecture via Strategy/Provider/Repository
New data sources or log backends MUST implement the relevant ABC in
`backend/strategies/`, with a concrete implementation in
`backend/providers/<type>/`. All persistence access MUST go through
`backend/repositories/<entity>_repo.py` — repositories are the ONLY place raw
SQL/ORM queries live; services and orchestrators MUST NOT import `db.session`
directly. Provider/strategy selection MUST go through `plugin_registry.py`;
scattered `if settings.x == "y"` provider branching in services is PROHIBITED.
Routers are organized one-per-domain (`routers/analysis.py`, `routers/cases.py`,
etc.); shared resources (DB session, project context, plugin registry instances)
are obtained via FastAPI `Depends()`, not constructed ad hoc inside handlers.
Every endpoint MUST declare a `response_model`; ORM models are never exposed
directly through the API — a Pydantic schema layer is required.

**Rationale**: This separation is the foundation the CRM/multi-project refactor
(`CRM_PLAN.md`) and plugin strategy (`PLUGIN_STRATEGY_PLAN.md`) depend on; bypassing
it creates rework when new providers/projects are added.

### IV. Test-First Discipline & Coverage Gates (NON-NEGOTIABLE)
New or changed logic MUST ship with unit tests meeting the per-layer coverage
targets: `services/` ≥85%, `repositories/` ≥80% (against a real test DB, not
mocked SQL), `providers/` ≥70% (external SDKs/HTTP mocked via `botocore.stub`,
`moto`, or `responses`/`httpx_mock` — never real AWS/LLM calls in tests),
`routers/` ≥75% (via FastAPI `TestClient`, mocking at the DI boundary), and
Pydantic `field_validator`/`model_validator` logic in `models/schemas.py`.
Overall `backend/` line coverage MUST be ≥80%, enforced via
`pytest --cov=backend --cov-fail-under=80`. Bug fixes MUST include a regression
test that fails before the fix and passes after. Every new strategy/provider
implementation MUST ship a contract test exercising its ABC. Third-party library
internals, trivial pass-through models, and exact LLM prompt wording are NOT to be
tested — test structured inputs/outputs instead.

**Rationale**: Coverage gates are the primary defense against AI-generated
regressions slipping through, given the speed of iteration this project moves at.

### V. Explicit Configuration & Secrets Management
All configuration flows through `backend/config.py` (`pydantic-settings`); reading
`os.environ` directly anywhere else is PROHIBITED. Per-project provider
configuration (CRM_PLAN.md Phase 2+) lives in the `projects` table and is loaded
into a `ProjectContext`; global `.env` settings act only as defaults/fallbacks.
Real credentials, API keys, and `.env` files MUST NEVER be committed — only
`.env.example` with placeholder values.

**Rationale**: Centralized config is required for the multi-project/CRM model and
prevents credential leaks across an increasingly automated workflow.

### VI. Structured Logging & Explicit Error Handling
Use the `logging` module (`logger = logging.getLogger(__name__)`) exclusively;
`print()` is PROHIBITED in application code. Code MUST raise specific exceptions
(built-in like `ValueError`, or custom exceptions in `backend/exceptions.py`) and
rely on FastAPI exception handlers to translate them to HTTP responses — route
handlers MUST NOT return ad-hoc error dicts. Exceptions MUST only be caught where
they can be meaningfully handled or re-wrapped with additional context; silent
swallowing is PROHIBITED.

**Rationale**: Consistent error handling keeps the RCA pipeline's own failures
debuggable and prevents masked errors from corrupting case data.

## Technology & Architecture Constraints

- Backend: Python 3.13, FastAPI ≥0.111, Pydantic v2 (`field_validator`/
  `model_validator`; v1 `@validator` is PROHIBITED). `Enum` is used for closed
  sets of string values (e.g. `TimeRange`, `case_status`).
- New DB-backed entities require two layers: an ORM model
  (`backend/db/models.py`) and a Pydantic schema for API I/O.
- Frontend: vanilla JS targeting ES2022+ (`const`/`let`, arrow functions, optional
  chaining, nullish coalescing, `async/await`). No inline `onclick="..."`
  handlers — listeners are attached via `addEventListener`. As `frontend/js/`
  grows, reusable pieces are split into modules by concern (`js/api.js`,
  `js/components/*.js`, `js/state.js`). New components reuse existing CSS custom
  properties from `style.css` rather than introducing ad-hoc values.
- Linting/formatting: `ruff format` (Black-compatible) and `ruff check`, target
  line length 100, with `F`, `E`, `I` (isort), and `UP` (pyupgrade) rules enabled.

## Development Workflow & Quality Gates

Every PR MUST satisfy this checklist before merge:
1. `ruff format` and `ruff check` pass with no errors.
2. New/changed logic has unit tests meeting the Principle IV coverage targets.
3. `pytest --cov=backend --cov-fail-under=80` passes.
4. No new global `.env`-only configuration for settings that should be
   per-project (per `CRM_PLAN.md` §6).
5. New providers/strategies are registered in `plugin_registry.py`, not
   hardcoded into services.
6. No secrets or credentials are committed.

For spec-driven feature work, `/speckit-plan` MUST include a Constitution Check
gate verifying the plan against Principles II-IV before Phase 0 research, and
re-verify after Phase 1 design. Any violation MUST be recorded in the plan's
Complexity Tracking table with rationale and the simpler alternative rejected.

## Governance

This constitution supersedes ad-hoc conventions where they conflict.
`CODING_GUIDELINES.md` remains the detailed reference; amendments to either
document that change a MUST/PROHIBITED rule MUST update both files in the same
change.

**Amendment procedure**: Propose the change via `/speckit-constitution` (or direct
edit + PR), update the Sync Impact Report, and bump the version per semantic
versioning: MAJOR for backward-incompatible principle removals/redefinitions,
MINOR for new principles or materially expanded guidance, PATCH for clarifications
and wording fixes.

**Compliance review**: The Development Workflow checklist above is the operational
enforcement of this constitution; PRs that fail it are not merged. `/speckit-plan`'s
Constitution Check gate is the enforcement point for spec-driven feature work.

**Version**: 1.0.0 | **Ratified**: 2026-06-15 | **Last Amended**: 2026-06-15
