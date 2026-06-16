---
plan_id: Plan_N0003
project_id: system-improvement
status: completed
log_ref: Plan/system-improvement/logs/Plan_N0003.log.md
---

# Repo-Local Skill Empirical Benchmark Tuning Plan

## 0. Positioning

This plan runs empirical benchmark tuning for every repo-local skill after
Plan_N0002's static trigger/effectiveness cleanup.

Primary goal:

```text
Measure, then improve, whether each skill's description, body, references, and
actual subagent outputs align under realistic task scenarios.
```

Hard rule:

```text
This plan only defines the benchmark and delegation protocol. Do not run
benchmarks or edit skills during Plan creation.
```

Use `skill-authoring-governance` in Empirical Integrity Tuning Mode. Each
subagent must read:

```text
.agents/skills/skill-authoring-governance/SKILL.md
.agents/skills/skill-authoring-governance/references/operating-modes.md
.agents/skills/skill-authoring-governance/references/rubric-design.md
.agents/skills/skill-authoring-governance/references/templates.md
.agents/skills/skill-authoring-governance/references/example-log.md
```

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

### Allowed write targets during execution

Per-skill subagents may write only within their assigned scope:

```text
.agents/skills/<skill>/SKILL.md
.agents/skills/<skill>/references/**
artifact/system-improvement/evidence/Plan_N0003/<skill>/**
artifact/system-improvement/verification/Plan_N0003/<skill>/**
```

Shared paths require a separate explicit integration step:

```text
.agents/skills/SKILL_INDEX.md
artifact/system-improvement/manifest.yaml
Plan/system-improvement/logs/Plan_N0003.log.md
tests/
```

The parent agent coordinates dispatch, records the final summary, and verifies
integration. Skill benchmark measurement and skill edits are owned by
subagents.

### Out of scope

```text
- plugin-installed skills
- adding, deleting, or renaming repo-local skills
- active docs or repo contracts
- app/source implementation code
- changing benchmark rubric or scenarios after an inner loop starts
- claiming empirical validation from lightweight-preflight only
- touching unrelated Plan/skill-roadmap-20260527 files
```

## 2. Design Gate

```yaml
design_gate:
  architecture_significance: local
  system_design_skill_required: false
  reason: "This is empirical tuning of repo-local skill instructions and benchmark evidence. It does not add a service boundary, public contract, persistent data owner, trust boundary, deployment topology, external write path, or irreversible migration."
```

Human gates still apply for protected actions, external writes, dependency
changes, release, deployment, secret-bearing work, or security-sensitive
runtime changes. The planned work should avoid those surfaces.

## 3. Execution Model

Run one skill at a time by default. If parallel execution is later approved,
each parallel subagent must use a separate owned branch/worktree and disjoint
write scope.

For each skill, assign a `Skill Benchmark Owner` subagent:

```text
role:
  Run the production empirical integrity workflow for exactly one skill.
scope:
  Target skill file, target skill references, benchmark artifacts for that
  skill, and directly adjacent skill descriptions needed for overlap review.
must_read:
  - target .agents/skills/<skill>/SKILL.md
  - target .agents/skills/<skill>/references/** only if linked or needed
  - skill-authoring-governance SKILL.md
  - all skill-authoring-governance references listed in section 0
must_not_read:
  - broad repo history
  - unrelated plans/logs
  - plugin-installed skills unless the target skill explicitly routes there
must_not_edit:
  - any other skill's files
  - active docs
  - source/app implementation code
  - shared index/tests without explicit integration assignment
```

If the benchmark owner cannot dispatch fresh isolated runner subagents itself,
the parent agent dispatches those runners from the owner's fixed benchmark
packet. The parent still must not score or edit the skill directly.

## 4. Production Benchmark Workflow

Each skill must follow the production path from
`skill-authoring-governance/references/operating-modes.md`.

### Iteration 0: static integrity check

The owner subagent records:

```text
- pre-change snapshot of the target skill file
- description/body/reference mismatches
- ambiguous terms or missing order
- broken or unreachable reference links
- false-positive and false-negative trigger risks
- one smallest theme to fix before empirical loop, if required
```

If only preflight is possible, the run must report
`integrity tuning skipped: dispatch unavailable` or
`lightweight-preflight only`; it must not claim production validation.

### Iteration 0.5: fixed benchmark packet

