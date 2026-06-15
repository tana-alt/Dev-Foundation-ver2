# AGENTS.md

Goal-first routing entrypoint for agents.

## Always Read

1. This file.
2. The current user request, task packet, or explicit scope.
3. Named `source_refs`.
4. `docs/01-agent-operating-contract.md`
5. `docs/02-output-verification-contract.md`
6. `docs/03-repo-boundary-and-storage-contract.md`

Do not read the whole repo, all references, all skills, broad logs, archives,
or unrelated history by default.

## Operating Rule

The goal is the product. Plans, specs, packets, reviews, and logs are tools only
when they help ship the goal.

Default flow:

```text
Goal -> Scope -> Done -> Plan -> Implement -> Verify -> Log result
```

Use lightweight `Plan/<project_id>/` plan and log files for substantial,
multi-file, or resumable work. Skip durable records for small read-only checks
or quick edits.

## Open By Need References

- Goal-to-spec thinking and subagent coordination:
  `docs/reference/specification-workflow-reference.md`
- Compact task packet, evidence, verification, and rework shapes:
  `docs/reference/packet-evidence-and-rework-reference.md`
- Runtime scope, retry/idempotency, and optional lane boundaries:
  `docs/reference/agent-runtime-and-scope-reference.md`
- project-scoped Plan/artifact/src placement and storage boundaries:
  `docs/reference/repo-boundary-and-storage-reference.md`
- Verification command choice, CI, CD, and PR details:
  `docs/reference/verification-ci-and-pr-reference.md`
- Git branch, changed-path evidence, worktree mechanics, and project-scoped
  worktree setup:
  `docs/reference/git-worktree-and-branch-reference.md`
  Use this for project-scoped worktree setup only when worktrees are actually
  needed.
- Migration acceptance checks:
  `docs/reference/migration-and-acceptance-reference.md`
- Hook observability, metrics store, issue surfacing, NFR budgets, benchmark
  comparison, and the AB evaluation pipeline (abrun/verdict/check/gate):
  `docs/reference/harness-observability-reference.md`
- Evaluation tool exit codes (0 pass / 1 fail / 2 inconclusive / 3 error):
  `docs/reference/exit-codes-reference.md`

Avoid operationalization, traceability, convergence, final-handoff, source
snapshot, and scorecard references for normal work. Those heavy-contract
surfaces are archived unless a user explicitly asks to inspect or restore them.

## Skill Routes

Use the smallest matching skill set. In normal work, pick at most one or two.

- Scope control: `.agents/skills/scope-routing-governance/SKILL.md`
- Specs and subagent dispatch:
  `.agents/skills/subagent-workflow-governance/SKILL.md`
- Spec WHAT/HOW separation:
  `.agents/skills/spec-authority-governance/SKILL.md`
- Parallel branch/worktree risk:
  `.agents/skills/merge-integrity-governance/SKILL.md`
- Hooks and validation scripts:
  `.agents/skills/hook-validation-governance/SKILL.md`
- Skill lifecycle:
  `.agents/skills/skill-authoring-governance/SKILL.md`
- Goal completion:
  `.agents/skills/goal-completion-governance/SKILL.md`

Retired heavy-contract skills such as traceability-gate,
review/fix/convergence, and residual-risk carryover are not default routes.

## Hard Rules

- Start from the provided goal, scope, and named refs.
- Prefer implementing and verifying over producing records.
- A mock, draft, or records-only output is incomplete unless the user only asked
  for that artifact.
- Before local writes, inspect current contents and relevant VCS status.
- Do not revert user changes.
- For parallel write work, use explicit branch/worktree ownership only when
  parallelism is actually needed.
- Human approval is required for secrets, external writes, deploy/release,
  dependency or CI/infra changes, database migrations, destructive Git, or
  irreversible/protected actions.
- Missing permission for a protected action blocks that action, not unrelated
  local implementation.
