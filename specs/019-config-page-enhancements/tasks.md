---
description: "Task list for Config Page Enhancements (019)"
---

# Tasks: Config Page Enhancements

**Input**: Design documents from `specs/019-config-page-enhancements/`

**Prerequisites**: plan.md âœ…, spec.md âœ…, research.md âœ…, data-model.md âœ…, contracts/api.md âœ…, contracts/ui-contract.md âœ…

**TDD**: Test tasks are included â€” constitution Principle IV mandates test-first. Write each test, confirm it fails, then implement.

**Organization**: Tasks grouped by user story for independent delivery.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and router wiring â€” these are one-time infrastructure tasks that block all user stories.

- [X] T001 Write Alembic migration `003_add_app_config.py` in `backend/db/migrations/versions/003_add_app_config.py` â€” creates `app_config` table with `id INTEGER CHECK(id=1)`, `aws_config JSONB`, `github_mcp_config JSONB`, `updated_at TIMESTAMPTZ`
- [X] T002 Add `AppConfig` ORM model class to `backend/db/models.py` â€” fields: `id`, `aws_config`, `github_mcp_config`, `updated_at`
- [X] T003 [P] Add config DTOs to `backend/models/schemas.py`: `AwsConfigStatus`, `GithubMcpConfigStatus`, `AppConfigRead`, `AwsConfigUpdate`, `GithubMcpConfigUpdate`, `ConfigSaveResult` (see data-model.md for field definitions and mask sentinel `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"`)
- [X] T004 [P] Create `backend/routers/config.py` â€” router stub with prefix `/api/config`, tags `["config"]`, three empty route stubs: `GET /api/config`, `PATCH /api/config/aws`, `PATCH /api/config/github-mcp`
- [X] T005 Wire `config_router` into `backend/main.py` â€” import and `app.include_router(config_router)`

**Checkpoint**: Run `alembic upgrade head` and confirm `app_config` table exists. Confirm `/api/config` returns 500/stub before implementation begins.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository layer and GET /api/config â€” these underpin every user story's save/load cycle.

**âš ï¸ CRITICAL**: No user story work can begin until this phase is complete.

### TDD Tests â€” write and confirm failing first

- [X] T006 [P] Write `backend/tests/repositories/test_config_repo.py` â€” test `get_app_config()` returns `None` when table is empty; test `get_app_config()` returns stored row after insert; use real test DB (per Principle IV â€” no mocked SQL)
- [X] T007 [P] Write `backend/tests/routers/test_config.py` â€” test `GET /api/config` returns `{"aws": {"configured": false, ...}, "github_mcp": {"configured": false, ...}}` when DB is empty; confirm secret fields are `null` not `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` when no data present

### Implementation

- [X] T008 Create `backend/repositories/config_repo.py` â€” implement `get_app_config(db: Session) -> AppConfig | None` (SELECT by id=1) and `_upsert_app_config(db, **kwargs) -> AppConfig` (INSERT ON CONFLICT DO UPDATE) â€” no AWS/GitHub logic yet
- [X] T009 Implement `GET /api/config` handler in `backend/routers/config.py` â€” calls `config_repo.get_app_config()`, merges with `settings.*` fallback, builds `AppConfigRead` response; masks secret fields as `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` when non-empty, `null` when absent

**Checkpoint**: `GET /api/config` returns `configured: false` for both groups on a fresh DB. T006/T007 tests pass.

---

## Phase 3: User Story 1 â€” Configure AWS Credentials (Priority: P1) ðŸŽ¯ MVP

**Goal**: Users can enter, save, and reload AWS Access Key ID, Secret Access Key, and region from the Config page.

**Independent Test**: Navigate to Config page, fill AWS card, save, reload â€” Access Key ID is visible, Secret is masked, `configured: true`.

### TDD Tests â€” write and confirm failing first

- [X] T010 [P] [US1] Extend `backend/tests/repositories/test_config_repo.py` â€” test `upsert_aws_config()` stores `access_key_id` and `secret_access_key`; test mask sentinel `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` is NOT written to DB (existing secret preserved); test clearing a field stores `null`
- [X] T011 [P] [US1] Extend `backend/tests/routers/test_config.py` â€” test `PATCH /api/config/aws` with valid payload returns `{"success": true, ...}`; test 422 when `access_key_id` is empty; test `GET /api/config` returns `configured: true` and masked secret after save

### Backend Implementation

- [X] T012 [US1] Add `upsert_aws_config(db: Session, data: AwsConfigUpdate) -> AppConfig` to `backend/repositories/config_repo.py` â€” reads existing row, skips secret write when sentinel detected, calls `_upsert_app_config` with merged JSONB
- [X] T013 [US1] Implement `PATCH /api/config/aws` handler in `backend/routers/config.py` â€” calls `config_repo.upsert_aws_config()`, returns `ConfigSaveResult`; add Pydantic `field_validator` on `AwsConfigUpdate` for non-empty `access_key_id` and `owner/repo` format (in `backend/models/schemas.py`)

