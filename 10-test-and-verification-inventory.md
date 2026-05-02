---
status: draft
owner: foundation
source_of_truth_level: distilled
created_at: 2026-05-02
source_refs:
  - Makefile
  - pyproject.toml
  - .github/workflows/ci.yml
  - docs/workflows/git-test-policy.md
  - docs/workflows/build-test-pr.md
  - docs/evals/regression.md
  - src/services/verification/
  - tests/unit/
---

# Test And Verification Inventory

This document extracts the test and verification system currently present in
this repo.

## Command Surface

The main local command surface is `Makefile`.

Core commands:

- `make lint`: runs `uv run ruff check .`
- `make format`: runs `uv run ruff format .`
- `make typecheck`: runs `uv run mypy apps src tests`
- `make test`: runs `uv run pytest`
- `make check-architecture`: runs `uv run python -m src.services.verification.cli architecture`
- `make check-doc-freshness`: runs `uv run python -m src.services.verification.cli doc-freshness`
- `make check-dangerous-diff`: runs `uv run python -m src.services.verification.cli dangerous-diff`
- `make check-harness-runtime`: runs `uv run python -m src.services.verification.cli harness-runtime`
- `make check-repo-profiles`: runs `uv run python scripts/repo_profiles/check_profile_contracts.py`
- `make check-required`: chains lint, typecheck, test, architecture,
  doc-freshness, dangerous-diff, and repo-profile checks.

## CI Surface

GitHub Actions are defined in `.github/workflows/ci.yml`.

Current CI jobs:

- `ruff`: installs with `uv sync --frozen --group dev`, then runs `uv run ruff check .`
- `mypy`: installs with `uv sync --frozen --group dev`, then runs `uv run mypy apps src tests`
- `pytest`: installs with `uv sync --frozen --group dev`, then runs `uv run pytest`
- `architecture-check`: installs with `uv sync --frozen --group dev`, then runs
  `uv run python -m src.services.verification.cli architecture`

Local deterministic checks are broader than CI. The git/test policy explicitly
notes that CI does not run every local deterministic check, so skipped or failing
checks must be recorded with command, result, and pre-existing status.

## Python Tooling

Defined in `pyproject.toml`:

- Python: `>=3.12,<3.13`
- test runner: `pytest`
- lint/format: `ruff`
- type checker: `mypy`
- mypy mode: `strict = true`
- mypy packages: `apps`, `src`
- pytest testpaths: `tests`
- coverage source: `apps`, `src`

The repo uses Pydantic heavily for schema and state contracts, but the main
typing policy is expressed through strict mypy, schema validators, backend
instructions, and contract tests rather than a single dedicated Pydantic policy
document.

## Verification Service

The verification implementation lives in `src/services/verification/`.

Main entry:

- `src/services/verification/cli.py`

CLI checks:

- `architecture`
- `doc-freshness`
- `dangerous-diff`
- `harness-runtime`

Service layer:

- `VerificationService.run_all`
- `run_lint_check`
- `run_typecheck_check`
- `run_test_check`
- `run_architecture_check`
- `run_dangerous_diff_check`
- `run_doc_freshness_check`
- `run_harness_runtime_check`

Important detail: `run_lint_check`, `run_typecheck_check`, and `run_test_check`
currently confirm that commands are configured. The actual execution happens
through Makefile, CI, or direct shell commands. The custom executable checks are
architecture, doc freshness, dangerous diff, and harness runtime validation.

## Custom Deterministic Checks

### Architecture Check

Implemented in `src/services/verification/service.py`.

It parses Python files with `ast` and enforces dependency direction:

- `src/db` must not import `src.graph` or `apps`
- `src/graph` must not import `apps`
- `src/services` must not import `apps`

Ignored roots:

- `.venv`
- `third_party`
- `node_modules`

### Doc Freshness Check

Implemented in `src/services/docs/freshness.py`.

It checks tracked markdown files for frontmatter, validation freshness, related
code references, and local link validity.

### Dangerous Diff Check

Implemented in `src/services/git/dangerous_diff.py` and fed by
`src/services/git/status.py`.

It classifies changed files and flags protected areas such as infra, secrets,
CI/CD, auth, billing, and deployment-sensitive surfaces.

### Harness Runtime Check

Implemented through `VerificationService.run_harness_runtime_check` and
validators in `src/services/verification/app_packet_contracts.py`.

It validates runtime artifacts and contract surfaces, including:

- harness contract artifacts
- content generation harness artifacts
- context scope artifact
- project runtime management artifacts
- agent runtime spec artifacts

## Contract Validators

