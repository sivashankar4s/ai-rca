# AI-RCA → CRM-Style Platform — Design Plan

## 1. Vision

Today AI-RCA is **stateless**: fetch failures from Athena → run a 4-step LLM pipeline → show results → save a JSON snapshot. Nothing is remembered between runs.

The goal is to evolve this into a **CRM-style RCA platform**:

- Every failure / RCA becomes a persistent **case** with a lifecycle (status, assignee, comments, history) — like a CRM tracks a lead through a pipeline.
- A growing **knowledge base** of root-cause "signatures" lets recurring failures auto-match prior RCAs instead of re-running the LLM every time — like a CRM recognizes a returning contact.
- The platform supports **multiple projects/applications** (not just `db11224`), each with its own data source and log backend, plus **cross-project dashboards**.
- Inputs (failure data) and outputs (log analysis) become **pluggable** — Athena/Postgres/DynamoDB for data, CloudWatch/Grafana for logs — building on the existing [`PLUGIN_STRATEGY_PLAN.md`](./PLUGIN_STRATEGY_PLAN.md).

This doc focuses on **architecture and data model**. No code changes are made yet.

---

## 2. How this relates to `PLUGIN_STRATEGY_PLAN.md`

That plan already defines the Strategy pattern for:
- `DataSourceStrategy` (Athena, LocalFile, ...)
- `LLMStrategy` (Navify, ...)
- `LogAnalysisStrategy` (CloudWatch, Grafana Loki, ...)

This CRM plan **extends it** in three ways:
1. Adds **Postgres** as both (a) a `DataSourceStrategy` provider (failures can be read from a Postgres table) and (b) the **persistence backbone** of the CRM itself (cases, signatures, projects — a separate concern from "where do failures come from").
2. Adds a **`projects` table** so provider selection + connection config become **per-project, runtime DB rows** instead of global `.env` values.
3. Adds a **case/signature data model** and **matching workflow** on top of the orchestrator's output.

The strategy interfaces (`fetch_records`, `invoke`, `execute_query`, `build_deep_link`) stay unchanged — only *where their config comes from* changes (DB row per project instead of `.env`).

---

## 3. Core Concepts & CRM Analogy

| CRM concept | AI-RCA equivalent |
|---|---|
| Account / Org | **Project** — one monitored application (e.g. `db11224`) |
| Lead / Contact | **Failure record** — a single FAILED event |
| Deal / Opportunity (pipeline stages) | **RCA Case** — New → Triaged → Analyzed → Assigned → Resolved → Recurring |
| Activity timeline | **Case activity log** — comments, status changes, re-analysis runs |
| "We've talked to this contact before" | **Root-cause signature match** — recurring error pattern recognized from history |
| Cross-account reporting | **Cross-project dashboard** — top recurring root causes, MTTR, trends |

---

## 4. Data Model (PostgreSQL)

```
┌────────────────┐       ┌────────────────────┐       ┌──────────────────────┐
│   projects      │ 1   N │  failure_records    │ N   N │   rca_cases           │
│ ──────────────  │──────▶│ ──────────────────  │──────▶│ ─────────────────────│
│ id              │       │ id                   │       │ id                    │
│ name             │       │ project_id (FK)     │       │ project_id (FK)       │
│ data_source_cfg  │       │ raw_payload (JSONB) │       │ status                │
│ log_backend_cfg  │       │ component_name      │       │ assignee              │
│ llm_cfg          │       │ error_code          │       │ summary               │
│ created_at       │       │ event_created_ts    │       │ root_cause            │
└────────────────┘       │ signature_hash      │       │ failure_category      │
                          │ created_at          │       │ cw_log_url            │
                          └────────────────────┘       │ created_at/updated_at │
                                                          └──────────┬────────────┘
                                                                     │ 1
                                                                     │ N
                                                          ┌──────────▼────────────┐
                                                          │   case_activity        │
                                                          │ ─────────────────────  │
                                                          │ id, case_id (FK)       │
                                                          │ activity_type          │
                                                          │ payload (JSONB)        │
                                                          │ created_by, created_at │
                                                          └────────────────────────┘

┌──────────────────────────────┐       ┌─────────────────────────┐
│  root_cause_signatures        │ N   N │  case_signature_links    │
│ ──────────────────────────── │──────▶│ ─────────────────────── │
│ id                            │       │ case_id (FK)             │
│ project_id (FK, nullable*)    │       │ signature_id (FK)        │
│ signature_hash (unique)       │       │ matched_at               │
│ component_name, error_code    │       └─────────────────────────┘
│ stage                         │
│ root_cause                    │
│ fix_notes                     │
│ failure_category              │
│ occurrence_count              │
│ first_seen / last_seen        │
└──────────────────────────────┘
   * project_id NULL = signature is "global" (cross-project pattern)
```

