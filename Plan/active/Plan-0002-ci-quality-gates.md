# Plan-0002: CI / Ruff / Mypy / Pytest

## Objective

Add GitHub Actions quality gates so every push or pull request runs static
checks and execution tests without requiring external LLM credentials.

## Scope

- GitHub Actions workflow
- `ruff check`
- `ruff format --check`
- `mypy`
- `pytest`
- Python dev dependency declarations

## Out of Scope

- Real LLM smoke tests as required CI gates
- Deployment automation
- README rewrite

## Dependencies

- `Plan-0001`

## Parallelization

Can run in parallel with `Plan-0003`, `Plan-0004`, and `Plan-0008`.

## Deliverables

- `.github/workflows/ci.yml`
- `pyproject.toml` dev tool dependencies and tool configuration

## Acceptance Criteria

- GitHub Actions installs the package with dev dependencies.
- CI runs `ruff check`, `ruff format --check`, `mypy`, and `pytest`.
- CI does not require OpenAI, Anthropic, SEC, or Yahoo credentials.
- Local equivalents of the CI commands pass.

## Commands

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src tests
.venv/bin/python -m pytest -q
```

## Log

### 2026-05-27

- Branch: current workspace
- Commits: not yet committed
- Done: Added `.github/workflows/ci.yml`, dev dependencies, and ruff/mypy
  configuration.
- Decisions: Keep real LLM smoke out of mandatory CI; fake provider work belongs
  to `Plan-0005`.
- Validation:
  - `.venv/bin/python -m ruff check .` passed.
  - `.venv/bin/python -m ruff format --check .` passed.
  - `.venv/bin/python -m mypy src tests` passed.
  - `.venv/bin/python -m pytest -q` passed with 31 tests.
- Risks / Follow-up: Mypy strictness may need phased tightening after current
  MVP passes.
