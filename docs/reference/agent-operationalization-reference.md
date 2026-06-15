---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-06-08
---

# Agent Operationalization Reference

Use this reference when implementing or reviewing the operationalization phase
pack: skill routing, context-scope manifests, residual-risk carryover,
review/fix/convergence records, and local deterministic check wiring.

## Trigger

Open this reference when:

- a task names the Codex operationalization integrated specification pack;
- scope routing, selected skills, denied context, or context expansion must be
  recorded;
- residual risk must carry pending human gates, deferred work, or unverified
  surfaces into next-flow refs;
- review, fix handoff, fix review, convergence, traceability, or final handoff
  records are created or checked;
- Make targets or local hooks are changed for existing operational check scripts.

Do not open this reference for ordinary implementation with a complete work
contract, small named-file edits, current command selection, or concrete Git
mechanics.

Adjacent references:

- Use `packet-evidence-and-rework-reference.md` for generic record fields.
- Use `specification-workflow-reference.md` for approved spec and subagent flow.
- Use `verification-ci-and-pr-reference.md` for current commands and gates.
- Use `agent-operationalization-95-hardening-reference.md` for 9.5 status,
  audit, source snapshot, and scorecard rules.

Expected effect after opening:

- Select at most two operational skills.
- Keep source refs narrow and record expansion reasons.
- Preserve active docs as routing and invariants only.
- Add or validate reusable templates, completed artifact records, and local
  deterministic checks without runtime coordination state.

## Source Pack Mapping

The source pack is implemented into supported roots:

```text
AGENTS.md
.agents/skills/
docs/reference/
templates/
scripts/
tests/
artifact/<project_id>/
Plan/<project_id>/
```

Do not track uploaded source packs as new root-level durable storage. Distill
their useful rules into active routes, references, skills, templates, scripts,
tests, or project-scoped artifacts.

## Operational Phases

| Phase | Purpose | Primary outputs |
|---|---|---|
| 5 | Docs-to-skills decomposition | operational skills, skill index, route coverage |
| 6 | Scope routing and context budget | `context-scope-manifest`, checker, Make target |
| 8 | Residual-risk carryover | residual-risk and final-handoff carryover records |
| R | Review/fix/convergence | review, fix, traceability, convergence, handoff records |
| 7 | Hook-backed stable operation | Make targets and hooks for scripts that exist |
| 9 | Operational example | compact canonical records and fixtures |

Phase work must not create a PR, push, merge, deploy, release, perform external
writes, mutate CI/GitHub Actions without approval, or add scheduler, queue,
lock, heartbeat, polling, dashboard, claim-state, or broad log behavior.

## Skill Routes

Use `.agents/skills/scope-routing-governance/SKILL.md` for context budgets,
named refs, denied context, allowed write targets, and expansion reasons.

Use `.agents/skills/spec-authority-governance/SKILL.md` for spec WHAT/HOW
separation.

Use `.agents/skills/traceability-gate-governance/SKILL.md` for REQ, AC, NFR,
EXC, SEC, DATA, API coverage and final handoff evidence.

Use `.agents/skills/merge-integrity-governance/SKILL.md` for lane, branch,
changed-path, sibling, and semantic-risk boundaries.

Use `.agents/skills/residual-risk-carryover/SKILL.md` for pending human gates,
deferred implementation, unverified surfaces, and next-flow seeds.

Use `.agents/skills/hook-validation-governance/SKILL.md` for deterministic
scripts, Make targets, hook wiring, and false-positive risk.

Use `.agents/skills/review-fix-convergence-governance/SKILL.md` for
narrow/wide/security review, fix handoff, fix review, convergence decision, and
final handoff.

The default budget is the context budget block in
`.agents/skills/scope-routing-governance/SKILL.md` (single source of truth;
do not restate it here).

## Context-Scope Manifest

Use `templates/context-scope-manifest.yaml` to record selected skill refs,
source refs opened, allowed write targets, denied context, context expansion
reasons, unopened optional refs, source snapshots, and next action.

Completed records belong at:

```text
artifact/<project_id>/evidence/context-scope-<work_id>.yaml
```

Denied context must include `secrets`, `runtime_state`, and `broad_repo_scan`.
Broad refs such as `.`, repo root, all docs, all tests, `docs/reference/`,
`archive/`, `runtime/`, and `source-docs/` require an explicit narrow
expansion reason and a policy ref. A missing optional record may be
`not_applicable`, but required context missing is not a pass.

## Residual Risk Carryover

Do not use terminal `blocked` only because human approval is pending, final
human review is pending, an implementation surface is deferred, or an external
environment was not approved. Use residual-risk records and next-flow seeds.

Use `INC-*` for concrete convergence defects:

```text
spec_vs_implementation
implementation_vs_tests
lane_conflict
missing_requirement
verification_gap
human_decision_required
```

Use `RISK-*` for carried residual risk:

```text
human_gate_pending
deferred_implementation
external_environment_unverified
accepted_partial_coverage
future_decision_required
semantic_conflict_unverified
```

Every risk item needs severity, type, summary, source refs, next-flow seed, and
affected requirement IDs when requirement-related. High or critical items need
an owner lane or human decision path.

## Review, Fix, And Convergence

Use separate records for narrow, wide, security, and fix review. Do not collapse
review output into verification output. Convert accepted review findings into a
fix handoff before implementation.

Traceability must cover these ID families when present:

```text
REQ-* AC-* NFR-* EXC-* SEC-* DATA-* API-* TEST-* FIX-* INC-* RISK-*
```

Convergence and final handoff must cite the traceability matrix, review refs,
verification refs, residual-risk refs, human gate status, and recommended next
action. Final handoff must not claim complete with unresolved critical/high
`INC-*`, unresolved `FIX-*`, required verification missing without risk
carryover, or a required human gate with no decision path.

## Hook And Make Target Rules

Operational checks are deterministic, offline, and record-shape focused. Add a
Make target only after its script exists. Hooks may call only existing local
scripts and must not require PR/lane context for ordinary local work.

Current operational targets:

```text
check-skill-routes
check-context-scope
check-result-envelope
check-residual-risk-carryover
check-review-convergence
check-audit-provenance
check-operational-scorecard
check-agent-operational
```

Do not add operational checks to the full foundation gate until false-positive
risk is reviewed. CI/GitHub Actions changes require explicit human approval.
