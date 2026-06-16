---
plan_id: Plan_N0004
project_id: system-improvement
status: draft
log_ref: Plan/system-improvement/logs/Plan_N0004.log.md
---

# Reference Doc Trigger Precision And Effectiveness Plan

## 0. Positioning

This plan adapts the empirical tuning model from
`skill-authoring-governance` to the repo's routed reference docs.

Primary goal:

```text
Improve whether agents open the correct docs/reference file when needed, avoid
opening unrelated references, and apply the reference after opening it.
```

Hard rule:

```text
This plan only creates the execution protocol. Do not run benchmarks, dispatch
answer subagents, or edit reference docs during Plan creation.
```

The improvement target is correct activation, not broad activation. Do not make
references always-read, do not move detailed reference material into active
docs, and do not broaden routes merely to increase reads.

## 1. Scope

### Included reference docs

```text
docs/reference/agent-runtime-and-scope-reference.md
docs/reference/packet-evidence-and-rework-reference.md
docs/reference/repo-boundary-and-storage-reference.md
docs/reference/verification-ci-and-pr-reference.md
docs/reference/git-worktree-and-branch-reference.md
docs/reference/migration-and-acceptance-reference.md
```

### Routing surfaces in scope only when needed

```text
AGENTS.md
README.md
```

Use these only to keep the compact reference route labels aligned with changed
reference trigger language. Do not expand them into manuals.

### Allowed write targets during execution

```text
docs/reference/*.md
AGENTS.md
README.md
tests/
artifact/system-improvement/evidence/Plan_N0004/**
artifact/system-improvement/verification/Plan_N0004/**
artifact/system-improvement/manifest.yaml
Plan/system-improvement/logs/Plan_N0004.log.md
```

Shared routing surfaces, tests, and artifact manifest updates are integration
work. Per-reference owners should edit only their assigned reference and their
own artifact directory unless a separate integration step assigns more.

### Out of scope

```text
- changing active contracts in docs/01-03
- changing repo-local skills or plugin-installed skills
- adding new reference docs
- deleting or renaming reference docs
- moving reference detail into AGENTS.md or active docs
- making any reference default reading material
- app/source implementation code
- runtime queues, lock ledgers, broad logs, dashboards, or storage roots
- claiming empirical validation from static review alone
```

## 2. Design Gate

```yaml
design_gate:
  architecture_significance: local
  system_design_skill_required: false
  reason: "This is reference-doc routing and effectiveness tuning under existing repo contracts. It does not add a service boundary, public contract, persistent data owner, trust boundary, external write path, deployment topology, or irreversible migration."
```

Human gates still apply for protected actions, external writes, dependency
changes, release, deployment, secret-bearing work, or security-sensitive runtime
changes. The planned work should avoid those surfaces.

## 3. Trigger Standard

Each included reference should have a compact trigger block near the top that
answers:

```text
- Open this reference when:
- Do not open this reference when:
- Adjacent references:
- Expected effect after opening:
```

Rules:

```text
- Trigger language must match the reference's actual body.
- Trigger language must improve discrimination, not raw read volume.
- "Do not open" bullets are required where overlap is likely.
- Adjacent references should resolve routing conflicts without making agents
  read all adjacent docs.
- Expected effect must be observable in output, chosen commands, write
  preconditions, evidence shape, or rework decision.
- Keep active docs compact. Route detail belongs in the reference itself.
```

## 4. Initial Reference Routing Map

Use this as the starting hypothesis for benchmark design. Execution may revise
wording only after empirical observation.

```text
agent-runtime-and-scope-reference:
  open for scope boundaries, invocation boundaries, handoff compatibility,
  parallel lanes at the concept level, retry/idempotency, or external runtime
  input.
  adjacent: git-worktree-and-branch for concrete branch/worktree operations;
  packet-evidence-and-rework for structured work contracts or rework records.

packet-evidence-and-rework-reference:
  open for creating or reviewing work contracts, packets, evidence records,
  verification records, and rework records.
  adjacent: verification-ci-and-pr for choosing current commands or PR evidence;
  agent-runtime-and-scope for handoff/runtime boundaries.

repo-boundary-and-storage-reference:
  open for repo layout, durable placement, project-scoped storage, ignored
  local state, skills/plugins placement, overlays, and past-source handling.
  adjacent: packet-evidence-and-rework for record fields; migration-and-acceptance
  for foundation rebuild acceptance.

verification-ci-and-pr-reference:
  open for current verification commands, fast/full gate choice, CI/CD
  readiness, PR or handoff evidence, and operational notes on human gates.
  adjacent: packet-evidence-and-rework for record schemas; git-worktree-and-branch
  for branch/worktree evidence.

git-worktree-and-branch-reference:
  open for local writes, branch isolation, parallel agent work, conflict checks,
  worktree creation, branch naming, and PR preparation.
  adjacent: agent-runtime-and-scope for conceptual parallel lanes;
  verification-ci-and-pr for push/PR verification.

migration-and-acceptance-reference:
  open for auditing the foundation rebuild, migration acceptance, or checking
  that compact active docs and routed references still satisfy the migration
  goals.
  adjacent: repo-boundary-and-storage for placement and storage details.
```

