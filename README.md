---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Foundation

This directory distills the reusable development foundation from this repo
without preserving the parent-agent / subagent orchestration model.

The foundation treats people, LLM sessions, tools, and automations as workers on
the same project surface. It focuses on clear context boundaries, work
contracts, evidence-carrying outputs, project-local source of truth, small
rework loops, and verification as a first-class output.

## Principles

- Keep context small and explicit.
- Start from observed source refs, not inference.
- Define work by input and output contracts.
- Let artifact dependencies shape workflow order.
- Keep decisions, evidence, changes, verification, blockers, and next action
  visible.
- Store project truth in project-local files.
- Use rework records for missing context, failed validation, and unsafe
  assumptions.

## Documents

- `01-principles.md`: foundation values and operating posture.
- `02-context-boundary.md`: how to scope context without role hierarchy.
- `03-work-contract.md`: work unit input and output contract model.
- `04-evidence-and-verification.md`: evidence, verification, and residual risk.
- `05-project-source-of-truth.md`: project-local storage and overlay rules.
- `06-rework-loop.md`: small rework loop for missing or invalid work.

## Templates

- `templates/work-contract.yaml`
- `templates/evidence-record.yaml`
- `templates/verification-record.yaml`
- `templates/rework-record.yaml`
- `templates/project-storage-map.yaml`

## Source Notes

This foundation is distilled from the existing repo materials, especially:

- `ARCHITECTURE.md`
- `artifacts/runtime/context-scope.yaml`
- `artifacts/runtime/agent-io-contract-map.yaml`
- `artifacts/packets/handoff-packet.yaml`
- `artifacts/packets/evidence-packet.yaml`
- `artifacts/packets/rework-packet.yaml`
- `artifacts/project-orchestration/project-boundary-policy.yaml`

Those files are treated as source material, not as runtime requirements for this
foundation.
