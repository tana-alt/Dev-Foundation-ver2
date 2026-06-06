# Templates Storage

`templates/` stores blank reusable formats only.

## Rules

- Keep templates generic, sanitized, and free of real project records.
- Use placeholders such as `<project_id>` instead of example project names when
  the value could become cargo-cult storage.
- Do not store completed plans, logs, evidence, verification records, runtime
  state, local paths, or secrets here.
- Add a template only when an active contract or reference explains when it is
  used.
- Use `templates/parallel-lane-map.yaml` for lane allocation templates; completed
  lane maps belong under `Plan/<project_id>/lane-maps/` when tracked.
- Use `templates/specification-packet.yaml`,
  `templates/specification-review-record.yaml`,
  `templates/implementation-policy-record.yaml`,
  `templates/workflow-run-record.yaml`, and
  `templates/inconsistency-register.yaml` for reusable
  specification/subagent workflow records; completed records belong under the
  owning `project_id`.
- Do not store completed specs, workflow runs, logs, evidence, verification
  records, or project records in `templates/`.
