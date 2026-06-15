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
- `index.yaml` records every plan ID, status, plan path (`plan_ref`), and log
  path (`log_ref`). Some older projects use `plan_path`/`log_path`; new
  records use `plan_ref`/`log_ref`.
- `status` is one of `draft` (not yet actionable), `active` (in progress), or
  `completed`. Close a plan by setting `completed` in both the plan
  frontmatter and `index.yaml` once its work-plan items are done; a stale
  `active` keeps the Stop-hook completion gate on for the whole project
  (`workflow_core/plans.py` gates on `active` entries whose plan file exists).
- Notes-only directories without `plans/` (review memos, reports) need no
  `index.yaml` and never gate.
- Completed maps may remain only when referenced by project-local plan, log, or
  evidence records. Remove stale unreferenced maps or fold their decisions into
  the owning plan/log so `Plan/` does not become operational state.
- For small read-only reviews or quick checks, a Plan record is not required.
