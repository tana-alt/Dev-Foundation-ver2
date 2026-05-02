---
name: review-to-actions
description: Use when review findings, QA feedback, or risk findings need to be converted into prioritized action items.
---

Turn review output into executable action items.

Read path:
- start from `Project-App/AGENTS.md` and the app runtime packets
- read `Apps/<app-slug>/artifacts/runtime/current-state.yaml` first
- read `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml` second
- only read older coordination surfaces when the runtime packets flag blocker persistence, contract drift, or gate drift

Required output per item:
- title
- severity
- owner_agent
- objective
- verification
- dependency
- whether it blocks release or progression

Rules:
- separate blockers from non-blockers
- merge duplicates
- preserve the original finding id if present
- propose the smallest defensible fix first
- prefer diff-first actions that target the changed surfaces listed in `latest-delta.yaml`
- if a blocker cannot be resolved from the changed surfaces, expand scope one surface at a time and say which surface forced the expansion

Do not:
- hide blocker status
- collapse unrelated issues into one giant task
