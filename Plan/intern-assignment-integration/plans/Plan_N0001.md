---
plan_id: Plan_N0001
project_id: intern-assignment-integration
status: draft
log_ref: Plan/intern-assignment-integration/logs/Plan_N0001.log.md
created_at: 2026-06-01
---

# Internship Assignment Integration Plan

## Intent

Make `/Users/yamamotokaito/dev/earnings-debate-agent/Dev-Foundation-ver2` the
canonical repository for the internship assignment while keeping its existing
remote unchanged and preserving the external assignment repository history.

Use the current repository's `AGENTS.md` and agent-development foundation. Use
the external assignment repository's `README.md` as the product-facing README.

## Source Refs

- Canonical repo: `/Users/yamamotokaito/dev/earnings-debate-agent/Dev-Foundation-ver2`
- External assignment repo: `/Users/yamamotokaito/dev/earnings-debate-agent`
- Canonical `AGENTS.md`
- Canonical active docs:
  - `docs/01-agent-operating-contract.md`
  - `docs/02-output-verification-contract.md`
  - `docs/03-repo-boundary-and-storage-contract.md`
- Canonical repo-boundary reference:
  - `docs/reference/repo-boundary-and-storage-reference.md`
- Canonical git/worktree reference:
  - `docs/reference/git-worktree-and-branch-reference.md`
- External product docs/config inspected:
  - `README.md`
  - `pyproject.toml`
  - `.gitignore`
  - `.env.example`
  - `.github/workflows/ci.yml`
  - `.github/workflows/pytest.yml`

## Current Findings

Canonical repo state:

- Remote remains `git@github.com:tana-alt/Dev-Foundation-ver2.git`.
- Current branch is `agent/lane-management-ci-v2/foundation/lane-map-ci`.
- No tracked local modifications were present before this Plan write.
- Existing untracked project records are present under:
  - `Plan/skill-roadmap-20260527/`
  - `Plan/system-improvement/`
  - `artifact/system-improvement/`

External assignment repo state:

- Remote is `git@github.com:tana-alt/Financial-debate-agents.git`.
- Current branch is `runtime/0013-exception-handling`.
- The tracked project contains:
  - product `README.md`
  - `.env.example`
  - `.github/workflows/ci.yml`
  - `.github/workflows/pytest.yml`
  - `pyproject.toml`
  - `src/` FastAPI, CLI, workflow, LLM provider, prompts, report-quality code
  - `tests/` product tests and fixtures
  - `samples/`
  - `outputs/` selected report artifacts
  - `scripts/validate_agent_assets.py`
  - `tools/create_interactive_external_sources.py`
- External `.env` exists locally but is ignored and not tracked.
- External `.env.example` is tracked.
- External `.env` history check showed no tracked `.env` commits in the
  inspected log path; pre-import secret scanning is still required.
- External repo has substantial uncommitted tracked changes across `src/`,
  `src/prompts/`, and `tests/`.
- External repo has untracked material:
  - `data/presentations/NVDA-F1Q27-Quarterly-Presentation-FINAL.pdf`
  - `data/sections/nvda-2027q1-presentation-sections.json`
  - `earnings_debate_90_plan_bundle/`
  - `tests/test_structured.py`
  - `tests/test_workflow_routing.py`
  - `.serena/`
  - nested `Dev-Foundation-ver2/`

## Design Verdict

Proceed with a staged, history-preserving import after the external dirty state
is resolved into an importable snapshot.

This is architecture-significant because it changes the long-lived repository
boundary: the canonical foundation repo becomes the product repository for the
internship assignment, while still retaining agent contracts, skills, docs, and
verification surfaces.

## Selected Integration Strategy

Use a history-preserving merge of the external assignment branch into an
integration branch in the canonical repo.

Planned mechanics:

1. In the canonical repo, create an integration branch from the intended base:
   `agent/intern-assignment-integration/product/import`.
2. Add the external assignment repo as a temporary local remote, for example:
   `assignment-source = /Users/yamamotokaito/dev/earnings-debate-agent`.
3. Fetch the selected external branch.
4. Merge with `--allow-unrelated-histories` so the external product history is
   retained in the canonical repository history.
