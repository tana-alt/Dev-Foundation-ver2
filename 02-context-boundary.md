---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Context Boundary

## Purpose

Context boundaries prevent workers from turning a focused task into a broad repo
reading exercise. They reduce drift, cost, stale assumptions, and accidental
coupling.

This document replaces role-based context rules with work-unit-based context
rules.

## Context Classes

### Required Context

Refs without which the task cannot be performed safely.

Examples:

- user request or work item
- project state
- relevant source files
- current design, plan, or requirement
- failing test output
- required template or schema

### Optional Context

Refs that may improve quality but are not needed to produce a valid first pass.

Examples:

- recent related decisions
- previous implementation notes
- examples from similar projects
- non-blocking research notes

### Denied By Default

Refs that should not be read unless the work contract explicitly asks for them.

Examples:

- archive directories
- unrelated project logs
- broad repo history
- secret material
- long monitoring logs
- speculative strategy notes

## Boundary Rules

- A work unit lists its `source_refs`.
- A worker reads the listed refs first.
- The worker may inspect nearby implementation context when necessary to make a
  safe local change.
- If required context is missing, the worker emits a rework record or asks a
  focused question.
- Optional context should be summarized when referenced.
- Denied-by-default context requires an explicit reason.

## Context Expansion

Context can expand only for a concrete reason:

- a referenced file points to a required schema or template
- a failing verification requires nearby implementation inspection
- a contract cannot be satisfied without a missing source ref
- a security, compliance, or data-sensitivity concern appears

When context expands, the output should note why.

## Minimal Context Checklist

- Is the task intent clear?
- Are source refs explicit?
- Are allowed write targets clear?
- Are expected outputs named?
- Are verification expectations clear?
- Is there a path for blockers or missing context?
