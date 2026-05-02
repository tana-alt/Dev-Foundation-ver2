---
status: reference
owner: foundation
source_of_truth_level: distilled
created_at: 2026-05-02
---

# Verification CI And PR Reference

## Purpose
This reference summarizes verification, CI source material, PR evidence, and
human gates. It is reference context only; active policy belongs in the active
contracts under `docs/`.

## Verification Posture
Start with the smallest relevant check, then widen only as needed.

Choose the first check from the changed surface:
- docs-only: inspect the changed doc, links, or rendered output when relevant.
- Python: run the nearest targeted unit or contract test.
- schema or contract: run the nearest validator, schema, or contract test.
- UI or plugin: run the app-local build or shortest useful smoke check.
- infra, CI, deployment, or safety-sensitive: run mapped local checks and require
  human review before merge or release.

Widen in this order when applicable:
1. targeted test or smoke check near the change
2. lint
3. typecheck or build
4. broader unit or integration tests
5. deterministic repo checks required by the touched surface
6. CI result, if the change is heading to PR or merge

Widen for shared behavior, cross-module contracts, generated artifacts, release
paths, or unclear blast radius. Do not run broad suites by default for small
local changes.

## Result States
Record each relevant check with one state:
- `passed`: the check ran and passed.
- `failed`: the check ran and failed.
- `blocked`: a dependency, environment, tool, or approval was unavailable.
- `skipped`: the check was intentionally not run; include the reason.
- `not_applicable`: the check does not apply to the work.

For `failed`, `blocked`, or `skipped`, include the command or inspection method,
the reason, and whether it appears pre-existing.

## Current Repo Reality
The current Foundation repo has a small root test surface:

- `pyproject.toml`: minimal `uv` project for `ruff`, `mypy`, and `pytest`.
- `uv.lock`: frozen dependency lock for clone-and-test behavior.
- `Makefile`: local check commands.
- `.github/workflows/ci.yml`: CI entrypoint.
- `tests/test_foundation_integrity.py`: repo structure and doc contract checks.
- `tests/test_contract_models.py`: Pydantic validation for YAML templates and
  archived packet examples.

The repo still does not have active app code, product tests, deployment config,
or a release target. Command lists copied from source material remain
source/reference examples unless corresponding files exist in this repo or in a
target project boundary.

## Current Commands

- `uv sync --frozen --group dev`: install locked test dependencies.
- `make lint`: run `ruff`.
- `make typecheck`: run `mypy` with the Pydantic plugin enabled.
- `make test`: run `pytest`.
- `make check-contracts`: run Pydantic contract validation tests directly.
- `make check-cd`: run the deployment-readiness guard directly.
- `make check-required`: run the local required chain.

## Current Contract And CD Checks

Pydantic validation is used as a dev-only test mechanism. It validates that
`templates/*.yaml` and `archive/packets/*.yaml` still match the expected
contract shape, while `mypy` checks the model definitions and test code.

The current CD state is `not_applicable` because this repo has no deployment
target, deployment workflow, or deployment config. The CD check is therefore a
guard: it confirms that no active deployment config exists and that CI still
runs the required local checks. If deployment files are introduced later, add a
specific deploy smoke check and require human review before release.

## Source Command Reference
Copied source command model:
- `make lint`: `uv run ruff check .`
- `make typecheck`: `uv run mypy apps src tests`
- `make test`: `uv run pytest`
- `make check-architecture`: architecture dependency validation
- `make check-doc-freshness`: markdown/frontmatter/link freshness validation
- `make check-dangerous-diff`: safety-sensitive changed-file validation
- `make check-harness-runtime`: runtime artifact and packet contract validation
- `make check-repo-profiles`: repo profile contract validation
- `make check-required`: source-defined required local chain

Copied CI model: separate `ruff`, `mypy`, `pytest`, and `architecture-check`
jobs after `uv sync --frozen --group dev`. These are historical and design
reference unless matching files are present.

## Evaluation Layers
Keep the layers separate:
- unit tests: normal runner checks near changed code.
- deterministic checks: machine pass/fail checks such as lint, typecheck,
  schema validation, architecture, doc freshness, and dangerous diff.
- rubric evals: LLM or adaptive checks for instruction following, grounding,
  safety, or output quality.
- trace and online evals: runtime trace review, anomaly detection, and dataset
  creation.
- offline regression: replayable datasets from known failures or failing traces.

CI, rubric, trace, and regression details remain reference, not active policy.
Rubric and trace signals should not replace normal CI or human review.

## PR Or Handoff Evidence
Include:
- Intent: what problem the change solves.
- Scope: changed paths, subsystems, artifacts, and non-goals.
- Changed paths/artifacts: files created, edited, generated, or left untouched.
- Verifier results: relevant checks, command or inspection method, result state,
  and important output summary.
- Docs impact: active docs, references, templates, or task docs changed; or why
  docs were not needed.
- Risk: known risks, unverified surfaces, residual uncertainty, and follow-up.
- Human review focus: where a reviewer should look first.

Evidence should separate observed facts from inference, cite source refs instead
of memory, avoid secrets, and preserve enough detail for review.

## Human Gates
Require human review or approval before merge, release, or operational use for:
secrets or credential handling; auth; billing; database migrations or schema
changes; deployment; CI/CD; GitHub Actions; infrastructure; public release;
dependency changes; and security-sensitive behavior or protected data.

AI review and rubric output are advisory. Source material keeps the merge gate
as human review plus required CI pass.
