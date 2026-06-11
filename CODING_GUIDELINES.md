# AI-RCA Coding Guidelines

Practical rules for this codebase — backend (Python 3.13 / FastAPI), frontend (vanilla JS), and the upcoming CRM/strategy refactor (`PLUGIN_STRATEGY_PLAN.md`, `CRM_PLAN.md`). Keep this file updated as conventions evolve.

---

## 1. General Principles

- **Use the language/framework version actually pinned** — Python 3.13, Pydantic v2, FastAPI ≥0.111. Prefer modern syntax over legacy patterns (see §2.1).
- **No premature abstraction.** Three similar lines beat a new helper/base class. Only extract a shared module/strategy/provider when a *second* concrete use case exists (see §4).
- **Type hints are mandatory** on all function signatures (params + return type) in `backend/`. `Any` is allowed only at true I/O boundaries (raw Athena rows, raw LLM text before parsing).
- **No dead code.** Delete unused functions/files instead of commenting them out (e.g. resolve the `rca_orchestrator.py` / `roca_orchestrator.py` duplication — keep one, delete the other).
- **Comments explain "why", not "what".** Don't restate what well-named code already says.

---

## 2. Backend (Python / FastAPI)

### 2.1 Use modern Python 3.13 features

- Built-in generics: `list[str]`, `dict[str, Any]`, `tuple[int, ...]` — not `List`/`Dict`/`Tuple` from `typing`.
- `X | None` instead of `Optional[X]`; `X | Y` instead of `Union[X, Y]`.
- `match`/`case` for provider-selection logic (already used in `PLUGIN_STRATEGY_PLAN.md` §6) instead of long `if/elif` chains.
- `async def` for any function that does I/O (HTTP calls to LLM, DB queries, boto3 calls via `asyncio.to_thread` if the client is sync).
- f-strings for all string formatting; no `.format()` or `%`.
- Dataclasses or Pydantic models for structured data — never bare `dict` for anything that crosses a function boundary more than once.

### 2.2 Pydantic v2 conventions

- All request/response DTOs live in `backend/models/schemas.py` (or a per-domain submodule once it grows — e.g. `schemas/cases.py`, `schemas/projects.py`).
- Use `field_validator` / `model_validator` (v2 API) — never the deprecated v1 `@validator`.
- Use `Enum` for closed sets of string values (see `TimeRange`, `case_status`).
- New DB-backed entities (Project, RcaCase, etc.) get **two layers**: an ORM model (`backend/db/models.py`) and a Pydantic schema for API I/O — don't expose ORM models directly through FastAPI.

### 2.3 FastAPI / routing conventions

- One router per domain (`routers/analysis.py`, `routers/projects.py`, `routers/cases.py`, `routers/dashboard.py`) — don't pile unrelated endpoints into one file.
- Use FastAPI `Depends()` for shared resources (DB session, project context, plugin-registry instances) — don't construct services manually inside route handlers.
- Path params for resource identity (`/api/projects/{project_id}/cases`), query params for filters (`?status=open&assignee=...`).
- Every endpoint must declare a `response_model`.

### 2.4 Strategy / provider / repository patterns

Follow `PLUGIN_STRATEGY_PLAN.md` and `CRM_PLAN.md` exactly:

- New data sources/log backends → implement the relevant ABC in `backend/strategies/`, concrete class in `backend/providers/<type>/`.
- New persistence access → a `backend/repositories/<entity>_repo.py` module with plain functions or a thin class — repositories are the **only** place raw SQL/ORM queries live. Services/orchestrators never import `db.session` directly.
- Provider/strategy selection goes through `plugin_registry.py` — never `if settings.x == "y"` scattered across services.

### 2.5 Config & secrets

- All config via `backend/config.py` (`pydantic-settings`). Never read `os.environ` directly elsewhere.
- Per-project provider config (Phase 2+ of `CRM_PLAN.md`) lives in the `projects` table, loaded into a `ProjectContext` — global `.env` settings become defaults/fallbacks only.
- Never commit real credentials, API keys, or `.env` — `.env.example` only.

### 2.6 Logging & error handling

- Use the `logging` module (`logger = logging.getLogger(__name__)`), never `print()`.
- Raise specific exceptions (`ValueError`, custom exceptions in `backend/exceptions.py` if needed) and let FastAPI exception handlers translate to HTTP responses — don't return ad-hoc error dicts from route handlers.
- Only catch exceptions you can meaningfully handle or re-wrap with context. Don't swallow errors silently.

### 2.7 Linting & formatting

- Format with `ruff format` (Black-compatible). Lint with `ruff check`.
- Add a `pyproject.toml` with `[tool.ruff]` config when this is set up — target line length 100, enable `F`, `E`, `I` (isort), `UP` (pyupgrade — enforces modern syntax from §2.1).

---

## 3. Frontend (Vanilla JS)

