# Quickstart: Auto-Link RCA Cases to GitHub Pull Requests

Validates the user stories in `spec.md` end-to-end. Requires the baseline
setup from `specs/001-ai-rca-tool/quickstart.md` plus a configured GitHub
repository (`GITHUB_REPO`, `GITHUB_TOKEN`, `GITHUB_MCP_COMMAND`) that contains
at least one pull request whose branch name or title references a component
name / error code present in your failure data.

## Prerequisites

- Baseline app running (`uvicorn backend.main:app --reload ...`) with Postgres
  migrated, including the new `linked_pr` column on `rca_cases`
  (`alembic upgrade head`)
- `GITHUB_REPO` configured and reachable via the GitHub MCP server
- A test pull request exists in that repo whose branch name or title contains
  a component name and/or error code matching a failure record you will
  analyze (e.g. branch `fix/lz-processor-s3-put` for component
  `dp-lz-s3-event-processor` / error `S3_PUT_FAILED`)

## Validate User Story 1 — Related PR surfaced on the report (P1)

1. Fetch failures and select records for the component matching your test PR.
2. Run `/api/analyze`.
3. **Expected**: The corresponding `failure_groups[]` entry includes
   `linked_pull_request` with the test PR's `title`, `author`, `state`, and
   `url` (FR-001–FR-004).
4. Repeat for a component/error with **no** matching PR.
5. **Expected**: That failure group has no `linked_pull_request`
   (acceptance scenario 2), and the rest of the response is unaffected.
6. Temporarily unset `GITHUB_REPO` and re-run `/api/analyze`.
7. **Expected**: Response is identical to the pre-feature baseline — no
   `linked_pull_request` anywhere, and `code_analysis` is `null` (FR-006,
   acceptance scenario 3).

## Validate User Story 2 — PR status reflects fix progress (P2)

1. With the test PR still **open**, run `/api/analyze` for the matching
   component.
2. **Expected**: `linked_pull_request.state == "open"`.
3. Merge the test PR on GitHub.
4. Re-run `/api/analyze` for the same component.
5. **Expected**: `linked_pull_request.state == "merged"`.
6. Repeat with a PR that is closed without merging.
7. **Expected**: `linked_pull_request.state == "closed"`.

## Validate User Story 3 — Persisted across recurring analyses (P3)

1. Run `/api/analyze` for a failure batch so that a new `RcaCase` is created
   with `linked_pr` set to the test PR (User Story 1).
2. Inspect `rca_cases.linked_pr` for that case — confirm it matches the test
   PR, and `case_activity` has a `pr_linked` row (FR-007, FR-009).
3. Re-run `/api/analyze` for a failure batch with the **same**
   `(component_name, error_code, stage)` signature, but in a state where no
   new candidate PR is found (e.g. temporarily make the GitHub MCP call fail,
   or use a component with no PRs).
4. **Expected**: `rca_cases.linked_pr` for that case is **unchanged**
   (acceptance scenario 1, FR-008).
5. Create a second, more relevant pull request (stronger match) and re-run
   `/api/analyze` for the same signature.
6. **Expected**: `rca_cases.linked_pr` is updated to the new PR, and a
   `pr_updated` `case_activity` row is recorded (acceptance scenario 2,
   FR-008/FR-009).

## Validate edge cases

- Delete/close-and-unlist the previously linked PR (or otherwise make it
  unresolvable) and run `/api/analyze` again for that case's signature with no
  replacement candidate found.
  **Expected**: `rca_cases.linked_pr` is cleared (`null`) and a `pr_unlinked`
  activity row is recorded (FR-010).
- Make the GitHub MCP call fail (e.g. invalid `GITHUB_MCP_COMMAND`) while
  `GITHUB_REPO`/`GITHUB_TOKEN` are set.
  **Expected**: `/api/analyze` still returns 200 with full `failure_groups`/
  `summary`; no `linked_pull_request` fields are populated (FR-005, SC-002).

## Run automated tests

```bash
pytest --cov=backend --cov-fail-under=80
ruff format --check .
ruff check .
```
