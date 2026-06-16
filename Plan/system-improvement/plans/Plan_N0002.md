---
plan_id: Plan_N0002
project_id: system-improvement
status: completed
log_ref: Plan/system-improvement/logs/Plan_N0002.log.md
---

# Repo-Local Skill Trigger Precision And Effectiveness Improvement Plan

## 0. Positioning

This plan improves all existing repo-local skills so they fire when genuinely
needed, preserve the user's intent, and produce a clearer effect after
activation without widening descriptions to catch more tasks.

Primary goals:

```text
- Make each skill's trigger precise, narrow, and aligned with its actual workflow.
- Make each triggered skill measurably improve the agent's behavior through
  concrete workflow, stop conditions, output shape, or verification focus.
```

Hard rule:

```text
Do not broaden `description` fields merely to increase activation frequency.
Descriptions must become more discriminating, not more expansive.
Effectiveness improvements belong primarily in the skill body, not by adding
more trigger surface to the description.
```

Use `skill-authoring-governance` for the work. This is a material revision of
repo-local skills, not a new skill-creation effort.

## 1. Scope

### Included repo-local skills

```text
api-contract
backend-implementation
browser-verification
db-migration
deploy-readiness
doc-lookup
figma-design-to-code
frontend-implementation
img-to-frontend
react-next-performance
release-check
research-before-build
security-check
skill-authoring-governance
system-design
tdd-scope
ui-art-direction
ui-quality-gate
```

### Allowed write targets for implementation

```text
.agents/skills/*/SKILL.md
.agents/skills/SKILL_INDEX.md
tests/
Plan/system-improvement/
```

Only add or modify tests when they directly enforce skill discovery,
frontmatter/index consistency, trigger precision guardrails, or regression
checks for this work.

### Out of scope

```text
- adding new skills
- deleting or renaming skills unless a duplicate is proven and separately approved
- editing plugin-installed skills
- changing active docs
- broadening descriptions to catch more tasks
- embedding large framework guidance in skill bodies
- turning skills into broad manuals or best-practice essays
- adding project-specific, stack-specific, or one-off skill material
- changing app/source implementation code
```

## 2. Design Gate

```yaml
design_gate:
  architecture_significance: local
  system_design_skill_required: false
  reason: "This is repo-local skill governance under existing contracts. It affects agent routing but does not add a new architecture boundary, persistent data, external write path, deployment topology, or trust boundary."
```

Existing Human Gate rules apply if implementation later attempts external
writes, dependency changes, release, protected actions, or other gated work.

## 3. Success Criteria

The work is complete when all are true:

```text
- Every repo-local skill has a precise frontmatter `description`.
- Directory name and frontmatter `name` still match for every skill.
- Each description reflects actual skill use conditions and excludes obvious
  non-use cases when overlap risk is high.
- Descriptions are not expanded merely to increase firing.
- Skill body sections support the description with compact Use when / Do not use
  when / Stop or Output guidance where needed.
- Each changed skill states the effect it should have on agent behavior, such as
  stricter contract review, safer migration planning, better browser proof, or
  narrower release verification.
- Effectiveness improvements are observable through output shape, decision
  criteria, verification focus, stop conditions, or reduced ambiguity.
- Overlap among adjacent skills is intentionally resolved or documented.
- `.agents/skills/SKILL_INDEX.md` remains accurate.
- Existing active contracts, storage rules, human gates, and allowed write
  targets are not overridden.
- Structural verification passes.
```

## 4. Method

### Phase 1: Inventory and overlap map

Read only:

```text
.agents/skills/SKILL_INDEX.md
.agents/skills/*/SKILL.md frontmatter
directly relevant skill body sections for skills being revised
```

Produce an overlap map before editing:

```text
- api-contract vs backend-implementation
- frontend-implementation vs ui-art-direction vs ui-quality-gate
- frontend-implementation vs react-next-performance
- browser-verification vs release-check
- research-before-build vs doc-lookup vs system-design
- security-check vs api-contract/db-migration/deploy-readiness
- img-to-frontend vs figma-design-to-code vs ui-art-direction
- skill-authoring-governance vs system-design/research-before-build
```

### Phase 2: Trigger standard

For each skill, classify its trigger as one of:

