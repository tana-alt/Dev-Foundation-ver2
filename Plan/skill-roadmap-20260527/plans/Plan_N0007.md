---
plan_id: Plan_N0007
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0007.log.md
---

# Plan_N0007 New Skill Audit And Agent Context Safety

## Source Refs

- Plan/new-skill.md
- Plan/skill-imp-idea.md
- .agents/skills/security-check/SKILL.md
- .agents/skills/doc-lookup/SKILL.md
- docs/01-agent-operating-contract.md
- docs/03-repo-boundary-and-storage-contract.md

## Objective

Execute the separate new-skill audit and decide whether
`agent-context-and-tool-safety` should be added or folded into existing policy.

## Minimal Tasks

- Produce a short decision record covering all candidates named in
  `Plan/new-skill.md`.
- Each decision record row must include candidate skill name, decision
  (`add`, `do not add`, `defer`, `plugin instead`, or `fold into existing
  skill`), reason tied to compact-foundation philosophy, existing skill or
  active contract coverage, and acceptance condition if adding later.
- First test whether `security-check` can absorb the
  `agent-context-and-tool-safety` failure mode.
- Add `agent-context-and-tool-safety` only if the audit shows a repeated
  agent-specific failure mode not covered by active docs, existing skills, or
  official plugins.
- If added, keep the skill compact and centered on untrusted context,
  instruction authority, side-effect boundaries, and tool output safety.
- Explicitly reject project-specific, PDF-derived, and narrow stack-specific
  local skill content.
- Cover "do not add" candidates from both source Plans, including
  `accessibility-review`, `observability-check`, `dependency-risk-review`,
  `openapi-contract`, `react-next-performance` as a pure new local skill,
  `mcp-server-development`, `skill-authoring-governance` as pure new rather
  than rename/extension, `privacy-review`, `prompt-engineering`,
  `tailwind-skill`, `shadcn-ui-skill`, `prisma-skill`, `stripe-skill`,
  `supabase-skill`, `python-ruff-uv-skill`, and PDF-derived skills.

## Acceptance

- The audit may conclude no new local skill should be added.
- If a new skill is added, the decision record explains why fold/plugin/doc
  lookup was insufficient.
- Any new local skill content passes the no project-specific, PDF-derived, or
  narrow stack-specific content rule.