`src/services/verification/app_packet_contracts.py` is the largest contract
validator module. It validates packet schemas, app workflow notes, runtime maps,
dry-run datasets, release evidence, remediation loops, and phase status
semantics.

Notable validator groups:

- `validate_packet_schema`
- `validate_harness_packet_payload`
- `validate_harness_contract_artifacts`
- `validate_content_generation_harness_artifacts`
- `validate_context_scope_artifact`
- `validate_project_runtime_management_artifacts`
- `validate_agent_runtime_spec_artifacts`
- `validate_planner_contract_surfaces`
- `validate_runtime_packet_artifacts`
- `validate_storage_map_artifacts`
- `validate_scaffold_backend_contract`
- `validate_planner_bundle_artifact`
- `validate_release_bundle`

`src/services/verification/app_agent_contracts.py` validates role prompt
surfaces and can run stateless agent contract evaluations. It expects responses
to return structured JSON with role summary, read surfaces, write targets, input
requirements, repair strategy, handoff outputs, and extension points.

`src/services/verification/ui_reference_pack.py` validates and optionally
materializes UI reference-pack evidence.

## Test Suite Inventory

All active test files are under `tests/unit/`. `tests/integration/` currently
contains only `.gitkeep`.

### API And Workflow

- `test_api.py`: API health, catalog, workflow CRUD, workflow run/chat,
  execution footer repair, loop/parallel visibility, knowledge/Obsidian API,
  Multica runtime bindings, voice inbox, TaskQuest demo, billing and privacy.

### App Agent And Packet Contracts

- `test_app_agent_contracts.py`: app agent contract loading, prompt coverage,
  stateless prompt extraction, response parsing, agent eval behavior.
- `test_app_packet_contracts.py`: packet contracts, runtime packet artifacts,
  planner/storage/scaffold contracts, harness runtime maps, dry-run dataset
  behavior, access matrix scoping, policy docs, release bundle semantics,
  remediation loop, phase status semantics.

### Services And Integrations

- `test_codex_cli_service.py`: Codex CLI chat service, missing binary/auth/model
  errors, backend selection, session resume behavior.
- `test_multica_client.py`: Multica issue/task/comment/project/agent APIs,
  auth headers, retries, and HTTP errors.
- `test_openai_service.py`: Codex auth path and OAuth fallback policy.
- `test_social_publish_service.py`: SNS auth request, connector inventory,
  dry-run publish, credential exclusion, live-publish gates.
- `test_knowledge_service.py`: Onyx/local search behavior and raw record creation.
- `test_knowledge_filesystem.py`: vault-to-knowledge mirror sync.

### Core State And Graph

- `test_langgraph_core.py`: delegated/supervised graph runs, human review stop,
  resume after approval, dangerous diff fallback.
- `test_state_machine.py`: state transition rules, invalid jumps, plan path
  requirement, mode changes, dangerous diff and repeated failure fallback.
- `test_execution_parser.py`: execution footer parsing.

### Verification And Repo Maintenance

- `test_verification_services.py`: dangerous diff, architecture check, knowledge
  steward checks, aggregate verification service behavior.
- `test_docs_freshness.py`: missing frontmatter and stale related code detection.
- `test_git_status.py`: git status and diff-base changed-file collection.
- `test_repo_profile_bootstrap.py`: profile repo bootstrap and overwrite guard.
- `test_repo_profile_export.py`: profile export and overwrite guard.
- `test_repo_profile_contracts.py`: profile contract validation.
- `test_system_dry_run.py`: dry-run formulas, 59-day samples, strategy layers,
  LLM post handling, JSON fallback, model profile config.
- `test_ui_reference_pack.py`: UI reference asset materialization and evidence
  validation.

## Development Policy Docs

Copied source docs are available in `foundation/source-docs/ci-cd/`.

Most important docs:

- `docs/workflows/git-test-policy.md`: short verification and human gate policy.
- `docs/workflows/build-test-pr.md`: detailed implementation-to-PR workflow.
- `docs/evals/regression.md`: unit, deterministic, rubric, trace, and offline
  regression layer definitions.
- `.github/instructions/infra.instructions.md`: CI/CD and infra change approval
  rule.
- `.github/pull_request_template.md`: PR evidence fields.

## Extracted Principles

- Run the smallest relevant test first, then widen.
- Treat CI as machine truth for merge, not as the only local quality gate.
- Keep deterministic checks separate from LLM/rubric evals.
- Record skipped, blocked, or pre-existing failures explicitly.
- Keep schema and contract changes synchronized with specs and task docs.
- Use strict typing and Pydantic/schema validators to make contracts executable.
- Protect infra, auth, billing, secret, deployment, DB, and CI/CD changes with a
  human gate.
