---
plan_id: Plan_N0005
project_id: system-improvement
status: completed
log_ref: Plan/system-improvement/logs/Plan_N0005.log.md
---

# Active Doc Trigger Precision And Effectiveness Plan

## 0. Goal

Apply the Plan_N0004 empirical trigger-tuning method to the active docs:

```text
AGENTS.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
```

Improve activation and effect by making each active route easier to apply, while
preserving the compact-foundation rule that `AGENTS.md` plus docs/01-03 stay at
or below 200 total lines.

## 1. Scope And Write Targets

Allowed write targets:

```text
AGENTS.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
Plan/system-improvement/plans/Plan_N0005.md
Plan/system-improvement/logs/Plan_N0005.log.md
Plan/system-improvement/index.yaml
artifact/system-improvement/evidence/Plan_N0005/**
artifact/system-improvement/verification/Plan_N0005/**
artifact/system-improvement/manifest.yaml
```

Out of scope:

```text
- editing docs/reference/** unless a later explicit rework task allows it
- broad repo rewrites, new storage roots, runtime ledgers, or queue state
- making active docs longer than the 200-line combined cap
- changing skills or plugin-installed skills
- protected branch pushes, merges, releases, deployments, or external writes
```

## 2. Trigger Standard

Each active file should make its role observable without becoming a manual:

```text
AGENTS.md: tells agents what to always read and which reference to open by need.
docs/01: controls scope, context boundaries, write preconditions, and side effects.
docs/02: controls complete output, verification order, handoff evidence, and gates.
docs/03: controls repo truth, placement, storage, secrets, and skill/plugin limits.
```

The desired change is not broader reading. It is faster correct routing,
stronger application after reading, and fewer false positives where a reference
or active contract is opened for an unrelated task.

## 3. Empirical Workflow

Use the `skill-authoring-governance` integrity-tuning ideas, adapted to docs:

1. Benchmark Creator creates fixed rubric and scenarios before doc edits.
2. Each doc owner runs observation with answer-runner evidence, patches only its
   assigned active file, and repeats until the stop condition is met.
3. A sealed hold-out and regression scenarios confirm the patch improved the
   target without increasing over-read or weakening active-contract behavior.
4. Parent supervisor reviews, enforces the 200-line cap, integrates manifest/log
   records, and runs the narrowest repo verification set.

One high-effort subagent owns one doc at a time. Per-doc owners must not edit
other active docs. They must keep their assigned file's line count no higher
than its starting count unless the parent explicitly reallocates line budget.

## 4. Stop Conditions

For each active file:

```text
- at least one target scenario passes at 1.0 or improves materially
- at least one non-target/regression scenario shows no broad over-read
- assigned file line count is unchanged or lower
- `AGENTS.md` + docs/01-03 total remains <= 200 lines
- evidence and verification records are written under Plan_N0005 artifacts
```

The overall plan is complete when all four files satisfy the stop conditions,
manifest/log records are updated, and local verification reports the remaining
risks.
