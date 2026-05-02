---
name: research-coordinator
summary: >
  Normalize a natural-language research brief, route it into the existing
  research lane, and return one synthesis packet instead of a loose swarm of
  unrelated prompts.
version: 0.1
status: draft
data_model_version: 0.1
description: >
  Use when a user or planner gives a broad natural-language research request and
  the existing research skills need a single coordinator. This skill chooses the
  right research lane, creates a normalized brief, and keeps evidence quality
  and open questions explicit.
---

# Skill: research-coordinator

## Purpose
Produce a `ResearchCoordinationBrief` that routes one natural-language research
ask into the existing research lane and returns a single normalized synthesis
surface.

## Non-goals
- Replacing the underlying research skills.
- Inventing evidence when the brief is weak or the sources are stale.
- Starting a broad multi-agent swarm by default.
- Hiding open questions inside a polished recommendation.

## Inputs

### Required
- natural-language research request
- app slug, project, or target topic

### Optional
- regions
- platforms
- freshness window
- existing `02-research.md`
- existing `Raw/`, `Summaries/`, `Hypotheses/`, or `Reviews/` refs

## Outputs

### Primary
- Format: `markdown`
- Type: `ResearchCoordinationBrief`
- Required fields:
  - `normalized_scope`
  - `recommended_lanes`
  - `route_plan`
  - `open_questions`
  - `evidence_gaps`
  - `target_note_ids`

### Secondary
- Handoff packet for the chosen research lane
- optional synthesis update in `02-research.md`

## Procedure
1. Normalize the user brief into scope, region, platform, evidence horizon, and
   desired outcome.
2. Choose the smallest suitable existing lane:
   - `app-dev-research`
   - `market-opportunity-research`
   - `market-chokepoint-research`
   - `synthesize-feedback-signals`
3. Keep route choice explicit in `recommended_lanes` and `route_plan`.
4. Separate hard evidence needs from open strategy questions.
5. If the brief is too broad or stale, emit `evidence_gaps` and narrow the ask
   before routing.
6. Return one synthesis surface with `target_note_ids` so planner and research
   roles can stay aligned.

## Completion Criteria
- The normalized scope is specific enough for one or more existing research
  skills to run.
- Chosen lanes are explicit and justified.
- Open questions and evidence gaps are separated from observed findings.
- The output names where the synthesis lands next.
- The coordinator never replaces missing evidence with prose confidence.

## Failure Modes
- **Coordinator becomes the researcher**
  - Cause: it tries to answer the whole brief itself.
  - Countermeasure: route into existing research skills and keep the coordinator
    focused on normalization and synthesis.
- **Broad swarm by default**
  - Cause: multiple lanes are launched without a bounded route plan.
  - Countermeasure: choose the smallest sufficient lane set.
- **Stale or weak evidence is hidden**
  - Cause: route planning ignores freshness and evidence quality.
  - Countermeasure: emit `evidence_gaps` before synthesis.
- **No landing surface**
  - Cause: outputs exist only as chat guidance.
  - Countermeasure: always name the target note or packet.

## References
- `docs/specs/app-planner-agent-contracts.md`
- `docs/specs/app-skill-registry.md`
- `app-research-skill-pack/README.md`
- `app-research-skill-pack/SKILL_REFERENCE_MAP.md`
- `docs/tasks/active/WORKFLOW-gap-consult-loop/skill-contract-minimums-report-2026-04-23.md`
