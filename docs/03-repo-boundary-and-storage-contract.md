# Repo Boundary And Storage Contract

## Active Surface
This compact foundation repo is routed by `AGENTS.md`. Active contracts in
`docs/` define behavior; detailed guidance lives in `docs/reference/`.

## Repo Truth
Repo truth includes `AGENTS.md`, `docs/`, `docs/reference/`, `README.md`,
`templates/`, `scripts/`, `tests/`, tooling files, `.github/`, `.agents/`,
`plugins/`, `hooks/`, `Plan/`, `app/`, `src/`, and `artifact/`.

Use `docs/reference/repo-boundary-and-storage-reference.md` for the folder map
and root README routes.

## Placement Gate
- Place durable tracked work only in documented roots.
- Keep project-specific plan/log, artifact, and source records under
  `Plan/<project_id>/`, `artifact/<project_id>/`, or `src/<project_id>/`.
- Keep `docs/` clean: direct new files must be repo-wide rules, contracts, or
  routing docs, and must be linked from an existing route.
- If placement is unclear, open the repo boundary reference and root README
  before writing.

## Storage Rules
Do not turn this repo into default storage for runtime queues, lock indexes,
broad logs, browser sessions, caches, or secret-bearing material.

Track sanitized templates, restore scripts, compact contracts, references, and
verification helpers instead of local operational state.

`Plan/` stores project-scoped agent plans, logs, and optional durable lane-map
records for planning and handoff; it is not runtime state. Local worktrees are not repo truth.

## Secrets And Past Source
`.serena/`, `archive/`, auth files, tokens, cookies, API keys, logs, caches,
and local runtime state are not repo truth.

Do not write secrets, credentials, raw bodies, browser sessions, or
secret-bearing metadata into prompts, packets, docs, logs, artifacts,
templates, or repo files.

Distill useful past-source content into active docs or current references.

## Skills And Plugins
Load only the smallest relevant skill. Name a skill ref in output when it
materially shapes work.

Skills and plugins do not override active docs, allowed write targets, denied
context, secret boundaries, human gates, verification requirements, or storage
rules.
