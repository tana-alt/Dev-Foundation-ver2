---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Migration And Acceptance Reference

Use this reference for foundation rebuild audits, migration acceptance, compact
active-doc and routed-reference goals, preserved-surface checks, and acceptance
risk notes.

## Trigger

Open this reference when:

- auditing whether the foundation rebuild or migration still satisfies its
  acceptance goals;
- checking that `AGENTS.md` stays a compact route map, active docs stay
  behavioral, and operational detail stays in routed references;
- assessing preserved repo surfaces or acceptance risks from the migration
  checklist.

Do not open this reference when:

- the task is a small named-file edit, ordinary implementation change, or
  routine verification choice with no migration audit or acceptance question;
- the only need is concrete repo placement, record schema, branch/worktree
  procedure, current command selection, PR evidence, or runtime scope.

Adjacent references:

- Use `repo-boundary-and-storage-reference.md` for concrete folder maps,
  durable placement, storage boundaries, unsupported roots, and ignored state.
- Use `verification-ci-and-pr-reference.md` for current verification commands,
  fast/full gate choice, result states, CI/CD readiness, and PR evidence.
- Use `git-worktree-and-branch-reference.md` for branch/worktree setup,
  changed-path evidence, conflict checks, and protected-branch mechanics.

Expected effect after opening:

- Judge acceptance against the migration note and checklist, keep active docs
  compact, preserve routed-reference detail, flag acceptance risks and
  unverified surfaces, and defer concrete placement, command, or Git mechanics
  to adjacent references.

## Migration Note

This rebuild reduces routine agent context and moves operational detail into
references. `AGENTS.md` is now only an entrypoint and routing map. Active docs
keep compact behavior, verification, and boundary rules. Detailed examples,
verification commands, packet fields, storage nuance, and worktree/branch
procedures live in `docs/reference/`.

The rebuild also adds explicit branch and worktree handling for parallel write
work without introducing repo-stored queues, lock ledgers, broad log roots, or
scheduler state.

Current repo-specific surfaces are preserved: templates, restore script, tests,
verification tooling, CI, skills, the plugin registry, `Plan/`, and reserved
`app/`, `src`, and `artifact/` surfaces. A `plugins/` payload root exists only
when plugins are actually installed.

## Acceptance Checklist

- [ ] `AGENTS.md` is a thin entrypoint and routing document, not a manual.
- [ ] Routine agents do not read all active docs, references, skills, logs,
      archives, or unrelated history by default.
- [ ] Active docs are short and behavioral.
- [ ] Detailed examples, commands, edge cases, packet fields, and operational
      nuance live in `docs/reference/`.
- [ ] Current repo surfaces are preserved: `docs/`, `docs/reference/`,
      `README.md`, `templates/`, `scripts/`, `tests/`, `pyproject.toml`,
      `uv.lock`, `Makefile`, `.github/workflows/ci.yml`, `.agents/skills/`,
      `.agents/plugins/marketplace.json`, `Plan/`, `app/`, `src/`, and
      `artifact/` (`plugins/` appears only when plugin payloads are installed).
- [ ] No default runtime queue, lock ledger, broad log root, dashboard root,
      `projects/`, plural `apps/`, or plural `artifacts/` is introduced.
- [ ] `Plan/` remains scoped planning material, not runtime state or a default
      agent ledger.
- [ ] Work contracts require allowed write targets and, for parallel write work,
      branch/worktree scope.
- [ ] Agents can execute worktree setup, branch validation, changed-path checks,
      and sibling conflict checks from the Git reference.
- [ ] Tracked hooks enforce agent branch/worktree policy locally and run required
      checks before push.
- [ ] Verification commands come from current repo files only.
- [ ] Current verification commands are reflected. The canonical command list
      lives in `docs/reference/verification-ci-and-pr-reference.md` and the
      `Makefile` `help` target; do not restate it here.
- [ ] CD remains `not_applicable` unless deployment config or a release target is
      introduced.
- [ ] Evidence uses refs and separates facts from inference.
- [ ] Work IDs, run IDs, correlation IDs, and idempotency keys are used only
      when concurrency, retry safety, handoff, or stored records require them.
- [ ] Skills do not override active docs, write targets, denied context, human
      gates, verification, or storage rules.
- [ ] Agents may push owned `agent/*` review branches and create or update PRs
      when scope and verification are clear, while direct `main` or `master`
      push and merge remain prohibited or human-controlled.
- [ ] Deployment, CI/CD changes, dependency changes, secrets, auth, billing,
      database migration, infrastructure, release, protected actions, and
      external writes outside the owned review branch or PR require explicit
      permission or human gate.
