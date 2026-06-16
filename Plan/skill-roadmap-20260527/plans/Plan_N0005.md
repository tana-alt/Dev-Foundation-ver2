---
plan_id: Plan_N0005
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0005.log.md
---

# Plan_N0005 UI Quality And Browser Verification

## Source Refs

- Plan/skill-imp-idea.md
- .agents/skills/design-system-audit/SKILL.md
- .agents/skills/ui-vercel-web-design-guidelines/SKILL.md
- .agents/skills/browser-qa/SKILL.md
- .agents/skills/e2e-verification/SKILL.md
- .agents/skills/img-to-frontend/SKILL.md
- .agents/skills/SKILL_INDEX.md

## Objective

Create two clearer verification routes: `ui-quality-gate` and
`browser-verification`, while narrowing `img-to-frontend` so normal frontend
work does not trigger an image-first concept workflow.

## Minimal Tasks

- Merge `design-system-audit` and `ui-vercel-web-design-guidelines` into
  `ui-quality-gate`.
- Keep project design-system consistency, accessibility, keyboard/focus,
  forms, motion, content overflow, responsive proof, and visual polish in scope.
- Preserve the required source hierarchy:
  project-local design system is repo truth, W3C WCAG/WAI-ARIA are accessibility
  sources, and Vercel Web Interface Guidelines are tactical review material.
- Prevent tactical Vercel guidance from overriding project design-system truth
  or official accessibility sources.
- Merge `browser-qa` and `e2e-verification` into `browser-verification`.
- Split browser verification modes into `automated-e2e` and
  `manual-browser-qa`.
- Narrow `img-to-frontend` so it only runs for explicitly image-first concept,
  screenshot-to-code, generated-design-to-code, or premium visual exploration
  requests.
- Remove or soften the unconditional "first deliverable is always 4 images"
  behavior so ordinary frontend implementation routes to
  `frontend-implementation` or `ui-art-direction` instead.
- Remove retired source directories after consolidation.

## Acceptance

- UI review/design quality and browser execution proof no longer compete across
  overlapping skills.
- `img-to-frontend` remains in the target inventory but is no longer a broad
  default route for normal frontend tasks.