## 5. Execution Roles

The work is split into three role types.

### Benchmark Creator

Purpose:

```text
Create fixed rubrics and scenarios before any answer subagent runs.
```

Must do:

```text
- read the included reference docs and compact route labels
- define expected reference opens and expected non-opens for each scenario
- create one shared rubric for reference selection and application
- create per-reference scenario sets with median, edge, negative, and sealed
  hold-out cases
- mark any scenario as multi-reference only when the task truly requires it
- store fixed benchmark packets before observation starts
```

Must not do:

```text
- edit docs
- score answer outputs
- change scenarios after observation starts
- inspect hold-out cases during the inner loop
```

### Answer Subagent

Purpose:

```text
Act as a fresh worker solving one realistic task packet and deciding which
reference docs to open.
```

Input:

```text
- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- one benchmark scenario
- no benchmark answer key
```

Required output:

```text
- task answer or handoff artifact
- source_refs_used
- refs_considered_but_not_opened, with reason
- why each opened reference was necessary
- where the reference changed the answer, command choice, evidence shape,
  write precondition, or rework decision
- confusion report for trigger wording, adjacent refs, stale routes, or missing
  expected effect
```

Must not do:

```text
- read all docs/reference files by default
- read benchmark rubrics, answer keys, observer notes, or prior iterations
- edit files
```

### Observer / Reference Owner

Purpose:

```text
Observe answer outputs, score them against fixed rubrics, choose one improvement
theme, and apply the smallest reference-doc or route-label edit needed.
```

Must do:

```text
- compare actual reference opens against expected opens and expected non-opens
- distinguish selection failure from application failure
- use answer self-report as a signal, not as sole proof
- choose exactly one improvement theme per iteration
- keep edits compact and local to the assigned reference or route label
- record score, confusion reports, patch summary, and next decision
```

Must not do:

```text
- solve benchmark scenarios directly
- rewrite rubrics or scenarios mid-loop
- broaden triggers solely to raise activation
- accept a run that skipped hold-out or regression as production-validated
```

## 6. Production Benchmark Workflow

Adapt the production path from
`.agents/skills/skill-authoring-governance/references/operating-modes.md`.

### Iteration 0: static routing integrity check

For each reference, record:

```text
- current top-level trigger phrase
- body sections that are not represented by trigger language
- trigger claims that are not supported by the body
- adjacent-reference overlap
- missing "do not open" guardrails
- missing expected effect after opening
- broken or stale cross-routes
```

If only this step runs, report `lightweight-preflight only`. Do not claim
production validation.

### Iteration 0.5: fixed benchmark packet

Before any answer subagent runs, fix and store:

```text
- rubric with 3-7 items scored as 0 / 0.5 / 1
- meta rubric check
- per-reference inner-loop scenarios:
  - one median positive case
  - one edge or overlap case
  - one negative non-trigger case
- one sealed hold-out case per reference
- Stage 2 regression cases
- thresholds:
  - minimum meaningful score gain: +0.05
  - hold-out degradation limit: -15 percentage points
  - over-read alert: more than 2 unrelated references opened
  - iteration limit: 4
```

The expected answer key must identify:

```text
- required references
- acceptable optional references
- references that should not be opened
- output behavior that proves the reference was applied
```

### Iterations 1..N: observe, edit, retest

For every iteration:

```text
1. Dispatch a fresh answer subagent for one scenario.
2. Answer subagent returns output and reference-use self-report.
3. Observer scores reference selection and application against the fixed rubric.
4. Observer chooses exactly one improvement theme.
5. Observer applies the smallest edit needed for that theme.
6. Observer records score, confusion reports, patch summary, and next decision.
```

The loop stops only when both are true for two consecutive iterations:

```text
- no new trigger ambiguity, stale route, or adjacent-reference confusion
- score gain is below the fixed improvement threshold or rubric is fully met
```

The loop escalates if the iteration limit is reached without meeting the stop
condition.

### Hold-out

Open sealed hold-out cases only after the stop condition is met. Score them
against the original fixed rubric.

Reject or rework the edit if:

```text
- hold-out score drops more than the fixed degradation limit from the latest
  inner-loop mean
- hold-out reveals a new trigger/body mismatch
- hold-out requires changing the rubric or scenario definitions
- hold-out causes over-reading of references that should remain unopened
```

### Stage 2 regression confirm

Run fixed regression cases after hold-out passes. Merge-ready status is allowed
only when no prior success case degrades.

## 7. Rubric Skeleton

The Benchmark Creator may refine labels, but must preserve these dimensions.

```text
reference selection recall:
  Did the answer subagent open every reference required by the scenario?

reference selection precision:
  Did the answer subagent avoid unrelated references and avoid all-reference
  reading?

trigger rationale:
  Did the answer subagent explain why each opened reference was needed using
  route language rather than generic caution?

reference application:
  Did the final answer, evidence, verification choice, write precondition, or
  rework decision reflect the opened reference?

adjacent-reference boundary:
  Did the answer subagent correctly choose among overlapping references or
  explicitly justify a multi-reference case?

active-contract preservation:
  Did the output keep AGENTS.md and docs/01-03 as active contracts and avoid
  treating reference docs as overriding rules?
```

