# AI-RCA → Engineering Operations Copilot

**Architecture & Roadmap — Principal Architect / AI Platform Lead review**

This document redesigns AI-RCA from a two-step "fetch → analyze" RCA tool into an
**Engineering Operations Copilot**: an agentic system that, given a failure, can explain
*what* broke, *why*, *what code/PR likely caused it*, *who*/what is impacted, *what was
done before*, and *what to do next* — pulling from Athena/Redshift, CloudWatch/Grafana,
GitHub, Jira, and Confluence via MCP.

---

## 1. Where we are today

```
Browser (2-step SPA)
  │  POST /api/failures   → DataSourceStrategy   (Athena | local file)
  │  POST /api/analyze    → LLMStrategy          (Navify/OpenAI-compatible)
  │                          LogAnalysisStrategy  (CloudWatch | Grafana Loki)
  │                          persistence_service  → Postgres (CRM tables)
  ▼
FastAPI backend, Strategy Pattern (plugin_registry.py), .env-selected providers
```

Strengths to build on:
- **Strategy Pattern already in place** (`DataSourceStrategy`, `LLMStrategy`,
  `LogAnalysisStrategy` + `plugin_registry.py`) — this is exactly the shape an
  MCP-tool abstraction needs.
- **CRM persistence** (`failure_records`, `rca_cases`, `root_cause_signatures`) is a
  ready-made "memory" for an agent — recurring-issue detection is half of "similar
  incident detection."
- **4-step LLM pipeline** in `rca_orchestrator.py` is effectively a *hardcoded single
  agent* (summarize → plan queries → execute → group). It generalizes naturally into a
  planner + specialist sub-agents.

Gaps for the target vision:
- Everything is single-turn, single-agent, AWS-only, no code/ticket/doc context.
- Provider selection is fixed at process start via `.env` — not user-selectable per run.
- No agent loop / tool-calling — the LLM never decides *which* tool to call next.

---

## 2. Target Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser — Ops Copilot SPA                                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────────┐ ┌────────────────────┐ │
│  │ Step 1      │ │ Step 2      │ │ Investigation   │ │ Executive Dashboard│ │
│  │ Failures    │ │ RCA Results │ │ Chat / Timeline │ │ (impact, fixes,    │ │
│  │ + source    │ │ + agents'   │ │ (follow-up Qs,  │ │  PRs, tickets,     │ │
│  │   picker    │ │   findings  │ │  drill-down)    │ │  confidence)       │ │
│  └────────────┘ └────────────┘ └────────────────┘ └────────────────────┘ │
└──────────────────────────────┬─────────────────────────────────────────-─┘
                                 │ REST + SSE (streaming agent steps)
┌────────────────────────────────────────────────────────────────────────-─┐
│                       FastAPI Backend — Copilot API                       │
│                                                                            │
│  /api/failures, /api/analyze   (existing, unchanged contracts)            │
│  /api/copilot/investigate      (NEW — agentic, streams agent steps)       │
│  /api/copilot/chat             (NEW — follow-up Q&A on a case)            │
│                                                                            │
│  ┌──────────────────────────── Agent Layer ─────────────────────────────┐│
│  │                     Planner Agent (orchestrator)                      ││
│  │   decomposes "RCA this failure group" into sub-tasks, dispatches to:  ││
│  │                                                                        ││
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐ ││
│  │  │Investigation│ │Log Analysis│ │Code Analysis│ │ Jira / Confluence  │ ││
│  │  │   Agent     │ │   Agent    │ │   Agent     │ │     Agents         │ ││
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────────┬──────────┘ ││
│  │        │              │              │                  │            ││
│  │  ┌─────┴──────┐ ┌─────┴──────┐ ┌─────┴──────┐ ┌─────────┴──────────┐ ││
│  │  │  DB Intel   │ │  Exec Summary Agent (final synthesis)            │ ││
│  │  │  Agent      │ │  → RCA, impact, fix, confidence, links            │ ││
│  │  └────────────┘ └───────────────────────────────────────────────────┘││
│  └────────────────────────────────────────────────────────────────────--┘│
│                                                                            │
│  Existing Strategy layer becomes the "local tool" half of the MCP Gateway:│
│  DataSourceStrategy / LLMStrategy / LogAnalysisStrategy  (unchanged)      │
└───────────────────────────────┬───────────────────────────────────────--─┘
                                  │  MCP client (stdio / HTTP+SSE)
