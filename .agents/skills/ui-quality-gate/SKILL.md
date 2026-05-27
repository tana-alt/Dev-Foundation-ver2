---
name: ui-quality-gate
description: Use after or during UI changes when accessibility, keyboard behavior, focus states, responsive layout, forms, motion, empty/error states, content overflow, design-system consistency, or visual polish may affect product quality. Do not redesign; produce minimal file/route-specific fixes.
---

# UI Quality Gate

Use this skill to review or repair UI quality without turning the task into a
new visual direction.

## Source Hierarchy

1. Project-local design system, components, tokens, and product conventions are
   repo truth.
2. W3C WCAG and WAI-ARIA are the accessibility authority.
3. Vercel Web Interface Guidelines may be used as tactical review material only.

Tactical guidance never overrides project design-system truth or official
accessibility sources. Use `doc-lookup` when current WCAG/WAI-ARIA or tactical
guideline details matter.

## Check

- Component reuse, token usage, spacing, typography, color, and layout.
- Keyboard access, focus order, focus visibility, labels, names, roles, and
  states.
- Form validation, errors, disabled/loading states, and recovery paths.
- Responsive layout, safe areas, touch targets, and content overflow.
- Motion timing, reduced-motion fallback, and avoidance of distracting effects.
- Empty, loading, error, permission, and no-results states.
- Visual polish: alignment, density, contrast, image behavior, and truncation.

## Constraints

- Do not invent a new design system.
- Do not redesign during a local quality fix.
- Do not treat subjective preference as a blocker.
- Keep findings specific to affected files, components, or routes.
- When checking accessibility, state whether proof is code review, browser QA,
  automated tooling, or manual keyboard inspection.

## Output

Return:

- `verdict`: pass / rework / blocked.
- `source_basis`: project system / WCAG-WAI / tactical guideline.
- `findings`: route or file references with minimal fixes.
- `verification`: command, browser check, or reason not run.
