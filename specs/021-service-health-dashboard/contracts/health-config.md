# Contract: Health configuration & discovery endpoints

All under the existing config router (`/api/config`), mirroring
`GET /api/config/cloudwatch/log-groups` and `PATCH /api/config/cloudwatch`.

## Discovery (for the Config-page pickers)

Each lists available resources from the connected AWS account for one service type.

| Endpoint | AWS source | `id` value | `label` |
|----------|-----------|------------|---------|
| `GET /api/config/health/glue-jobs` | `glue:ListJobs` | job name | job name |
| `GET /api/config/health/glue-workflows` | `glue:ListWorkflows` | workflow name | workflow name |
| `GET /api/config/health/lambda-functions` | `lambda:ListFunctions` | function name | function name |
| `GET /api/config/health/datasync-tasks` | `datasync:ListTasks` | task ARN | task name |

**Response `200` — `HealthResourcesResponse`**
```json
{ "resources": [ { "id": "etl-daily", "label": "etl-daily" } ] }
```

**Errors**
- AWS/credential failure → `400` with `{ "detail": "<message>" }` (same handling as the
  CloudWatch log-group discovery endpoint; discovery raising `RuntimeError`).

## Persist selection

## `PATCH /api/config/health`

**Request body — `HealthConfigUpdate`**
```json
{
  "glue_jobs": ["etl-daily"],
  "glue_workflows": ["nightly-pipeline"],
  "lambda_functions": ["ingest-fn", "notify-fn"],
  "datasync_tasks": [{ "id": "arn:aws:datasync:...:task/task-0abc", "label": "s3-to-efs" }]
}
```
- All four fields optional, default `[]`. Whitespace-only entries stripped.
- Empty across all four is allowed (clears monitoring).

**Response `200` — `ConfigSaveResult`**
```json
{ "success": true, "message": "Health configuration saved.", "updated_at": "2026-07-06T10:00:00Z" }
```

## Read (extends existing `GET /api/config`)

`AppConfigRead` gains a `health` field of type `HealthConfigStatus`:
```json
{
  "health": {
    "configured": true,
    "glue_jobs": ["etl-daily"],
    "glue_workflows": ["nightly-pipeline"],
    "lambda_functions": ["ingest-fn", "notify-fn"],
    "datasync_tasks": [{ "id": "arn:aws:datasync:...:task/task-0abc", "label": "s3-to-efs" }]
  }
}
```
`configured` is `true` when any list is non-empty.

**Contract tests (`routers/test_config.py`, `repositories/test_config_repo.py`)**
- Discovery endpoint returns `{resources: [...]}` on success; `400` on AWS error.
- `PATCH /api/config/health` persists and round-trips via `GET /api/config`.
- `upsert_health_config` writes all four lists; empty lists allowed; re-save overwrites.
