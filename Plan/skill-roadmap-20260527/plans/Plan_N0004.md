---
plan_id: Plan_N0004
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0004.log.md
---

# Plan_N0004 UI Art Direction Consolidation

## Source Refs

- Plan/skill-imp-idea.md
- .agents/skills/frontend-design/SKILL.md
- .agents/skills/ui-anthropic-frontend-design/SKILL.md
- .agents/skills/ui-openai-frontend-design/SKILL.md
- .agents/skills/SKILL_INDEX.md

## Objective

Merge the three overlapping frontend visual design skills into one vendor-neutral
`ui-art-direction` skill.

## Minimal Tasks

- Create `.agents/skills/ui-art-direction/SKILL.md`.
- Use the more actionable `ui-openai-frontend-design` guidance as the core.
- Preserve useful `frontend-design` and `ui-anthropic-frontend-design` guidance
  only when it improves the compact execution contract.
- Preserve license/source attribution from imported skills.
- Remove retired duplicate skill directories after content is consolidated.

## Acceptance

- Only `ui-art-direction` remains for premium visual/page/app design.
- Ordinary UI implementation remains routed to `frontend-implementation`.
