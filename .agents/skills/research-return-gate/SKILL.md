---
name: research-return-gate
summary: >
  Validate the current research surface against the app-flow research contract
  and emit the smallest concrete return payload instead of letting planner infer
  missing structure.
version: 0.1
status: draft
data_model_version: 0.1
description: >
  Use when `02-research.md` may be incomplete, stale, or too summary-heavy for
  planning to proceed safely. This skill checks required research surfaces,
  freshness, and evidence links, then returns the smallest missing artifact to
  the research lane.
---

# Skill: research-return-gate

## Purpose
Produce a `ResearchReturnGateResult` that either clears `02-research.md` for
planning or returns it with an explicit smallest-next-repair target.

## Non-goals
- Performing the missing research directly.
- Rewriting `03-plan.md` to compensate for weak research.
- Accepting prose-only summaries when the required research surfaces are absent.
- Deciding business direction beyond the research contract itself.

## Inputs

### Required
- `Apps/<app-slug>/artifacts/runtime/current-state.yaml`
- `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml`
- `02-research.md`

### Optional
- freshness window policy
- required-section override for an intentionally narrow slice
- linked evidence in `Raw/`, `Summaries/`, `Hypotheses/`, and `Reviews/`
- `10-log.md` when runtime packets flag blocker persistence or repeated returns

## Outputs

### Primary
- Format: `markdown`
- Type: `ResearchReturnGateResult`
- Required fields:
  - `verdict`
  - `missing_surfaces`
  - `freshness_gaps`
  - `retry_target`
  - `return_payload`
  - `evidence_refs`
  - `target_note_ids`

### Secondary
- Return or acceptance note in `10-log.md`

## Procedure
1. Read runtime packets first; only widen outward if the changed surfaces still
   do not explain the current state.
2. Validate `02-research.md` against the current research contract:
   - `Market Wedge`
   - `Functional Core Evidence`
   - `Differentiator vs Baseline`
   - `App Structure / Function Map Research`
   - `Technical Pattern / Stack Signal Research`
3. Check whether evidence links and freshness are strong enough for the current
   slice.
4. Emit one verdict:
   - `accepted`
   - `returned_for_revision`
   - `policy_missing`
5. If returned, name the smallest missing artifact first and produce a precise
   `return_payload` rather than a broad rewrite request.
6. Record the decision in `10-log.md` and point downstream roles at the same
   `target_note_ids`.

## Completion Criteria
- `verdict` is explicit.
- Missing surfaces are named precisely rather than as broad “do more research”.
- `retry_target` points to the smallest missing artifact first.
- Evidence and freshness gaps are separated from product judgment.
- The return packet gives planning enough structure to wait without guessing.

## Failure Modes
- **Planner inference disguised as acceptance**
  - Cause: summary prose is accepted even though required research surfaces are
    absent.
  - Countermeasure: fail on missing sections, not only on missing words.
- **Broad rewrite request**
  - Cause: the gate returns the whole research lane instead of the smallest
    missing surface.
  - Countermeasure: always emit `retry_target`.
- **Freshness and completeness are mixed**
  - Cause: stale evidence is treated the same as missing structure.
  - Countermeasure: keep `freshness_gaps` separate from `missing_surfaces`.
- **Return has no concrete next owner**
  - Cause: the gate reports a problem but does not say who fixes it next.
  - Countermeasure: include `return_payload` with next owner and target note ids.

## References
- `docs/specs/app-agentic-flow.md`
- `docs/specs/app-skill-registry.md`
- `docs/tasks/active/WORKFLOW-gap-consult-loop/skill-contract-minimums-report-2026-04-23.md`
- `app-research-skill-pack/README.md`
