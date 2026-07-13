# Contract: Health check endpoint

## `GET /api/health/services`

Returns combined on-demand health for all configured resources. Powers the Health tab
and its Refresh action.

**Query parameters**

| Name | Type | Required | Default | Notes |
|------|------|----------|---------|-------|
| `window` | enum `1h` \| `24h` \| `7d` | no | `24h` | Failure-count lookback window |

**Response `200` — `ServiceHealthResponse`**
```json
{
  "window": "24h",
  "generated_at": "2026-07-06T10:15:00Z",
  "results": [
    {
      "service_type": "glue_job",
      "id": "etl-daily",
      "label": "etl-daily",
      "status": "up",
      "failure_count": 2,
      "last_activity_ts": "2026-07-06T09:00:00Z",
      "detail": "last run SUCCEEDED"
    },
    {
      "service_type": "lambda_function",
      "id": "ingest-fn",
      "label": "ingest-fn",
      "status": "down",
      "failure_count": 0,
      "last_activity_ts": null,
      "detail": "function State=Inactive"
    },
    {
      "service_type": "datasync_task",
      "id": "arn:aws:datasync:us-east-1:123:task/task-0abc",
      "label": "s3-to-efs",
      "status": "unknown",
      "failure_count": 0,
      "last_activity_ts": null,
      "detail": "AccessDenied: datasync:ListTaskExecutions"
    }
  ]
}
```

**Behavior**
- Empty `results` when nothing is configured (HTTP `200`, not an error) — frontend shows
  an empty state (FR-014).
- Invalid `window` value → `422` (FastAPI enum validation).
- Missing/invalid AWS credentials or a whole-service discovery failure → each affected
  resource appears with `status: "unknown"` and a `detail`; the request still returns
  `200` (FR-012). A total credential failure yields all-`unknown` results with details.
- One resource's failure never removes other resources from `results` (partial degradation).

**Contract tests (`routers/test_health.py`)**
- Configured resources → one result object per resource with a valid `status`.
- No config → `results == []`.
- Bad `window` → `422`.
- Provider raising for one resource → that resource `unknown`, others present.
- `window` echoed in response equals request.
