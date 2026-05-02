---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Project Source Of Truth

## Purpose

Each project should keep its canonical state, artifacts, logs, and decisions
inside the project-local directory.

Overlays can exist for reading, dashboards, sync, or presentation, but they are
not the canonical record.

## Project-Local Rule

Canonical project files live under:

```text
projects/{project_id}/
```

Recommended surfaces:

```text
projects/{project_id}/
  brief.md
  state.yaml
  storage-map.yaml
  notes/
  artifacts/
  implementation/
  logs/
```

## Storage Map

Each project should include a `storage-map.yaml` that explains where major
records live.

It should identify:

- project state
- work notes
- decisions
- artifacts
- evidence
- verification
- implementation refs
- logs
- overlays

## Overlay Rule

External overlays may mirror or summarize project state.

Examples:

- Obsidian vaults
- dashboards
- generated reports
- exported docs
- issue trackers

Overlay content should link back to project-local refs. If an overlay and the
project-local record conflict, the project-local record wins unless a migration
or correction explicitly changes that rule.

## Logs

Logs should be project-local when they describe project work.

Shared lessons may be promoted to a shared knowledge surface, but the project
log should retain the original context and evidence.

## Migration Checklist

- Is the canonical path under `projects/{project_id}/`?
- Does the storage map name the artifact location?
- Are overlays marked as overlays?
- Are generated exports distinguishable from source records?
- Can a new worker resume the project from project-local files alone?
