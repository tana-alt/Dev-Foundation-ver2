---
plan_id: Plan_N0001
project_id: contract-lightening-20260610
status: active
log_ref: Plan/contract-lightening-20260610/logs/Plan_N0001.log.md
---

# Contract Lightening Plan

## Goal

Archive the heavy contract workflow before deletion, then keep the useful
engineering thinking in a goal-first, lightweight form.

## Why

The current contract-heavy workflow encouraged records-only completion,
excessive handoff artifacts, lane/worktree expansion, and repeated human-gate
deferral. Some ideas remain useful, especially spec writing, lightweight
source-scope control, and subagent coordination. The next version should keep
only the parts that help produce working software.

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- Plan/README.md
- .agents/skills/scope-routing-governance/SKILL.md
- .agents/skills/skill-authoring-governance/SKILL.md
- .agents/skills/subagent-workflow-governance/SKILL.md
- .agents/skills/spec-authority-governance/SKILL.md
- .agents/skills/merge-integrity-governance/SKILL.md
- .agents/skills/hook-validation-governance/SKILL.md
- scripts/agent_operational_checks.py
- hooks/pre-push
- Makefile
- templates/README.md

## Allowed Write Targets

- Plan/contract-lightening-20260610/
- archive/heavy-contracts-20260610/
- AGENTS.md
- docs/
- .agents/skills/
- templates/
- hooks/pre-push
- scripts/agent_operational_checks.py
- Makefile
- tests/

## Current Scope

- Snapshot heavy contract references, templates, governance skills, checkers,
  and related tests into archive.
- Rewrite active contracts around goal completion, narrow scope, and honest
  verification.
- Retire record-heavy traceability, residual-risk carryover, and convergence
  routes from default workflow.
- Keep legacy heavy-contract checks and templates available only by explicit
  opt-in.
- Do not create new worktrees.

## Working Decisions

- Keep lightweight `Plan/<project>/plan.md` and `log.md` as the normal project
  memory model.
- Keep spec guidance only when it defines observable WHAT and explicit Done
  criteria.
- Keep subagent workflow guidance only as a small routing checklist, not a
  record factory.
- Keep human gates only for real protected side effects.
- Archive traceability, convergence, final handoff, operational scorecard,
  source snapshot, and residual-risk carryover machinery as heavy-contract
  candidates.
- Rework or remove templates and skills that exist mainly to support
  records-only completion.
- Default checks should prove implementation readiness, not heavy-contract
  record completeness.
- Legacy contract checks remain available through `make check-legacy-contracts`.

## Done For This Pass

- Archive snapshot exists.
- Active docs describe goal-first completion and lightweight records.
- Active templates expose goal brief, mini-spec, task packet, and verification
  note as defaults.
- Heavy traceability/residual-risk/convergence skills are retired stubs.
- `pre-push` no longer forces residual-risk or convergence checks by default.
- `check-fast` and `check-push` pass.
