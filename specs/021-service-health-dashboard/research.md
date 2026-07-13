# Phase 0 Research: Service Health Dashboard

All Technical Context items were resolvable from the existing codebase and AWS SDK
behavior — no open `NEEDS CLARIFICATION` remained. Decisions below record the boto3
call shapes and semantics each provider relies on, plus the cross-cutting choices.

## 1. Per-service health semantics (boto3 call mapping)

### Glue job — `GlueJobHealthCheck`
- **Discovery (picker)**: `glue:ListJobs` → job names (paginate `NextToken`).
- **Current status**: `glue:GetJobRuns(JobName=..., MaxResults=1)` → most recent run's
  `JobRunState`. Up if state ∈ {`SUCCEEDED`, `RUNNING`, `STARTING`, `WAITING`}; down if
  latest is `FAILED`/`TIMEOUT`/`ERROR`/`STOPPED`; unknown if no runs / call error.
- **Failure count**: page `GetJobRuns` and count runs whose `StartedOn` ≥ window start
  and `JobRunState` ∈ {`FAILED`, `TIMEOUT`, `ERROR`}. Stop paging once `StartedOn` <
  window start (runs are returned newest-first).
- **Decision**: Bound paging to a sane cap (e.g. first ~200 runs / few pages) to avoid
  unbounded scans; the 7d window is the widest we support.
- **Alternatives considered**: CloudWatch Glue metrics — rejected; run-state via
  `GetJobRuns` is authoritative and needs no metric namespace assumptions.

### Glue workflow — `GlueWorkflowHealthCheck`
- **Discovery**: `glue:ListWorkflows` → workflow names.
- **Current status**: `glue:GetWorkflowRuns(Name=..., MaxResults=1)` → latest run
  `Status`. Down if latest ∈ {`ERROR`, `STOPPED`}; up if {`COMPLETED`, `RUNNING`}.
- **Failure count**: page `GetWorkflowRuns` and count runs with `StartedOn` in window and
  `Status` == `ERROR` (Glue workflow runs don't have a `TIMEOUT`; failed actions roll up
  to run `Status = ERROR`). `Statistics.FailedActions > 0` also counts as a failed run.
- **Alternatives considered**: inspecting individual node/action states — rejected as
  over-detailed for a dashboard; run-level `Status`/`Statistics` is sufficient.

### Lambda — `LambdaHealthCheck`
- **Discovery**: `lambda:ListFunctions` → function names.
- **Current status**: `lambda:GetFunctionConfiguration(FunctionName=...)` → `State`. Up if
  `State == Active`; down if `Inactive`/`Failed`; unknown on error / not found.
- **Failure count**: `cloudwatch:GetMetricStatistics` (or `GetMetricData`) for namespace
  `AWS/Lambda`, metric `Errors`, dimension `FunctionName`, `Statistics=[Sum]`, `Period`
  covering the window, `StartTime`=window start, `EndTime`=now → sum the returned data
  points. Zero/no datapoints ⇒ 0 failures.
- **Decision**: Use `Errors` (not `Throttles`/`Duration`) as the single failure signal —
  matches the spec ("invocation errors"). Period = full window length so one datapoint
  suffices; sum defensively across datapoints regardless.
- **Alternatives considered**: scanning invocation logs in CloudWatch Logs Insights —
  rejected; metrics are cheaper, faster, and already aggregated.

### DataSync — `DataSyncHealthCheck`
- **Discovery**: `datasync:ListTasks` → entries of `{TaskArn, Name, Status}`. Store the
  **ARN** as the stable id; show `Name` as the label.
- **Current status**: from `ListTasks` entry `Status` (or `datasync:DescribeTask`) — up if
  `AVAILABLE`; down if `UNAVAILABLE`; unknown otherwise.
- **Failure count**: `datasync:ListTaskExecutions(TaskArn=...)` → execution entries with
  `Status`. Count executions with `Status == ERROR`. Execution list entries do **not**
  carry a start timestamp, so to scope by window we call
  `datasync:DescribeTaskExecution(TaskExecutionArn=...)` for candidate ERROR executions
  and read `StartTime`.
- **Decision**: To bound cost, list newest executions first and only `DescribeTaskExecution`
  on ERROR entries until one falls outside the window. Cap the number of describes per task.
