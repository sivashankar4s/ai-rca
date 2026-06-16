# Feature Specification: Copilot Chat / Case Q&A (Upcoming)

**Feature Branch**: `010-copilot-chat`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §2, Phase 2

## Summary

A `/api/copilot/chat` endpoint for follow-up Q&A on a case: a conversational drill-down
where an engineer can ask questions about an investigation's findings and timeline and
get grounded answers, reusing the case context and agent tools.

## In scope (when specified)

- Conversational endpoint scoped to a single case's context.
- Grounded answers over the investigation findings / timeline.
- Reuses the agent tool layer for live follow-up lookups.

## Dependencies

- Depends on `007-agentic-investigation` (case context + agent layer).

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
