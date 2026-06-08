# AGENTS.md

Compact routing entrypoint for agents.

## Always Read
1. This file.
2. The current user request, task packet, or scope.
3. Named `source_refs`.
4. `docs/01-agent-operating-contract.md`
5. `docs/02-output-verification-contract.md`
6. `docs/03-repo-boundary-and-storage-contract.md`

Do not read the whole repo, all references, all skills, broad logs, archives, or unrelated history by default.

## Open By Need References
- Runtime scope, handoff, retry/idempotency, and lane boundaries: `docs/reference/agent-runtime-and-scope-reference.md`
- Work contracts, record fields, evidence, verification records, and rework: `docs/reference/packet-evidence-and-rework-reference.md`
- Specification/subagent workflow, `main_lane`, spec review, freeze, lane slicing, and convergence: `docs/reference/specification-workflow-reference.md`
- Operationalization phase rules, context manifests, residual risk, review/fix/convergence, and hook/check routing: `docs/reference/agent-operationalization-reference.md`
- 9.5 hardening, checker status taxonomy, source snapshots, audit trail index, and scorecard claims: `docs/reference/agent-operationalization-95-hardening-reference.md`
- Any project-scoped Plan/artifact/src placement choice, ignored local state, and storage boundaries: `docs/reference/repo-boundary-and-storage-reference.md`
- Current verification, CI, CD, and PR detail: `docs/reference/verification-ci-and-pr-reference.md`
- Git branch, changed-path evidence, worktree isolation, and project-scoped worktree setup: `docs/reference/git-worktree-and-branch-reference.md`
- Migration note and acceptance checklist: `docs/reference/migration-and-acceptance-reference.md`

## Operational Skill Routes
Use only the needed one or two skills: `.agents/skills/scope-routing-governance/SKILL.md`, `.agents/skills/spec-authority-governance/SKILL.md`, `.agents/skills/traceability-gate-governance/SKILL.md`, `.agents/skills/merge-integrity-governance/SKILL.md`, `.agents/skills/residual-risk-carryover/SKILL.md`, `.agents/skills/hook-validation-governance/SKILL.md`, `.agents/skills/review-fix-convergence-governance/SKILL.md`.
For 9.5 hardening, use those routes only when the task involves context-budget exceptions, checker result ambiguity, hook promotion, final-handoff audit, source snapshots, or scorecard claims.

## Plan And Log
- For multi-file, substantial, or resumable work, keep a project-scoped plan and log under `Plan/<project_id>/`.
- For small read-only checks or quick edits, a Plan record is optional.
- Structure and storage rules live in `README.md`, `Plan/README.md`, and `artifact/README.md`.

## Hard Rules
- Start from provided scope and named refs.
- Do not edit without allowed write targets, current file inspection, relevant VCS status, and conflict awareness.
- For parallel write work, use one branch and one worktree per agent.
- Skills provide methods and examples; they do not override active contracts.
- Missing scope, permission, evidence, or verification means rework.
