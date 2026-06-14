# AI Root Cause Analyzer (AI-RCA)

> **Hackathon Project**
> Automated, AI-driven Root Cause Analysis for data-pipeline failures — from raw failure
> records to grouped root causes, log deep-links, and a CRM-style case history.

---

## Problem Statement

When a data-pipeline failure occurs, engineers must manually:
1. Query Athena (or another store) to find failing records
2. Open CloudWatch / Grafana and write log queries from scratch
3. Read through hundreds of log lines to spot patterns
4. Write an RCA report
5. Remember whether this exact failure has happened before, and what fixed it last time

This is time-consuming, error-prone, and requires deep platform knowledge.
**AI-RCA automates the entire process** and keeps a searchable history of root causes.

---

## Solution

A two-step web UI backed by a FastAPI service that orchestrates:

| Step | What happens |
|------|-------------|
| **Step 1 — Fetch** | User selects a time range (1h / 1d / 1w, or a custom date range) and optional component filter → the configured data source returns matching `FAILED` records |
| **Step 2 — Analyze** | User selects specific records → LLM summarizes failures, generates targeted log queries, groups failures by root cause, and produces an executive summary |

Each failure group includes a **direct deep-link into the log backend** (CloudWatch
Logs Insights or Grafana Explore) pre-populated with the right query and time window —
one click to see the relevant logs.

Every fetched failure record is persisted to Postgres as soon as Step 1 runs (deduped
by `file_trace_id` on re-fetch), and every analysis additionally links those records to
an RCA case: failures with the same `(component_name, error_code, stage)` signature are
linked to the same case, so recurring issues are flagged automatically.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Dark-theme SPA)               │
│  ┌──────────────────┐       ┌──────────────────────────┐ │
│  │  Step 1           │       │  Step 2                  │ │
│  │  Failure Table    │──────▶│  RCA Results             │ │
│  │  + Pagination     │       │  + log backend deep-links│ │
│  └──────────────────┘       └──────────────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                      │ REST (JSON)
                      ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Python 3.13)               │
│                                                           │
│  POST /api/failures   ──▶  RCAOrchestrator.fetch_records │
│  POST /api/analyze    ──▶  RCAOrchestrator.analyze_records│
│         │                          │                      │
│         ▼                          ▼                      │
│  DataSourceStrategy   LLMStrategy        LogAnalysisStrategy
│  (Athena / local file)(Navify/OpenAI-compat)(CloudWatch / Grafana Loki)
│                                                           │
│  └──▶ persistence_service ──▶ Postgres (CRM tables)      │
└─────────────────────────────────────────────────────────┘
```

The orchestrator (`backend/services/rca_orchestrator.py`) depends only on three
abstract strategy interfaces — `DataSourceStrategy`, `LLMStrategy`,
`LogAnalysisStrategy`. Concrete providers are wired up at request time by
`backend/plugin_registry.py` based on `.env` settings (`DATA_SOURCE_PROVIDER`,
`LLM_PROVIDER`, `LOG_ANALYSIS_PROVIDER`). New backends are added as a single new
provider file — the orchestrator and router never change. See
[PLUGIN_STRATEGY_PLAN.md](PLUGIN_STRATEGY_PLAN.md) for the full design.

### LLM Pipeline (5 steps inside `/api/analyze`)

```
Selected failure records
        │
   Step 1 │ Summarize failures (LLM)
        │   → "3 components failing, S3_PUT_FAILED dominant…"
        │
   Step 2 │ Generate log queries for the configured backend (LLM)
        │   → 3 targeted queries (CloudWatch Insights or LogQL)
        │
   Step 3 │ Execute log queries against the configured backend
        │   → Collect relevant log lines
        │
   Step 4 │ RCA + grouping (LLM)
        │     → JSON array of FailureGroup objects
        │     → Executive summary
        │
   Step 5 │ Code Analysis Agent (GitHub MCP)
              → Recent commits/PRs in the configured repo within the failure
                time window — surfaced as a "Related Code Changes" card
