---
name: ui-art-direction
description: Use when a web page, app surface, prototype, demo, game UI, or component needs premium visual art direction, strong hierarchy, image-led composition, tasteful motion, and avoidance of generic AI-looking design. Ordinary UI implementation still routes to frontend-implementation.
license: Complete terms in LICENSE.txt
---

# UI Art Direction

Use this skill when the task depends on visual judgment: composition, brand
presence, hierarchy, imagery, motion, atmosphere, and polish. Do not use it as a
default route for routine form, state, routing, or business-logic UI work.

Source attribution: this consolidates prior repo-local `frontend-design`,
`ui-anthropic-frontend-design`, and `ui-openai-frontend-design` guidance. The
retained imported material is Apache-licensed; see `LICENSE.txt`.

## Working Model

Before building visually led work, write three short notes for yourself:

- Visual thesis: mood, material, energy, and audience fit.
- Content plan: the few sections or regions that carry the experience.
- Interaction thesis: 2-3 motions or state changes that improve hierarchy.

Then implement real UI code. The output should be usable, accessible, and
consistent with the project architecture, not a static mockup.

## Routing Boundaries

- Use `frontend-implementation` for ordinary React/Next/UI implementation.
- Use `figma-design-to-code` for implementation from a Figma frame or node.
- Use `img-to-frontend` only for explicit image-first concept,
  screenshot-to-code, generated-design-to-code, or premium visual exploration.
- Use `ui-quality-gate` when reviewing or repairing UI quality after a change.

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

## Output

Return a concise implementation note with:

- visual thesis used
- changed files
- verification or screenshot checks
- known visual risks if browser proof was limited
