# Plan_N0001 Log

Date: 2026-06-16

## Context

User requested that the current repository audit be preserved as a Plan and
integrated with:

- `Plan/harness-review/plans/dev_foundation_docs_integration_proposal.md`
- `Plan/harness-review/plans/dev-foundation-harness-docs-integrated.md`

## Audit Inputs

- Subagent audit of docs/templates reachability.
- Subagent audit of code/runtime entrypoints.
- Subagent audit of current contract harness workflow.
- Main-agent inspection of active docs, reference docs, templates, Makefile,
  pyproject, harness CLI, contract harness modules, and related tests.

## Result

Created `Plan/harness-review/plans/Plan_N0001.md` as the integrated cleanup
plan. The plan keeps the useful parts of the two source docs but changes the
execution direction from docs expansion to active surface cleanup.

## Key Decisions Captured

- Do not broaden active/reference docs.
- Remove or implement phantom harness CLI surfaces.
- Align role enforcement with emitted agent tools.
- Shrink default Writer packet.
- Keep Reviewer focused on diff and evidence.
- Do not expose reviewer-facing budget as a semantic anchor.
- Treat legacy heavy-contract retirement and demo adapter retirement as
  separate implementation slices.

## Verification

Not run in this logging-only step.

## Execution Update: 2026-06-16

Implemented the safe execution slice from Phase 1 through Phase 4:

- removed the parser-visible phantom `./harness rfc` command;
- kept RFC evidence creation through `./harness report --type rfc`;
- removed rejected/default-broad tools from Writer and Reviewer packets;
- kept measurement/eval tools discoverable through the explicit
  `./harness tools --profile measurement` path;
- moved `review-collect` visibility to Integrator tools;
- added reviewer packet diff path/hash/index instructions without exposing a
  reviewer-facing budget;
- bounded inline diff transfer and required artifact reads for large diffs;
- removed only unreferenced templates:
  - `templates/codex-hooks.json`
  - `templates/approved-spec-freeze.yaml`

Deferred by plan stop conditions:

- `templates/context-request.yaml`
- `templates/context-result.yaml`
- legacy heavy-contract retirement
- demo adapter retirement

Verification:

- `uv run pytest -q tests/workflow_core/test_contract_harness.py`: passed,
  38 tests.
- `uv run ruff format --check src/workflow_core/contract_harness/cli.py
  src/workflow_core/contract_harness/agent_tools.py
  src/workflow_core/contract_harness/semantic_review.py
  tests/workflow_core/test_contract_harness.py`: passed.
- `uv run ruff check src/workflow_core/contract_harness/cli.py
  src/workflow_core/contract_harness/agent_tools.py
  src/workflow_core/contract_harness/semantic_review.py
  tests/workflow_core/test_contract_harness.py`: passed.
- `uv run pytest -q tests/test_foundation_integrity.py -k
  "required_contract_files_exist or reference_set_matches_routed_reference_docs
  or doc_consistency_specification_subagent_workflow_is_routed_and_compact"`:
  passed, 3 tests.
- `make check-doc-consistency`: passed, 4 tests.
- `uv run pytest -q tests/test_foundation_integrity.py
  tests/test_clean_checkout_reproducibility.py`: failed on pre-existing
  tracked/index state:
  - tracked nonconforming
    `Plan/harness-review/plans/ideal-workflow-bottleneck-acceptance.md`;
  - tracked top-level `harness` not yet included in the local allowlist;
  - untracked `.agents/skills/implementation-slice-verification/SKILL.md`
    present in the worktree but absent from `git ls-files`.

## Execution Update: 2026-06-16 Archive Expansion

Archived dead active surfaces under local ignored storage:

- `archive/harness-review-dead-surface-20260616/`

Moved out of active repo truth:

- workflow UI app and package:
  - `app/workflow_console/`
  - `src/workflow_ui/`
- Codex SDK / App Server / CommonDB demo adapters:
  - `src/workflow_adapters/codex_sdk_adapter.py`
  - `src/workflow_adapters/codex_app_server_adapter.py`
  - `src/workflow_adapters/commondb_context_adapter.py`
- demo runner/checker scripts:
  - `scripts/run-approved-work-contract.py`
  - `scripts/check-demo-workflow.py`
- workflow-ui project records and artifacts:
  - `Plan/workflow-ui-commondb-20260608/`
  - `artifact/workflow-ui-commondb-20260608/`
- template-only and heavy-contract surfaces, including app-server, SDK,
  context-request/result, context-scope manifest, hook settings, handoff,
  convergence, traceability, audit, operational scorecard, and related record
  templates.
- tests that existed only to validate the archived demo/template surfaces:
  - `tests/workflow_ui/`
  - `tests/workflow_adapters/`
  - `tests/workflow_core/test_demo_fixture.py`
  - `tests/workflow_core/test_approved_work_contract.py`

Kept active:

- default lightweight templates;
- `work-contract`, `evidence-record`, `verification-record`, `rework-record`,
  `project-storage-map`, `parallel-lane-map`;
- local restore templates `serena-project.yml` and
  `codex-config.toml.example`;
- `src/workflow_adapters/mock_runtime.py`, because it backs local eval/runtime
  tests.

Synchronized active registries and references:

- `README.md` no longer routes to workflow-ui artifact docs.
- `templates/README.md` states archived template surfaces are no longer active.
- `docs/reference/harness-observability-reference.md` no longer points at an
  active hook-settings template.
- `.agents/skills/scope-routing-governance/SKILL.md` no longer requires
  `templates/context-scope-manifest.yaml`.

Verification:

- `make check-skill-routes`: passed.
- `make check-doc-consistency`: passed.
- `uv run pytest -q tests/workflow_core/test_runtime_port.py
  tests/test_system_design_integrity.py tests/test_lane_map_check.py
  tests/test_context_scope_check.py tests/workflow_core/test_state_transitions.py
  tests/workflow_core/test_checks.py tests/test_contract_models.py`: passed,
  63 tests.
- `make check-fast`: passed.
- `uv run pytest -q`: failed only on pre-existing tracked/index state:
  - untracked `.agents/skills/implementation-slice-verification/SKILL.md`;
  - tracked nonconforming
    `Plan/harness-review/plans/ideal-workflow-bottleneck-acceptance.md`;
  - tracked top-level `harness` not yet included in local allowlist.