```text
always-core-for-domain:
  Required whenever the named domain surface is directly changed.

conditional-risk:
  Required only when a risk, gate, verification need, or cross-boundary concern
  exists.

specialized-input:
  Required only when the user supplies a specific asset, source, or design mode
  such as Figma, screenshot, generated image, or current official docs.

governance-only:
  Required only for skill lifecycle or policy integrity work.
```

Do not use this classification as new user-facing taxonomy unless it helps a
specific skill. It is an implementation aid for description precision.

### Phase 3: Effectiveness standard

For each skill being changed, define:

```text
effect_target:
  What better behavior should happen when this skill fires?

behavior_change:
  What should the agent do differently from default coding behavior?

observable_output:
  What output, check, decision, or evidence should show the skill worked?

non_effect:
  What should this skill not try to improve?
```

Effectiveness rules:

```text
- Prefer concrete workflow steps over generic advice.
- Prefer stop conditions, required outputs, and verification focus over prose.
- Keep reusable guidance small enough to fit context.
- Do not improve effectiveness by broadening the frontmatter description.
- Do not add framework/API details that should be handled by doc-lookup.
- Do not make every skill responsible for planning, security, design, and
  release; route to adjacent skills when those concerns are material.
```

### Phase 4: Revise descriptions and bodies

For each skill:

```text
1. Compare frontmatter description to actual body workflow.
2. Identify false-positive triggers and false-negative triggers.
3. Tighten description without expanding activation scope.
4. Identify the skill's intended effect on agent behavior.
5. Add or refine `Do not use when` only where overlap is likely.
6. Add or refine compact Output / Stop / Verification guidance where it makes
   the skill more effective.
7. Keep SKILL.md compact.
8. Avoid framework details that belong in doc-lookup or references.
```

Description rules:

```text
- Start with "Use when ..." or equivalent direct trigger language.
- Name concrete surfaces, artifacts, or risks.
- Avoid broad terms such as "improve", "work on", "any", "general",
  "best practices", or "quality" unless narrowed by a specific surface.
- Prefer exclusions over expansion when overlap exists.
- Do not list every possible stack or file type.
```

### Phase 5: Verification and review

Run the narrowest relevant checks first:

```sh
uv run pytest -q tests/test_extension_surface_integrity.py
uv run pytest -q tests/test_system_design_integrity.py
make test-fast
make check-foundation
```

If skill trigger guardrail tests are added, include them in `make test-fast` only
when they are fast and structural.

### Phase 6: Cross-review

Use two read-only subagents after implementation:

```text
Reviewer 1: trigger precision, overlap, and false-positive review.
Reviewer 2: skill effectiveness, output usefulness, governance, storage,
active-doc, and verification review.
```

Each reviewer must receive a narrow file scope and return findings first with
file/line references.

## 5. Skill-Specific Review Focus