### 4.1 `projects`

Replaces global `.env` provider settings with per-project config rows.

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,          -- e.g. "db11224"
    description     TEXT,
    data_source_cfg JSONB NOT NULL,                -- {"provider": "athena", "database": "...", "table": "..."}
    log_backend_cfg JSONB NOT NULL,                -- {"provider": "cloudwatch", "log_group": "..."}
    llm_cfg         JSONB,                          -- optional override of global LLM model
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.2 `failure_records`

Normalized copy of raw failures pulled from any data source (Athena today, Postgres/Dynamo later). `signature_hash` is computed at ingest time for fast matching.

```sql
CREATE TABLE failure_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id),
    application_name    TEXT,
    component_name      TEXT,
    organization        TEXT,
    file_trace_id       TEXT,           -- custom_key1
    file_name           TEXT,           -- custom_key2
    device_id           TEXT,           -- custom_key3
    error_code          TEXT,
    stage               TEXT,
    event_created_ts    TIMESTAMPTZ,
    event_inserted_ts   TIMESTAMPTZ,
    raw_payload         JSONB NOT NULL, -- full original record (event_data etc.)
    signature_hash      TEXT NOT NULL,  -- hash(component_name, error_code, stage)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_failure_records_project_signature ON failure_records(project_id, signature_hash);
CREATE INDEX idx_failure_records_project_created ON failure_records(project_id, event_created_ts DESC);
```

### 4.3 `rca_cases`

The CRM "deal" — a group of related failures with a lifecycle.

```sql
CREATE TYPE case_status AS ENUM (
    'new', 'triaged', 'analyzing', 'analyzed', 'assigned', 'resolved', 'recurring'
);

CREATE TABLE rca_cases (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id),
    status           case_status NOT NULL DEFAULT 'new',
    assignee         TEXT,
    component_name   TEXT,
    error_pattern    TEXT,
    root_cause       TEXT,
    failure_category TEXT,
    immediate_action TEXT,
    likely_fix       TEXT,
    affected_files   JSONB,            -- list of strings
    escalation_path  TEXT,
    impact_count     INT NOT NULL DEFAULT 0,
    cw_log_url       TEXT,
    summary          TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rca_cases_project_status ON rca_cases(project_id, status);
```

A join table `case_failure_records (case_id, failure_record_id)` links cases to the underlying raw failures (many-to-many — a recurring case accumulates new failure records over time).

### 4.4 `case_activity`

Timeline / audit log — every status change, comment, and re-analysis.

