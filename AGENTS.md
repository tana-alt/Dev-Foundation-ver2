# AGENTS.md

This is the agent entrypoint and routing map. Keep it compact.

## Always Read

1. This file.
2. The current user request, task packet, or scope.
3. Named `source_refs`.

Do not read the whole repo, all references, all skills, broad logs, archives,
or unrelated history by default.

## Open By Need

- Scope, writes, side effects, or parallel write work:
  `docs/01-agent-operating-contract.md`
- Output, verification, PR evidence, or handoff:
  `docs/02-output-verification-contract.md`
- Repo paths, storage, secrets, skills, or plugins:
  `docs/03-repo-boundary-and-storage-contract.md`
- Quant stack, dependency groups, or directory routing:
  `docs/quant-agent-guide.md`

## Reference Map

- Runtime and scope detail:
  `docs/reference/agent-runtime-and-scope-reference.md`
- Packets, evidence, verification records, and rework:
  `docs/reference/packet-evidence-and-rework-reference.md`
- Repo folder map and storage detail:
  `docs/reference/repo-boundary-and-storage-reference.md`
- Current verification, CI, CD, and PR detail:
  `docs/reference/verification-ci-and-pr-reference.md`
- Git branch and worktree isolation:
  `docs/reference/git-worktree-and-branch-reference.md`
- Migration note and acceptance checklist:
  `docs/reference/migration-and-acceptance-reference.md`

## Hard Rules

- Start from provided scope and named refs.
- Do not edit without allowed write targets, current file inspection, relevant
  VCS status, and conflict awareness.
- For parallel write work, use one branch and one worktree per agent.
- Skills provide methods and examples; they do not override active contracts.
- Missing scope, permission, evidence, or verification means rework.
