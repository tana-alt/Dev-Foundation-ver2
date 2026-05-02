# MODEL-APP-FLOW

Self-contained app delivery repository derived from `MODEL-ARCHITECTURE`.

## Role
- owns the app-facing workflow end to end, including API, web UI, Obsidian plugin, prompts, docs, and tests
- keeps the core runtime and UI modules together so dependency drift does not appear immediately after the split
- retains app-specific repo skills and repo-scoped config as the main workflow entrypoints

## Current Split Policy
1. The full core implementation has been copied into this repo except for secrets, caches, local SQLite files, and excluded third-party checkouts.
2. `apps/*` is intentionally kept for now so the split remains runnable without dependency surgery.
3. Domain-specific pruning can happen later once the app workflow stabilizes inside this repo.

## Project Discovery Quickstart

When a terminal agent is asked to understand a project, resolve the project id first instead of guessing from the largest or most familiar directory.

- App/project index: `artifacts/project-orchestration/app-project-index.yaml`
- 3Dtask project repo: `projects/project_app_3dtask/`
- 3Dtask hub: `projects/project_app_3dtask/notes/00-hub.md`
- 3Dtask agent-readable index: `projects/project_app_3dtask/artifacts/registry/agent-readable-index.yaml`
- 3Dtask current implementation surface: `apps/3dtask-swift/`

For 3Dtask, treat `projects/project_app_3dtask/` as the source of truth and `apps/3dtask-swift/` as the primary implementation surface. Do not start from `obsidian-vault/Apps/*` or `project_agentic_flow_app_flow` unless the user explicitly names that project.

Aliases that should resolve to the same project: `3dtaskproject`, `3dtask project`, `3Dtask`, `3dtask`, `project_app_3dtask`, and `3dtask_app_project`.
