# Feature Specification: Multi-Project Configuration & RBAC (Upcoming)

**Feature Branch**: `012-multi-project-config`

**Created**: 2026-06-16

**Status**: 🔜 Upcoming — placeholder, not yet specified

**Roadmap**: ENGINEERING_OPS_COPILOT_VISION.md §8 (Phase 3); Constitution Principle V

## Summary

Per-project / per-tenant provider configuration loaded into a `ProjectContext` (rather
than a single global `.env`), with role-based access control on the configuration drawer
so only authorized users can change provider settings.

## In scope (when specified)

- Per-project provider selection stored in the `projects` table, with global `.env` as
  defaults/fallbacks only.
- `ProjectContext` loaded per request; provider selection resolved per project.
- RBAC on the config drawer.

## Dependencies

- Extends `004-provider-selection` from global to per-project.
- Aligns with CRM_PLAN.md Phase 2+ project model.

## Next step

Roadmap placeholder. When work begins, run `/speckit-specify` to expand into a full Spec
Kit, as done for `004-provider-selection`.

> 🔜 Coming soon.
