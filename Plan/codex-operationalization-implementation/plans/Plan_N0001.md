---
plan_id: Plan_N0001
project_id: codex-operationalization-implementation
status: complete
log_ref: Plan/codex-operationalization-implementation/logs/Plan_N0001.log.md
---

# Codex Operationalization Implementation

## Objective

Implement the source packs:

- `agent-ops-95-hardening-docs/`
- `codex_operationalization_integrated_spec/`

## Source Refs

- `AGENTS.md`
- `docs/01-agent-operating-contract.md`
- `docs/02-output-verification-contract.md`
- `docs/03-repo-boundary-and-storage-contract.md`
- `codex_operationalization_integrated_spec/`
- `agent-ops-95-hardening-docs/`

## Allowed Write Targets

Derived from the phase prompts and repo storage contracts:

- `AGENTS.md`
- `.agents/skills/`
- `docs/reference/`
- `templates/`
- `scripts/`
- `tests/`
- `Makefile`
- `hooks/`
- `artifact/`
- `Plan/codex-operationalization-implementation/`

## Plan

1. Distill source-pack routing and reference material into supported repo roots.
2. Add operational skills and keep skill index/front matter consistent.
3. Add record templates, validation scripts, fixtures, and tests.
4. Wire only local deterministic Make/hook targets for scripts that exist.
5. Verify with targeted tests and the narrowest repo gates that cover the touched surfaces.

## Verification

- `make check-agent-operational`: passed.
- `make check-fast`: passed.
- `make check-required`: passed.
- `make check-foundation`: passed; 86 pytest tests plus CD readiness guard.