```sql
CREATE TABLE case_activity (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id       UUID NOT NULL REFERENCES rca_cases(id),
    activity_type TEXT NOT NULL,   -- 'status_change' | 'comment' | 'analysis_run' | 'signature_match'
    payload       JSONB,
    created_by    TEXT,            -- free-text user identifier (no auth yet)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.5 `root_cause_signatures` — the knowledge base

```sql
CREATE TABLE root_cause_signatures (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID REFERENCES projects(id),  -- NULL = global/cross-project pattern
    signature_hash    TEXT NOT NULL,
    component_name    TEXT,
    error_code        TEXT,
    stage             TEXT,
    root_cause        TEXT NOT NULL,
    fix_notes         TEXT,
    failure_category  TEXT,
    occurrence_count  INT NOT NULL DEFAULT 1,
    first_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, signature_hash)
);
```

`case_signature_links (case_id, signature_id, matched_at)` records which cases matched which signatures — gives you "this exact failure has happened 14 times across 3 projects."

---

## 5. Signature Matching & Dedup Workflow

```
New failures fetched (per project)
        │
        ▼
Compute signature_hash = hash(component_name, error_code, stage)
        │
        ▼
Look up root_cause_signatures
   (project-scoped first, then global)
        │
   ┌────┴─────┐
   │ match?   │
   └────┬─────┘
   yes  │   no
        │   │
        │   └──▶ Run existing 4-step LLM pipeline ──▶ create new rca_case (status=analyzed)
        │                                              + create new root_cause_signature
        │
        └──▶ Auto-link new failure_records to existing case
             - if case.status == 'resolved' → set status='recurring', notify
             - else → bump impact_count, append case_activity('signature_match')
             - LLM pipeline skipped (cost saving) unless user requests "re-analyze"
```

This is the core CRM intelligence: **the system "remembers" a failure pattern and its resolution**, the same way a CRM recognizes a returning customer and pulls up their history instead of starting a fresh conversation.

---

## 6. Multi-Project Architecture

- Every API route becomes project-scoped: `/api/projects/{project_id}/failures`, `/api/projects/{project_id}/analyze`, `/api/projects/{project_id}/cases`.
- A `ProjectContext` is resolved once per request (loads `data_source_cfg`, `log_backend_cfg`, `llm_cfg` from the `projects` row) and passed into the plugin registry from `PLUGIN_STRATEGY_PLAN.md`:

```python
def get_data_source(project: Project) -> DataSourceStrategy:
    cfg = project.data_source_cfg
    match cfg["provider"]:
        case "athena":
            return AthenaDataSource(database=cfg["database"], table=cfg["table"])
        case "postgres":
            return PostgresDataSource(table=cfg["table"])
        case "dynamodb":
            return DynamoDBDataSource(table=cfg["table"])
        ...
```

- Cross-project views (dashboards, knowledge base search) query across all projects by omitting the `project_id` filter — these become a new set of read-only aggregate endpoints, e.g. `/api/dashboard/top-root-causes`, `/api/dashboard/recurring-cases`.
- The frontend adds a **project switcher** (dropdown) at the top of the UI; case list / dashboard views are scoped to the selected project (or "All Projects").

---

## 7. New/Updated API Surface (high level)

| Endpoint | Purpose |
|---|---|
| `GET /api/projects` / `POST /api/projects` | Manage projects (CRUD on `projects` table) |
| `POST /api/projects/{id}/failures` | (existing, project-scoped) fetch + persist failures |
| `POST /api/projects/{id}/analyze` | (existing, project-scoped) run LLM pipeline → creates/updates `rca_cases` |
| `GET /api/projects/{id}/cases` | List cases (filter by status/component/assignee) — the "case queue" |
| `GET /api/cases/{case_id}` | Case detail + activity timeline |
| `PATCH /api/cases/{case_id}` | Update status/assignee/comment |
| `GET /api/dashboard/top-root-causes` | Cross-project aggregate |
| `GET /api/dashboard/recurring-cases` | Cross-project recurring-pattern view |

---

## 8. Folder Structure Additions

**Migrations: Alembic (SQLAlchemy)** — chosen over Prisma because the backend is pure Python/FastAPI; Alembic integrates directly with SQLAlchemy ORM models (autogenerate diffs from `db/models.py`), avoids introducing a separate schema language/Node tooling, and is the de facto standard for this stack.

```
backend/
├── db/
│   ├── __init__.py
│   ├── session.py              # SQLAlchemy engine/session (Postgres)
│   ├── models.py                # ORM models: Project, FailureRecord, RcaCase, CaseActivity, RootCauseSignature
│   └── migrations/               # Alembic env + versioned migration scripts
│       ├── env.py
│       └── versions/
│           └── 0001_initial_schema.py   # creates tables from §4 (projects, failure_records,
│                                          # rca_cases, case_activity, root_cause_signatures,
│                                          # case_signature_links, case_failure_records)
├── alembic.ini
├── repositories/
│   ├── project_repo.py
│   ├── failure_repo.py
│   ├── case_repo.py
│   └── signature_repo.py
├── services/
│   ├── signature_service.py     # compute hash, match/dedup logic
│   └── rca_orchestrator.py       # (existing, extended to persist results via repos)
├── providers/
│   └── data_source/
│       └── postgres.py           # PostgresDataSource(DataSourceStrategy)
└── routers/
    ├── projects.py
    ├── cases.py
    └── dashboard.py
