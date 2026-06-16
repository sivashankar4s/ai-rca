# Feature Specification: Executive Dashboard (Upcoming)

**Feature Branch**: `009-executive-dashboard`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §6, Phase 2

## Summary

A per-case Executive Dashboard view surfacing root cause, impact (failure count / time
span), affected studies/customers, related code (files, commits, PRs), related tickets,
recommended fix, confidence score, and recurrence history — synthesized from the agent
outputs and existing CRM tables.

## In scope (when specified)

- Per-case dashboard view assembling agent + CRM data.
- Alembic migration adding nullable JSONB columns `code_refs`, `ticket_refs`, `doc_refs`,
  and `confidence_score` to the relevant CRM tables.
- Reuses existing `RcaCase` / `CaseActivity` / `RootCauseSignature` tables.

## Dependencies

- Depends on `007-agentic-investigation` (produces the synthesized findings) and,
  for ticket/doc refs, `008-jira-confluence-agents`.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
