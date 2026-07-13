# Quickstart & Validation: Service Health Dashboard

Validates the feature end-to-end. See [data-model.md](./data-model.md) and
[contracts/](./contracts/) for field/endpoint detail — not repeated here.

## Prerequisites

- Backend deps installed (`pip install -r requirements.txt`) and the test/dev Postgres
  reachable (same setup as existing features; see `LOCAL_SETUP.md`).
- AWS credentials configured on the Config page (or via env fallback) with read access to
  Glue, Lambda, DataSync, and CloudWatch metrics.

## Setup

```bash
# Apply the new migration (adds app_config.health_config)
alembic -c backend/db/migrations/alembic.ini upgrade head   # or the project's usual alembic invocation

# Run the app
uvicorn backend.main:app --reload
```

## Validation scenarios

### 1. Configure monitored resources (User Story 3)
1. Open the app → **Config** tab.
2. In each new picker (Glue Jobs, Glue Workflows, Lambda Functions, DataSync Tasks),
   type to filter, select one or more, and **Save**.
3. Reload the page → selections persist (served from `GET /api/config` → `health`).
   - **Expected**: chosen resources remain selected after reload.

### 2. View health on demand (User Story 1)
1. Open the new **Health** tab.
2. **Expected**: one card per configured resource, each with a status badge
   (🟢 up / 🟡 up-with-failures / 🔴 down / neutral unknown) and a failure count.
3. Force a red card: pick a Glue job whose latest run FAILED → its card shows down / a
   non-green badge.

### 3. Change the lookback window (User Story 2)
1. On the Health tab, change the window dropdown between **1h / 24h / 7d**.
2. **Expected**: failure counts recompute for the selected window without a full reload
   (`GET /api/health/services?window=...` re-issued).

### 4. Refresh
1. Click **Refresh**.
2. **Expected**: all cards re-run and update; no duplicate cards.

### 5. Graceful degradation (FR-012)
1. Temporarily select a resource then delete/rename it in AWS (or revoke a permission).
2. **Expected**: that card shows **unknown** with a detail; all other cards still render.

### 6. Empty & error states (FR-014)
- No resources configured → Health tab shows an empty state prompting configuration.
- Remove AWS credentials → discovery pickers and health cards surface a clear error/unknown
  message rather than false "up".

## Automated test commands

```bash
# Full backend suite with coverage gate (Constitution IV: ≥80% overall)
pytest --cov=backend --cov-fail-under=80

# Feature-focused
pytest backend/tests/providers/test_health_checks.py \
       backend/tests/services/test_health_service.py \
       backend/tests/routers/test_health.py \
       backend/tests/routers/test_config.py \
       backend/tests/repositories/test_config_repo.py
```

**Expected**: all pass; per-layer coverage meets targets (services ≥85%, providers ≥70%,
routers ≥75%, repositories ≥80%). AWS is mocked (`botocore.stub`/`moto`) — no real calls.

## Success-criteria mapping

| Criterion | Validated by |
|-----------|--------------|
| SC-001 (status < 10s) | Scenario 2 + concurrent fan-out (research §3) |
| SC-002 (every resource has a state) | Scenario 2; contract test one-result-per-resource |
| SC-003 (window scoping) | Scenario 3; provider window tests |
| SC-004 (window updates, no reload) | Scenario 3 |
| SC-005 (partial degradation) | Scenario 5; service partial-failure test |
| SC-006 (config → view < 2 min) | Scenarios 1–2 |
