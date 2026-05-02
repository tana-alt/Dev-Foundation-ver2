---
name: agent-visibility-skill
description: Use when an agent must verify in a real browser that the requested UI behavior actually works end-to-end with Playwright and screenshots. Trigger this skill for browser-driven E2E checks, action validation, regression confirmation, and before-and-after screenshot evidence grounded in the visible result.
---

# Agent Visibility Skill

Use this skill when the right next step is to prove in a browser that the requested behavior works, instead of assuming it from code or unit tests alone.

## Quick Flow

1. Open the target page with Playwright and wait for a stable state.
2. Reproduce the user-facing scenario as a short E2E path.
3. Capture screenshots before, during, or after key steps as evidence.
4. Apply the smallest useful fix when the behavior fails.
5. Re-run the same browser path and capture matching evidence again.

## Practical Rules

- Prefer short, bounded browser flows over one long end-to-end script when a failure point is still unknown.
- Test at the viewport where the app is actually used, including intermediate desktop widths such as `1440px`, not only wide desktop and mobile extremes.
- When a click fails, assume overlap first: inspect fixed footers, sticky headers, side panels, and adjacent columns before blaming the control itself.
- Treat screenshots and Playwright action errors together as the proof set for a failure.
- If Playwright is unavailable in the repo, use an isolated temporary runtime instead of changing project dependencies just to inspect the UI.

## Required Checks

- The agent can reach the intended page or state from a realistic starting point.
- The required user action can be performed in the browser without guesswork.
- The expected result becomes visible after the action.
- Errors, blocked transitions, and stale UI states are caught as failures.
- Screenshots reflect the state transition or final success condition.
- If the interface claims a structural capability, verify it in the browser instead of inferring it from labels or code.
- If the interface exposes relationships between entities, verify that those relationships remain understandable from the rendered state.
- If the interface claims non-linear behavior such as branching, parallelism, or multiple active paths, verify that the visible interaction model can actually express it.

## Read These Only When Needed

- Browser workflow: `reference/playwright-workflow.md`
- E2E verification rubric: `reference/e2e-verification-checklist.md`

## Output Rules

- Describe the failing browser step before changing code.
- Prefer concrete observations such as `Clicking Save leaves the dialog open and no success toast appears.`
- Refresh screenshots after each meaningful UI fix or state transition.
- If the page cannot be evaluated because of auth, seed data, or runtime failure, report that blocker explicitly.