```

### Code Analysis Agent (GitHub MCP)

`backend/agents/code_analysis_agent.py` talks to the official
[github-mcp-server](https://github.com/github/github-mcp-server) over stdio
(`backend/mcp/client.py`) to fetch recent commits and pull requests for a
configured repository within the failure's time window. Configure it via
`.env` or the Configuration drawer:

- `GITHUB_MCP_COMMAND` — path/name of the `github-mcp-server` binary on PATH (default `github-mcp-server`)
- `GITHUB_TOKEN` — a GitHub PAT, passed to the MCP server as `GITHUB_PERSONAL_ACCESS_TOKEN`
- `GITHUB_REPO` — `owner/repo` to inspect

If `GITHUB_REPO` is not set, the analysis response simply omits `code_analysis`
(no card is shown). If `GITHUB_REPO` is set but `GITHUB_TOKEN` is missing or the
MCP server can't be reached, the card shows an inline error instead of failing
the whole RCA request.

### CRM Persistence

`persistence_service` writes to Postgres at two points:

- **Step 1 (`/api/failures`)** — every fetched record is upserted into
  `failure_records`, deduped by `file_trace_id` so repeated fetches of the same
  time range don't create duplicate rows.
- **Step 2 (`/api/analyze`)** — for each failure group, its
  `(component_name, error_code, stage)` is hashed into a **root-cause signature**:
  - A new signature → a new RCA case is created (`status = new`).
  - A signature seen before → the existing case is linked and re-flagged as
    **recurring**, with an activity-log entry recording the recurrence.

This gives every RCA run a persistent history without any manual triage. See
[CRM_PLAN.md](CRM_PLAN.md) for the full data model, case lifecycle, and roadmap.

---

## Key Features

- **Two-step UI** — fetch first, analyze only what you select
- **Paginated failure table** — configurable page size (5 / 10 / 20 / 50), selections persist across pages
- **Select-all** across all pages, not just visible rows
- **LLM-generated log queries** — no manual query authoring, adapted to the configured log backend
- **One-click log-backend deep-links** per failure group — pre-loaded with query, log group, and time window
- **Failure grouping** — similar failures clustered by root cause with categories: `Database`, `Network`, `Application`, `Configuration`, `Timeout`, `Authentication`, `Resource`, `Unknown`
- **Executive summary** — 2–3 sentence human-readable report ready to paste into a ticket
- **Recurring-issue detection** — root-cause signatures link repeat failures to existing CRM cases
- **Pluggable providers** — swap data source / LLM / log backend via env vars, no code changes
- **Local dev mode** — `LOCAL_DATA_FILE=./sample_failures.json` skips Athena entirely
- **Snapshot save** — every fetched batch is saved to `./snapshots/` for audit/replay

---

## Sample Failure Data Schema

The default Athena provider targets a table shaped like this:

| Column | Type | Description |
|--------|------|-------------|
| `application_name` | VARCHAR | Tenant / application identifier |
| `component_name` | VARCHAR | Which pipeline component failed |
| `custom_key1` | VARCHAR | `file_trace_id` — unique trace for the file |
| `custom_key2` | VARCHAR | `file_name` — original file being processed |
| `custom_key3` | VARCHAR | `device_id` — source device |
| `event_created_timestamp` | TIMESTAMP | When the event occurred |
| `event_inserted_timestamp` | TIMESTAMP | When the record was written |
| `organization` | VARCHAR | Organization / tenant alias |
| `status` | VARCHAR | `FAILED` (only FAILED records are fetched) |
| `event_data` | VARCHAR | JSON string with `stage`, `error_code`, `object_type`, `retry_count`, `fhir_org_id`, etc. |

**Sample record:**
```json
{
  "application_name": "db11224",
  "component_name": "dp-lz-s3-event-processor",
  "custom_key1": "b5d83711-4e2e-48f2-8413-08a53cf2d4c7",
  "custom_key2": "voice_42b420b6-...-countdown-smartphone-microphone.raw",
  "custom_key3": "42b420b6-bc84-4583-a0a6-7d193047b318",
  "event_created_timestamp": "2026-05-06 14:13:09.152000",
  "event_inserted_timestamp": "2026-05-06 14:14:17.519000",
  "organization": "db11224",
  "status": "FAILED",
  "event_data": "{\"stage\": \"lz-processor\", \"error_code\": \"S3_PUT_FAILED\", \"retry_count\": 0, ...}"
}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, uvicorn |
| Persistence | PostgreSQL 16, SQLAlchemy 2.0 (ORM), Alembic (migrations) |
| Failure data sources | Amazon Athena (Presto SQL via boto3), local JSON file |
| Log analysis | Amazon CloudWatch Logs Insights, Grafana Loki (LogQL) |
| AI / LLM | Navify Enrichment API (OpenAI-compatible chat completions) |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript (no framework) |
| Config | pydantic-settings, `.env` file |
| Testing / Lint | pytest, pytest-cov, ruff |

