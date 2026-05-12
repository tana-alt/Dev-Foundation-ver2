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
```

## Rules

- `Plan_N0001` is a project-local `plan_id`; keep IDs stable.
- Each `plans/Plan_N0001.md` must have `logs/Plan_N0001.log.md`.
- The plan frontmatter must include `plan_id`, `project_id`, `status`, and
  `log_ref`.
- The log frontmatter must include `plan_id`, `project_id`, and `plan_ref`.
- `index.yaml` records every plan ID, status, plan path, and log path.
- For small read-only reviews or quick checks, a Plan record is not required.
