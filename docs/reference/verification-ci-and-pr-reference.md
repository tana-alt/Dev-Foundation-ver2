---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-05-06
---

# Verification CI And PR Reference

Use this reference for current verification commands, CI source material, CD
readiness, PR evidence, and human gates.

## Verification Posture

Start with the smallest relevant check, then widen only as needed.

Choose the first check from the changed surface:

- docs-only: inspect the changed doc, routing, links, or rendered output when
  relevant.
- Python: run the nearest targeted unit or contract test.
- schema or contract: run the nearest validator, schema, or contract test.
- UI or plugin: run the app-local build or shortest useful smoke check.
- infra, CI, deployment, or safety-sensitive: run mapped local checks and
  require human review before merge or release.

Widen in this order when applicable:

1. targeted test or smoke check near the change
2. lint
3. typecheck or build
4. broader unit or integration tests
5. deterministic repo checks required by the touched surface
6. CI result, if the change is heading to PR or merge

Do not run broad suites by default for small local changes.

## Current Repo Reality

The current Foundation repo has a small root test surface:

- `pyproject.toml`: minimal `uv` project for `ruff`, `mypy`, and `pytest`.
- `.python-version`: local and CI Python version hint.
- `.github/workflows/ci.yml`: pins the CI runner label and setup tool versions
  used by the foundation gate.
- `.editorconfig` and `.gitattributes`: lightweight editor and line-ending
  defaults.
- `.gitleaks.toml`: minimal allowlist for sanitized example values in tracked
  docs.
- `uv.lock`: frozen dependency lock for clone-and-test behavior.
- `Makefile`: local check commands.
- `.github/workflows/ci.yml`: CI entrypoint for required checks and the CD
  readiness guard.
- `.agents/plugins/marketplace.json` and `plugins/`: local plugin registry and
  plugin payloads.
- `tests/test_foundation_integrity.py`: repo structure and doc contract checks.
- `tests/test_contract_models.py`: Pydantic validation for YAML templates.
- `tests/test_clean_checkout_reproducibility.py`: required tracked-file checks
  for clone-and-test reliability.
- `tests/test_extension_surface_integrity.py`: structural skill and plugin
  metadata/path checks.

The repo does not currently have active app code, product tests, deployment
config, or a release target.

## Current Commands

Use only commands backed by current repo files. Current verification surfaces
include:

- `uv sync --frozen --group dev`: install locked dev/test dependencies.
- `make lint`: run `ruff`; plugin payload roots are excluded from foundation
  lint scope.
- `make typecheck`: run `mypy` with the Pydantic plugin enabled.
- `make test`: run `pytest`.
- `make check-toolchain`: report local toolchain versions used by the foundation
  gate.
- `make doctor`: inspect local Git, hook, Python, and tool setup, including
  command versions, without changing files.
- `make check-contracts`: run Pydantic contract validation tests directly.
- `make check-doc-consistency`: run doc and worktree-policy consistency tests
  directly.
- `make check-hooks`: run shell syntax checks for tracked hook scripts.
- `make check-shell`: run ShellCheck static analysis on shell hooks and
  scripts.
- `make check-hygiene`: check tracked ignored files, forbidden local or
  past-source roots, sensitive tracked path names, gitlink metadata, and
  unignored nested Git directories.
- `make check-secrets`: run Gitleaks with redacted output and the tracked
  `.gitleaks.toml` config against the tracked tree and Git history when commits
  exist.
- `make check-cd`: run the deployment-readiness guard directly.
- `make check-required`: run the local required chain.
- `make check-foundation`: run the Foundation Robustness Gate by combining
  `make check-toolchain`, `make check-required`, and `make check-cd`.

For docs-only edits, at minimum inspect the changed docs and run the smallest
available contract or required check if the repo checkout and tools are
available.

## Current Contract And CD Checks

Pydantic validation is a dev-only test mechanism. It validates that
`templates/*.yaml` still match the expected contract shape, while `mypy` checks
the model definitions and test code.

CD is currently `not_applicable` because this repo has no deployment target,
deployment workflow, or deployment config. `make check-cd` is a guard: it
confirms no active deployment config or deployment workflow exists and CI still
runs required local checks.

If deployment files are introduced later, add targeted deploy smoke checks and
require human review before release.

## What The Test Suite Validates

The test suite validates repo structure, active doc compactness, doc routing,
required templates and scripts, tracked hook installation, clean-checkout
tracked-file reproducibility, ignored runtime surfaces, local environment
restore behavior, lightweight dev defaults, ShellCheck and Gitleaks wiring,
explicit skill roots, structural plugin integrity, YAML contract models,
result-state spelling, work contract `git_scope`, and CD readiness.

## Result States

Record each relevant check with one state:

- `passed`: the check ran and passed.
- `failed`: the check ran and failed.
- `blocked`: a dependency, environment, tool, or approval was unavailable.
- `skipped`: the check was intentionally not run; include the reason.
- `not_applicable`: the check does not apply to the work.

For `failed`, `blocked`, or `skipped`, include the command or inspection method,
the reason, and whether it appears pre-existing.

## PR Or Handoff Evidence

Include:

- intent: what problem the change solves
- scope: changed paths, subsystems, artifacts, and non-goals
- changed paths or artifacts
- verifier results: check, method or command, result state, and output summary
- docs impact
- known risks, unverified surfaces, and follow-up
- human review focus

Evidence should separate observed facts from inference, cite source refs instead
of memory, avoid secrets, and preserve enough detail for review.

## Human Gates

Canonical human gate rules are defined in
`docs/02-output-verification-contract.md`. This reference provides operational
notes only.

Agents may push owned `agent/*` review branches and create or update PRs when
scope, branch/worktree ownership, verification, and evidence are clear. Direct pushes to `main` or `master` are prohibited. Merge remains human-controlled and
requires required CI pass when a merge is planned.

Require human review or explicit approval before release or operational use for
secrets or credential handling, auth, billing, database migrations or schema
changes, deployment, CI/CD, GitHub Actions, infrastructure, public release,
dependency changes, external write outside the owned review branch or PR,
branch/worktree deletion, irreversible/protected actions, security-sensitive
behavior, or protected data.

AI review and rubric output are advisory.

## Local Hooks

Tracked hooks live in `hooks/` and are installed by
`scripts/setup-agent-environment.sh` through `core.hooksPath=hooks`.

- `pre-commit`: runs `scripts/check-agent-worktree-policy.sh`.
- `pre-push`: runs `scripts/check-agent-worktree-policy.sh`, then
  `make check-foundation`.

The worktree policy blocks commits and pushes from the canonical repo root,
blocks direct writes on `main` or `master`, and requires
`agent/<work_id>/<lane>/<slug>` branch naming. Hooks are commit/push
guardrails, not runtime filesystem monitors. Required CI remains the merge
gate.

`pre-push` also rejects remote destination refs for `main` and `master`, so an
agent branch cannot be pushed as `HEAD:main` or `HEAD:master`.