```

---

## 9. Implementation Phases

### Phase 1 — Postgres persistence foundation (single project, current flow unchanged)
- [ ] Add Postgres connection (SQLAlchemy), `db/models.py` for all 6 tables above
- [ ] Initialize Alembic (`alembic init backend/db/migrations`), generate `0001_initial_schema` migration from the ORM models, run it against the dev Postgres instance
- [ ] Seed one `projects` row representing today's `db11224` config (from current `.env`)
- [ ] After `/api/analyze` runs, persist `failure_records` + `rca_cases` + `case_activity` (no behavior change visible to user yet)
- [ ] Implement `signature_service` — compute `signature_hash`, write to `root_cause_signatures` on first occurrence

### Phase 2 — Apply `PLUGIN_STRATEGY_PLAN.md` strategy refactor
- [ ] Implement strategy ABCs + provider migration as already planned
- [ ] Add `PostgresDataSource` provider
- [ ] Move provider config from `.env` → `projects.data_source_cfg` / `log_backend_cfg`

### Phase 3 — Case management UI (the "CRM" surface)
- [ ] `GET/PATCH /api/cases` endpoints
- [ ] Case list view (queue) with status/assignee filters
- [ ] Case detail view with activity timeline + comments

### Phase 4 — Signature matching / dedup workflow
- [ ] On new failure ingest, check `root_cause_signatures` before running LLM
- [ ] Auto-link matched failures to existing case; handle `resolved → recurring` transition
- [ ] "Re-analyze anyway" override for users

### Phase 5 — Multi-project + cross-project dashboards
- [ ] `projects` CRUD UI (admin screen for adding new monitored apps)
- [ ] Project switcher in frontend
- [ ] Cross-project dashboard endpoints + UI (top root causes, recurrence trends, MTTR)

### Phase 6 — Grafana log backend (per `PLUGIN_STRATEGY_PLAN.md` Phase 3)
- [ ] `GrafanaLokiBackend` provider
- [ ] Per-project `log_backend_cfg` supports `"provider": "grafana"`

---

## 10. Open Questions / Decisions for Later

| Question | Options | Notes |
|---|---|---|
| Signature definition | `(component_name, error_code, stage)` exact match vs. embedding similarity | Start with exact-match hash (cheap, deterministic); add embedding-based fuzzy match later if needed |
| Where does Postgres run? | RDS (managed) vs. self-hosted on existing infra | Cost-driven — user prefers low-cost; could start with a small RDS instance or existing shared Postgres |
| Auth/multi-user | Free-text `assignee` vs. real auth | Deferred — free-text for now, matches "single-user/internal" decision |
| Re-analysis cost control | Auto-skip LLM on signature match vs. always allow override | Default: skip + show "matched known issue", with manual "re-analyze" button |
