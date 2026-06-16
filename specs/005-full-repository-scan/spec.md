# Feature Specification: Full Repository Scan (Upcoming)

**Feature Branch**: `005-full-repository-scan`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: README "Roadmap / Planned Enhancements" (item 3)

## Summary

A "Scan Repository" mode that walks the entire configured repository — not just a single
pull-request or branch diff — and runs the full AI Code Review checklist (security, SQL
injection, SonarQube-style code quality, formatting, and feature recommendations) across
the codebase, producing a repo-wide report.

## In scope (when specified)

- A repo-wide scan action distinct from the existing per-PR / per-branch review.
- Reuses the existing AI Code Review checklist and finding model.
- A consolidated, navigable report grouping findings by file/severity/category.

## Dependencies

- Builds on the existing AI Code Review feature and GitHub MCP integration
  (`code_review_service`, `mcp/client.py`).
- Naturally pairs with `003-inline-pr-comments` for posting results.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand this into a full
Spec Kit (spec, plan, research, data-model, contracts, quickstart, tasks, checklist), as
done for `004-provider-selection`.

> 🔜 Coming soon.
