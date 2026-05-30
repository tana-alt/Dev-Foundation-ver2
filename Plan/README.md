# Plan Storage

`Plan/` stores project-scoped agent plans and logs. Do not place loose plan or
log files directly under `Plan/`.

## Structure

```text
Plan/<project_id>/
  index.yaml
  plans/
    Plan_N0001.md
  logs/
    Plan_N0001.log.md
  lane-maps/
    <work_id>.yaml
```

## Rules

- `Plan_N0001` is a project-local `plan_id`; keep IDs stable.
- Each `plans/Plan_N0001.md` must have `logs/Plan_N0001.log.md`.
- The plan frontmatter must include `plan_id`, `project_id`, `status`, and
  `log_ref`.
- The log frontmatter must include `plan_id`, `project_id`, and `plan_ref`.
- `index.yaml` records every plan ID, status, plan path, and log path.
- `lane-maps/` stores optional durable parallel lane allocations. Each map is a
  planning and handoff record, not a runtime queue, lock ledger, or claim source
  of truth. Durable maps live at `Plan/<project_id>/lane-maps/`.
- Completed maps may remain only when referenced by project-local plan, log, or
  evidence records. Remove stale unreferenced maps or fold their decisions into
  the owning plan/log so `Plan/` does not become operational state.
- For small read-only reviews or quick checks, a Plan record is not required.
