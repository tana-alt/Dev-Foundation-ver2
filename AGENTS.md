# AGENTS.md

This is the agent entrypoint and routing map. Keep it compact.

## Always Read
1. This file.
2. The current user request, task packet, or scope.
3. Named `source_refs`.
4. `docs/01-agent-operating-contract.md`
5. `docs/02-output-verification-contract.md`
6. `docs/03-repo-boundary-and-storage-contract.md`

Do not read the whole repo, all references, all skills, broad logs, archives,
or unrelated history by default.

## Open By Need References
- Runtime and scope detail:
  `docs/reference/agent-runtime-and-scope-reference.md`
- Packets, evidence, verification records, and rework:
  `docs/reference/packet-evidence-and-rework-reference.md`
- Repo folder map, project-scoped Plan/artifact/src placement, and storage detail:
  `docs/reference/repo-boundary-and-storage-reference.md`
- Current verification, CI, CD, and PR detail:
  `docs/reference/verification-ci-and-pr-reference.md`
- Git branch, worktree isolation, and project-scoped worktree setup:
  `docs/reference/git-worktree-and-branch-reference.md`
- Migration note and acceptance checklist:
  `docs/reference/migration-and-acceptance-reference.md`

## Plan And Log

- For tasks that span multiple files, require substantial labor, or need resumable
handoff, keep a project-scoped plan and log under `Plan/<project_id>/` so
progress, decisions, commands, and verification remain traceable.

- For small read-only checks or quick edits, a Plan record is optional.

- Detailed structure and storage rules live in `README.md`, `Plan/README.md`, and
`artifact/README.md`.

## Hard Rules
- Start from provided scope and named refs.
- Do not edit without allowed write targets, current file inspection, relevant
  VCS status, and conflict awareness.
- For parallel write work, use one branch and one worktree per agent.
- Skills provide methods and examples; they do not override active contracts.
- Missing scope, permission, evidence, or verification means rework.
