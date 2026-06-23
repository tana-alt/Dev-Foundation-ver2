# Repo Boundary And Storage Contract

## Repo Truth

Repo truth is the tracked product, docs, tooling, templates, tests, plans,
artifacts, source roots, hooks, plugins, `.agents/`, and `.github/`.

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

## Storage Rules

Prefer small records that help the next action: plan, log, task packet,
verification note, or optional spec.

Do not store raw bodies, credentials, local runtime ledgers, browser sessions,
secret-bearing metadata, or unrelated context in docs, plans, artifacts,
templates, or prompts.

## Skills And Plugins

Skills are compact routing helpers. They do not override the user request,
active contracts, allowed write targets, human gates, verification, or storage
rules.
