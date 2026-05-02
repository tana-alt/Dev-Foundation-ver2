---
status: active
owner: steward
last_validated_at: 2026-04-28
source_of_truth_level: primary
---

# Git And Test Policy

This is the short policy agents should read before changing code. Use it as the
index; open the detailed docs only when the task needs them.

## Source Of Truth

- Detailed build and PR flow: `docs/workflows/build-test-pr.md`
- Command definitions: `Makefile`
- Regression/eval model: `docs/evals/regression.md`
- PR evidence shape: `.github/pull_request_template.md`

## Git

- Work on `codex/*` branches unless a human asks for a different prefix.
- Do not push directly to `main`.
- Make a checkpoint commit before broad cleanup or migration work.
- Keep commits reviewable: one behavioral or structural change per commit.
- Never revert unrelated user changes to make the tree look clean.
- The harness repo tracks orchestration, templates, policies, validators, and explicit fixtures.
- Concrete `projects/{project_id}/` instances are ignored by the harness and should use their own nested Git repo when active or productized.
- Create new projects by copying `projects/_template/`, then initialize Git inside the copied project when it becomes operational.

## Verification Order

Run the smallest relevant check first, then widen:

1. targeted unit or contract test near the changed code
2. `make lint`
3. `make typecheck`
4. app-local build or smoke check when UI/plugin code changed
5. broader `make test`
6. deterministic checks required by the touched surface

## Required Checks

Use these when the touched files make them relevant:

- Python code: `uv run pytest <target>`, `make lint`, `make typecheck`
- App web UI: `cd apps/web && npm run build`
- Obsidian plugin: `cd apps/obsidian-plugin && npm run build`
- Architecture/docs contracts: `make check-architecture`
- Docs freshness: `make check-doc-freshness`
- Safety-sensitive diffs: `make check-dangerous-diff`
- Profile/export changes: `make check-repo-profiles`

CI currently does not run every local deterministic check. Record any skipped
or failing check with the command, result, and whether the failure pre-existed.

## Logs And Lessons

- Project work logs go under `projects/{project_id}/logs/`.
- App overlay logs are summaries and links only.
- Lessons useful to more than one project go to
  `knowledge/shared/agent-lessons-index.md`.

## Human Gate

Escalate before merging or shipping changes involving secrets, auth, billing,
database migrations, deployment, CI/CD, GitHub Actions, or public release.
