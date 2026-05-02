---
name: planning-stronger-monetization
summary: >
  Convert research-backed pricing, paywall, and monetization observations into
  a planner-ready addendum without inventing unsupported commercial or legal
  decisions.
version: 0.1
status: draft
data_model_version: 0.1
description: >
  Use when planner needs a stronger monetization lane, especially for pricing
  posture, paywall timing, regional differences, and downstream UX or release
  implications. This skill strengthens planning inputs but must not invent
  pricing or compliance certainty from zero-shot reasoning.
---

# Skill: planning-stronger-monetization

## Purpose
Produce a `MonetizationPlanningAddendum` that turns research-backed pricing and
paywall evidence into planner-readable assumptions, open questions, and
downstream implications.

## Non-goals
- Final pricing approval.
- Legal or compliance signoff.
- Generating a new business model without external evidence.
- Hiding unsupported monetization guesses inside polished planner prose.

## Inputs

### Required
- `Apps/<app-slug>/artifacts/runtime/current-state.yaml`
- `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml`
- `02-research.md`
- `03-plan.md`

### Optional
- `09-decisions.md`
- evidence linked from `app-dev-research` or `market-*` outputs
- locale / segment policy when already fixed
- release assumptions in `08-release.md`

## Outputs

### Primary
- Format: `markdown`
- Type: `MonetizationPlanningAddendum`
- Required fields:
  - `pricing_posture`
  - `paywall_timing_assumptions`
  - `region_caveats`
  - `compliance_touchpoints`
  - `ux_and_release_implications`
  - `open_policy_questions`
  - `evidence_refs`
  - `target_note_ids`

### Secondary
- Short planner note update in `03-plan.md`
- optional decision write in `09-decisions.md` when a monetization decision is
  already human-approved

## Procedure
1. Read runtime packets first and stay on the active planner/research surfaces.
2. Gather monetization evidence from `02-research.md`, especially pricing,
   paywall timing, regional differences, and failure signals.
3. Separate:
   - observed evidence
   - supported inference
   - unresolved policy questions
4. Write the addendum so planner can pass downstream implications to UX,
   release, and compliance without guessing.
5. If a claim is not evidence-backed, leave it in `open_policy_questions` rather
   than normalizing it into a plan.
6. Record the update in `10-log.md` if the addendum changes downstream scope,
   release assumptions, or role responsibilities.

## Completion Criteria
- Every monetization claim is either evidence-backed or explicitly marked as an
  unresolved policy question.
- `paywall_timing_assumptions` and `region_caveats` are not collapsed into one
  generic global rule unless evidence supports that collapse.
- UX and release implications are named explicitly.
- The addendum does not replace `03-plan.md`; it strengthens it.

## Failure Modes
- **Pricing is invented**
  - Cause: planner pressure turns weak signals into hard pricing decisions.
  - Countermeasure: keep unsupported items under `open_policy_questions`.
- **Paywall timing is flattened across locales**
  - Cause: one region or platform is treated as global truth.
  - Countermeasure: keep `region_caveats` explicit.
- **Compliance certainty is implied**
  - Cause: the addendum sounds final about legal/compliance posture.
  - Countermeasure: describe only touchpoints and open approvals.
- **Downstream impact is omitted**
  - Cause: pricing notes are written without UX or release consequences.
  - Countermeasure: require `ux_and_release_implications`.

## References
- `.agents/skills/app-prd-gate/SKILL.md`
- `app-research-skill-pack/skills/app-dev-research/SKILL.md`
- `app-research-skill-pack/skills/app-dev-research/references/paywall-taxonomy.md`
- `docs/specs/app-agentic-flow.md`
- `docs/tasks/active/WORKFLOW-gap-consult-loop/skill-contract-minimums-report-2026-04-23.md`
