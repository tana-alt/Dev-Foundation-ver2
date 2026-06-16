# Plan_N0001: Harness Active Surface Cleanup Integrated Plan

Date: 2026-06-16
Project: `harness-review`
Status: draft

## Objective

Integrate the two existing harness docs with the current repository audit into
one executable cleanup plan.

The goal is not to add more active documentation. The goal is to reduce the
agent-facing surface so Writer, Reviewer, and Integrator receive only the
minimum task-relevant contract, diff, tools, and evidence needed to act.

This plan supersedes direct execution of these two plan drafts:

- `Plan/harness-review/plans/dev_foundation_docs_integration_proposal.md`
- `Plan/harness-review/plans/dev-foundation-harness-docs-integrated.md`

Both drafts remain useful as source material, but their docs-expansion parts are
not the preferred execution path.

## Source Inputs

- Current user direction: do not broaden docs; old active/reference/template
  surfaces are already too large.
- Current user direction: reviewer packet should guide review of the diff and
  evidence, not hand the reviewer a `budget` that can become an excuse.
- Read-only subagent audit of docs/templates.
- Read-only subagent audit of code/runtime entrypoints.
- Read-only subagent audit of current contract harness workflow.
- Local inspection of `AGENTS.md`, `docs/01-03`, `docs/reference/`,
  `templates/`, `Makefile`, `pyproject.toml`, `harness`,
  `src/workflow_core/contract_harness/`, and related tests.

## Integrated Decision

Do not solve the harness problem by adding more reference docs.

Instead:

1. Make the active harness surface match implemented behavior.
2. Remove phantom commands and tool-role mismatches.
3. Shrink default Writer and Reviewer packets.
4. Keep detailed or optional tools outside the default packet.
5. Retire dead templates and stale docs from active registries.
6. Treat legacy heavy-contract compatibility as a separate retirement stream.

## What To Preserve

- `AGENTS.md` remains the goal-first routing entrypoint.
- `docs/01-agent-operating-contract.md`,
  `docs/02-output-verification-contract.md`, and
  `docs/03-repo-boundary-and-storage-contract.md` remain the only always-read
  active docs.
- Reference docs remain open-by-need only.
- `./harness` remains the contract harness CLI.
- Machine verification remains the first gate before semantic review.
- Semantic review remains valuable, but it should interpret diff and evidence,
  not override failed machine gates.
- Worktree separation and merge/push safety remain active behavior.

## What Changes From The Two Source Docs

### Adopt

- Active surface / bootstrap must be reliable.
- Role/tool consistency must be machine checked.
- Phantom `rfc` CLI surface must be removed or implemented.
- Machine evidence, candidate diff hash, scope map, quality evidence, tool
  candidates, mutation evidence, and metric evidence should be available to
  reviewers when relevant.
- Writer and Reviewer packets should show tool availability thinly and
  explicitly.
- Dead docs/templates/code should be identified by reachability and tests.

### Modify

- Do not add new reference-doc sections as the first implementation step.
- Do not make `context_manifest.budget` a reviewer-facing semantic anchor.
- Do not treat packet byte budgets as proof that context is sufficient.
- Do not require full `docs/reference/` or full `templates/` to be visible to
  agents.
- Do not keep archived heavy-contract templates in the active-required registry
  merely because they exist.

### Do Not Adopt

- Broad docs integration into active/reference docs.
- Default gate broadening with AB or benchmark flows.
- Reviewer approval overriding failing machine gates.
- Runtime queues, dashboards, lock ledgers, or broad operational logs.
- Budget language that gives a semantic reviewer a reason to ignore missing
  diff/evidence.

## Current Audit Findings

### Harness Surface

- `./harness rfc` is registered by the parser but has no dispatch handler. It
  falls through to `deferred_in_mvp`. This is a phantom active command.
- Reviewer tools advertise `review-collect`, but role policy allows
  `review:collect` only for Integrator. This is a role/tool mismatch.
- Writer capsule currently exposes measurement and eval tools such as `abrun`,
  `check-runner`, `measure-eval`, and `surface-issues` by default.
- Reviewer packet currently includes full `candidate_diff`,
  `candidate_diff_path`, `candidate_diff_index`, full capsule, full contract,
  review workspace, reverse scope map, verify result, mutation result, quality
  result, tool candidates, metric evidence, reviewer policy, and test
  interpretation.
- Reviewer packet does not currently expose a `context_manifest.budget`; that
  planned shape exists only in the draft plan.

### Docs And Templates

- Default templates are documented as:
  - `templates/goal-brief.md`
  - `templates/mini-spec.md`
  - `templates/detailed-spec.md`
  - `templates/task-packet.yaml`
  - `templates/verification-note.md`
- Heavy-contract templates are described as archived/non-default, but many are
  still required by `tests/test_foundation_integrity.py`.