- Target modern ES2022+ (the project ships its own static files, no transpilation) — use `const`/`let`, arrow functions, optional chaining (`?.`), nullish coalescing (`??`), `async/await` for `fetch` calls.
- **Reusable UI pieces become small functions/modules**, not copy-pasted DOM blocks. As the app grows past `app.js`, split into `frontend/js/` modules by concern, e.g.:
  - `js/api.js` — all `fetch()` calls (one function per endpoint)
  - `js/components/table.js` — generic paginated table renderer (reused for failure list, case list)
  - `js/components/caseCard.js`, `js/components/projectSwitcher.js` (new, for CRM UI)
  - `js/state.js` — shared app state (selected project, pagination state)
- No inline `onclick="..."` handlers in HTML — attach listeners in JS via `addEventListener`.
- CSS: keep using the existing dark theme variables in `style.css`; new components reuse existing CSS custom properties (colors, spacing) rather than introducing new ad-hoc values.

---

## 4. Reusable Components — When to Extract

Extract a shared function/module/component **only when**:
1. The same logic/markup is needed in **2+ places**, or
2. It's a designated extension point from `PLUGIN_STRATEGY_PLAN.md` / `CRM_PLAN.md` (strategies, providers, repositories) where future implementations are explicitly planned.

Do **not**:
- Build generic "framework" code for a single current use case.
- Add config flags / feature toggles for hypothetical future requirements.
- Create wrapper classes that just forward to one underlying call.

---

## 5. Unit Testing Standards

### 5.1 Tooling

- `pytest` + `pytest-asyncio` for backend (add to `requirements.txt` / a new `requirements-dev.txt`).
- `pytest-cov` for coverage reporting.
- Test files live in `backend/tests/`, mirroring the source tree:
  ```
  backend/tests/
  ├── services/
  │   ├── test_rca_orchestrator.py
  │   └── test_signature_service.py
  ├── repositories/
  │   └── test_case_repo.py
  ├── routers/
  │   └── test_analysis.py
  └── providers/
      ├── data_source/test_athena.py
      └── llm/test_navify.py
  ```

### 5.2 Coverage standards

| Layer | Target coverage | Notes |
|---|---|---|
| `services/` (orchestrator, signature matching) | ≥85% | Core business logic — must be covered, including edge cases (no failures, malformed `event_data`, signature match vs. no match) |
| `repositories/` | ≥80% | Test against a real test DB (e.g. `testcontainers` Postgres or SQLite for simple cases) — not mocked SQL |
| `providers/` (Athena, Navify, CloudWatch, Grafana) | ≥70% | Mock the external SDK/HTTP client (`boto3` via `botocore.stub.Stubber` or `moto`; `requests` via `responses`/`httpx_mock`) — never call real AWS/LLM in tests |
| `routers/` | ≥75% | Use FastAPI `TestClient`; mock services/repos at the dependency-injection boundary |
| `models/schemas.py` (Pydantic) | Validators only | Test custom `field_validator`/`model_validator` logic (e.g. `parse_event_data`), not auto-generated Pydantic behavior |

Overall project target: **≥80% line coverage** on `backend/`, enforced via `pytest --cov=backend --cov-fail-under=80`.

### 5.3 Test conventions

- One test file per source module; test function names describe behavior: `test_<unit>_<scenario>_<expected_result>` (e.g. `test_signature_match_recurring_failure_links_existing_case`).
- Use `pytest.fixture` for shared setup (sample `FailureRecord`s, mock LLM client, test DB session) — put shared fixtures in `backend/tests/conftest.py`.
- Every new strategy/provider implementation **must** ship with a test that exercises the ABC contract (e.g. a parametrized test run against all `LogAnalysisStrategy` implementations to confirm `build_deep_link` returns a valid URL).
- Bug fixes require a regression test that fails before the fix and passes after.
- Frontend: if/when component modules are introduced (§3), add lightweight tests with `vitest` for pure logic (e.g. pagination math, signature formatting) — DOM-heavy code can stay untested initially but should be kept thin enough to not need it.

### 5.4 What NOT to test

- Third-party library internals (boto3, FastAPI, Pydantic).
- Trivial getters/pass-through Pydantic models with no custom logic.
- LLM prompt wording exactly — instead test that the orchestrator sends the expected *structured inputs* and correctly *parses* the expected response shape (mock the LLM response).

---

## 6. PR Checklist

Before opening a PR:
- [ ] `ruff format` + `ruff check` pass
- [ ] New/changed logic has unit tests meeting §5.2 targets
- [ ] `pytest --cov=backend --cov-fail-under=80` passes
- [ ] No new global `.env`-only config for things that should be per-project (`CRM_PLAN.md` §6)
- [ ] New providers/strategies registered in `plugin_registry.py`, not hardcoded in services
- [ ] No secrets/credentials committed
