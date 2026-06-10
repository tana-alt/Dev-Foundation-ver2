# Repo Boundary And Storage Contract

## Active Surface

This repo is routed by `AGENTS.md`. Active contracts in `docs/` keep work
goal-first, bounded, and verifiable. Detailed guidance lives in
`docs/reference/` and should be opened only when needed.

## Repo Truth

Repo truth includes `AGENTS.md`, `docs/`, `docs/reference/`, `README.md`,
`templates/`, `scripts/`, `tests/`, tooling files, `.github/`, `.agents/`,
`plugins/`, `hooks/`, `Plan/`, `app/`, `src/`, and `artifact/`.

`archive/`, `.serena/`, caches, broad logs, local runtime state, browser
sessions, credentials, tokens, cookies, and secret-bearing files are not repo
truth.

## Placement

- Use `Plan/<project_id>/` for lightweight plans and logs.
- Use `artifact/<project_id>/` only for durable, useful outputs or evidence.
- Use `src/<project_id>/` or existing shared source paths for implementation.
- Keep `docs/` for repo-wide rules and references.
- Use `templates/` only for compact blank formats that are still active.

Optional durable lane-map records may live under
`Plan/<project_id>/lane-maps/` for real parallel write work. They are not a
runtime scheduler, queue, lock ledger, heartbeat, dashboard, or completion
claim.

Do not introduce runtime queues, lock ledgers, dashboards, broad operational
logs, or unowned project storage.

## Storage Rules

Prefer small records that help the next action:

- plan
- log
- task packet
- verification note
- optional spec

Do not store raw bodies, credentials, local runtime ledgers, browser sessions,
secret-bearing metadata, or unrelated context in docs, plans, artifacts,
templates, or prompts.

Heavy contract artifacts such as final handoffs, traceability matrices,
convergence decisions, source snapshot locks, operational scorecards, and
residual-risk carryover records are archived patterns, not default storage.

## Skills And Plugins

Skills are compact routing helpers. They do not override the user request,
active contracts, allowed write targets, human gates, verification, or storage
rules.