┌───────────────────────────────────────────────────────────────────────--─┐
│                              MCP Servers                                   │
│  ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ GitHub MCP  │ │ Jira MCP │ │Confluence  │ │CloudWatch│ │ Athena /     │ │
│  │ (repos,     │ │ (tickets,│ │MCP (docs,  │ │MCP (logs,│ │ Redshift MCP │ │
│  │ commits,PRs)│ │ search)  │ │ runbooks)  │ │ metrics) │ │ (SQL query)  │ │
│  └────────────┘ └──────────┘ └────────────┘ └──────────┘ └──────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent Design

All agents share one **case context** (failure group + signature + history from
Postgres) and write their findings back onto it. The Planner runs a bounded
tool-calling loop (LLM decides next tool call, max N iterations, falls back gracefully).

| Agent | Responsibility | Inputs | Tools (MCP/local) | Output |
|---|---|---|---|---|
| **Planner** | Decompose the case into sub-investigations, sequence/parallelize agents, stop when confidence threshold met | Failure group, CRM history | none directly — calls other agents as tools | Plan + final routing to Exec Summary |
| **Investigation Agent** | Correlate failure metadata: component, error code, stage, trace IDs, recurring signatures | Failure records, `root_cause_signatures` | local (Postgres CRM repo) | Known-pattern match, "seen before" flag |
| **Log Analysis Agent** | Generate + run log queries, extract error stack traces / anomalies | Time window, component | CloudWatch MCP / Grafana Loki MCP (existing `LogAnalysisStrategy`) | Relevant log excerpts, anomaly summary |
| **Code Analysis Agent** | Map component → repo, find recent commits/PRs touching relevant files, flag suspicious changes near failure time | component_name, error timestamp, affected_files | GitHub MCP | Likely commit/PR, diff summary, file list |
| **Jira Agent** | Search for similar past incidents/defects, suggest new ticket | error pattern, root cause draft | Jira MCP | Related ticket links, draft ticket payload |
| **Confluence Agent** | Find runbooks/architecture docs for the component | component_name, failure_category | Confluence MCP | Runbook links, troubleshooting steps |
| **DB Intelligence Agent** | Identify affected studies/customers/orgs from failure records, estimate blast radius | `organization`, `custom_key*`, Athena/Redshift | Athena MCP / Redshift MCP (existing `DataSourceStrategy`) | Affected entity list, impact size |
| **Executive Summary Agent** | Synthesize all sub-agent outputs into the final report | All agent outputs | none (pure LLM synthesis) | RCA, impact, fix, confidence score, links |

**Confidence score** = weighted combination of: signature match strength (exact vs.
fuzzy), whether a code change was found near the failure window, whether a prior
resolved case with the same signature exists, and LLM self-reported certainty.

---

## 4. MCP Architecture

### 4.1 Why MCP here specifically
The Strategy Pattern already isolates "how do I get failure data / logs / LLM calls"
behind ABCs. MCP is the same idea at the *tool* level, standardized, and lets the LLM
pick tools dynamically instead of the orchestrator hardcoding the sequence. Two of your
existing strategies (`DataSourceStrategy`, `LogAnalysisStrategy`) map almost 1:1 onto
"Athena/Redshift MCP" and "CloudWatch/Grafana MCP" — they can be wrapped as MCP
**servers** later without touching the orchestrator contract.

### 4.2 AI-RCA as an MCP **host** (consumes external MCP servers)
```
backend/
├── mcp/
│   ├── client.py            # MCP client manager — connects to configured servers
│   ├── registry.py          # maps logical tool names → MCP server + tool
│   └── servers.yaml          # which MCP servers are enabled + connection config
```
- `mcp/registry.py` exposes a flat tool list to the agent layer
  (`github.search_commits`, `jira.search_issues`, `confluence.search`,
  `cloudwatch.query_logs`, `athena.run_query`, ...).
