---
name: img-to-frontend
description: "Use only for explicit image-first concept exploration, screenshot-to-code, generated-design-to-code, or premium visual exploration where images are the primary design reference. Do not use for ordinary frontend implementation."
---

# Img to Frontend

## Overview

Use this skill to run an image-first design-to-code workflow. It must adapt to
the user's brief, audience, content model, interaction needs, and brand intent
rather than forcing a fixed category or visual trope.

The workflow is staged only when the request is explicitly image-first:

1. Establish or receive the image reference.
2. Translate the selected image into a precise implementation prompt when useful.
3. Build the real page and iterate against screenshots until structure,
   hierarchy, typography, spacing, color, media treatment, component geometry,
   interactions, and responsive behavior are close to the reference.

Load `references/visual-iteration-checklist.md` for design variety, implementation, close visual replication, premium website work, complex UI sections, or repeated visual refinement.

## When To Use

Use this skill only when the user explicitly asks to:

- Create several distinct website or page concepts before coding.
- Turn an image or generated design into a real frontend page.
- Produce a detailed prompt another coding agent can use to build a design.
- Replicate a screenshot as real HTML/CSS/React rather than as an image.
- Do premium visual exploration where generated images are the primary
  deliverable or design reference.

Do not use this skill for ordinary frontend implementation, business-logic
changes, backend features, simple copy edits, or design critique that will not
lead to generated images, a detailed implementation prompt, or frontend code.

## Image Reference Gate

Do not force image generation when the user already supplied the reference image,
screenshot, or generated design to implement.

Use the smallest image step that matches the request:

- Existing screenshot/image: use it directly as the design reference.
- Generated-design-to-code: use the selected generated image already in context.
- Concept exploration: generate 2-4 distinct website/page images, or the exact
  count requested by the user, then pause for selection.
- Direct implementation request with a selected image: proceed to implementation
  after extracting the build prompt.

If image generation is requested but unavailable or fails, report that blocker
and ask whether the user wants text-only fallbacks. Do not silently substitute
text briefs for an explicitly requested image stage.

## Core Workflow

### 1. Design Exploration

Start by identifying the site context, audience, goal, style constraints, viewport, and must-have sections. If the user already gave enough context, do not pause for more input.

For explicit concept exploration, generate 2-4 distinct website/page images
through `$imagegen` unless the user requested a specific count. Each image must
have its own visual language, not minor palette swaps. Vary structure,
hierarchy, typography strategy, interaction model, information architecture,
content emphasis, density, and brand behavior.

Choose directions that fit the site's purpose and audience. Different website types should develop from their own communication needs, not from a shared default template.

Use `ui-mockup` as the image-generation use case unless the user asks for a different raster style. The images should be polished enough for the user to choose between real visual directions, not rough wireframes.

For each direction, briefly label:

- Overall art direction and emotional tone.
- Page layout and content hierarchy.
- Typography treatment and scale relationship.
- Color palette with exact roles.
- Visual centerpiece appropriate to the site's purpose, content, and user task.
- Credibility, context, or trust treatment when relevant.
- Motion idea, if appropriate.
- What makes it meaningfully different from the other three.

### 2. Selection Pause

After concept images are created, stop and wait for the user to pick one or
request revisions. Do not write the detailed build prompt and do not begin
implementation until the user selects an image or explicitly asks to skip
selection.

When the user references a selected image, verify which image they mean from the conversation context. If there is ambiguity, ask a short clarification before writing the prompt or coding.

### 3. Deep Build Prompt

Before coding, convert the selected image into a granular implementation prompt. The prompt should be specific enough that another frontend agent can build a near exact replica without guessing.

Include:

