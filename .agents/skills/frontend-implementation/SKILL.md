---
name: frontend-implementation
description: "Use for ordinary React or Next.js UI implementation: components, forms, routing, client state, data wiring, and local loading/error/responsive/accessibility behavior within existing product patterns."
---


## Purpose

Keep frontend changes small, testable, accessible, and consistent with the existing UI architecture.

## Effect

When this skill fires, inspect the existing frontend structure first, implement
the smallest project-native UI change, preserve expected states and
accessibility, and verify the affected route or component with the closest
available check.

External visually strong frontend skills may inform craft expectations, but
ordinary component, form, routing, and data-wiring work stays here when the task
does not require a new visual direction.

## Use when

- Adding or changing UI components.
- Implementing forms, navigation, client state, data wiring, or error/loading states.
- Touching responsive layout or accessibility behavior.

## Do not use when

- The primary task is visual direction, premium composition, brand expression,
  or image-led design; use `ui-art-direction`.
- The task is reviewing or repairing UI quality after a change; use
  `ui-quality-gate`.
- The task starts from a Figma frame, node, selection, or URL; use
  `figma-design-to-code`.
- The task is screenshot/image-to-code or generated visual exploration; use
  `img-to-frontend`.
- The main risk is React/Next performance, server/client boundaries, caching,
  hydration, bundle size, or render frequency; use `react-next-performance`.

## Success conditions

- The component has clear responsibility boundaries.
- Loading, empty, error, and success states are handled when applicable.
- Basic keyboard and screen-reader accessibility are preserved.
- Form validation occurs at the appropriate client/server boundaries.
- Styling follows existing tokens, components, and layout conventions.
- Reusable component APIs avoid boolean-prop proliferation and one-off mode
  props; prefer explicit variants, children slots, compound components,
  provider-owned state, or composition when that matches local patterns.
- If the project uses source-copied component systems such as shadcn/ui, inspect
  `components.json`, aliases, existing `components/ui`, and local conventions
  before adding or modifying components. Route current CLI/API details through
  `doc-lookup`.

## Constraints

- Do not expose secrets, tokens, raw errors, or private data to the client.
- Do not add a new state library or UI library unless necessary.
- Do not perform broad redesign while implementing a local change.
- Do not hide server authorization requirements behind UI-only checks.
- Do not add arbitrary animations or decorative complexity without task need.

## Stop

Stop and route or ask before implementing when the request requires a new design
system, broad redesign, unprovided visual reference, unclear route ownership,
new client-exposed sensitive data, or a framework/version-sensitive API that
needs `doc-lookup`.

## Output

- Frontend surface changed.
- States handled: loading / empty / error / success / disabled as applicable.
- Accessibility and responsive checks performed or not applicable.
- Verification command, browser check, or blocked reason.
- Adjacent skill routed or intentionally not needed.
