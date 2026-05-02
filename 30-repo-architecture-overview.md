---
status: draft
owner: foundation
source_of_truth_level: distilled
created_at: 2026-05-02
source_refs:
  - README.md
  - ARCHITECTURE.md
  - docs/index.md
  - docs/specs/repo-profile-split.md
  - profiles/manifest.yaml
  - apps/
  - src/
  - artifacts/
  - projects/
  - skills/
  - tests/
---

# Repo Architecture Overview

This document summarizes the basic skeleton of the current repo in a readable
form.

## Repo Role

`MODEL-APP-FLOW` is an app-delivery and agentic-workflow repository derived from
`MODEL-ARCHITECTURE`.

It currently keeps the app-facing workflow together:

- API
- web UI
- Obsidian plugin
- prompts
- docs
- tests
- workflow/runtime services
- project-local operation artifacts

The repo has not been fully split into separate domain repos. It keeps core
runtime and UI modules together so the system remains runnable while the app
workflow stabilizes.

## Top-Level Areas

### `apps/`

Runnable app surfaces.

- `apps/api/`: FastAPI entrypoint and API boundary.
- `apps/web/`: Vite/React web UI.
- `apps/obsidian-plugin/`: Obsidian plugin source, build scripts, and package config.
- `apps/3dtask-swift/`: current Swift implementation surface for 3Dtask.
- `apps/obsidian-vault/`: app-facing vault mirror/overlay.

### `src/`

Shared Python implementation.

- `src/db/`: persistence models and DB session.
- `src/graph/`: state machine, routing, graph nodes, hooks.
- `src/schemas/`: Pydantic request/response/domain schemas.
- `src/services/`: reusable domain services.
- `src/prompts/`: base prompts, role prompts, manifests, and task templates.
- `src/models.yaml`: model configuration.

### `docs/`

Human and agent-readable documentation.

- `docs/workflows/`: build/test/PR and git/test policy.
- `docs/evals/`: regression and eval model.
- `docs/specs/`: app flow, planner contracts, repo split, and related specs.
- `docs/tasks/`: active/completed task templates and logs.
- root-level docs such as `AGENTS.md`, `ARCHITECTURE.md`, and `docs/rules.md`
  define operating principles and boundaries.

### `artifacts/`

Machine-readable contracts, packet templates, runtime maps, dry-run datasets,
and project-orchestration policies.

- `artifacts/packets/`: packet templates such as handoff, evidence, rework,
  operation, routing, and release-related records.
- `artifacts/runtime/`: runtime maps for context scope, agent I/O, skill
  directory, capability routing, policies, scheduled jobs, dry-run datasets, and
  virtual runs.
- `artifacts/project-orchestration/`: project boundary and storage policies.

### `projects/`

Project-local source-of-truth directories.

Common project shape:

- `brief.md`
- `state.yaml`
- `storage-map.yaml`
- `notes/`
- `artifacts/`
- `implementation/`
- `logs/`
- `content/`
- `runtime/`

Important current convention: concrete project outputs belong under
`projects/{project_id}/`, while overlays such as Obsidian views are not the
canonical source of truth.

### `profiles/`

Repo split and overlay export machinery.

- `profiles/manifest.yaml`: shared/app/quant profile definitions.
- `profiles/templates/`: repo-scoped templates for split repos.
- `scripts/repo_profiles/`: bootstrap, export, and contract-check tools.

The split strategy is to keep shared runtime and schemas in a core repo, while
domain repos carry instructions, skills, docs, prompts, and contracts as overlay
assets.

### `skills/`

Repo-owned skill roots for specialized work such as orchestration, research,
planning, UI/UX, implementation, monitoring, security review, and social launch.

These are historical and operational inputs for the existing agent architecture.
For the next foundation, they are better treated as examples of specialized work
surfaces rather than as required runtime structure.

### `obsidian-vault/`

Local knowledge and app overlay surface.