Before any inner loop begins, the owner fixes and stores:

```text
- rubric with 3-7 items scored as 0 / 0.5 / 1
- meta rubric check
- 2-3 inner-loop scenarios
- 1 sealed hold-out scenario
- Stage 2 regression cases
- thresholds:
  - minimum meaningful score gain: +0.05
  - hold-out degradation limit: -15 percentage points
  - tool-use skew alert: 5x
  - iteration limit: 4
```

Rubrics must not exceed the skill description's scope. Scenario sets must
include one median case and one or two edge cases.

### Iterations 1..N: empirical loop

For every iteration:

```text
1. Dispatch a fresh isolated runner subagent using the subagent prompt template.
2. Runner reads only the target skill text, target references, and the scenario.
3. Runner returns artifact output plus self-report.
4. Owner scores output against the fixed rubric.
5. Owner chooses exactly one improvement theme.
6. Owner applies the smallest skill edit needed for that theme.
7. Owner records score, tool-use signals, self-report gaps, patch, and decision.
```

The loop stops only when both are true for two consecutive iterations:

```text
- no new ambiguity or broken-reference report
- score gain is below the fixed improvement threshold or the rubric is fully met
```

The loop also stops and escalates if the iteration limit is reached without
meeting the stop condition.

### Hold-out

Open the sealed hold-out only after the stop condition is met. Score it against
the original fixed rubric.

Reject or rework the skill if:

```text
- hold-out score drops more than the fixed degradation limit from the latest
  inner-loop mean
- hold-out reveals a new description/body mismatch
- hold-out requires changing the rubric or scenario definitions
```

### Stage 2 regression confirm

Run the fixed regression cases after hold-out passes. Merge-ready status is
allowed only when no prior success case degrades.

## 5. Subagent Role And Scope Matrix

Each row is one independent benchmark owner assignment.

```text
api-contract:
  scope: .agents/skills/api-contract/**
  adjacent refs: backend-implementation, security-check, tdd-scope
  stress focus: API contract shape, compatibility, errors, auth, pagination.

backend-implementation:
  scope: .agents/skills/backend-implementation/**
  adjacent refs: api-contract, db-migration, security-check
  stress focus: backend runtime changes after contracts and schema are clear.

browser-verification:
  scope: .agents/skills/browser-verification/**
  adjacent refs: frontend-implementation, ui-quality-gate, release-check
  stress focus: route/flow proof, console/network evidence, viewport risk.

db-migration:
  scope: .agents/skills/db-migration/**
  adjacent refs: backend-implementation, security-check, release-check
  stress focus: schema/index/constraint/backfill safety and rollback.

deploy-readiness:
  scope: .agents/skills/deploy-readiness/**
  adjacent refs: release-check, security-check, backend-implementation
  stress focus: env/build/runtime/health/rollback readiness.

doc-lookup:
  scope: .agents/skills/doc-lookup/**
  adjacent refs: research-before-build, react-next-performance, security-check
  stress focus: current official docs without replacing repo-local truth.

figma-design-to-code:
  scope: .agents/skills/figma-design-to-code/**
  adjacent refs: frontend-implementation, img-to-frontend, ui-art-direction
  stress focus: Figma source truth, component mapping, parity evidence.

frontend-implementation:
  scope: .agents/skills/frontend-implementation/**
  adjacent refs: ui-art-direction, ui-quality-gate, react-next-performance
  stress focus: ordinary React/Next UI implementation and adjacent routing.

img-to-frontend:
  scope: .agents/skills/img-to-frontend/**
  adjacent refs: figma-design-to-code, ui-art-direction, frontend-implementation
  stress focus: screenshot/generated/image-first implementation boundaries.

react-next-performance:
  scope: .agents/skills/react-next-performance/**
  adjacent refs: frontend-implementation, doc-lookup, release-check
  stress focus: server/client boundaries, data fetching, caching, hydration.

release-check:
  scope: .agents/skills/release-check/**
  adjacent refs: browser-verification, deploy-readiness, security-check
  stress focus: handoff/merge/release verification breadth and residual risk.

research-before-build:
  scope: .agents/skills/research-before-build/**
  adjacent refs: doc-lookup, system-design, backend-implementation
  stress focus: repo patterns, external constraints, dependency uncertainty.

security-check:
  scope: .agents/skills/security-check/**
  adjacent refs: api-contract, db-migration, deploy-readiness
  stress focus: trust boundary, user input, secrets, authz, unsafe tool output.

skill-authoring-governance:
  scope: .agents/skills/skill-authoring-governance/**
  adjacent refs: system-design, research-before-build, release-check
  stress focus: skill lifecycle changes, empirical tuning, compact evidence.

system-design:
  scope: .agents/skills/system-design/**
  adjacent refs: research-before-build, api-contract, deploy-readiness
  stress focus: significant architecture boundaries and not-significant routing.

tdd-scope:
  scope: .agents/skills/tdd-scope/**
  adjacent refs: api-contract, backend-implementation, frontend-implementation
  stress focus: failing-test-first behavior when expected behavior is clear.

ui-art-direction:
  scope: .agents/skills/ui-art-direction/**
  adjacent refs: frontend-implementation, img-to-frontend, ui-quality-gate
  stress focus: visually led creation/redesign versus ordinary UI work.

ui-quality-gate:
  scope: .agents/skills/ui-quality-gate/**
  adjacent refs: frontend-implementation, ui-art-direction, browser-verification
  stress focus: post-change UI quality review and minimal targeted fixes.
```

