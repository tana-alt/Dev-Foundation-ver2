---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Repo Boundary And Storage Reference

Use this reference for repo layout, storage boundaries, ignored local state,
skills, plugins, and overlays.

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
- `.agents/plugins/marketplace.json`: local plugin registry.
- `plugins/`: local plugin bundles and downloaded plugin payloads.
- `Plan/`: project-scoped agent plans and logs, not a runtime queue or lock
  ledger.
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

Plugin registry and payload changes are repo changes. Treat them as local writes
and run relevant structure, contract, lint, typecheck, or smoke checks when
applicable.

Extension-surface integrity checks are structural only:

- each local skill directory has a parseable `SKILL.md` with minimal metadata
- the human skill index covers repo-local skill roots
- plugin registry paths are relative and resolve under `plugins/`
- plugin manifests and MCP config samples parse and point to existing local
  paths

Do not install plugin dependencies, launch MCP servers, perform network calls,
or turn skills/plugins into a package-manager or marketplace-governance system
unless a future distribution contract explicitly requires it.

## Past-Source Rule

Past-source material is not tracked repo truth. Distill useful content into the
current active docs or references before relying on it.
