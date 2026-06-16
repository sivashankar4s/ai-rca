# Feature Specification: AI-RCA as an MCP Server (Upcoming)

**Feature Branch**: `018-ai-rca-mcp-server`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §4.3 (Phase 4, low priority)

## Summary

Expose AI-RCA's own capability — "given a component + time window, return an RCA" — as an
MCP **server** so other internal tools (for example a company Slack bot or another
copilot) can call it as a standard MCP tool.

## In scope (when specified)

- An MCP server surface wrapping the RCA capability.
- A stable tool contract (component + time window → RCA result).
- Auth / access control for external callers.

## Dependencies

- Worth doing only once the agent core (`007-agentic-investigation`) is stable;
  complements `006-mcp-gateway` (host) by making AI-RCA also a server.

## Next step

Roadmap placeholder; forward-looking, low-priority item. When work begins, run
`/speckit-specify` to expand into a full Spec Kit.

> 🔜 Coming soon.