```text
api-contract:
  Ensure it fires for API contracts and schemas, not every backend edit.
  Improve effect by forcing request/response, status code, error, auth,
  pagination, and compatibility thinking before implementation.

backend-implementation:
  Ensure it fires for backend business logic/runtime work, not API contract
  design that belongs first to api-contract.
  Improve effect by making repository/service/job/data-access changes follow
  existing boundaries with focused verification.

browser-verification:
  Ensure it fires when real browser proof is needed, not every UI change.
  Improve effect by requiring concrete browser evidence for the route or flow at
  risk, including console/network/viewport concerns when relevant.

db-migration:
  Ensure it fires only for schema/index/constraint/migration/backfill/data
  strategy changes.
  Improve effect by forcing rollback/backfill/data-safety and migration-order
  reasoning.

deploy-readiness:
  Ensure it fires for deployment/runtime/CI/CD/env/build/release surfaces, not
  ordinary code verification.
  Improve effect by surfacing runtime config, health, rollback, and operational
  readiness gaps.

doc-lookup:
  Ensure it fires for current external docs and stale API risk, not stable
  repo-local behavior.
  Improve effect by making official/current documentation constrain the answer
  without replacing repo-local truth.

figma-design-to-code:
  Ensure it fires only for implementing code from Figma design context or Figma
  URLs, not general UI design.
  Improve effect by preserving design context, component mapping, assets, and
  visual parity checks.

frontend-implementation:
  Ensure it fires for React/Next/UI implementation work, while delegating visual
  art direction, quality gate, and performance concerns to adjacent skills when
  those are specifically present.
  Improve effect by strengthening accessibility, state, routing, loading/error,
  and responsive implementation defaults.

img-to-frontend:
  Ensure it fires only for explicit image-first/screenshot/generated-design
  implementation workflows.
  Improve effect by keeping image-derived implementation grounded in the actual
  visual reference rather than generic UI patterns.

react-next-performance:
  Ensure it fires only when React/Next server-client boundaries, fetching,
  caching, hydration, bundle, render, or responsiveness risk is present.
  Improve effect by making performance-sensitive implementation choices explicit
  and verifiable.

release-check:
  Ensure it fires for handoff/merge/release readiness, not during every small
  edit.
  Improve effect by matching verification breadth to release risk and reporting
  residual risk clearly.

research-before-build:
  Ensure it fires before building when repo patterns, external constraints, or
  dependency/version uncertainty matter, not for obvious local refactors.
  Improve effect by preventing premature implementation and recording the
  decisive pattern or constraint.

security-check:
  Ensure it fires for concrete security-sensitive surfaces, not generic quality
  concerns.
  Improve effect by forcing threat, trust-boundary, input, secret, and side
  effect review where material.

skill-authoring-governance:
  Ensure it fires only for repo-local skill lifecycle or empirical tuning work.
  Improve effect by making skill changes evidence-backed, compact, and
  index/frontmatter consistent.

system-design:
  Ensure it fires only for significant architecture boundaries or high-blast
  radius design choices under the simplified design gate.
  Improve effect by requiring options, tradeoffs, boundaries, rollback, and
  verification before significant implementation.

tdd-scope:
  Ensure it fires for focused failing-test-first work, not every test addition.
  Improve effect by requiring the smallest useful failing test before risky
  implementation.

ui-art-direction:
  Ensure it fires for premium visual direction and art-quality UI decisions, not
  ordinary frontend implementation.
  Improve effect by raising visual hierarchy, composition, motion, and
  domain-fit decisions without replacing implementation skills.

ui-quality-gate:
  Ensure it fires for post/during UI quality checks and minimal fixes, not broad
  redesign.
  Improve effect by catching accessibility, focus, responsive, overflow, and
  state-quality issues with minimal targeted fixes.
```

## 6. Expected Outputs

Implementation should produce:

```text
- revised .agents/skills/*/SKILL.md files as needed
- possibly updated .agents/skills/SKILL_INDEX.md if grouping or notes need
  precision
- focused tests only if they enforce durable trigger, effectiveness, or
  governance behavior
- Plan_N0002.log.md updates with decisions, commands, verification, and
  residual risk
```

## 7. Acceptance Criteria

```text
- No new repo-local skills are added.
- No skill is renamed or deleted without explicit follow-up approval.
- No description becomes broader solely to increase activation.
- Each changed skill has a clear trigger and, where needed, a clear non-trigger.
- Each changed skill has a clear intended effect on agent behavior.
- Effect improvements are expressed as compact workflow, output, stop, or
  verification guidance, not broad manuals.
- Adjacent skills have less trigger overlap than before.
- Skill bodies remain compact.
- Directory/frontmatter/index consistency passes.
- Active docs are unchanged.
- No storage roots are added.
- Verification results are recorded in Plan_N0002.log.md.
- Two read-only subagent cross-reviews are completed after implementation.
```

## 8. Verification Targets

Minimum:

```sh
uv run pytest -q tests/test_extension_surface_integrity.py
make test-fast
```

Full:

```sh
make check-foundation
```

## 9. Current Source Refs

```text
AGENTS.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
.agents/skills/skill-authoring-governance/SKILL.md
.agents/skills/SKILL_INDEX.md
.agents/skills/*/SKILL.md
tests/test_extension_surface_integrity.py
tests/test_system_design_integrity.py
Makefile
Plan/README.md
```

## 10. Next Action

Implementation should start with an inventory diff and overlap map, then revise
skills in small batches by adjacent trigger groups. Do not begin by bulk-editing
all descriptions.
