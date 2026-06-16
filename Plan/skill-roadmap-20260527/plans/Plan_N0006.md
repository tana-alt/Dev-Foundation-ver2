---
plan_id: Plan_N0006
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0006.log.md
---

# Plan_N0006 Official Stack Skill Alignment

## Source Refs

- Plan/skill-imp-idea.md
- .agents/skills/ui-vercel-react-best-practices/SKILL.md
- .agents/skills/ui-openai-figma-implement-design/SKILL.md
- .agents/skills/api-contract/SKILL.md
- .agents/skills/deploy-readiness/SKILL.md
- .agents/skills/SKILL_INDEX.md

## Objective

Replace vendor-specific imported stack skills with compact repo-local execution
contracts that prefer official/current docs.

## Minimal Tasks

- Replace `ui-vercel-react-best-practices` with `react-next-performance`.
- Replace `ui-openai-figma-implement-design` with `figma-design-to-code`.
- Require Figma MCP or equivalent design context access for
  `figma-design-to-code`.
- Make the Figma workflow fetch or verify design context, screenshot,
  variables/assets when available, implement with project components, and
  validate visual parity.
- Remove or rewrite references to sibling Figma skills that are not present in
  this repo unless clearly marked as external official plugin routes.
- Route write-to-Figma or Figma canvas mutation to official Figma skills/plugins
  instead of this repo-local design-to-code skill.
- Add an OpenAPI mode to `api-contract`, not a separate local skill.
- Add a thin GitHub Actions/CI mode to `deploy-readiness` only if it stays
  within deployment/readiness scope.
- Record that MCP server development should use an official plugin route rather
  than a local skill unless a future repo-local need is proven.
- Preserve imported license/source attribution for retained Vercel and Figma
  guidance, or remove imported payloads when they are no longer used.

## Acceptance

- Directory names and frontmatter names match.
- Official stack details are routed through `doc-lookup` or external official
  plugin routes instead of becoming bulky local skill content.
- Figma implementation scope is design-to-code only, with write-to-Figma
  explicitly out of scope.
