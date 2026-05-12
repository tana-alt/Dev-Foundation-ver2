---
name: project-storage-placement
description: Use when adding or editing Plan, artifact, or src files so project_id-scoped folder rules and change checks are followed.
---

# Project Storage Placement

Use this when writing durable project files under `Plan/`, `artifact/`, or
`src/`.

## Place Files

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

Root metadata is limited to documented files such as `Plan/README.md`,
`artifact/README.md`, `artifact/.gitkeep`, `src/README.md`, and `src/.gitkeep`.

## Check Scope

Single-project work may change only matching project paths. Multi-project work
may change only IDs listed in `FOUNDATION_ALLOWED_PROJECT_IDS`.

Run:

```sh
scripts/check-project-scoped-changes.sh
```

If the check blocks, move files under the declared project ID, narrow the
change, or explicitly switch to multi mode with a recorded reason.