- Each agent only sees the tools relevant to it (least-privilege).
- Local strategies (existing `AthenaDataSource`, `CloudWatchLogBackend`) remain the
  *default* implementations for `/api/failures` and `/api/analyze` (Step 1/2,
  unchanged contracts) — MCP is additive, for the new `/api/copilot/*` agentic
  endpoints.

### 4.3 AI-RCA as an MCP **server** (optional, later)
Expose AI-RCA's own capability ("given a component + time window, return RCA") as an
MCP tool so it can be called from other internal copilot/chat tools (e.g., a company
Slack bot). Low priority — only worth doing once the agent core is stable.

### 4.4 MCP servers to evaluate
| MCP Server | Source | Used by | Notes |
|---|---|---|---|
| GitHub MCP | `github/github-mcp-server` (official) | Code Analysis Agent | repo→component mapping needs a config table (component_name → repo) |
| Jira MCP | Atlassian official / community | Jira Agent | needs Jira project key mapping |
| Confluence MCP | Atlassian official / community | Confluence Agent | space key mapping |
| CloudWatch MCP | AWS Labs `cloudwatch-mcp-server` | Log Analysis Agent | can replace/augment `CloudWatchLogBackend` |
| Athena/Redshift MCP | AWS Labs `aws-athena-mcp` / custom Redshift MCP | DB Intelligence Agent | reuse existing IAM permissions |

---

## 5. Near-term UI/Backend change (your immediate ask) — Phase 1 scope

This is the concrete, buildable-now slice that also sets up the MCP work above.

**Backend:**
- Extend `FailuresRequest` with `data_source: Optional[Literal["athena","postgres"]]`
  and `AnalyzeRequest`/a new `/api/copilot/investigate` with
  `log_backend: Optional[Literal["cloudwatch","grafana_loki","mcp"]]`.
- `plugin_registry.get_data_source(override=None)` / `get_log_backend(override=None)` —
  request-level override falling back to `.env` default.
- New `PostgresDataSource` provider implementing `DataSourceStrategy` — queries
  `failure_records` directly (this becomes trivial now that Step 1 persists there,
  per the change just made).
- `GET /api/providers` — returns available data sources / log backends (+ "mcp" once
  configured) so the UI can populate dropdowns dynamically rather than hardcoding.

**Frontend (generic layout):**
- Header: drop the "Powered by Amazon Athena · CloudWatch · Claude AI" tagline (too
  AWS-specific) → "Powered by pluggable data, log & AI providers".
- Controls card: add a **Source** selector (Athena / Postgres) next to the time-range
  controls, and a **Log Backend** selector (CloudWatch / Grafana / MCP) shown in the
  Step 2 analyze panel — both default from `/api/providers`' reported defaults.
- Config drawer: keep AWS/Athena section, add collapsible "Postgres", "Grafana", and
  "MCP Servers" sections — only the relevant one expands based on the selectors above.

This is independent of the agent work and ships value immediately (you already have
the Postgres data populated from Phase 0).

---

## 6. Executive Dashboard

A new top-level view (per case), showing:

| Field | Source |
|---|---|
| Root Cause | Exec Summary Agent |
| Impact (failure count, time span) | `rca_cases.impact_count`, failure records |
| Affected studies/customers | DB Intelligence Agent (Athena/Redshift MCP) |
| Related code (files, commits) | Code Analysis Agent (GitHub MCP) |
| Related PRs | Code Analysis Agent |
| Related tickets | Jira Agent |
| Recommended fix | Exec Summary Agent (`likely_fix`, `immediate_action` — already in schema) |
| Confidence score | Planner (composite, §3) |
| Recurrence history | `root_cause_signatures.occurrence_count`, `case_activity` timeline |