- `docs/reference/agent-operationalization-reference.md` and
  `docs/reference/agent-operationalization-95-hardening-reference.md` are not
  routed by `AGENTS.md`, but are retained as legacy reference docs in tests.
- Zero-reference or near-zero-reference template candidates:
  - `templates/codex-hooks.json`
  - `templates/context-request.yaml`
  - `templates/context-result.yaml`
  - `templates/approved-spec-freeze.yaml`

### Code And Demo Surfaces

- `workflow_core.contract_harness` and metric/eval CLIs are active through
  tests and current harness work. Do not delete them.
- `workflow_adapters.mock_runtime` is active through `make eval`.
- Codex App Server adapter, Codex SDK runner, `workflow_ui`, and CommonDB demo
  validator are test/demo-backed but not current harness runtime entrypoints.
  Treat them as one product decision: keep as demo evidence, or retire code,
  tests, templates, and artifact references together.
- Legacy operational check scripts are still exposed through Make targets. They
  are not dead until the legacy compatibility surface is retired.

## Semantic Reviewer Packet Decision

The Reviewer should receive enough to review the actual change:

- candidate diff path
- candidate diff hash
- candidate diff index
- verify result
- mutation result when configured
- quality result
- tool candidates when present
- metric evidence when present
- reverse scope map as advisory impact evidence
- reviewer policy focused on diff/evidence interpretation

The Reviewer should not receive `budget` as a semantic excuse.

If the harness must truncate or omit material, the packet should mark the review
as incomplete or require artifact reads. The reviewer should not be invited to
decide that a byte budget was enough. Missing required diff/evidence is a
machine condition, not a semantic shortcut.

Preferred shape:

```json
{
  "candidate_diff_path": ".../candidate.diff",
  "candidate_diff_sha256": "sha256:...",
  "candidate_diff_index": {},
  "diff_instruction": "Review the diff and evidence. If required diff or evidence is absent, block.",
  "omitted_required_evidence": [],
  "requires_artifact_read": false
}
```

Avoid:

```json
{
  "context_manifest": {
    "budget": {
      "max_bytes": 65536,
      "actual_bytes": 32000,
      "truncated": false
    }
  }
}
```

Budget can remain an internal harness implementation detail if needed for
resource safety. It should not become a reviewer-facing judgment anchor.

## Implementation Phases

### Phase 0: Preserve This Plan

Add this plan and its log/index entry only.

Verification:

```sh
uv run pytest -q tests/test_foundation_integrity.py -k "plan_project_records or tracked_top_level"
```

Expected:

- The plan file is in `Plan/harness-review/plans/Plan_N0001.md`.
- The matching log is in `Plan/harness-review/logs/Plan_N0001.log.md`.
- `Plan/harness-review/index.yaml` exists.
- If these files are tracked later, the plan/log/index convention remains CI
  compatible.

### Phase 1: Active Harness Surface Consistency

Acceptance tests first:

- `./harness` help does not expose unimplemented active commands.
- A command listed in `agent_tools` is executable by the listed role, or is
  explicitly marked template-only and not emitted in the default packet.
- Reviewer default tools do not include commands rejected by Reviewer role.
- `report --type rfc` remains available as RFC evidence if needed.

Implementation:

- Remove the parser-visible `rfc` command unless implementing real RFC
  decision processing in the same slice.
- Remove `review-collect` from Reviewer default tools, or allow
  `review:collect` for Reviewer. The minimal-context preference is removal from
  Reviewer default tools.
- Keep Integrator responsible for collecting reviewer verdict state.

Target files:

- `src/workflow_core/contract_harness/cli.py`
- `src/workflow_core/contract_harness/agent_tools.py`
- `src/workflow_core/contract_harness/roles.py`
- `tests/workflow_core/test_contract_harness.py`

Verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "role_boundaries or agent_tool"
```

### Phase 2: Writer Packet Minimization

Acceptance tests first:

- Default Writer packet includes only:
  - `scope-map-forward`
  - `explain`
  - `verify`
  - `submit`
  - necessary `report-*` evidence commands
- Default Writer packet does not include broad measurement/eval tools such as
  `abrun`, `check-runner`, `measure-eval`, or `surface-issues`.
- Optional measurement tools remain discoverable only through an explicit
  profile or non-default command if still needed.

Implementation:

- Split default tools from optional measurement tools.
- Update `prepare` / capsule tests that currently pin the broad tool list.
- Keep tool commands absolute/runnable from `.harness` worktrees.

Target files:

- `src/workflow_core/contract_harness/agent_tools.py`
- `src/workflow_core/contract_harness/contract.py`
- `tests/workflow_core/test_contract_harness.py`

Verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "capsule or tools or explain"
```

### Phase 3: Reviewer Packet Diff/Evidence Contract

Acceptance tests first:

- Reviewer packet includes `candidate_diff_path`, `candidate_diff_sha256`, and
  `candidate_diff_index`.