## 8. Scenario Coverage Requirements

Each reference needs at least:

```text
- 2 positive cases where the reference should open
- 1 negative case where the reference should not open
- 1 overlap case against an adjacent reference
- 1 sealed hold-out case
```

The full suite must include combined workflows that require two references, but
combined cases must name why both are necessary. Example stress points:

```text
- parallel write task: git-worktree-and-branch plus verification-ci-and-pr
- new durable artifact placement: repo-boundary-and-storage plus
  packet-evidence-and-rework only if a structured evidence record is required
- failed check needing rework: verification-ci-and-pr plus
  packet-evidence-and-rework
- external runtime handoff: agent-runtime-and-scope, and packet-evidence only
  if a structured work contract is requested
- foundation migration audit: migration-and-acceptance, with repo-boundary only
  for storage or route placement claims
```

Negative cases are required to prevent broadening:

```text
- quick typo or formatting fix in an already named file
- direct question answer requiring no repo placement, packet, branch, or CI
- ordinary implementation with clear allowed write targets and obvious nearest
  test
- reading every reference "just in case"
```

## 9. Evidence And Artifact Layout

Store sanitized benchmark evidence under:

```text
artifact/system-improvement/evidence/Plan_N0004/
  benchmark/
    rubric.md
    scenarios.md
  <reference-name>/
    snapshot.md
    preflight.md
    iteration-01.md
    iteration-02.md
    iteration-03.md
    iteration-04.md
    hold-out.md
    regression.md

artifact/system-improvement/verification/Plan_N0004/
  benchmark-creator-check.md
  <reference-name>/
    score-summary.md
    structural-checks.md
```

Update `artifact/system-improvement/manifest.yaml` during integration if
artifact records are created.

Do not store secrets, raw browser sessions, credentials, broad logs, runtime
ledger state, or unscoped historical material in artifacts.

## 10. Acceptance Criteria

Execution is complete when all are true:

```text
- Every included reference has a production benchmark result or explicit
  skipped status with reason.
- Every production result includes Iteration 0, fixed rubric/scenarios,
  answer-subagent loop, stop check, hold-out, and Stage 2 regression.
- Benchmark Creator, Answer Subagent, and Observer roles remained separate.
- Rubrics and scenarios were fixed before answer-subagent runs and not changed
  mid-loop.
- Reference trigger wording became clearer without making references
  always-read.
- Adjacent-reference overlap is intentionally resolved or documented.
- AGENTS.md route labels remain compact and aligned when touched.
- Active contracts in docs/01-03 are not changed.
- `make test-fast` passes.
- `make check-foundation` passes before handoff if the aggregate change is
  merge-ready.
```

## 11. Verification Targets

Per-reference owner verification:

```sh
git diff --check
uv run pytest -q tests/test_foundation_integrity.py
```

Parent integration verification:

```sh
git diff --check
make test-fast
make check-foundation
```

For docs-only edits, the narrowest acceptable check is inspection of changed
docs plus the closest structural test. Run broader checks only when the
aggregate change is heading to PR, merge, or release handoff.

## 12. Parent Coordination Rules

The parent agent must:

```text
- dispatch the Benchmark Creator before any answer subagent
- keep the answer key hidden from answer subagents
- dispatch fresh answer subagents for scenarios
- prevent answer subagents from reading observer notes or prior iterations
- reject runs that skip production steps but claim production validation
- integrate shared routing-surface edits only after scored evidence exists
- record final results in Plan_N0004.log.md
```

Parallel execution is allowed only with complete `git_scope`, separate owned
branch/worktree per lane, and disjoint write targets. Otherwise run one
reference owner at a time.

## 13. Current Source Refs

```text
AGENTS.md
README.md
Plan/README.md
artifact/README.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
docs/reference/agent-runtime-and-scope-reference.md
docs/reference/packet-evidence-and-rework-reference.md
docs/reference/repo-boundary-and-storage-reference.md
docs/reference/verification-ci-and-pr-reference.md
docs/reference/git-worktree-and-branch-reference.md
docs/reference/migration-and-acceptance-reference.md
.agents/skills/skill-authoring-governance/SKILL.md
.agents/skills/skill-authoring-governance/references/operating-modes.md
.agents/skills/skill-authoring-governance/references/rubric-design.md
.agents/skills/skill-authoring-governance/references/templates.md
.agents/skills/skill-authoring-governance/references/example-log.md
Plan/system-improvement/plans/Plan_N0003.md
Plan/system-improvement/logs/Plan_N0003.log.md
```

## 14. Next Action

Start execution by assigning a Benchmark Creator subagent to produce
`artifact/system-improvement/evidence/Plan_N0004/benchmark/rubric.md` and
`artifact/system-improvement/evidence/Plan_N0004/benchmark/scenarios.md`.
No reference edits should happen until those benchmark packets are fixed.
