# Repo Boundary And Storage Contract

## Active Surface
This product repo is routed by `AGENTS.md`; `docs/` defines active agent
behavior, and `docs/reference/` holds details opened only by need.

## Repo Truth
Repo truth includes `AGENTS.md`, `README.md`, `.env.example`, `docs/`,
`templates/`, `scripts/`, `tools/`, `tests/`, tooling files, `.github/`,
`.agents/`, `plugins/`, `hooks/`, `Plan/`, `app/`, `src/`, `samples/`,
`outputs/`, and `artifact/`.

Use `docs/reference/repo-boundary-and-storage-reference.md` for the folder map
and root README routes.

## Placement Gate
- Place durable tracked work only in documented roots.
- Keep project-specific plan/log, artifact, and source records under
  `Plan/<project_id>/`, `artifact/<project_id>/`, or `src/<project_id>/`.
- Keep `docs/` clean: direct new files must be routed repo-wide rules.
- If placement is unclear, open the repo boundary reference and root README
  before writing.

## Storage Rules
Do not turn this repo into default storage for runtime queues, lock indexes,
broad logs, browser sessions, caches, or secret-bearing material.

Track sanitized templates, restore scripts, compact contracts, references, and
verification helpers instead of local operational state.

`Plan/` stores project-scoped agent plans, logs, and optional durable lane-map
records for planning and handoff; it is not runtime state.

`src/` stores product code; `samples/` and selected `outputs/` store small
fixtures/examples. Generated outputs and local `data/` stay ignored unless
accepted as artifacts.

## Secrets And Past Source
`.serena/`, `archive/`, auth files, tokens, cookies, API keys, logs, caches,
and local runtime state are not repo truth.

Do not write secrets, credentials, raw bodies, browser sessions, or
secret-bearing metadata into prompts, docs, logs, artifacts, templates, or repo files.

Distill useful past-source content into active docs or current references.

## Skills And Plugins
Load only the smallest relevant skill and name it when it shapes work. Skills
and plugins do not override active docs, targets, gates, verification, or storage.