5. Resolve root conflicts deliberately:
   - keep canonical `AGENTS.md`
   - use external `README.md`
   - merge `.gitignore`
   - merge `.env.example`
   - merge `pyproject.toml`
   - consolidate `.github/workflows/`
   - keep canonical `docs/`, `.agents/skills/`, `templates/`, `hooks/`, and
     foundation scripts unless a later decision moves them
6. Retain product code at root-level `src/`, product tests under `tests/`, and
   foundation tests in the same test tree or a clearly named `tests/foundation/`
   subdirectory as needed during conflict resolution.
7. Remove placeholder files such as `src/.gitkeep` and `app/.gitkeep` only if
   their owning directories become populated by real product code.
8. Run the staged verification chain and update docs/config until the product
   and foundation checks are coherent.
9. Remove or document the temporary import remote after merge review, without
   changing canonical `origin`.

## Options Considered

Option A: Prefix import under `app/earnings-debate-agent/`.

- Pros: low conflict risk, easy rollback, clean separation from foundation.
- Cons: external README paths become inaccurate, package/CLI config needs more
  adaptation, final repo feels less like a polished product repository.

Option B: Root-level unrelated-history merge.

- Pros: keeps assignment repository history, preserves normal product layout,
  allows external README to remain product-facing, and makes the canonical repo
  look like a real deliverable.
- Cons: higher conflict risk in `README.md`, `.gitignore`, `pyproject.toml`,
  `.github/`, `tests/`, and verification configuration.

Option C: Change remote or make the external repo canonical.

- Pros: simplest product repo shape.
- Cons: conflicts with the stated requirement that this repo is canonical and
  the remote target should not change.

Selected: Option B.

## Import Scope Decisions

Import by default:

- External committed history for the selected branch.
- External product `README.md`.
- External product source under `src/`.
- External product tests and fixtures under `tests/`.
- External product samples under `samples/`.
- External tracked report examples under `outputs/`.
- External product `.env.example`.
- External product scripts/tools that support validation or demo runs.

Keep from canonical repo:

- `AGENTS.md`.
- `docs/` and `docs/reference/`.
- `.agents/skills/` and `.agents/plugins/marketplace.json`.
- `templates/`, `hooks/`, and foundation restore/check scripts unless replaced
  by an explicit later decision.
- `Plan/` and `artifact/` project-scoped records.

Do not import by default:

