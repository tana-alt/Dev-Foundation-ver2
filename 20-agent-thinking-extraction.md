---
status: draft
owner: foundation
source_of_truth_level: distilled
created_at: 2026-05-02
source_refs:
  - AGENTS.md
  - ARCHITECTURE.md
  - docs/rules.md
  - docs/context-scope-policy.md
  - docs/agent-io-dependency-map.md
  - docs/project-operation-harness.md
  - docs/harness-contract.md
  - artifacts/runtime/context-scope.yaml
  - artifacts/runtime/agent-io-contract-map.yaml
  - artifacts/runtime/runtime-policy.yaml
  - artifacts/packets/handoff-packet.yaml
  - artifacts/packets/evidence-packet.yaml
  - artifacts/packets/rework-packet.yaml
---

# Agent Thinking Extraction

This document extracts the reusable thinking model from the repo's
agent-oriented materials without preserving the parent-agent / subagent
structure as a required architecture.

## Core Shift

The reusable idea is not "make a hierarchy of agents."

The reusable idea is:

```text
bounded work + scoped context + explicit contracts + evidence + verification + small rework
```

An LLM session, human, script, or automation can all use this model.

## Thinking Loop

The implied thinking loop across the repo is:

1. Resolve the work boundary.
2. Read only the refs needed for that boundary.
3. Identify the expected output contract.
4. Separate facts, inferences, and missing context.
5. Produce the smallest useful artifact.
6. Attach evidence refs and changed paths.
7. Run or name verification.
8. Emit next action, blocker, or rework.

## Grounding

The repo repeatedly insists that work must start from observed context.

Reusable principle:

- Do not begin from memory or broad assumptions.
- Read the explicitly named source refs first.
- When current facts are needed, use current evidence.
- If facts are missing, record a blocker instead of inventing them.
- Keep facts and inferences separate in outputs.

## Context Discipline

The context-scope materials encode a strong anti-pattern:

```text
Do not read the whole repo just because it is available.
```

Reusable principle:

- Every work unit should define required refs, optional refs, and denied-by-default surfaces.
- Context may expand only when it is needed to satisfy the task or verify the result.
- Archives, broad logs, unrelated projects, and secrets stay out of normal work.
- If scoped context is insufficient, ask for a scoped expansion or emit rework.

## Contract-First Work

The agent I/O maps frame workflow as compatible inputs and outputs rather than
as a fixed story.

Reusable principle:

```text
previous output -> next input requirement -> next work unit
```

Work contracts should name:

- task intent
- source refs
- expected outputs
- allowed write targets
- evidence requirements
- verification requirements
- next action

This survives even if there are no named agents.

## Evidence-Carrying Outputs

The handoff/evidence/rework packet family shows a consistent output shape:

- expected outputs
- evidence refs
- changed paths
- verification results
- blockers
- next owner or next action

Reusable principle:

- An artifact should carry enough evidence for another worker to continue.
- Claims without evidence should be marked as assumptions or removed.
- Missing context should become a rework record, not hidden prose.

## Verification As Part Of Thinking

The repo treats verification as part of the output, not a final decorative step.

Reusable principle:

- Choose the smallest relevant check first.
- Widen only when the change surface requires it.
- Record checks that pass, fail, are skipped, or are blocked.
- Explain residual risk.
- Treat verification failure as a local repair signal before broad rewrites.

## Project-Local Truth

The project boundary materials separate canonical project state from overlays.

Reusable principle:

- Concrete project artifacts belong under `projects/{project_id}/`.
- Dashboards, Obsidian views, exported docs, and summaries are overlays.
- Shared lessons are distilled from project-local evidence; they are not raw log mirrors.
- If an overlay conflicts with project-local state, project-local state wins unless a migration says otherwise.

## Safety And Authority

The repo draws a line between recommendation and authority.

Reusable principle:

- Human approval is required for irreversible or sensitive decisions.
- Secrets, credentials, tokens, cookies, and browser sessions stay outside prompts, packets, and logs.
- CI/CD, deployment, auth, billing, database migrations, public release, and secret changes require explicit gatekeeping.
- LLM output is a recommendation or work artifact, not final authority by default.

## Rework Instead Of Guessing

The rework packet idea is central.

Reusable principle:

Use rework when:

- context is missing
- instructions are ambiguous
- contract shape is invalid
- verification fails
- evidence is insufficient
- risk is outside the worker's authority

Good rework is small. It identifies the missing input or failed condition and
asks for the minimum repair needed to continue.

## Memory And Recency

The repo's activity-memory rules try to avoid both amnesia and log bloat.

Reusable principle:

- Use short recent activity summaries before reading long logs.
- Promote only reusable lessons to shared knowledge.
- Keep local hypotheses separate from validated shared patterns.
- Do not let a single event validate a general rule.

## Abstracted Worker Contract

A role-neutral worker should be able to answer:

- What work am I doing?
- What sources am I allowed or required to read?
- What am I expected to produce?
- Where may I write?
- What evidence supports my output?
- What verification did I perform?
- What remains uncertain?
- What should happen next?

## What To Keep

Keep these ideas for the next foundation:

- scoped context
- source refs
- expected outputs
- allowed write targets
- evidence refs
- changed paths
- verification results
- blockers/open questions
- rework records
- project-local source of truth
- human gate for sensitive actions

## What To Drop Or Demote

Demote these from foundation doctrine to examples or legacy material:

- parent-agent / subagent hierarchy
- SNS-specific roles
- hardcoded role names as architecture
- legacy runtime wording
- broad app-flow assumptions
- project-specific overlays

## Minimal Reusable Formula

```text
Work Request
  -> Context Boundary
  -> Work Contract
  -> Artifact
  -> Evidence Record
  -> Verification Record
  -> Next Action or Rework Record
```

This is the part worth carrying forward.