- Canvas and viewport assumptions, including desktop target size and responsive requirements.
- Exact page structure, grid proportions, maximum widths, gutters, and alignment rules.
- Typography hierarchy, font choices, letter spacing, line-height, weights, italics, uppercase treatments, and no-wrap constraints.
- Color tokens for background, surfaces, borders, primary accents, muted text, active states, status states, shadows, and media treatments.
- Component inventory covering only the modules that actually appear in the selected design, described by their role, hierarchy, layout behavior, and content type.
- Detailed behavior for any complex visual systems present in the selected image, including their structure, anchors, scale rules, states, responsive behavior, and fallback behavior.
- Animation rules that are restrained and purposeful.
- Explicit "do not" constraints that prevent fake implementation, generic styling, broken geometry, unreadable content, and overlapping responsive modules.
- Acceptance criteria and screenshot comparison checklist.

### 4. Codebase Discovery

Inspect the project before editing. Determine the framework, routing model, styling system, package manager, existing design tokens, component patterns, image/font handling, lint/test/build commands, and primary codepath.

Respect existing architecture and design-system conventions. If the user is asking about library or framework docs, use the appropriate documentation skill before relying on memory.

If a reference image includes browser chrome, operating system UI, or mock browser decorations, treat that chrome as presentation context only. Build the actual page content, not the browser wrapper, unless the user explicitly asks for a browser mockup component.

### 5. Implementation

Build the selected design as real UI code.

Requirements:

- Use semantic structure and accessible interactive elements.
- Define design tokens for colors, spacing, typography, borders, shadows, media treatment, and breakpoints.
- Prefer real CSS/SVG/HTML for visual marks, controls, structured visuals, content modules, and other interface details.
- Do not flatten the design into a static image.
- If the design includes linked, anchored, or spatially related elements, keep them in a shared coordinate or layout system so they resize together.
- Use responsive layout rules that shrink complex UI first, then stack or simplify before overlap.
- Preserve premium whitespace while avoiding unusable dead zones on large monitors.
- Keep copy readable and avoid truncation unless the design explicitly calls for it.
- Add only meaningful motion: page-load reveals, subtle hover states, media transitions, scroll reveals, or interface ambience when it supports the design.

### 6. Visual Iteration Loop

Run the page locally and capture screenshots at the reference viewport plus at least one wide desktop, one constrained desktop/tablet, and one mobile width when feasible.

Loop until the implementation has no obvious visual mismatch:

1. Compare the screenshot against the selected reference image.
2. Identify the largest visible mismatch first: composition, scale, alignment, typography, spacing, color, imagery, component geometry, complex-widget behavior, or responsive behavior.
3. Patch the implementation.
4. Re-run the page and capture a new screenshot.
5. Repeat until additional changes are minor refinements rather than structural corrections.

Pay special attention to failures that commonly appear in screenshot replication:

- Content is bunched together because component scale is too large.
- Large monitors have excessive deadspace because the layout max-width is too narrow.
- Orientation elements are offset from the main content system.
- First-read text elements do not share the alignment, rhythm, or hierarchy shown in the reference.
- Action labels wrap, icons drift, or control geometry breaks.
- Repeated content, media, input, or trust modules collide with adjacent sections.
- Dense component labels truncate because internal spacing is too tight.
- Anchored or connected visual elements separate from the objects they are meant to describe.
- Complex widgets overlap before the layout stacks or simplifies.
- Mobile layout waits too long to stack.

Ensure the accuracy of your final output, especially before yielding back to the user. The mock generated image and the final output should look nearly identical. Focus on the details and precision.

### 7. Verification And Closeout

Run the most relevant checks available for the project: lint, typecheck, build, unit tests, and visual browser verification. If a check cannot run, state why.

Final response should include:

- What was built or changed.
- Files changed.
- Verification commands and results.
- Any residual visual risks, especially if screenshot comparison was limited by tooling or missing references.

## Quality Bar

The output should feel like a premium website, not a generated template. Favor confident hierarchy, intentional palette, sharp spacing, precise alignment, brief-appropriate content modules, and a single strong visual thesis.

When matching a reference, optimize for visible fidelity over code cleverness. Typography, spacing, alignment, imagery, component geometry, and responsive behavior are first-class deliverables, not polish.

When the user says something looks wrong, treat it as direct visual evidence. Inspect the current implementation and reference, then patch the specific mismatch rather than explaining it away.
