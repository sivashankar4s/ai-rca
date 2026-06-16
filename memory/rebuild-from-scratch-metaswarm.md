---
name: rebuild-from-scratch-metaswarm
description: Why backend/ and frontend/ are deleted in the working tree, and how the app is being rebuilt
metadata:
  type: project
---

On branch `feature/metaswarm` (as of 2026-06-16), the entire `backend/` and
`frontend/` app is **intentionally deleted** in the working tree (still present in
HEAD / commit 25d1307). The user is **rebuilding the app from scratch** using the
metaswarm spec-driven, TDD development workflow, feature by feature, starting with
`specs/001-ai-rca-tool`.

**Why:** They want the codebase (re)built through the metaswarm orchestration technique
(IMPLEMENT → VALIDATE → ADVERSARIAL REVIEW → COMMIT, TDD, coverage gates) rather than
keeping the previously hand-written implementation.

**How to apply:** Do NOT `git restore`/recreate the deleted backend/frontend from HEAD.
Treat the existing `specs/00X` Spec Kits as the source of truth and implement each
feature from scratch via the metaswarm workflow. The old HEAD code can be a reference
only. See [[spec-scope-preference]].
