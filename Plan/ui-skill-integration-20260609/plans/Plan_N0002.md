---
plan_id: Plan_N0002
project_id: ui-skill-integration-20260609
status: completed
log_ref: Plan/ui-skill-integration-20260609/logs/Plan_N0002.log.md
---

# UI Skill Integration Quality Review And Fix Plan

## Goal

Review whether Plan_N0001 fully integrated the requested external UI skill
essence into repository-local core skills, then apply the smallest fixes needed
to close quality gaps.

## Source Refs

- User-provided source-to-target mapping for creation and review mode sources.
- Plan/ui-skill-integration-20260609/plans/Plan_N0001.md
- Plan/ui-skill-integration-20260609/logs/Plan_N0001.log.md
- .agents/skills/SKILL_INDEX.md
- .agents/skills/ui-art-direction/SKILL.md
- .agents/skills/ui-quality-gate/SKILL.md
- .agents/skills/frontend-implementation/SKILL.md
- .agents/skills/figma-design-to-code/SKILL.md
- .agents/skills/browser-verification/SKILL.md
- .agents/skills/react-next-performance/SKILL.md
- .agents/skills/img-to-frontend/SKILL.md
- .agents/skills/doc-lookup/SKILL.md
- .agents/skills/skill-authoring-governance/SKILL.md

## Allowed Write Targets

- .agents/skills/SKILL_INDEX.md
- .agents/skills/ui-art-direction/SKILL.md
- .agents/skills/ui-quality-gate/SKILL.md
- .agents/skills/frontend-implementation/SKILL.md
- .agents/skills/figma-design-to-code/SKILL.md
- .agents/skills/browser-verification/SKILL.md
- .agents/skills/react-next-performance/SKILL.md
- .agents/skills/skill-authoring-governance/SKILL.md
- Plan/ui-skill-integration-20260609/

## Change Impact Classification

- change_type: skill documentation / routing contract
- side_effects: no external write, no dependency change, no CI/CD change, no
  protected action, no secret handling
- risk_level: medium
- reason: local skill routing changes affect future agent behavior, and external
  skill source material carries prompt-injection and provenance risk.
- required_review_modes: narrow_review, fix_review, convergence_decision
- human_gate_required: false for local edits; human review remains recommended
  before closing the GitHub issue.

## Review And Fix Workflow

1. Completed: ran a read-only quality reviewer against the mapping and changed
   skills.
2. Completed: converted known gaps into fix handoff items.
3. Completed: applied the smallest local skill edits for known gaps.
4. Completed: ran fix review and structural verification.
5. Completed: recorded convergence decision and residual risk.

## Fix Handoff

- FIX-001: Add explicit shadcn/source-copied component system guidance to
  `frontend-implementation` and route current CLI/API detail through
  `doc-lookup`.
- FIX-002: Clarify that external frontend-skill craft expectations do not
  reroute ordinary UI implementation away from `frontend-implementation`.
- FIX-003: Add design-engineering principle that motion, visual design, code
  structure, and performance are evaluated together.
- FIX-004: Make `ui-quality-gate` audit scoring explicitly optional and tied to
  the 5-axis set requested in the source mapping.
- FIX-005: Correct `ui-art-direction` attribution so external/local skill
  sources are described as untrusted reference material, not repo-local
  authority.

Must not change:

- Do not add new local skill directories.
- Do not copy external skill bodies or live guideline payloads.
- Do not make Figma canvas generation/mutation a local repo skill.
- Do not broaden `ui-quality-gate` into redesign.

## Narrow Review Result

- REV-001: medium; `ui-art-direction` attribution implied external material was
  prior repo-local authority. Accepted as FIX-005.
- REV-002: low; shadcn-ui principle needed to live in
  `frontend-implementation`, not only the index. Closed by FIX-001.

## Fix Review

- FIX-001: resolved; shadcn/source-copied component guidance added to
  `frontend-implementation` and `SKILL_INDEX.md`.
- FIX-002: resolved; ordinary frontend implementation route clarified in
  `frontend-implementation`.
- FIX-003: resolved; motion, design, code structure, and performance are linked
  in `ui-art-direction` and `ui-quality-gate`.
- FIX-004: resolved; optional 5-axis audit scoring is explicit in
  `ui-quality-gate`.
- FIX-005: resolved; `ui-art-direction` attribution now identifies
  external/local Codex UI skill sources as untrusted reference material.

New risk check:

- new_requirement_violation: none
- new_security_surface: none
- new_scope_leak: none
- neighboring_lane_impact: none

## Convergence Decision

- status: complete_with_residual_risk
- reason: quality review findings are resolved, structural markers are present,
  and verification passed.
- unresolved_fix: 0
- unverified_required_checks: 0
- residual_risk: external source license/provenance remains intentionally
  handled by principle-level absorption only; no external bodies were copied.
