---
plan_id: Plan_N0006
project_id: skill-roadmap-20260527
plan_ref: Plan/skill-roadmap-20260527/plans/Plan_N0006.md
---

# Plan_N0006 Log

## 2026-05-27

- Status: pending.
- Rework applied before implementation: added Figma MCP/context, parity,
  write-to-Figma out-of-scope guard, and imported attribution preservation.
- Replaced `ui-vercel-react-best-practices` with
  `react-next-performance`.
- The replacement prefers official React and Next.js documentation through
  `doc-lookup`; Vercel guidance is retained only as optional tactical
  attribution, and the bulky imported payload was removed.
- Replaced `ui-openai-figma-implement-design` with
  `figma-design-to-code`, retaining Figma assets and Developer Terms
  attribution.
- `figma-design-to-code` requires Figma MCP or equivalent design context,
  screenshot, variables/assets when available, project components, and parity
  validation. Write-to-Figma is explicitly out of scope.
- Added OpenAPI mode to `api-contract`.
- Added a thin GitHub Actions/CI mode to `deploy-readiness` within readiness
  scope.
- MCP server development remains an official plugin route, not a local skill.
- Status: completed.