- `.serena/`.
- `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `*.egg-info/`.
- `.claude/` and external `.agents/` ignored local skill surfaces.
- `archive/`, `.report_quality_full_backup/`, and ignored local setup/backups.
- Local PDFs or large `data/` inputs unless explicitly selected and justified.
- Nested `Dev-Foundation-ver2/` from the external repo working tree.

Needs explicit decision before import:

- External uncommitted tracked changes on `runtime/0013-exception-handling`.

Explicitly excluded from first import by user decision:

- All external untracked files and directories, except `.env` as described
  below.
- External untracked tests:
  - `tests/test_structured.py`
  - `tests/test_workflow_routing.py`
- External untracked demo data and `earnings_debate_90_plan_bundle/`.
- External untracked `data/`, `.serena/`, nested `Dev-Foundation-ver2/`, and
  other untracked local-only material.

Special `.env` handling:

- The external `.env` may be copied into the canonical working tree as a
  local-only ignored file.
- Do not read, print, diff, log, commit, or otherwise expose `.env` contents.
- Verify `.env` is ignored before and after the copy.
- Keep `.env.example` as the tracked public configuration surface.
- If `.env` ever appears in `git status` as trackable content, stop and fix
  `.gitignore` before continuing.

## Pyproject And Tooling Plan

Merge the two `pyproject.toml` files instead of choosing one wholesale.

Target direction:

- Product package name: `earnings-debate-agent`.
- Product dependencies from the external repo remain.
- Dev dependencies include product test tooling plus foundation tools:
  `pytest`, `ruff`, `mypy`, `pyyaml`, `pydantic`, type stubs, and secret/hygiene
  check support.
- Preserve console script:
  `earnings-debate = "src.main:cli"`.
- Decide Python floor during implementation:
  - external product currently targets Python `>=3.11`
  - canonical foundation currently targets `>=3.12,<3.15`
  - prefer `>=3.12,<3.15` if foundation gates remain mandatory, unless
    assignment constraints require Python 3.11 compatibility.
- Ruff/mypy excludes should cover local caches, ignored data, outputs,
  archives, plugin payloads, and agent skill docs.

## Gitignore And Env Plan

Merged `.gitignore` must include at minimum:

- `.env`
- `.venv/`
- `__pycache__/`
- `.mypy_cache/`
- `.pytest_cache/`
- `.ruff_cache/`
- `.serena/`
- `.DS_Store`
- `*.pyc`
- `*.egg-info/`
- `samples/cache/`
- generated or local-only `outputs/` policy
- local data policy for `data/`, especially PDFs
- archive/backups that are not repo truth

Tracked environment documentation:

- Keep only `.env.example` and README setup instructions.
- Do not track `.env` or real API keys.
- Treat external `.env` as local runtime state. Copy it without inspecting
  contents only after `.gitignore` is confirmed to ignore `.env`.
- Run secret scanning before any merge is accepted.

## README Plan

Use the external repo's `README.md` as the root `README.md`.

Required polish after import:

- Update the submission repository URL if needed.
- Keep the investment-advice disclaimer prominent.
- Ensure setup commands match the merged toolchain.
- Ensure test commands match the merged Makefile/CI.
- Add a compact note that agent-development rules live in `AGENTS.md` and
  `docs/`, if needed without turning README into an agent manual.

## CI And Verification Plan

Initial local verification after merge conflict resolution:

1. `python -m pytest -q` or `uv run pytest -q`, depending on final toolchain.
2. `python -m ruff check .`
3. `python -m ruff format --check .`
4. `python -m mypy src tests`
5. Foundation structural checks that remain relevant:
   - contract/doc consistency tests
   - extension-surface integrity tests
   - repo hygiene checks
   - secret scanning
6. CLI smoke:
   `LLM_PROVIDER=fake earnings-debate run --api-url local --input-json samples/request.document-files.example.json --out <temp-output>`
7. Optional API smoke:
   start the FastAPI app locally and hit `POST /reviews` with a sample request.

CI direction:

- Consolidate duplicate external `ci.yml` and `pytest.yml` into one clear
  product/foundation quality workflow.
- Keep canonical remote unchanged.
- Do not add deployment, release, or external write behavior in this integration
  unless separately approved.

## Rollback Or Mitigation

- Perform all import work on a new `agent/*` integration branch.
- Do not alter canonical `origin`.
- Keep temporary `assignment-source` remote local-only.
- If root merge becomes too noisy, abort and fall back to prefix import under
  `app/earnings-debate-agent/`.
- If secret scanning reports committed secrets in external history, stop import
  and scrub/rewrite the external source before merging into canonical history.
- If external dirty state cannot be safely committed or snapshotted, import only
  the clean external branch and record the remaining dirty changes as follow-up.

## Human Gates And Open Questions

Human gate status:

- Planning-only write to `Plan/` is complete.
- Actual external import is not yet performed.
- Any rewrite of external history, secret cleanup, branch deletion, remote
  deletion, or CI/deployment-side effect needs explicit approval.

Open questions before implementation:

- Should the external uncommitted tracked changes be committed in the external
  repo first, or should the canonical import intentionally use only the external
  committed branch head?
- Should Python 3.11 compatibility be preserved for the internship evaluator,
  or can the integrated repo standardize on Python 3.12?
- Should generated `outputs/` examples stay tracked as submission evidence, or
  should only one compact example remain tracked?

## Next Implementation Steps

1. Resolve external dirty-state policy.
2. Create or use a canonical integration branch.
3. Add and fetch the external repo as a temporary local remote.
4. Run a pre-import secret scan against the external repo history and working
   tree, excluding ignored local runtime state.
5. Merge with unrelated histories and resolve conflicts according to this plan.
6. Run verification and update README/tooling until the repo is coherent.
7. Record changed paths, verification results, residual risk, and any follow-up
   in this Plan log.
