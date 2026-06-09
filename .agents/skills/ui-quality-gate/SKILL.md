---
name: ui-quality-gate
description: Use after or during UI changes when accessibility, keyboard behavior, focus states, responsive layout, forms, motion, empty/error states, content overflow, design-system consistency, or visual polish may affect product quality. Do not redesign; produce minimal file/route-specific fixes.
---

# UI Quality Gate

Use this skill to review or repair UI quality without turning the task into a
new visual direction.

## Effect

When this skill fires, narrow the work to quality defects in the changed UI
surface: identify concrete user-facing risks, apply or recommend the smallest
local fix, and verify the specific route, component, or state affected.

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

## Review Modes

Use only the smallest mode needed. These modes distill external UI review
workflows into local review vocabulary without importing their full rule bodies:

- `critique`: design-director review of hierarchy, information architecture,
  cognitive load, tone, emotional fit, anti-patterns, and priority issues.
- `audit`: measurable review of accessibility, performance signals,
  theming/token use, responsive behavior, forms, navigation/state, animation,
  touch targets, internationalization risk, and UI anti-patterns. Use a 5-axis
  score for accessibility, performance, theming, responsive behavior, and
  anti-patterns only when the user explicitly asks for scoring.
- `polish`: final pass for design-system alignment, spacing, typography,
  interaction states, copy, loading/error/empty states, and edge cases.
- `distill`: remove redundant UI, copy, actions, cards, decoration, or
  information complexity while preserving necessary function and accessibility.
- `quieter`: reduce saturation, contrast extremes, heavy type, decorative
  layers, and motion intensity without erasing product personality.
- `typeset`: typography-focused pass for font choice, hierarchy, type scale,
  line length, line-height, contrast, and consistency.

Scoring is optional and should be used only when the user asks for an audit
score. When current WCAG/WAI-ARIA, Vercel guideline details, or framework
behavior matter, route through `doc-lookup` rather than relying on embedded
local copies. Browser evidence routes to `browser-verification` when needed.
When reviewing files, prefer terse actionable findings with file and line
references over broad commentary.
For design-engineering checks, evaluate motion, visual design, code structure,
and performance together instead of treating polish as separate from runtime
behavior.

## Do Not Use When

- The task is to create a new UI, route, component, or data-wired interaction;
  use `frontend-implementation`.
- The task asks for a new visual direction, premium styling, art direction, or
  broad redesign; use `ui-art-direction`.
- The task is primarily screenshot/Figma/image-to-code implementation; use the
  relevant visual-source skill first, then this skill only as a quality pass.
- The concern is release readiness across non-UI areas; use `release-check`.

## Constraints

- Do not invent a new design system.
- Do not redesign during a local quality fix.
- Do not treat subjective preference as a blocker.
- Keep findings specific to affected files, components, or routes.
- When checking accessibility, state whether proof is code review, browser QA,
  automated tooling, or manual keyboard inspection.
- If the request mixes out-of-scope redesign, new implementation, or
  release-wide work with local UI quality concerns, route the out-of-scope part
  and continue only the affected quality-gate surface.
- If files, routes, or runnable UI needed for proof are unavailable, do not
  infer pass or fail; mark the proof blocked, list exactly what remains
  unverified, and recommend only fixes supported by the provided evidence.

## Stop

Stop and route elsewhere when the fix requires a new design system, broad visual
redirection, product requirements, current external docs, or release-wide
verification beyond the affected UI surface.

## Output

Return:

- `verdict`: pass / rework / blocked.
- `scope_checked`: route, component, viewport, state, or file.
- `source_basis`: project system / WCAG-WAI / tactical guideline / skill
  scope-routing rule when routing or blocking out-of-scope work.
- `findings`: route, component, state, or file references with minimal fixes;
  use the narrowest known surface when exact files are unavailable.
- `verification`: code review, command, browser check, keyboard check,
  automated accessibility check, or reason not run.
- `residual_risk`: unverified viewport, state, browser, keyboard, or source
  surfaces.