It contains Apps, Inbox, Raw, Summaries, Hypotheses, Lessons, Reviews,
Templates, and shared knowledge. The repo policy treats this as a useful
overlay, not the canonical source of project truth.

### `tests/`

Python test suite.

- `tests/unit/`: all active pytest files.
- `tests/integration/`: currently scaffolded with `.gitkeep`.
- `tests/references/`: reference assets for tests.

## Core Dependency Direction

The architecture and verification service enforce a dependency direction:

```text
apps/api
  -> src/services
  -> src/schemas
  -> src/db

apps/web and apps/obsidian-plugin
  -> apps/api over HTTP/JSON

src/services
  -> src/db, src/schemas, selected external clients

src/graph
  -> src/services, src/schemas, graph state/routing

src/db
  -> persistence only
```

Forbidden dependency checks:

- `src/db` must not import `src.graph` or `apps`
- `src/graph` must not import `apps`
- `src/services` must not import `apps`

This keeps the API as the public boundary and prevents lower layers from
depending on app entrypoints.

## Main Runtime Lanes

### API Lane

`apps/api/main.py` gathers service functionality into HTTP endpoints. It is the
boundary consumed by the web UI, Obsidian plugin, and tests.

### Workflow Lane

`src/services/workflows/service.py` coordinates workflow records, graph routing,
state, schemas, LLM services, Multica runtime integration, and verification.

It reads prompt roles and templates from `src/prompts/`.

### Knowledge Lane

`src/services/knowledge/service.py` manages knowledge records and search.

It is mostly independent from the workflow lane and is consumed by the API.

### Obsidian Lane

`src/services/obsidian/service.py` handles vault listing, note read/write, path
safety, and app scaffold behavior.

### LLM And Runtime Lane

`src/services/llm/` contains OpenAI, Anthropic, Codex CLI, and runtime adapter
selection.

`src/services/multica/` contains Multica client and runtime integration.

### Verification Lane

`src/services/verification/` contains custom deterministic checks, packet and
agent contract validators, and UI reference-pack evidence validation.

## Data And Contract Style

The repo uses a contract-heavy style:

- Pydantic models in `src/schemas/`
- YAML maps in `artifacts/runtime/`
- packet templates in `artifacts/packets/`
- markdown specs in `docs/specs/`
- tests that validate docs, packets, runtime maps, and schemas stay aligned

The important pattern is that prose docs are not enough. Many claims are backed
by executable validators or tests.

## Project-Oriented Operation

The repo contains both shared runtime artifacts and concrete project folders.

The desired boundary is:

```text
shared foundation / runtime maps / packet templates
  -> project-local state, logs, artifacts, evidence, and implementation refs
  -> overlay views and summaries
```

This means new work should first resolve the project id and then read that
project's local state and storage map.

## Testing Architecture

Testing is layered:

- unit tests with pytest
- deterministic checks through Makefile and verification CLI
- strict mypy type checking
- ruff linting
- CI jobs for ruff, mypy, pytest, and architecture check
- local checks for doc freshness, dangerous diffs, harness runtime, and repo profiles

See `foundation/10-test-and-verification-inventory.md` for the detailed test
extraction.

## Agent Architecture Status

The existing repo contains a rich parent-agent/subagent orchestration model.
However, for the next foundation this should be treated as source material, not
as a required structure.

The reusable parts are:

- scoped context
- explicit source refs
- input/output contracts
- evidence refs
- verification results
- project-local truth
- rework records
- human gate for sensitive decisions

See `foundation/20-agent-thinking-extraction.md` for the abstracted model.

## Minimal Mental Model

```text
User or scheduled work
  -> project/source resolution
  -> scoped context
  -> contract-shaped work
  -> code/docs/artifact change
  -> deterministic verification
  -> evidence + next action
```

The next foundation can keep this mental model while shedding the heavier
agent-role hierarchy.
