# Codex App Development Skills Index

This index is for humans. Codex discovers skills from each skill's YAML front
matter in `SKILL.md`.

## Core skills

- `research-before-build`
- `doc-lookup`
- `api-contract`
- `frontend-implementation`
- `backend-implementation`
- `security-check`
- `release-check`

## Conditional skills

- `system-design`
- `tdd-scope`
- `db-migration`
- `deploy-readiness`
- `browser-verification`

## UI and official-stack skills

- `ui-art-direction`
- `ui-quality-gate`
- `img-to-frontend`
- `react-next-performance`
- `figma-design-to-code`

## Governance skills

- `skill-authoring-governance`
- `subagent-workflow-governance`
- `scope-routing-governance`
- `spec-authority-governance`
- `traceability-gate-governance`
- `merge-integrity-governance`
- `residual-risk-carryover`
- `hook-validation-governance`
- `review-fix-convergence-governance`

## Routing notes

- Treat skills as a discovery layer plus a compact execution contract.
- Convert best practices into success conditions and constraints.
- Keep framework-specific details outside skills unless repeatedly needed.
- Use doc-lookup for current official docs instead of embedding bulky stack
  guidance.
- Agent context and tool-output safety is folded into security-check, not a
  separate local skill.
- Operational governance skills route record-heavy workflow, context, hooks,
  review, traceability, and residual-risk tasks without making active docs long.
