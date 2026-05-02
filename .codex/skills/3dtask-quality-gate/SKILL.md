---
name: 3dtask-quality-gate
description: Use when checking 3Dtask app quality in React, Swift, or webview builds, especially 3D canvas rendering, timeline axis readability, latency, button placement drift, UI overlap, and node interaction return behavior. Trigger for 3Dtask quality gates, browser-based visual QA, 3D canvas nonblank checks, and regression checks before handoff or release.
---

# 3Dtask Quality Gate

Use this skill to run repeatable browser-visible checks for the 3Dtask application. It is intentionally narrow: it proves the current UI is reachable, visibly rendered, and structurally usable at desktop and mobile sizes.

## Quick Flow

1. Start or locate the 3Dtask app URL.
2. Run the bundled Playwright gate:

```bash
node .codex/skills/3dtask-quality-gate/scripts/run-3dtask-quality-gate.cjs <url>
```

3. Read the JSON result from stdout. Treat `errors` and `warnings` as quality-gate evidence.
4. Inspect the screenshot paths listed in the JSON when the result is ambiguous.
5. Store summaries, blocker notes, and follow-up actions under `projects/project_app_3dtask/artifacts/quality/`.

## What The Gate Checks

- Page-load latency for each viewport.
- Visible button/control count, clipped controls, small tap targets, and overlap warnings.
- 3D canvas nonblank-ish signal using browser-side canvas pixel sampling where possible.
- Timeline/axis label presence through DOM text and accessible labels.
- Screenshot evidence for desktop `1440x900` and mobile `390x844`.
- Basic node-operation return behavior when obvious node-like elements are present.

## Script Notes

- The script first tries repo-local Playwright at `apps/web/node_modules/playwright`.
- If Playwright is unavailable, it exits with a clear JSON error and does not install dependencies.
- Pass `--out-dir <dir>` to control screenshot output. The default is `projects/project_app_3dtask/artifacts/quality/screenshots/<timestamp>/`.
- Pass `--timeout-ms <number>` to change navigation timeout.

## Output Expectations

The script emits one JSON object with:

- `targetUrl`
- `viewports`
- `pageLoadLatencyMs`
- `visibleButtonCount`
- `overlapWarnings`
- `canvasChecks`
- `axisLabelPresence`
- `nodeReturnChecks`
- `screenshotPaths`
- `errors`

When reporting results, cite the JSON fields and screenshot paths rather than relying on memory.
