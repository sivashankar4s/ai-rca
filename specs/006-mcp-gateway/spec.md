# Feature Specification: MCP Gateway / Multi-Server Host (Upcoming)

**Feature Branch**: `006-mcp-gateway`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §4 (MCP Architecture), Phase 2

## Summary

Turn AI-RCA into an MCP **host** that consumes multiple external MCP servers behind a
single gateway: an MCP client manager, a registry mapping logical tool names to a server
+ tool (`github.search_commits`, `jira.search_issues`, `cloudwatch.query_logs`, …), and a
`servers.yaml` declaring which servers are enabled and how to connect. The gateway
exposes a flat, least-privilege tool list to the agent layer so each agent sees only the
tools relevant to it.

## In scope (when specified)

- `mcp/client.py` connection manager for multiple configured servers (stdio / HTTP+SSE).
- `mcp/registry.py` logical-tool-name → server+tool mapping.
- `mcp/servers.yaml` enabled-servers + connection config.
- Per-agent tool scoping (least privilege).

## Dependencies

- Extends the existing single-server GitHub MCP client (`backend/mcp/client.py`).
- Foundational for `007-agentic-investigation`, `008-jira-confluence-agents`,
  `011-redshift-db-intelligence`.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
