# Phase 0 Research: AI-Powered RCA Tool for Production Incidents

All items in the Technical Context are already resolved by the existing
implementation; this document records the decisions as-built so they can be
revisited deliberately rather than re-derived implicitly by future features.

## Data source for failure records

- **Decision**: Pluggable `DataSourceStrategy` with two providers — Amazon
  Athena (Presto SQL via boto3) for production, and a local JSON file
  (`LOCAL_DATA_FILE=./sample_failures.json`) for local development.
- **Rationale**: Athena is the production source of truth for pipeline failure
  events; the local-file provider lets the full UI/analysis flow be exercised
  without AWS credentials.
- **Alternatives considered**: Direct Postgres query against a replicated
  failures table — deferred; `providers/data_source/` already anticipates a
  `postgres` option (`DataSourceProvider` literal includes `"postgres"`) but no
  concrete provider exists yet, so it remains a future extension point, not a
  gap in this baseline.

## AI / LLM provider

- **Decision**: Navify Enrichment API (OpenAI-compatible chat completions),
  defaulting to `us.anthropic.claude-sonnet-4-5-20250929-v1:0`.
- **Rationale**: OpenAI-compatible interface lets `LLMStrategy` stay provider
  agnostic; Claude Sonnet balances reasoning quality and latency for the
  5-step pipeline (summarize, generate log queries, group/RCA, executive
  summary).
- **Alternatives considered**: Direct `bedrock:InvokeModel` — rejected to avoid
  requiring AWS Bedrock IAM permissions when only log/data-source AWS access is
  needed; Gemini/GPT models remain selectable via the same OpenAI-compatible
  interface without code changes.

## Log analysis backend

- **Decision**: Pluggable `LogAnalysisStrategy` with two providers — CloudWatch
  Logs Insights and Grafana Loki (LogQL), selected via `LOG_ANALYSIS_PROVIDER`
  or per-request `log_backend` override.
- **Rationale**: Different deployments use different observability stacks;
  both providers generate queries from the same LLM-produced query plan and
  produce a deep-link URL plus sample log lines.
- **Alternatives considered**: Elastic/OpenSearch — not implemented; would be
  added as a third `LogAnalysisStrategy` provider without orchestrator changes
  if needed.

## Persistence / CRM model

- **Decision**: PostgreSQL 16 via SQLAlchemy 2.0 + Alembic. Failure records are
  upserted (deduped by `file_trace_id`); failure groups are hashed into a
  root-cause signature (`component_name` + `error_code` + `stage`) that links
  to `rca_cases`, creating a new case or flagging an existing one as recurring.
- **Rationale**: Gives every analysis run a persistent, queryable history
  without manual triage, satisfying FR-012–FR-014.
- **Alternatives considered**: In-memory/session-only results (no persistence)
  — rejected, since recurring-issue detection (User Story 3) requires history
  across sessions.

## Related code changes (GitHub MCP)

- **Decision**: `backend/agents/code_analysis_agent.py` calls the official
  `github-mcp-server` over stdio (`backend/mcp/client.py`) to list commits/PRs
  for `GITHUB_REPO` within the failure time window.
- **Rationale**: Surfacing recent code changes next to a root cause helps
  engineers spot likely-causal deploys without leaving the RCA report.
- **Alternatives considered**: Direct GitHub REST API calls — rejected in
  favor of MCP to reuse the standard `github-mcp-server` tool surface and avoid
  maintaining a bespoke GitHub client.

## Frontend approach

- **Decision**: Vanilla HTML/CSS/JS single-page app (`frontend/`), no framework.
- **Rationale**: Matches project scale (two-step workflow, single results view)
  and constitution constraint to avoid unnecessary framework overhead.
- **Alternatives considered**: React/Vue SPA — rejected as premature for the
  current scope; can be revisited if UI complexity grows materially.