### Available LLM Models (via Navify Enrichment API)

| Model ID | Best for |
|----------|----------|
| `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | ✅ **Default** — best balance of speed + reasoning |
| `global.anthropic.claude-opus-4-5-20251101-v1:0` | Maximum accuracy, slower |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Fastest, simple tasks only |
| `gemini-2.5-pro` | Alternative — strong reasoning |
| `gpt-4.1` | Alternative — strong JSON output |
| `bedrock-titan-embed-text-v2:0` | Embeddings only — **not for chat** |

---

## Project Structure

```
ai-rca/
├── backend/
│   ├── main.py                       # FastAPI app, middleware, static serving
│   ├── config.py                     # Pydantic settings from .env
│   ├── plugin_registry.py            # Selects providers based on .env settings
│   ├── strategies/                   # Abstract provider interfaces
│   │   ├── data_source.py            # DataSourceStrategy
│   │   ├── llm.py                    # LLMStrategy
│   │   └── log_analysis.py           # LogAnalysisStrategy
│   ├── providers/                    # Concrete provider implementations
│   │   ├── data_source/
│   │   │   ├── athena.py             # AthenaDataSource
│   │   │   └── local_file.py         # LocalFileDataSource
│   │   ├── llm/
│   │   │   └── navify.py             # NavifyLLMProvider
│   │   └── log_analysis/
│   │       ├── cloudwatch.py         # CloudWatchLogBackend
│   │       └── grafana_loki.py       # GrafanaLokiBackend
│   ├── models/
│   │   └── schemas.py                # FailureRecord, EventData, FailureGroup DTOs
│   ├── routers/
│   │   └── analysis.py               # POST /api/failures, POST /api/analyze, /api/config
│   ├── services/
│   │   ├── rca_orchestrator.py       # 4-step LLM pipeline (provider-agnostic)
│   │   ├── signature_service.py      # Root-cause signature hashing/matching
│   │   └── persistence_service.py    # Persists analysis results to CRM tables
│   ├── repositories/                 # DB access layer (SQLAlchemy queries)
│   │   ├── project_repo.py
│   │   ├── failure_repo.py
│   │   ├── signature_repo.py
│   │   └── case_repo.py
│   ├── db/
│   │   ├── models.py                 # SQLAlchemy ORM models (CRM tables)
│   │   ├── session.py                # Engine, SessionLocal, get_db()
│   │   └── migrations/               # Alembic migrations
│   └── tests/                        # pytest suite
├── frontend/
│   ├── index.html                    # Single-page app shell
│   ├── app.js                        # Two-step UI logic + pagination
│   └── style.css                     # Dark theme
├── sample_failures.json              # Local dev test data (real schema)
├── snapshots/                        # Auto-saved fetch results
├── docker-compose.yml                # Local Postgres
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
└── .env                               # Local config (not committed)
```

---

## Setup

See **[LOCAL_SETUP.md](LOCAL_SETUP.md)** for the full local development guide:
environment variables, PostgreSQL + Alembic setup, running the app, tests, and lint.

Quick start:

```bash
git clone <repo-url>
cd ai-rca

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements-dev.txt
cp .env.example .env             # then fill in your values

docker compose up -d             # start local Postgres
alembic upgrade head             # create CRM tables

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