### Frontend Implementation

- [X] T014 [US1] Add "Config" nav tab to `frontend/index.html` â€” nav item + `#config-section` div (hidden by default) containing `#config-aws-card` with form fields: `#config-aws-key-id` (text), `#config-aws-secret` (password), `#config-aws-region` (text), `#config-aws-save` button, `.config-feedback` div
- [X] T015 [US1] Add config tab switching logic to `frontend/app.js` â€” `addEventListener` on the Config tab to show `#config-section` and hide other sections (no `onclick` attributes)
- [X] T016 [US1] Add `loadConfigPage()` function to `frontend/app.js` â€” calls `GET /api/config`, populates AWS card fields (key ID shown, secret as `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` or empty), sets `.config-status-badge` to "Configured" / "Not Configured"
- [X] T017 [US1] Add AWS save handler to `frontend/app.js` â€” `addEventListener` on `#config-aws-save`; inline validates required fields (show error, abort if empty); sends `PATCH /api/config/aws`; on success shows success message and re-runs `loadConfigPage()`; on error shows error message without clearing fields
- [X] T018 [US1] Add config card styles to `frontend/style.css` â€” `.config-status-badge`, `.config-card`, `.config-feedback` using existing CSS custom properties; no ad-hoc hex/px values

**Checkpoint**: T010/T011 pass. Config tab is reachable in browser, AWS credentials can be saved and reload correctly with masking.

---

## Phase 4: User Story 2 â€” Configure GitHub MCP Settings (Priority: P1)

**Goal**: Users can enter, save, and reload GitHub repository slug and personal access token from the Config page.

**Independent Test**: Fill GitHub MCP card, save, reload â€” repo slug visible, token masked, `configured: true`. AWS card is unaffected.

### TDD Tests â€” write and confirm failing first

- [X] T019 [P] [US2] Extend `backend/tests/repositories/test_config_repo.py` â€” test `upsert_github_mcp_config()` stores `repo` and `token`; test mask sentinel preserves existing token; test invalid `repo` format raises `ValueError`
- [X] T020 [P] [US2] Extend `backend/tests/routers/test_config.py` â€” test `PATCH /api/config/github-mcp` with valid payload returns `{"success": true, ...}`; test 422 when `repo` is not in `owner/repo` format; test 422 when `token` is empty

### Backend Implementation

- [X] T021 [US2] Add `upsert_github_mcp_config(db: Session, data: GithubMcpConfigUpdate) -> AppConfig` to `backend/repositories/config_repo.py` â€” same sentinel-aware pattern as US1; validates `repo` matches `owner/repo` pattern before upsert
- [X] T022 [US2] Implement `PATCH /api/config/github-mcp` handler in `backend/routers/config.py` â€” calls `config_repo.upsert_github_mcp_config()`, returns `ConfigSaveResult`; add Pydantic `field_validator` on `GithubMcpConfigUpdate` for `repo` format (in `backend/models/schemas.py`)

### Frontend Implementation

- [X] T023 [US2] Add `#config-github-mcp-card` to `frontend/index.html` (inside existing `#config-section`) â€” form fields: `#config-github-repo` (text, placeholder `owner/repo`), `#config-github-token` (password), `#config-github-branch` (text, optional), `#config-github-mcp-save` button, `.config-feedback` div
- [X] T024 [US2] Extend `loadConfigPage()` in `frontend/app.js` to populate GitHub MCP card â€” repo slug shown, token as `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` or empty, status badge updated
- [X] T025 [US2] Add GitHub MCP save handler to `frontend/app.js` â€” `addEventListener` on `#config-github-mcp-save`; inline validates `repo` non-empty and contains `/`; sends `PATCH /api/config/github-mcp`; success/error feedback without clearing fields on error

**Checkpoint**: T019/T020 pass. GitHub MCP settings can be saved and reload correctly. AWS and GitHub MCP cards operate independently.

---

## Phase 5: User Story 3 â€” Config Status Overview (Priority: P3)

**Goal**: The Config page shows accurate "Configured" / "Not Configured" badges for each integration on load, allowing users to identify missing credentials at a glance.

**Independent Test**: Load Config page with only AWS credentials set â€” AWS badge shows "Configured", GitHub MCP badge shows "Not Configured". Verify with `GET /api/config`.

### TDD Tests â€” write and confirm failing first

- [X] T026 [US3] Extend `backend/tests/routers/test_config.py` â€” test `GET /api/config` returns `configured: true` for AWS when env-var fallback (`settings.aws_access_key_id`) is non-empty and DB is empty; test `configured: false` when both DB and env-var are empty; test partial config (key ID present, secret absent) returns `configured: false`

### Backend Implementation

