# Templates Storage

`templates/` stores blank reusable formats only.

## Rules

- Keep templates generic, sanitized, and free of real project records.
- Use placeholders such as `<project_id>` instead of example project names when
  the value could become cargo-cult storage.
- Do not store completed plans, logs, evidence, verification records, runtime
  state, local paths, or secrets here.
- Add or keep a template only when it helps complete future goals.

## Default Active Templates

Use these lightweight shapes first:

- `templates/goal-brief.md`
- `templates/mini-spec.md`
- `templates/detailed-spec.md`
- `templates/task-packet.yaml`
- `templates/verification-note.md`

Use existing project `Plan/<project_id>/plans/Plan_N0001.md` and
`Plan/<project_id>/logs/Plan_N0001.log.md` for durable project memory.

## Optional Templates

- `templates/parallel-lane-map.yaml`: only for real parallel write work.
- `templates/work-contract.yaml`: only when a separate worker needs a bounded
  task packet.
- `templates/evidence-record.yaml` and `templates/verification-record.yaml`:
  only when inline verification notes are not enough.

## Archived Template Surfaces

Heavy-contract, workflow UI, SDK, app-server, context-request/result, and hook
configuration templates are not active templates. They were moved under
`archive/` for inspection only.
