# Source Storage

`src/` contains the tracked Python package for the Earnings Debate Agent
product code.

## Structure

```text
src/*.py
src/prompts/
src/<project_id>/
```

## Rules

- Keep product runtime code and prompt assets directly under `src/`.
- Use `src/<project_id>/` for project-specific implementation code.
- Do not store notes, plans, logs, generated dumps, caches, or artifacts here.
- If implementation is shared across projects, document ownership before adding
  it outside a `project_id` directory.
