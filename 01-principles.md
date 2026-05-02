---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Principles

## Purpose

The foundation exists to make development work legible, verifiable, and easy to
continue across humans, LLM sessions, tools, and automations.

It does not require a parent-agent / subagent hierarchy. Instead, it defines
small work units, explicit context, evidence-carrying outputs, and project-local
records.

## Core Principles

### Ground Work In Observed Context

Work starts from explicit `source_refs`, existing files, prior records, user
instructions, or verified external evidence. When needed context is missing, the
worker records the gap instead of filling it with assumptions.

### Keep Context Small

Each work unit should receive only the context needed to perform and verify the
task. Broad repo history, unrelated logs, archived experiments, and hidden
strategy state stay out unless they are explicitly relevant.

### Use Contracts, Not Role Hierarchies

Work is defined by:

- input refs
- expected outputs
- allowed write targets
- evidence requirements
- verification requirements
- next action

The person or tool doing the work is less important than the contract the work
must satisfy.

### Let Artifacts Shape Workflow

Workflow order should follow artifact compatibility:

```text
output artifact -> next input requirement
```

This keeps the process adaptable. A plan, prototype, review, test result, or
release note can all become the next input if its contract is explicit.

### Carry Evidence With Outputs

Outputs should include the evidence needed to understand and trust them:

- source refs used
- changed paths
- decisions made
- facts vs inferences
- verification performed
- residual risk
- blockers and open questions

### Keep Project Truth Local

The canonical state of a project belongs under that project's directory. External
views, dashboards, vaults, and sync overlays can make project state easier to
read, but they should not become the source of truth.

### Prefer Small Rework

When work is blocked, invalid, risky, or under-specified, return the smallest
useful rework record. The goal is to repair the next step without restarting the
whole process.

### Verification Is Output

Verification is not an afterthought. Every meaningful work unit should say what
was checked, what could not be checked, and what risk remains.