- Reviewer packet includes verification, quality, tool candidate, mutation, and
  metric evidence summaries when present.
- Reviewer packet does not expose a reviewer-facing `budget` field.
- If required diff/evidence is missing or omitted, the packet marks review as
  incomplete or requires artifact reads.
- Reviewer policy says to review diff/evidence and block on missing required
  material.

Implementation:

- Keep or add explicit diff/evidence instructions.
- Add omission/incomplete fields only as machine conditions, not budget
  discretion.
- Bind any new packet freshness fields into reviewer evidence freshness only if
  they affect review correctness.

Target files:

- `src/workflow_core/contract_harness/semantic_review.py`
- `src/workflow_core/contract_harness/evidence.py`
- `src/workflow_core/contract_harness/review.py`
- `tests/workflow_core/test_contract_harness.py`

Verification:

```sh
uv run pytest -q tests/workflow_core/test_contract_harness.py -k "semantic_reviewer or reviewer_packet"
```

### Phase 4: Safe Dead Template Cleanup

Acceptance tests first:

- Deleted templates are not listed in the active template registry.
- `rg` finds no active references to deleted paths.
- `templates/README.md` does not claim deleted templates exist.

Initial deletion candidates:

- `templates/codex-hooks.json`
- `templates/context-request.yaml`
- `templates/context-result.yaml`
- `templates/approved-spec-freeze.yaml`

Target files:

- `templates/`
- `templates/README.md`
- `tests/test_foundation_integrity.py`
- `tests/test_clean_checkout_reproducibility.py`

Verification:

```sh
uv run pytest -q tests/test_foundation_integrity.py tests/test_clean_checkout_reproducibility.py
make check-doc-consistency
```

### Phase 5: Legacy Heavy-Contract Retirement

Do this as a separate PR or implementation slice.

Candidate surfaces:

- `docs/reference/agent-operationalization-reference.md`
- `docs/reference/agent-operationalization-95-hardening-reference.md`
- final handoff templates
- convergence templates
- traceability templates
- source snapshot templates
- operational scorecard templates
- residual-risk carryover templates
- review/fix/convergence checker scripts
- `check-legacy-contracts` Make target
- related tests and fixtures

Acceptance tests first:

- `AGENTS.md` says to avoid heavy-contract surfaces, and tests no longer
  require them as active tracked files.
- Default gates do not require retired legacy checkers.
- Any retained legacy material is not active agent-facing context.

Verification:

```sh
uv run pytest -q tests/test_foundation_integrity.py tests/test_clean_checkout_reproducibility.py
make check-fast
```

### Phase 6: Demo Adapter Product Decision

Do not mix this with harness packet cleanup unless the scope is explicitly to
retire demo surfaces.

Decision required:

- Keep Codex App Server / SDK / workflow UI / CommonDB demo as demo evidence.
- Or retire code, tests, templates, and artifact references together.

If retiring, target as one coordinated slice:

- `src/workflow_adapters/codex_app_server_adapter.py`
- `src/workflow_adapters/codex_sdk_adapter.py`
- `src/workflow_adapters/commondb_context_adapter.py`
- `src/workflow_ui/`
- `app/workflow_console/`
- `scripts/run-approved-work-contract.py`
- `scripts/check-demo-workflow.py`
- app-server / codex-sdk templates
- related tests and artifact references

Verification:

```sh
uv run pytest -q tests/workflow_adapters tests/workflow_ui tests/test_foundation_integrity.py
make test
```

## Recommended Execution Order

1. Phase 1: active CLI/tool/role consistency.
2. Phase 2: Writer packet minimization.
3. Phase 3: Reviewer diff/evidence packet cleanup.
4. Phase 4: safe zero-reference template deletion.
5. Phase 5: legacy heavy-contract retirement.
6. Phase 6: demo adapter product decision.

This order fixes actual harness behavior before broad repository deletion.

## Done Criteria For Cleanup Stream

- No default agent packet exposes stale or rejected commands.
- No default agent packet requires reading all docs/reference or templates.
- Reviewer packet anchors review on diff and machine evidence, not a byte
  budget.
- Phantom CLI commands are gone or implemented.
- Role/tool listings match role enforcement.
- Zero-reference templates are removed or explicitly justified.
- Legacy heavy-contract material is no longer active-required unless explicitly
  retained for compatibility.
- `make test` passes for implementation slices.
- `make check-required` passes before PR or external handoff.

## Stop Conditions

Stop and ask before:

- deleting demo adapter surfaces if their product role is still wanted;
- deleting legacy heavy-contract compatibility tests without accepting that
  archive/audit compatibility is retired;
- changing external write, push, rollback, or protected branch behavior;
- adding new docs/reference sections as a workaround for unclear behavior;
- making reviewer-facing budgets a substitute for missing diff/evidence.
