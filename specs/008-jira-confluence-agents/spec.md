# Feature Specification: Jira & Confluence Agents (Upcoming)

**Feature Branch**: `008-jira-confluence-agents`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §3, Phase 2

## Summary

Add Jira and Confluence MCP servers and the agents that use them. The Jira Agent searches
for similar past incidents/defects and drafts a new ticket payload; the Confluence Agent
finds runbooks and architecture docs for the failing component and returns
troubleshooting links.

## In scope (when specified)

- Jira MCP server config + Jira Agent (search issues, draft ticket).
- Confluence MCP server config + Confluence Agent (search runbooks/docs).
- Project-key / space-key mapping for the configured component.

## Dependencies

- Depends on `006-mcp-gateway` and `007-agentic-investigation`.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
