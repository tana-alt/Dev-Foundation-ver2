---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Repo Boundary And Storage Reference

Use this reference for repo layout, storage boundaries, ignored local state,
skills, plugins, and overlays.

## Trigger

Open this reference when:

- deciding repo layout, documented roots, or durable `Plan/<project_id>/`,
  `artifact/<project_id>/`, or `src/<project_id>/` placement;
- assessing storage boundaries, repo truth, ignored local state, overlays,
  skills/plugins surfaces, unsupported roots, or past-source handling;
- a task proposes runtime queues, lock ledgers, broad logs, dashboards,
  `projects/`, plural `apps/`, or plural `artifacts/` as repo storage.

Do not open this reference when:

- the task is a small named-file edit or ordinary implementation change with no
  placement or storage decision;
- the only need is record fields, evidence/rework schema, runtime scope,
  handoff/retry behavior, verification command choice, branch/worktree setup,
  PR evidence, or migration acceptance.

Adjacent references:

- Use `packet-evidence-and-rework-reference.md` for work-contract fields and
  evidence, verification, or rework record schemas.
- Use `agent-runtime-and-scope-reference.md` for runtime-supplied scope,
  handoff compatibility, retry/idempotency, and conceptual parallel lanes.
- Use `migration-and-acceptance-reference.md` for foundation rebuild acceptance
  checks; use this reference for the placement and storage facts inside them.

Expected effect after opening:

- Choose documented project-scoped roots, reject loose `artifact/` files and
  unsupported new roots, keep runtime/local/secret-bearing state out of repo
  truth, and cite adjacent references only for their own decisions.

## README Routes

Read root-specific placement rules before writing durable project files:

- `Plan/`: `Plan/README.md`
- `artifact/`: `artifact/README.md`
- `templates/`: `templates/README.md`
- `src/`: `src/README.md`

`docs/` has no local README. Its route is `AGENTS.md`, the active contracts in
`docs/01-03`, and this reference.

## Formal Project Structure

Project-scoped storage uses one `project_id` per root:

```text
Plan/<project_id>/index.yaml
Plan/<project_id>/plans/Plan_N0001.md
Plan/<project_id>/logs/Plan_N0001.log.md
Plan/<project_id>/lane-maps/<work_id>.yaml

artifact/<project_id>/manifest.yaml
artifact/<project_id>/evidence/
artifact/<project_id>/verification/
artifact/<project_id>/output/

src/<project_id>/
```

Use `templates/` only for blank reusable formats. Real plan, log, evidence,
verification, artifact, or implementation files belong under the owning
`project_id`.

## Current Folder Map

- `AGENTS.md`: thin agent entrypoint and routing document.
- `docs/`: compact active agent contracts.
- `docs/reference/`: detailed reference material opened only when needed.
- `README.md`: human-facing overview and restore instructions.
- `templates/`: reusable contract, evidence, verification, rework, storage, and
  local environment templates.
- `scripts/setup-agent-environment.sh`: local agent environment restore script.
- `scripts/check-dev-environment.sh`: read-only local environment inspection.
- `scripts/check-repo-hygiene.sh`: tracked-file and metadata hygiene check.
- `hooks/`: tracked Git hooks installed by the restore script.
- `tests/`: integrity, contract, and readiness checks.
- `pyproject.toml`, `uv.lock`, `Makefile`: local verification tooling.
- `.python-version`, `.editorconfig`, `.gitattributes`: lightweight local
  development defaults.
- `.github/workflows/ci.yml`: CI entrypoint for required checks.
- `.agents/skills/`: current repo-local skills.
- `.agents/plugins/marketplace.json`: local plugin registry. It may be empty by
  default to avoid implying that optional payloads are installed.
- `plugins/`: optional local plugin bundles and downloaded plugin payloads.
- `Plan/`: project-scoped agent plans, logs, and optional durable lane-map
  records for planning and handoff, not a runtime queue, lock ledger, worker
  heartbeat, or claim source of truth.
- `app/`: reserved runnable app surface; keep empty unless truly needed.
- `src/`: project-scoped or documented shared implementation surface.
- `artifact/`: project-scoped durable outputs, evidence, verification, and
  fixtures, not a broad project log.

Do not introduce default roots such as runtime queues, active plan files, lock
ledgers, dashboards, `projects/`, plural `apps/`, or plural `artifacts/`.
New durable storage requires explicit ownership, retention, verification, and
cleanup rules.

## Project-Local Truth

Canonical project state, decisions, artifacts, evidence, verification, and logs
belong under the `project_id` surface that owns them. This foundation repo
should not become a generic unscoped storage root.

When project storage exists, it should be self-describing: state, decisions,
artifacts, logs, evidence, verification, implementation refs, and overlays
should be discoverable from project-local records.

`Plan/<project_id>/lane-maps/` stores optional durable parallel lane allocation
records only while they are needed for planning, handoff, or review. A lane map
is not a scheduler, runtime queue, lock ledger, worker heartbeat, or claim
source of truth. Completed maps may remain only when referenced by
project-local plan, log, or evidence records; stale unreferenced maps should be
removed or folded into the owning plan/log.

## Overlays

Dashboards, vaults, summaries, exports, generated reports, and issue trackers
may mirror or summarize project state. They are overlays unless an explicit
storage map says otherwise. If an overlay conflicts with the project-local
record, the project-local record wins unless a migration changes that rule.

## Ignored Or Non-Truth Surfaces

`.serena/`, `archive/`, auth files, tokens, cookies, API keys, logs, caches,
browser sessions, downloaded runtime payloads, and local runtime state are not
repo truth.

Scripts may create ignored local tool state during restore, but tracked files
must remain sanitized and must not embed credentials or machine-specific logs.
Required secret scanning covers committable content and Git history. Ignored and
untracked local state is outside required CI and hook scope. Optional local deep
scans may be run manually, but they are not repo truth.

## Skills And Plugins

Load only the smallest relevant skill. Do not read all skill roots by default.

Skills provide domain method, examples, and local conventions. They do not
override active docs, allowed write targets, denied context, secret boundaries,
human gates, verification requirements, or storage rules.

Plugin registry changes are repo changes. Treat plugin payload changes as repo
changes only when payloads are present and tracked. Run relevant structure,
contract, lint, typecheck, or smoke checks when applicable.

Extension-surface integrity checks are structural only:

- each local skill directory has a parseable `SKILL.md` with minimal metadata
- the human skill index covers repo-local skill roots
- plugin registry paths are relative and stay under `plugins/`
- plugin manifests and MCP config samples parse and point to existing local
  paths when optional plugin payloads are present

Do not install plugin dependencies, launch MCP servers, perform network calls,
or turn skills/plugins into a package-manager or marketplace-governance system
unless a future distribution contract explicitly requires it.

## Past-Source Rule

Past-source material is not tracked repo truth. Distill useful content into the
current active docs or references before relying on it.
