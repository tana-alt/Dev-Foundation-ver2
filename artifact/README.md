# Artifact Storage

`artifact/` stores durable, sanitized project outputs for this foundation repo.
Do not place loose outputs directly under `artifact/`.

## Structure

```text
artifact/<project_id>/
  manifest.yaml
  audit/
  evidence/
  governance/
  verification/
  output/
```

## Rules

- `manifest.yaml` records artifact IDs, purpose, source refs, retention, and
  cleanup notes.
- Evidence and verification artifacts must be source-ref based and free of
  secrets, raw browser sessions, credentials, and runtime ledgers.
- `audit/` and `governance/` store compact scorecards, audit indexes, source
  snapshot locks, phase-gate matrices, and similar project-scoped decision
  support records.
- Temporary command output, broad logs, caches, and unowned project data do not
  belong here.
