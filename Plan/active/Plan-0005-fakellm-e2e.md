# Plan-0005: FakeLLM / E2E Execution Path

## Objective

Provide an API-key-free execution path that runs the seven-agent workflow through
final Markdown generation.

## Scope

- `LLM_PROVIDER=fake`
- deterministic response per runtime agent role
- normal path with seven LLM calls and no repair retry
- generated `markdown_report`

## Out of Scope

- Real LLM quality tuning
- External financial API correctness
- README rewrite

## Dependencies

- `Plan-0001`
- `Plan-0004`

## Parallelization

Should complete before `Plan-0006`, `Plan-0007`, and final CI integration.

## Deliverables

- Fake provider implementation
- E2E sample request dependency, if not already present
- E2E tests

## Acceptance Criteria

- `LLM_PROVIDER=fake` runs the workflow without OpenAI or Anthropic keys.
- Normal fake run performs exactly seven LLM calls.
- `markdown_report` is non-empty and includes the core report sections.
- Existing validation gates remain active.

## Commands

```bash
LLM_PROVIDER=fake .venv/bin/python -m pytest tests/test_workflow_e2e.py -q
```

## Log

### 2026-05-27

- Branch: `runtime/0005-fake-provider`
- Commits: pending commit
- Done: Added `LLM_PROVIDER=fake` provider factory path, deterministic
  schema-valid responses for all seven runtime roles, and E2E tests that run
  through final Markdown without OpenAI or Anthropic keys.
- Decisions: Fake provider is the mandatory CI path; real LLM smoke remains
  optional.
- Validation:
  - `LLM_PROVIDER=fake .venv/bin/python -m pytest tests/test_workflow_e2e.py -q` passed with 2 tests.
- Risks / Follow-up: Fake responses must stay schema-valid as models evolve.
