---
plan_id: Plan_N0007
project_id: skill-roadmap-20260527
plan_ref: Plan/skill-roadmap-20260527/plans/Plan_N0007.md
---

# Plan_N0007 Log

## 2026-05-27

- Status: pending.
- Rework applied before implementation: added required decision-record columns,
  explicit no project-specific/PDF-derived/narrow-stack rule, and full
  candidate coverage from both source Plans.
- Tested whether `agent-context-and-tool-safety` can fold into
  `security-check`. Decision: fold into existing skill, do not add a separate
  local skill in this pass.
- Reason: active contracts already define instruction/source authority,
  scope boundaries, storage boundaries, and side-effect gates; `security-check`
  now has an `agent_context` section to trigger on untrusted external context
  and MCP/plugin/tool output. This satisfies the repeated failure mode without
  expanding the compact local skill inventory.

## Decision record

| Candidate | Decision and compact-foundation reason | Existing coverage | Later acceptance condition |
|---|---|---|---|
| `agent-context-and-tool-safety` | fold into existing skill; separate skill not needed after adding agent-context checks to security | AGENTS, operating/storage contracts, security-check | Add only if repeated evidence shows security-check fails to trigger or is too broad for instruction-authority/tool-boundary failures |
| `accessibility-review` | do not add; UI quality belongs in a merged gate | ui-quality-gate, frontend-implementation, browser-verification | Add only if accessibility review needs a dedicated recurring workflow beyond WCAG/WAI checks |
| `observability-check` | do not add; readiness/backend success conditions can absorb it | backend-implementation, deploy-readiness | Add only with repeated observability-specific release failures |
| `dependency-risk-review` | do not add; supply-chain checks belong in security | security-check | Add only if dependency review grows beyond security-check scope |
| `openapi-contract` | fold into existing skill; separate OpenAPI skill is too narrow for this foundation | api-contract OpenAPI mode, doc-lookup | Add only in a repo with heavy OpenAPI generation/review volume |
| `react-next-performance` as pure new | do not add as pure new; implemented only as replacement for retired imported Vercel skill | react-next-performance, doc-lookup | Keep only while React/Next performance remains a repeated local routing need |
| `mcp-server-development` | plugin instead; local MCP implementation knowledge would be bulky and version-sensitive | official MCP plugin route, doc-lookup | Add local skill only with proven recurring repo-local MCP implementation work |
| `skill-authoring-governance` as pure new | do not add as pure new; implemented as rename/extension of existing integrity tuning skill | skill-authoring-governance | Already satisfied by extension path |
| `privacy-review` | do not add; current boundary is secrets/storage/security, not regulatory privacy workflow | security-check, storage contract | Add only for repeated privacy/compliance scope with clear owner |
| `prompt-engineering` | do not add; too broad and better handled by active contracts/user request | AGENTS and operating contract | No local skill unless a specific repeated repo workflow emerges |
| `tailwind-skill` | do not add; narrow stack detail should use project docs or doc-lookup | doc-lookup, project design system | Add only inside a Tailwind-heavy project with repeated failures |
| `shadcn-ui-skill` | do not add; UI kit detail is project-specific | doc-lookup, frontend-implementation | Add only inside a shadcn-specific project |
| `prisma-skill` | do not add; ORM detail is stack-specific | db-migration, backend-implementation, doc-lookup | Add only inside a Prisma-heavy project |
| `stripe-skill` | do not add; payments are high-risk and current official docs are required | security-check, api-contract, doc-lookup | Add only inside a payments project with recurring Stripe workflows |
| `supabase-skill` | do not add; auth/storage/RLS details are project-specific and current-doc sensitive | security-check, backend-implementation, doc-lookup | Add only inside a Supabase-specific project |
| `python-ruff-uv-skill` | do not add; repo tooling is already in Makefile/pyproject/docs | release-check, active verification docs | Add only if repeated Python tool workflow failures appear |
| PDF-derived skills | do not add; skills are not a knowledge store | repo contracts, external searchable references | Add none; distill only durable repo-wide rules into active docs |

- Status: completed.
