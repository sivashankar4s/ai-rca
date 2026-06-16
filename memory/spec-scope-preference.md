---
name: spec-scope-preference
description: How the user wants roadmap features turned into specs/ folders
metadata:
  type: feedback
---

When asked to "create all requirements under specs/", the user wants only the concrete,
near-term feature(s) written as a full Spec Kit (8 files: spec/plan/research/data-model/
contracts/quickstart/tasks/checklist, matching specs/001–003). All later/speculative
roadmap features should be left as lightweight **"upcoming soon"** placeholder stubs
(a short spec.md with Status: Upcoming + summary + link to the vision doc), NOT full
spec kits.

**Why:** Speculative phases (vision doc Phase 3–4) have open architectural questions;
full specs for them would invent implementation detail that doesn't exist yet — against
the project constitution's YAGNI principle ([[[constitution Principle II]]]).

**How to apply:** Build the full kit only for what's being worked on now; stub the rest
with a "coming soon" marker and a pointer to ENGINEERING_OPS_COPILOT_VISION.md. Expand a
stub into a full spec via /speckit-specify when that feature actually starts.