For a quick UI-only check without AWS or Postgres, set
`LOCAL_DATA_FILE=./sample_failures.json` in `.env`.

---

## API Reference

### `POST /api/failures`

Fetch `FAILED` records from the configured data source.

**Request:**
```json
{
  "time_range": "1h",
  "component": "dp-lz-s3-event-processor"
}
```

**Response:**
```json
{
  "total": 47,
  "time_range": "1h",
  "records": [
    {
      "application_name": "db11224",
      "component_name": "dp-lz-s3-event-processor",
      "custom_key1": "b5d83711-...",
      "custom_key2": "voice_42b420b6-...-microphone.raw",
      "custom_key3": "42b420b6-...",
      "event_created_timestamp": "2026-05-06 14:13:09.152000",
      "event_inserted_timestamp": "2026-05-06 14:14:17.519000",
      "organization": "db11224",
      "status": "FAILED",
      "event_data": {
        "stage": "lz-processor",
        "error_code": "S3_PUT_FAILED",
        "retry_count": 0,
        "object_type": "application/rpmct",
        "file_name": "voice_42b420b6-...-microphone.raw",
        "device_id": "42b420b6-..."
      }
    }
  ]
}
```

### `POST /api/analyze`

Run the 5-step LLM RCA pipeline on selected records, then persist the results to Postgres.

**Request:**
```json
{
  "time_range": "1h",
  "records": [ /* array of FailureRecord objects selected from Step 1 */ ],
  "log_backend": "cloudwatch"   // optional: "cloudwatch" | "grafana_loki", overrides LOG_ANALYSIS_PROVIDER
}
```

**Response:**
```json
{
  "total_failures": 12,
  "time_range": "1h",
  "analyzed_at": "2026-05-12T10:30:00+00:00",
  "summary": "12 failures across 2 components. S3_PUT_FAILED errors in dp-lz-s3-event-processor suggest an IAM permission issue on the landing-zone bucket introduced in the last deployment.",
  "failure_groups": [
    {
      "group_id": "grp-1",
      "component": "dp-lz-s3-event-processor",
      "error_pattern": "S3_PUT_FAILED on lz-processor stage",
      "root_cause": "IAM role missing s3:PutObject permission on the landing-zone bucket after a policy update.",
      "failure_category": "Configuration",
      "impact_count": 10,
      "immediate_action": "...",
      "likely_fix": "...",
      "affected_files": ["..."],
      "escalation_path": "...",
      "cw_log_url": "https://us-west-2.console.aws.amazon.com/cloudwatch/...",
      "records": [...],
      "log_samples": [...]
    }
  ],
  "code_analysis": {
    "repo": "owner/repo",
    "items": [
      { "type": "commit", "title": "...", "author": "...", "date": "...", "url": "..." },
      { "type": "pull_request", "title": "...", "author": "...", "date": "...", "url": "..." }
    ],
    "error": null
  }
}
```

`code_analysis` is `null` if `GITHUB_REPO` is not configured.

### `GET /api/config` / `POST /api/config`

Read or update runtime AWS/Athena/LLM configuration in-memory (does not persist to `.env`).

### `GET /api/models`

Proxies the configured LLM provider's `/v1/models` endpoint.

### `GET /api/health`

Returns `{"status": "ok"}`.

---

## Required AWS IAM Permissions

```json
{
  "Effect": "Allow",
  "Action": [
    "athena:StartQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "logs:StartQuery",
    "logs:GetQueryResults",
    "logs:DescribeLogGroups"
  ],
  "Resource": "*"
}
```

> No `bedrock:InvokeModel` permission needed — the LLM is called via the Navify
> Enrichment API over HTTPS. Not required at all when `LOG_ANALYSIS_PROVIDER=grafana_loki`
> and/or `DATA_SOURCE_PROVIDER` uses local file mode.

---

## How the Log Deep-Link Works

For each failure group the API returns a `cw_log_url` — a pre-built deep link into the
configured log backend that:
- Points to the configured log group / Loki datasource
- Filters by `component_name`
- Sets the time window to match the selected time range
- Opens directly in the AWS console or Grafana Explore — no manual query needed

---