- [X] T027 [US3] Refine `GET /api/config` handler in `backend/routers/config.py` â€” ensure `configured` flag logic is correct: `true` only when BOTH required fields are non-empty (DB row wins over env-var; env-var is fallback); log a warning when falling back to env-vars (per Principle VI)

### Frontend Implementation

- [X] T028 [P] [US3] Ensure `.config-status-badge` renders visually distinct "Configured" (green accent) and "Not Configured" (grey/warning) states in `frontend/style.css`
- [X] T029 [US3] Verify `loadConfigPage()` in `frontend/app.js` correctly sets badge state for both cards on initial load â€” no save required; covers edge case where one is configured and the other is not

**Checkpoint**: T026 passes. Status badges accurately reflect both DB-stored and env-var-fallback configuration state on page load.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge case handling, accessibility, linting.

- [X] T030 [P] Add clear-credential confirmation dialog to `frontend/app.js` â€” when a required field (secret or repo) is cleared (empty string submitted), call `window.confirm("This will remove the stored [field name]. Are you sure?")` before sending PATCH; abort if user cancels
- [X] T031 [P] Add input whitespace trimming to `backend/models/schemas.py` â€” add `field_validator` on `AwsConfigUpdate.access_key_id` and `GithubMcpConfigUpdate.repo` to strip leading/trailing whitespace before validation
- [X] T032 [P] Add structured logging to `backend/repositories/config_repo.py` â€” log at INFO level on successful upsert; log at WARNING when returning env-var fallback values (no `print()` statements per Principle VI)
- [X] T033 Run `ruff format backend/ && ruff check backend/` â€” fix any linting issues in all modified files
- [X] T034 Run `pytest --cov=backend --cov-fail-under=80 -v` â€” confirm all tests pass and overall backend coverage â‰¥80%; fix any failing tests or coverage gaps before PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies â€” start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion â€” BLOCKS all user stories
- **Phase 3 (US1 â€” AWS)**: Depends on Phase 2 completion
- **Phase 4 (US2 â€” GitHub MCP)**: Depends on Phase 2 completion â€” can run in parallel with Phase 3
- **Phase 5 (US3 â€” Status Overview)**: Depends on Phase 3 + Phase 4 being complete (needs both cards present)
- **Phase 6 (Polish)**: Depends on Phase 5 completion

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2 completes
- **US2 (P1)**: Independent after Phase 2 completes â€” can be developed in parallel with US1
- **US3 (P3)**: Depends on US1 and US2 (needs both cards to exist for status overview to be meaningful)

### Within Each User Story

- TDD tests written FIRST and confirmed failing before implementation begins
- Models/schemas before repository operations
- Repository operations before router handlers
- Router handlers before frontend markup
- Frontend markup before frontend JS handlers
- JS handlers before CSS styling (style only what exists)

### Parallel Opportunities

Within Phase 1: T003 (schemas) and T004 (router stub) can run in parallel after T002
Within Phase 3: T010 and T011 (tests) can run in parallel; T014 (markup) and T010/T011 (tests) are independent
Across Phase 3 and 4: All of Phase 4 can start once Phase 2 is done, in parallel with Phase 3

---

## Parallel Example: Phase 3 + Phase 4

```bash
# Once Phase 2 is complete, launch both user stories in parallel:
# Agent A: Work through T010 â†’ T018 (US1 â€” AWS)
# Agent B: Work through T019 â†’ T025 (US2 â€” GitHub MCP)
# Both share backend/repositories/config_repo.py but add different functions â€” coordinate on that file
```

---

## Implementation Strategy

### MVP (User Stories 1 only)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational)
3. Complete Phase 3 (US1 â€” AWS Credentials)
4. **STOP and VALIDATE**: Config tab visible, AWS credentials save and reload, masking works
5. Optionally demo before adding US2

### Full Delivery

1. Phase 1 + 2 â†’ Foundation ready
2. Phase 3 (US1) + Phase 4 (US2) in parallel â†’ Both credential types configurable
3. Phase 5 (US3) â†’ Status overview polishes the UX
4. Phase 6 (Polish) â†’ Coverage gate, linting, edge cases
5. Run quickstart.md scenarios end-to-end before PR

---

## Notes

- `[P]` tasks = different files, no pending dependencies
- TDD is mandatory (Principle IV) â€” never mark a test task done before confirming it fails first
- `backend/repositories/config_repo.py` is touched in Phase 2, 3, and 4 â€” coordinate if working in parallel
- Mask sentinel `"â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"` (8 Ã— U+2022) must be consistent between frontend and backend â€” define as a constant in the repository layer
- Coverage gate: `pytest --cov=backend --cov-fail-under=80` must pass before PR (T034 is a blocking gate)
- No `os.environ` reads outside `backend/config.py` (Principle V)
- No `print()` in application code; use `logging.getLogger(__name__)` (Principle VI)