- **Alternatives considered**: counting all-time ERROR executions (ignore window) —
  rejected; violates FR-006 (window scoping). CloudWatch DataSync metrics are sparse —
  rejected in favor of the executions API which is authoritative for ERROR outcomes.

## 2. Credential resolution

- **Decision**: Reuse the exact pattern in `data_source/cloudwatch.py:206-238` — accept an
  optional `aws_credentials: dict | None`; if `access_key_id` present use DB creds + region,
  else fall back to `settings.*`; never mix DB keys with an env session token. The registry
  builder reads `aws_config` from `app_config` (as `_build_cloudwatch_source` does).
- **Rationale**: Single, proven source of truth; avoids `UnrecognizedClientException` from
  mixed credentials; satisfies Constitution V.

## 3. Fan-out concurrency

- **Decision**: `health_service` builds the full list of (service_type, resource_id) checks
  from `health_config` and runs them via `concurrent.futures.ThreadPoolExecutor`
  (bounded `max_workers`, e.g. 8). Each future returns a `ServiceHealth`; exceptions are
  caught per-future and converted to an `unknown` result with a detail string.
- **Rationale**: boto3 is blocking; sequential checks over tens of resources risk breaching
  the ~10s target (SC-001). A small bounded pool keeps it responsive without overwhelming
  AWS API rate limits. Per-future try/except delivers FR-012 partial degradation.
- **Alternatives considered**: `asyncio` + aioboto3 — rejected (new dependency, whole
  codebase is sync boto3). Sequential — rejected on latency grounds.

## 4. Lookback window model

- **Decision**: `HealthWindow` `Enum` with members `H1` (`1h`), `H24` (`24h`), `D7` (`7d`)
  carrying their `timedelta`. The endpoint accepts `?window=24h` (default `24h`). The
  service computes `start = now - window.delta`, `end = now`.
- **Rationale**: Closed set → `Enum` per Constitution I; fixed presets match the spec
  (arbitrary ranges out of scope). One window applies uniformly to all cards (assumption).

## 5. Persistence shape

- **Decision**: Add `health_config` JSONB column to `app_config` (migration `007`,
  `down_revision = 006_add_athena_config`). Shape:
  `{"glue_jobs": [...], "glue_workflows": [...], "lambda_functions": [...], "datasync_tasks": [{"arn":..,"name":..}] }`.
  Follow the existing per-domain column convention (`aws_config`, `cloudwatch_config`, …).
- **Rationale**: Mirrors established `app_config` pattern; no secrets to mask (plain
  identifiers); no new table needed for a single-row global config.
- **Alternatives considered**: a dedicated `monitored_resources` table — rejected as
  premature (single global config, no per-row metadata, YAGNI).

## 6. Endpoint surface

- **Decision**:
  - `GET /api/health/services?window=24h` — combined health (new `routers/health.py`).
    Kept distinct from the existing liveness probe `GET /api/health` in `main.py`
    (different path, no collision).
  - Discovery for pickers under the config domain, mirroring
    `GET /api/config/cloudwatch/log-groups`:
    `GET /api/config/health/glue-jobs`, `/glue-workflows`, `/lambda-functions`,
    `/datasync-tasks` — each returns `{resources: [{id, label}]}`.
  - `PATCH /api/config/health` — persist selections.
- **Rationale**: One-domain-per-router (Constitution III); discovery lives with config since
  it powers the config pickers, exactly like the CloudWatch log-group discovery endpoint.

## 7. Frontend integration

- **Decision**: Add a `nav-health` tab + `health-view` following the existing
  `_activateTab` pattern (`app.js:1038`). Health view: window `<select>`, Refresh button,
  and a card grid grouped by service type. Introduce **one** reusable multi-select picker
  helper for the 4 new Config pickers (parameterized by fetch URL + storage key), leaving
  the existing bespoke CloudWatch picker untouched (surgical change).
- **Rationale**: Matches existing vanilla-JS style and CSS custom properties; the shared
  picker helper is justified by 4 uses (Constitution II condition *a*).
- **Alternatives considered**: splitting into `frontend/js/` modules now — deferred; the
  codebase is still a single `app.js`, so matching that avoids an unrelated refactor.

## Open questions

None. All resolved. Permission gaps (e.g. missing `cloudwatch:GetMetricStatistics`)
surface as `unknown` results with a detail message per FR-012 — not a hard failure.
