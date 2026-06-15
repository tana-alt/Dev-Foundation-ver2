# Ideal Workflow Bottleneck Acceptance

## Objective

Make the contract harness robust for the intended writer -> reviewer ->
integrator workflow before optimizing implementation details.

The tests below are acceptance tests for the ideal workflow. They are allowed to
fail before implementation. A failure is a bottleneck diagnosis, not a reason to
weaken the workflow.

## Design Decisions

1. Writer startup evidence is part of the task packet.
   The writer must see runnable tools and relevant skills before editing. Tool
   commands must work from the project `.harness` directory because that is the
   intended terminal entry point.

2. Writer submit does not perform integration inside the writer workspace.
   `submit --wait` may trigger integration, but integration must run in an
   integrator workspace and write handoff evidence that records the source
   writer workspace and integration workspace.

3. Reviewer context is a packet, not inherited chat context.
   The semantic reviewer must receive writer handoff evidence, test
   interpretation, tool and skill lists, reverse scope evidence, and a compact
   diff index. Full diff may remain available by path.

4. Integrator worktree must stay reusable after dispatch.
   Machine/review evidence produced during dispatch must not dirty the
   integrator worktree or cause `land` to fail on worktree reuse.

## Acceptance Tests

- Smoke:
  `tests/workflow_core/test_contract_harness.py::test_prepare_capsule_exposes_existing_agent_tool_set`

  Pass criteria: capsule contains writer tools, writer skills, reviewer and
  integrator skill packets, and a writer tool command can be executed from
  `.harness`.

- CLI:
  `tests/workflow_core/test_contract_harness.py::test_submit_wait_dispatches_in_integrator_boundary`

  Pass criteria: submit from a sealed writer worktree with `--wait` dispatches
  from an integrator worktree, not from the writer worktree, and writes
  `integrator-handoff.json`.

- E2E packet:
  `tests/workflow_core/test_contract_harness.py::test_e2e_semantic_reviewer_receives_writer_handoff_diff_index_tools_and_skills`

  Pass criteria: semantic reviewer can approve based on writer handoff,
  diff-index, reviewer tools, reviewer skills, and generated verification
  evidence without inherited chat context.

- E2E land:
  `tests/workflow_core/test_contract_harness.py::test_e2e_integrator_dispatch_then_land_keeps_integrator_worktree_reusable`

  Pass criteria: integrator dispatch succeeds, leaves the integrator worktree
  clean, and `land` reuses that worktree successfully.

## Bottleneck Mapping

- Missing `agent_skills` or non-runnable tool command:
  tool visibility exists only as documentation, not as an executable writer
  startup packet.

- Missing `integration_workspace` or `integrator-handoff.json`:
  `submit --wait` collapses writer and integrator boundaries.

- Missing `writer_handoff` or `candidate_diff_index` in reviewer packet:
  semantic reviewer depends on inherited context or full diff scanning.

- Dirty integrator worktree after dispatch:
  machine evidence writes into a merge workspace and makes later land fragile.

## Implementation Guardrails

- Do not loosen role enforcement to make tests pass.
- Do not mark these tests xfail.
- Do not move scope ownership into policy; policy remains shared goal,
  constraints, and bottlenecks.
- Keep machine gates factual. Semantic judgement remains reviewer-owned.
- Preserve existing deterministic reviewer behavior while adding semantic
  packet evidence.
