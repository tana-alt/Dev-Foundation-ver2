---
name: browser-verification
description: Use when a frontend route, browser flow, visual regression, responsive behavior, console/network error risk, or release-critical user journey needs proof in a real or scripted browser. Choose automated-e2e when tests exist; choose manual-browser-qa for preview/local smoke checks.
---

# Browser Verification

Use this skill to prove browser behavior, not to redesign the UI.

## Modes

### automated-e2e

Use when an existing Playwright or e2e path can verify the target flow, or when
the user explicitly asks for an e2e reproduction.

- Prefer existing e2e tests.
- Add only the smallest deterministic test for the target flow when needed.
- Avoid arbitrary sleeps; use assertions and deterministic waits.
- Report the command, failing step, artifact, and likely implementation area.

### manual-browser-qa

Use when a local app or preview needs a focused smoke check.

- Load the critical route or flow.
- Check console errors and relevant network 4xx/5xx where possible.
- Sample desktop and mobile widths when layout changed.
- Check keyboard basics for forms and controls.
- Avoid production accounts, destructive actions, and unrelated pages.

## Constraints

- Do not inspect every page unless requested.
- Do not create a broad e2e suite during a local task.
- Do not hide flakiness; report it as risk.
- Do not treat cosmetic preference as a release blocker unless it breaks the
  stated goal or accessibility.

## Output

Return:

- mode used: `automated-e2e` or `manual-browser-qa`
- route or flow checked
- command/tool and result: pass / fail / blocked
- artifacts or concise failure summary
- patch made, if any
