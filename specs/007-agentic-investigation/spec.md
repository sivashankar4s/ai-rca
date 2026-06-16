# Feature Specification: Agentic Investigation (Planner + Sub-Agents) (Upcoming)

**Feature Branch**: `007-agentic-investigation`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §2–§3, Phase 2 (multi-agent core)

## Summary

A new agentic `/api/copilot/investigate` endpoint backed by a Planner Agent that runs a
bounded tool-calling loop, decomposing "RCA this failure group" into sub-investigations
and dispatching specialist agents (Investigation, Log Analysis, Code Analysis, DB
Intelligence) plus an Executive Summary agent for final synthesis. Agent steps stream to
the UI via SSE; the result includes RCA, impact, recommended fix, and a composite
confidence score.

## In scope (when specified)

- Planner Agent + bounded tool-calling loop with graceful fallback.
- Specialist agents sharing one case context, writing findings back onto it.
- SSE streaming of agent steps; composite confidence scoring.

## Dependencies

- Depends on `006-mcp-gateway` for multi-tool access.
- Generalizes the existing hardcoded 4-step `rca_orchestrator` pipeline.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
