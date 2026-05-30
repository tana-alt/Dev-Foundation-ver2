---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Packet, Evidence, And Rework Reference

Use this reference when creating or reviewing structured work contracts,
packets, evidence records, verification records, and rework records. Keep
records small and use refs instead of raw bodies or logs.

## Trigger

Open this reference when:

- a task asks for work-contract, packet, evidence-record, verification-record,
  or rework-record fields or templates;
- evidence must separate facts, inferences, decisions, stale or missing refs,
  residual risk, and next action;
- a verification or rework result needs record shape, allowed result states, or
  evidence refs rather than current command selection.

Do not open this reference when:

- the task is a small named-file edit with no packet, record, evidence,
  verification-record, or rework output;
- the only need is current verification commands, CI/PR readiness, repo
  placement, storage boundaries, runtime scope, handoff compatibility, retry
  behavior, branch/worktree setup, or migration acceptance.

Adjacent references:

- Use `verification-ci-and-pr-reference.md` for current commands, fast/full gate
  choice, CI/PR readiness, and PR or handoff evidence.
- Use `repo-boundary-and-storage-reference.md` for storage placement, repo
  truth surfaces, ignored local state, and durable artifact paths.
- Use `agent-runtime-and-scope-reference.md` for runtime-supplied scope,
  handoff compatibility, retry/idempotency, and conceptual parallel lanes.
- Use `git-worktree-and-branch-reference.md` for concrete branch/worktree
  setup, changed-path evidence, conflict checks, and PR preparation.

Expected effect after opening:

- Use the right record fields, leave unsupplied identity fields empty or
  deleted, cite refs instead of raw bodies or logs, separate facts from
  inferences and decisions, use allowed verification result states, and return
  rework when context, permission, evidence, verification, or repo-truth
  alignment is missing.

## Work Contract Fields

A work contract defines one bounded unit of work for a human, LLM session,
script, automation, review lane, or release lane.

Core fields:

- `task_intent`
- `success_criteria`
- `source_refs`
- `optional_refs`
- `expected_outputs`
- `allowed_write_targets`
- `design_gate`
- `denied_context`
- `evidence_required`
- `verification_required`
- `git_scope`
- `lane_map_ref`
- `artifact_refs`
- `changed_paths`
- `decision_refs`
- `verification_results`
- `residual_risk`
- `blockers`
- `open_questions`
- `next_action`

Identity fields such as `work_id`, `run_id`, `project_id`, `correlation_id`,
and `idempotency_key` are required when concurrency, retry safety, handoff, or
stored records need them. Templates may show placeholders; delete or leave empty
identity fields that were not supplied by scope.

Use `git_scope` in work contract boundaries when branch or worktree isolation
matters:

```yaml
git_scope:
  mode: single | parallel
  base_ref: origin/main
  merge_target: origin/main
  branch_target: agent/<work_id>/<lane>/<slug>
  worktree_target: ../worktrees/<repo>/<work_id>-<lane>
  sibling_branch_refs: []
  conflict_policy: no_overlap
```

## Parallel Lane Map Template

Use `templates/parallel-lane-map.yaml` when the task is to split or govern
multiple agent lanes before individual work contracts are issued. The lane map
records lane status, owner, task intent, source refs, allowed write targets,
denied context, expected outputs, verification, and branch/worktree target.

Keep lane maps thin. Store durable maps under `Plan/<project_id>/lane-maps/`
only when handoff or review needs repo-tracked lane allocation. Do not use them
as runtime queues, locks, or broad context bundles.

## Design Gate

Use `design_gate` to decide whether `.agents/skills/system-design/SKILL.md`
is required before implementation.

Set `architecture_significance` to:

- `none`: no design work needed
- `local`: local design reasoning is enough
- `significant`: system-design skill is required

Use `significant` only for material architecture boundaries or high-blast-radius
behavior: public/external contracts, persistent data ownership, trust
boundaries, external write paths, queues/workers/schedulers, deployment
topology, irreversible changes, or material design tradeoffs.

For significant work, output should name:

```yaml
skill_refs_used:
  - .agents/skills/system-design/SKILL.md
```

Use existing `human_gate` rules when significant work also touches public APIs,
trust boundaries, persistent data, external writes, deployment, security,
dependencies, CI/CD, release, infrastructure, or irreversible/protected actions.

Return rework when required design inputs, verification, rollback/mitigation, or
an existing required human gate is missing.

## Ref Fields

Prefer refs over embedded bodies:

- `source_refs`
- `artifact_refs`
- `evidence_refs`
- `verification_refs`
- `decision_refs`
- `content_ref`
- `body_ref`
- `rework_refs`

Do not embed raw bodies, credentials, tokens, cookies, browser sessions, local
logs, secret-bearing metadata, or unrelated context in docs, packets, records,
prompts, or artifacts.

## Evidence Rules

Evidence should separate observed facts from inference.

- Cite concrete source refs.
- Put observations under `facts`.
- Put conclusions under `inferences` and label them as inference.
- Record decisions separately from facts and inferences.
- State missing evidence, stale refs, confidence, residual risk, and next action.
- Preserve enough detail for another worker to reproduce the check.

## Verification Records

Each verification record should include check name, method or command, result
state, evidence ref, unverified surfaces, residual risk, and next action.

Result states:

- `passed`: check ran and passed.
- `failed`: check ran and failed.
- `blocked`: check could not run because of a blocker.
- `skipped`: check was intentionally not run.
- `not_applicable`: check does not apply to this work unit.

## Rework

Return rework when work is incomplete, unsafe, unverifiable, ambiguous, missing
required context, missing permission, missing evidence, mismatched to contract,
or conflicting with repo truth.

A useful rework record includes type, blocker summary, failed or missing
requirement, evidence refs, requested repair, and suggested next action. Use
`work_id` or `project_id` only when the scope already provides them or handoff
safety requires them.

Common types: `missing_context`, `ambiguous_instruction`, `contract_mismatch`,
`verification_failed`, `evidence_gap`, `unsafe_assumption`,
`blocked_dependency`, and `scope_conflict`.

## Template Locations

Use `templates/work-contract.yaml`, `templates/evidence-record.yaml`,
`templates/verification-record.yaml`, `templates/rework-record.yaml`, and
`templates/parallel-lane-map.yaml` when the task asks for structured records or
parallel lane allocation.