## 6. Evidence And Artifact Layout

Per skill, store sanitized evidence under:

```text
artifact/system-improvement/evidence/Plan_N0003/<skill>/
  snapshot.md
  preflight.md
  rubric.md
  scenarios.md
  iteration-01.md
  iteration-02.md
  iteration-03.md
  iteration-04.md
  hold-out.md
  regression.md

artifact/system-improvement/verification/Plan_N0003/<skill>/
  structural-checks.md
  score-summary.md
```

Update `artifact/system-improvement/manifest.yaml` during integration if it
does not exist yet.

Do not store secrets, raw browser sessions, credentials, broad logs, or runtime
ledger state in artifacts.

## 7. Acceptance Criteria

Execution is complete when all are true:

```text
- Every included skill has a production benchmark result or explicit skipped
  status with reason.
- Every production result includes Iteration 0, fixed rubric/scenarios,
  empirical loop, stop check, hold-out, and Stage 2 regression.
- Every skill edit was made by a subagent within its assigned scope.
- Parent agent did not directly benchmark-score or edit skills.
- Rubrics and scenarios were fixed before each loop and not changed mid-loop.
- No skill description was broadened solely to increase activation.
- Hold-out and regression results are recorded.
- Structural skill discovery/frontmatter/index checks pass.
- `make test-fast` passes.
- `make check-foundation` passes before handoff if the aggregate change is
  merge-ready.
```

## 8. Verification Targets

Per-skill owner verification:

```sh
uv run pytest -q tests/test_extension_surface_integrity.py
uv run pytest -q tests/test_system_design_integrity.py
```

Parent integration verification:

```sh
git diff --check
make test-fast
make check-foundation
```

If a subagent changes tests, it must run the closest affected tests and record
the command and result in its artifact summary.

## 9. Parent Coordination Rules

The parent agent must:

```text
- dispatch one skill owner at a time by default
- give each owner the exact target skill, adjacent refs, allowed writes, and
  benchmark references
- avoid direct edits to skill files
- integrate only completed subagent patches
- reject runs that skip production steps but claim production validation
- record final results in Plan_N0003.log.md
```

The parent may perform shared-path integration only after all per-skill outputs
are available, or after a subagent explicitly requests shared-path handling.

## 10. Current Source Refs

```text
AGENTS.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
artifact/README.md
Plan/README.md
.agents/skills/skill-authoring-governance/SKILL.md
.agents/skills/skill-authoring-governance/references/operating-modes.md
.agents/skills/skill-authoring-governance/references/rubric-design.md
.agents/skills/skill-authoring-governance/references/templates.md
.agents/skills/skill-authoring-governance/references/example-log.md
.agents/skills/SKILL_INDEX.md
Plan/system-improvement/plans/Plan_N0002.md
Plan/system-improvement/logs/Plan_N0002.log.md
```

## 11. Next Action

Start execution by assigning the first `Skill Benchmark Owner` subagent a single
skill, its scope row, the governance references, and instructions to produce
Iteration 0 and Iteration 0.5 artifacts before any empirical loop starts.
