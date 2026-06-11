# Local Development Setup

This guide covers everything needed to run AI-RCA on your machine: Python environment,
database setup, environment variables, migrations, running the app, tests, and linting.

For the project overview / architecture / API reference, see [README.md](README.md).
For the CRM data model and provider plugin design, see [CRM_PLAN.md](CRM_PLAN.md) and
[PLUGIN_STRATEGY_PLAN.md](PLUGIN_STRATEGY_PLAN.md).

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.13+ | Backend runtime |
| PostgreSQL | 16 | CRM persistence (cases, signatures, activity log) |
| Docker (optional) | — | Easiest way to run Postgres locally via `docker-compose.yml` |

---

## 2. Clone & create the virtual environment

```bash
git clone <repo-url>
cd ai-rca

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

> **Always use this project's `.venv`** for installs and commands below
> (`./.venv/Scripts/python.exe -m ...` on Windows, `./.venv/bin/python -m ...` on macOS/Linux).
> A global Python install may have conflicting package versions (e.g. Airflow pins
> `sqlalchemy<2.0`).

## 3. Install dependencies

```bash
# Runtime dependencies
pip install -r requirements.txt

# + dev tools (pytest, ruff, coverage) — recommended for local dev
pip install -r requirements-dev.txt
```

---

## 4. Configure environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

### Environment variable reference

| Variable | Default | Required | Description |
|---|---|---|---|
| `AWS_REGION` | `us-east-1` | Yes (unless `LOCAL_DATA_FILE` is set) | AWS region for Athena/CloudWatch |
| `AWS_ACCESS_KEY_ID` | _(empty)_ | No | Leave blank to use IAM role / instance profile |
| `AWS_SECRET_ACCESS_KEY` | _(empty)_ | No | Paired with the access key above |
| `AWS_SESSION_TOKEN` | _(empty)_ | No | Only needed for temporary/STS credentials |
| `ATHENA_DATABASE` | `default` | Yes (if using Athena) | Glue/Athena database name |
| `ATHENA_TABLE` | `monitoring_table` | Yes (if using Athena) | Table holding failure events |
| `ATHENA_OUTPUT_BUCKET` | _(empty)_ | Conditional | `s3://...` URI for query results. **Leave empty** if the Athena workgroup manages results itself |
| `LOCAL_DATA_FILE` | _(empty)_ | No | Path to a local JSON file (e.g. `./sample_failures.json`) — when set, skips Athena/AWS entirely |
| `SNAPSHOTS_DIR` | `./snapshots` | No | Directory where fetched failure batches are saved as JSON. Empty disables snapshotting |
| `CLOUDWATCH_LOG_GROUP` | `/aws/application/logs` | Yes (if using CloudWatch) | Log group queried during RCA |
| `LLM_BASE_URL` | Navify dev endpoint | Yes | OpenAI-compatible chat completions base URL |
| `LLM_API_KEY` | _(empty)_ | Yes | API key/bearer token for the LLM endpoint |
| `LLM_MODEL` | `gpt-4o` | Yes | Model ID, e.g. `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `DATABASE_URL` | `postgresql+psycopg2://airca:airca@localhost:5432/airca` | Yes | Postgres connection string for CRM persistence |
| `DATA_SOURCE_PROVIDER` | `athena` | No | `athena` (or local file mode via `LOCAL_DATA_FILE`) |
| `LLM_PROVIDER` | `navify` | No | `navify` \| `openai` |
| `LOG_ANALYSIS_PROVIDER` | `cloudwatch` | No | `cloudwatch` \| `grafana_loki` |
| `GRAFANA_LOKI_URL` | _(empty)_ | Conditional | Grafana base URL — required if `LOG_ANALYSIS_PROVIDER=grafana_loki` |
| `GRAFANA_API_KEY` | _(empty)_ | Conditional | Grafana service-account/API token |
| `GRAFANA_DATASOURCE_UID` | _(empty)_ | Conditional | UID of the Loki datasource in Grafana (used for queries + Explore deep-links) |

> **Local dev without AWS:** set `LOCAL_DATA_FILE=./sample_failures.json` to bypass Athena
> entirely and serve the bundled sample data with the real schema.

---

## 5. Set up PostgreSQL

The CRM layer (cases, root-cause signatures, activity log) persists to Postgres.

### Option A — Docker (recommended)

```bash
docker compose up -d
```

This starts `postgres:16-alpine` on `localhost:5432` with:
- user: `airca`
- password: `airca`
- database: `airca`

This matches the default `DATABASE_URL` in `.env.example` — no further changes needed.

### Option B — Native PostgreSQL install

If you already have PostgreSQL 16 running locally, create the role and database:

```sql
CREATE USER airca WITH PASSWORD 'airca';
CREATE DATABASE airca OWNER airca;
```

Then set `DATABASE_URL` in `.env` accordingly (adjust host/port/credentials if different):

```env
DATABASE_URL=postgresql+psycopg2://airca:airca@localhost:5432/airca
```

### Run migrations

```bash
alembic upgrade head
```

This creates all CRM tables (`projects`, `failure_records`, `rca_cases`, `case_activity`,
`root_cause_signatures`, `case_signature_links`, `case_failure_records`).

To generate a new migration after changing `backend/db/models.py`:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

---

## 6. Run the app

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- App: http://localhost:8000
- Swagger / OpenAPI docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

---

## 7. Run tests

Tests run against a real Postgres database (using SAVEPOINT-based transaction rollback,
so no test data is persisted). Make sure Postgres is up and migrations have been applied
(steps 5 above) before running tests.

```bash
pytest
```

With coverage:

```bash
pytest --cov=backend --cov-report=term-missing
```

---

## 8. Lint

```bash
ruff check .

# auto-fix what's safe to fix
ruff check . --fix
```

---

## 9. Quick start (local-only, no AWS / Postgres)

For a fast UI-only check without setting up AWS or Postgres:

```env
LOCAL_DATA_FILE=./sample_failures.json
```

Note: persistence to Postgres still requires `DATABASE_URL` to point at a reachable
database — if Postgres isn't running, `/api/analyze` will log the persistence error
and roll back, but still return the RCA result to the UI.