Reuses existing `RcaCase`/`CaseActivity`/`RootCauseSignature` tables — add nullable
JSONB columns (`code_refs`, `ticket_refs`, `doc_refs`, `confidence_score`) via Alembic
migration when Phase 2 lands.

---

## 7. AWS Services Mapping

| Capability | AWS Service | Status |
|---|---|---|
| Failure data | Athena (Glue table) | ✅ existing |
| CRM persistence | RDS/Aurora Postgres | ✅ existing (local Docker for dev) |
| Log analysis | CloudWatch Logs Insights | ✅ existing |
| LLM inference | Navify Enrichment API (Bedrock-backed) | ✅ existing |
| DB Intelligence (Redshift) | Redshift Serverless / Redshift MCP | 🔲 Phase 3 |
| Code Analysis | GitHub (SaaS) via GitHub MCP — no AWS service needed | 🔲 Phase 2 |
| Jira/Confluence | Atlassian Cloud via MCP — no AWS service needed | 🔲 Phase 2 |
| Agent orchestration runtime | ECS Fargate / Lambda (existing FastAPI container, no new infra for MVP) | 🔲 Phase 2 |
| Auto-remediation PRs | GitHub MCP `create_pull_request` + CI | 🔲 Phase 4 |
| Predictive failure detection | SageMaker / Bedrock batch on `failure_records` history | 🔲 Phase 4 |

---

## 8. Implementation Phases

### Phase 0 — Done
- Strategy Pattern, CRM persistence, Step-1 failure persistence (just shipped).

### Phase 1 — Hackathon MVP (1–2 weeks)
- Provider-selection UI (§5): Athena/Postgres source picker, CloudWatch/Grafana log
  backend picker, generic header/branding.
- `PostgresDataSource` provider + `/api/providers` endpoint.
- Stub `mcp/` package with a **single** MCP server wired end-to-end (recommend
  **GitHub MCP** — highest demo value: "this PR likely caused it").
- Code Analysis Agent (single agent, not full multi-agent yet) added as an optional
  extra step after `/api/analyze`, surfaced as a new card in the RCA results.
- Demo narrative: fetch → analyze → "Likely caused by PR #123 (merged 2h before
  failures started)".

### Phase 2 — Multi-agent core (3–6 weeks)
- Planner Agent + tool-calling loop (bounded iterations, streaming via SSE).
- Investigation, Log Analysis, DB Intelligence agents wired to existing strategies.
- Jira + Confluence MCP servers, agents, Executive Dashboard v1.
- Alembic migration for `code_refs`/`ticket_refs`/`doc_refs`/`confidence_score`.

### Phase 3 — Enterprise hardening (6–12 weeks)
- Redshift MCP, multi-project/tenant config (per-project provider selection, not
  just global `.env`), RBAC on the config drawer, audit log of agent tool calls.
- Confidence scoring calibration, feedback loop (mark RCA correct/incorrect →
  improves signature matching).
- Observability: trace every agent run (OpenTelemetry), cost/token dashboards.

### Phase 4 — Self-healing (future)
- Auto-generated remediation PRs (GitHub MCP `create_pull_request`, draft + human
  approval gate — never auto-merge).
- Predictive failure detection from `failure_records` trend analysis.
- Self-healing workflows: known-signature + known-fix → propose automated runbook
  execution (still human-approved for production safety).

---

## 9. Open Questions Before Phase 1 Starts

1. **Component → repo mapping**: is there an existing config (CMDB, Backstage,
   internal wiki) mapping `component_name` to GitHub repos, or do we need a small
   YAML/DB table for this?
2. **MCP server hosting**: do these run as local subprocesses (stdio) alongside the
   FastAPI app, or as separate services reached over HTTP+SSE? Affects deployment.
3. **Per-project vs. global config**: Phase 1's provider pickers are global (one
   `Project` row exists today, `get_or_create_default_project`). Multi-project
   selection is a Phase 3 item — confirm that's acceptable for now.
4. **Which MCP server first?** Recommendation above is GitHub (demo impact), but Jira
   may be more valuable if your team's workflow is ticket-centric.
