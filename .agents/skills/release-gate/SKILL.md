---
name: release-gate
description: Use when a quant execution package or app build is about to move into release, deployment, or live operation and needs a final gate review.
---

Perform the final pre-release gate.

Read path:
- start from `Project-App/AGENTS.md` and the app runtime packets
- read `Apps/<app-slug>/artifacts/runtime/current-state.yaml` first
- read `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml` second
- only expand to `10-log.md`, `11-agent-map.md`, or `12-agent-evals.md` when the runtime packets flag gate drift or blocker persistence

Check:
- acceptance criteria complete
- known blockers closed
- monitoring hooks present
- rollback plan present
- limitations documented
- ownership after release is clear

Required output:
- verdict: go | no-go
- residual_risks
- rollback_readiness
- monitoring_readiness
- required_follow_up

Do not:
- assume observability exists
- issue go without a rollback path
