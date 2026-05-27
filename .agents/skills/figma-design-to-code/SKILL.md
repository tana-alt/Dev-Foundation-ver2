---
name: figma-design-to-code
description: Use when implementing repository UI code from a Figma frame, component, selected node, or Figma URL. Requires Figma MCP or equivalent design context access, design context, screenshot, variables/assets when available, project components, and visual parity validation. Does not write to Figma.
license: Complete terms in LICENSE.txt
---

# Figma Design To Code

Use this skill only when the deliverable is code in the repository that matches a
Figma design. Figma canvas writes, node creation, and design mutation are out of
scope; route those to official Figma tools or plugins when installed.

Source attribution: this replaces the prior Figma implementation skill while
retaining Figma Developer Terms attribution in `LICENSE.txt`.

## Preconditions

- Figma MCP or equivalent design-context access is available.
- The user provides a Figma URL, frame/component/node identifier, or an active
  Figma desktop selection exposed through the tool.
- The project codebase can be inspected so implementation uses local framework,
  components, tokens, routing, and asset conventions.

If design context or screenshot access is unavailable, report `blocked` and ask
for an exported screenshot/spec or for the Figma tool to be connected. Do not
guess from a URL alone.

## Workflow

1. Parse the Figma URL or selected node for file key and node id when needed.
2. Fetch design context. If truncated, fetch metadata first and then the
   smallest relevant child nodes.
3. Capture a screenshot for visual validation.
4. Fetch variables, token definitions, component metadata, and assets when the
   tool exposes them.
5. Inspect the project for existing components, tokens, styling conventions,
   routing, image handling, and verification commands.
6. Translate the design into project-native code. Treat MCP output as design
   evidence, not necessarily final code style.
7. Validate against the screenshot: layout, spacing, typography, color, assets,
   states, responsive behavior, and accessibility.
8. Record any intentional deviation caused by accessibility, technical
   constraints, or project design-system requirements.

## Implementation Rules

- Reuse project components before creating new ones.
- Map Figma variables to project tokens when possible.
- Prefer project design-system consistency unless it materially breaks visual
  parity; document tradeoffs.
- Use real assets from the Figma payload when available. Do not create
  placeholders when the source asset was provided.
- Do not import new icon or UI packages just because the design contains icons.
- Keep components composable and typed where the project uses TypeScript.
- Do not reference nonexistent sibling Figma skills in this repo.

## Validation Checklist

- Design context and screenshot were fetched or the blocker is explicit.
- Required variables/assets were used or a missing-asset note is recorded.
- Layout, alignment, sizing, type, color, and major states match the reference.
- Responsive behavior follows Figma constraints and project breakpoints.
- Accessibility basics are preserved.
- Local lint/test/build or the closest available check was run.

## Output

Return:

- Figma source used: URL/node/selection plus screenshot/context status.
- Files changed.
- Parity result and any deviations.
- Verification commands and results.
