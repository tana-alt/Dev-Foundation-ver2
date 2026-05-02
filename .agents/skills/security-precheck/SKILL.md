---
name: security-precheck
summary: >
  Run a planner-facing security precheck before implementation starts and emit
  an explicit allowed, warned, blocked, or policy-missing decision tied to
  current stack and release assumptions.
version: 0.1
status: draft
data_model_version: 0.1
description: >
  Use when planner or engineering needs an early security gate before code is
  written, especially for auth, secrets, external integrations, data
  sensitivity, uploads, or deployment choices. This skill prepares a
  planner-facing precheck report and return path; it does not replace the final
  `security-review` deployment gate.
---

# Skill: security-precheck

## Purpose
Produce a planner-facing `SecurityPrecheckReport` that checks the current
`StackDecisionSpec`, release assumptions, and high-risk architecture choices
before implementation starts.

## Non-goals
- Final release approval or deploy-time signoff.
- Full codebase scanning or a substitute for `security-review`.
- Inventing blocked / warned / allowed thresholds when the human policy line is
  still unset.
- Rewriting planner scope or stack decisions without a documented return.

## Inputs

### Required
- `Apps/<app-slug>/artifacts/runtime/current-state.yaml`
- `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml`
- `03-plan.md#StackDecisionSpec`
- `03-plan.md#ContextSpecPackage`
- `03-plan.md#Release Requirements Manifest`

### Optional
- `08-release.md#Security Skill Invocation Packet`
- `08-release.md#Compliance Review Gate`
- `06-backend.md` when an earlier backend note already exists
- explicit human policy pack for `blocked`, `warned`, and `allowed` thresholds
- stack-specific evidence refs from `02-research.md`

## Outputs

### Primary
- Format: `markdown`
- Type: `SecurityPrecheckReport`
- Required fields:
  - `decision`
  - `policy_state`
  - `findings`
  - `required_follow_up_actions`
  - `planner_return_target`
  - `evidence_refs`
  - `target_note_ids`

### Secondary
- Short note update for `03-plan.md`
- Progress note in `10-log.md`

## Procedure
1. Read the runtime packets first and stay on the changed surfaces they point
   to.
2. Inspect `StackDecisionSpec`, `ContextSpecPackage`, and the release
   assumptions that could create early security debt.
3. Separate three classes of output:
   - observed architecture/security facts
   - supported risk inferences
   - missing policy that must stay human-owned
4. Emit one explicit decision:
   - `allowed`
   - `warned`
   - `blocked`
   - `policy_missing`
5. If the result is not `allowed`, name the planner return target and the
   smallest missing or unsafe surface to repair first.
6. Write the report into the planner-owned surface, then record the handoff or
   return in `10-log.md`.

## Completion Criteria
- `decision` is explicit and not implied.
- `policy_state` says whether the result came from a real policy line or from a
  missing-policy fallback.
- Every finding links back to `03-plan.md`, `08-release.md`, or research
  evidence.
- The next owner or return target is named.
- The report never silently downgrades `policy_missing` into `allowed`.

## Failure Modes
- **Final security review confused with precheck**
  - Cause: the skill is treated as deploy-ready signoff.
  - Countermeasure: always point final release signoff back to `security-review`
    and `08-release.md`.
- **Blocked or warned lines are invented**
  - Cause: the skill guesses thresholds that human policy has not fixed.
  - Countermeasure: emit `policy_missing` and escalate instead of guessing.
- **Findings float without planner anchors**
  - Cause: risks are described generically, not tied to the chosen stack or
    release assumptions.
  - Countermeasure: require `evidence_refs` to `StackDecisionSpec`,
    `ContextSpecPackage`, or release assumptions.
- **Planner return path is vague**
  - Cause: a risk is raised but the smallest repair target is not named.
  - Countermeasure: always name the first surface to fix and the next owner.

## References
- `docs/specs/app-agentic-flow.md`
- `docs/specs/app-planner-agent-contracts.md`
- `docs/tasks/active/WORKFLOW-gap-consult-loop/skill-contract-minimums-report-2026-04-23.md`
- `security-review/SKILL.md`
