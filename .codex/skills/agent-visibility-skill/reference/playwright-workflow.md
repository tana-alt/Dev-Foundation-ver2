# Playwright Workflow

## Goal

Use Playwright to prove that a user-facing behavior works in the browser.

## Steps

1. Open the target page and wait for a stable state.
2. Reproduce the requested scenario with the smallest useful browser path.
3. Capture screenshots around the key interaction points.
4. If the action fails, inspect the visible UI for overlap, stale state, or blocked transitions.
5. Fix the smallest thing that explains the failure.
6. Re-run the same flow and capture matching evidence again.

## Notes

- Prefer realistic viewport sizes.
- Keep the script short when the failure point is unknown.
- Treat the screenshot and the action error as a single proof set.
