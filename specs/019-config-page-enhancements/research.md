# Research: Config Page Enhancements

## Decision 1: Credential Storage Strategy

**Decision**: Store credentials in a new `app_config` PostgreSQL table (single-row, JSONB columns per integration group) rather than writing to `.env` at runtime.

**Rationale**: Writing to `.env` at runtime requires file-system write permissions that may not exist in containerised deployments, creates a race condition if multiple workers run, and is hard to audit. A DB row is transactional, survives restarts, and fits the existing SQLAlchemy/Alembic migration pattern already in this project.

**Alternatives considered**:
- Write to `.env` at runtime — rejected: file-permission issues in prod containers, no concurrent-safe semantics.
- Use `projects` table per-row — rejected: per-project config is explicitly deferred to `specs/012-multi-project-config`; polluting the `projects` table with global settings creates confusion.
- Separate key-value store (Redis, file-based secrets store) — rejected: adds a new infrastructure dependency for a feature that is not latency-sensitive.

---

## Decision 2: Secret Masking Strategy

**Decision**: Secrets (AWS Secret Access Key, GitHub token) are stored as-is in the DB but are never returned in full to the API response. On GET, the response replaces any non-empty secret with the fixed mask `"••••••••"`. On PATCH, an incoming field value equal to `"••••••••"` is treated as "no change" and the stored value is preserved.

**Rationale**: This is the standard pattern used by GitHub, AWS Console, and Vercel for credential fields — familiar to users, prevents over-the-shoulder leakage, and avoids complex re-entry UX.

**Alternatives considered**:
- Return the full secret on every GET — rejected: violates FR-009 and creates credential exposure in browser devtools/logs.
- Encrypt at rest in the DB column — not rejected as future hardening; deferred because the DB is already protected by network ACLs and the constitution doesn't require application-layer encryption for v1.

---

## Decision 3: Single-row vs. Multi-row Config Table

**Decision**: `app_config` has exactly one row, enforced by a `CHECK (id = 1)` constraint and an `ON CONFLICT DO UPDATE` upsert pattern in the repository.

**Rationale**: There is only one global config in this iteration. A single-row table is the simplest design that avoids a key-value schema while keeping JSONB flexibility for future additions within each integration group.

**Alternatives considered**:
- Key-value rows (one row per config key) — rejected: requires a schema change to add new keys and adds parsing complexity in the repository.
- Multiple rows keyed by integration type — rejected: unnecessary complexity for a single-tenant global config; the JSONB column approach achieves the same flexibility.

---

## Decision 4: Frontend Config Page Approach

**Decision**: Add a new "Config" tab to the existing single-page navigation (same pattern as the existing analysis and GitHub sections). Each integration group (AWS, GitHub MCP) is a card with a form. Fields are rendered as password-type inputs. Save buttons are per-section (not one global save) to isolate concerns.

**Rationale**: Matches the existing SPA pattern (no new routing library needed), per-section saves are idiomatic for credential management UIs (GitHub Settings, AWS Console), and keeping masked fields as `type="password"` prevents autocomplete leakage.

**Alternatives considered**:
- Single "Save All" button — rejected: if one section fails validation, the other section's data is blocked unnecessarily.
- Separate route/page per integration — rejected: the project has no client-side router; adding one for one config page violates YAGNI.

---

## Decision 5: API Endpoint Shape

**Decision**: Two PATCH endpoints (`PATCH /api/config/aws` and `PATCH /api/config/github-mcp`) plus one GET (`GET /api/config`) on a new `routers/config.py` router. Each PATCH accepts only the fields relevant to that integration group.

**Rationale**: Granular PATCH endpoints map directly to the per-section save UX, allow independent validation schemas, and avoid partial-update ambiguity. A single GET returns all config status in one call to minimise page-load round-trips.

**Alternatives considered**:
- Single `PUT /api/config` with full payload — rejected: forces the client to re-send all fields (including masked secrets) for unrelated changes, increasing the risk of accidentally wiping a field.
- Separate GET per integration group — rejected: two network calls on page load for no benefit; both groups are always displayed together.
