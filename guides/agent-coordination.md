# Agent Coordination

## Overview

metaswarm uses two coordination modes depending on available tools:

- **Team Mode** — When `TeamCreate` and `SendMessage` tools are available. Agents run in parallel, dispatch is explicit, and results are aggregated before presenting to the user.
- **Task Mode** — Fallback when Team Mode tools are absent. Agents run sequentially via `TaskCreate`/`TaskUpdate`.

## Agent Roster

| Agent | Role |
|---|---|
| `architect-agent` | System design, API contracts, database schema |
| `coder-agent` | Implementation, TDD, feature code |
| `test-automator-agent` | Test strategy, coverage, edge cases |
| `code-review-agent` | Correctness, security, style review |
| `security-auditor-agent` | Threat modeling, vulnerability analysis |
| `security-design-agent` | Secure design patterns |
| `product-manager-agent` | Acceptance criteria, user stories |
| `designer-agent` | UI/UX, frontend component design |
| `sre-agent` | Observability, deployment, reliability |
| `researcher-agent` | Investigation, unknowns, spike research |
| `metrics-agent` | Performance analysis, KPIs |
| `cto-agent` | Final architectural sign-off |

## Quality Gates

### Design Review Gate (5 agents in parallel)
Triggered by `/review-design` after brainstorming. Dispatches: PM, Architect, Designer, Security Design, CTO. ALL must approve before implementation begins.

### Plan Review Gate (3 agents in parallel)
Automatic after any plan is drafted. Dispatches: Feasibility Reviewer, Completeness Reviewer, Scope & Alignment Reviewer. ALL must PASS.

### Coverage Gate
Runs before every PR creation. Reads `.coverage-thresholds.json` (currently 90%). Blocks PR if any threshold is not met.

## Handoff Protocol

When an agent finishes, it writes its output to `.beads/context/execution-state.md` so the next agent picks up from a known state rather than re-deriving context. After compaction: `bd prime --work-type recovery`.
