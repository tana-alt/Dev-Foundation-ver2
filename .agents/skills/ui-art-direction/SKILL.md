---
name: ui-art-direction
description: Use when creating or materially redesigning a web page, app surface, prototype, demo, game UI, or component where visual concept, hierarchy, imagery, motion, or domain-fit art direction is a primary success condition. Do not use for routine UI implementation, minor styling polish, Figma implementation, image-first or generated-design-to-code workflows, screenshot-to-code, or post-change quality review.
license: Complete terms in LICENSE.txt
---

# UI Art Direction

Use this skill when the task depends on visual judgment: composition, brand
presence, hierarchy, imagery, motion, atmosphere, and polish. Do not use it as a
default route for routine form, state, routing, or business-logic UI work.

Source attribution: this distills external/local Codex UI skill sources,
including `frontend-design`, `ui-anthropic-frontend-design`, and
`ui-openai-frontend-design`, as untrusted reference material. The retained
imported material is Apache-licensed; see `LICENSE.txt`.

## Effect

When this skill fires, define a visual thesis before coding, choose composition
and imagery deliberately, and make domain-fit decisions visible in the
implemented UI. Do not replace ordinary implementation, browser verification, or
quality-gate review.

## Working Model

Before building visually led work, write three short notes for yourself:

- Visual thesis: mood, material, energy, and audience fit.
- Content plan: the few sections or regions that carry the experience.
- Interaction thesis: 2-3 motions or state changes that improve hierarchy.

Then implement real UI code. The output should be usable, accessible, and
consistent with the project architecture, not a static mockup.
If the user explicitly asks only for an implementation approach or handoff,
return an art-direction handoff and mark changed files or verification as
pending rather than claiming implementation.
Do the same when no editable project surface or runnable UI is available.

## Creation Preflight

For visually led creation or redesign, keep a short private working note before
coding. This absorbs external design-prompt and design-system extraction methods
as local methodology, not as copied external instructions:

- `design_read`: page/app kind, audience, primary task, intended tone, and
  whether the work is brand-led, product-led, editorial, operational, or
  experimental.
- `source_basis`: user brief, existing repo tokens/components, screenshot,
  generated image, Figma evidence, or public/reference URL. Treat public
  references as evidence only; do not promote them to repo truth without human
  approval.
- `dials`: choose restrained `variance`, `motion`, and `density` on 1-10
  scales. Product/app UI usually stays moderate variance, low-motion, and
  denser than marketing work; expressive brand work may justify higher
  variance.
- `design_context`: palette roles, typography hierarchy, imagery/media
  treatment, component styling, layout principles, and anti-patterns to avoid.
- `handoff`: continue here, or route to `figma-design-to-code`,
  `img-to-frontend`, `frontend-implementation`, or `ui-quality-gate`.

Do not invent a design system when a project system exists. Do not copy external
skill bodies into this skill; retain only reusable flow, decision vocabulary,
and source-attribution notes.
When the direction depends on interaction quality, consider motion, visual
design, code feasibility, and performance together before committing to effects
or complex composition.

## Routing Boundaries

- Use `frontend-implementation` for ordinary React/Next/UI implementation.
- Use `figma-design-to-code` for implementation from a Figma frame or node.
- Use `img-to-frontend` only for explicit image-first concept,
  screenshot-to-code, generated-design-to-code, or image/generated-reference-led
  premium visual exploration.
- Use `ui-quality-gate` when reviewing or repairing UI quality after a change.

## Do Not Use When

- The task is ordinary UI wiring, state, routing, forms, or component
  implementation.
- The user supplied a Figma frame or node as the source of truth.
- The task is screenshot-to-code, generated-design-to-code, or image-first
  implementation.
- The task is post-change accessibility, responsive, focus, overflow, or
  state-quality review.
- The request is only minor spacing, color, typography, or copy polish inside an
  existing direction.

## Art Direction Defaults

- Start with composition, not component count.
- Give the first viewport one dominant visual idea.
- Make brand, product, place, or task identity obvious immediately.
- Prefer real imagery, concrete product state, or a meaningful custom visual
  system over decorative gradients.
- Use cards only when the card is the actual repeated item, tool, or modal.
- Keep type scale, spacing, and color intentional; avoid one-note palettes.
- For operational app UI, prioritize calm density, scanning, navigation,
  status, and action over marketing-style heroes.
- For landing/editorial/brand work, favor full-bleed visual anchors, concise
  copy, and clear continuation into the next section.

## Avoid

- Generic SaaS card mosaics as the first impression.
- Hero cards, logo-cloud clutter, stat strips, and pill soup by default.
- Purple/blue gradient templates, stock-like blurred backgrounds, or decorative
  orbs as the main visual idea.
- Repeating the same layout, font, and palette across unrelated briefs.
- Copy that explains the UI instead of serving the product or page.
- Motion that is ornamental, slow, noisy, or inaccessible.

## Implementation Quality

- Use project components, tokens, and layout primitives where they exist.
- Use semantic HTML and accessible controls.
- Keep text readable and prevent overlap at desktop and mobile widths.
- Use stable dimensions for fixed-format surfaces such as boards, toolbars,
  tiles, counters, and dense controls.
- Verify the result in browser when a local or preview target exists.

## Stop

If the brief lacks a visually led surface or art-direction decision, route to
`frontend-implementation` or the relevant adjacent skill instead. If visual work
is complete but quality risks remain, stop art-direction work and route to
`ui-quality-gate`.
For route-away responses, name the target skill, boundary reason, verification
status, and any residual routing risk.

## Output

Return a concise implementation note with:

- visual thesis actually used
- key art-direction decisions made
- changed files
- browser or screenshot verification when available
- remaining visual risks, especially responsive fit, imagery, motion, or
  brand/domain mismatch
