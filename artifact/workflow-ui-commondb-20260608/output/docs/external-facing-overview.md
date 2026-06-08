# External-Facing Foundation Overview

## What This Repo Is

Dev-Foundation-ver2 is a compact governance and workflow foundation for
human-supervised agent work. It is meant to make small teams more explicit
about scope, source refs, allowed writes, verification, handoff evidence, and
human gates before an agent changes files or hands work back for review.

The repo is intentionally small. The active behavior is routed through
`AGENTS.md`, `README.md`, and the three operating contracts in `docs/`. Longer
reference material exists under `docs/reference/`, but agents open those
references only when a task needs them.

## Current Runnable And Check Surfaces

The current runnable surface is local verification and environment restoration,
not an end-user workflow app.

- `make doctor` inspects the local development environment without writing
  project state.
- `uv sync --frozen --group dev` restores locked development dependencies.
- `make check-fast` runs the fast local guard: formatting check, lint,
  shell syntax checks, lane-map checks, and fast structural tests.
- `make check-foundation` runs the full Foundation Robustness Gate used for
  CI-equivalent confidence when required tools are available.
- `sh scripts/setup-agent-environment.sh` restores ignored local agent wiring
  from tracked templates.

The tracked hooks, scripts, templates, and tests support the governance layer:
they check branch/worktree policy, lane-map shape, contract consistency,
environment assumptions, shell scripts, and repo hygiene.

## Workflow Shape

The foundation treats agent execution as a bounded workflow rather than an open
chat transcript. A typical planned slice moves through:

```text
IssueCandidate
  -> Issue
  -> ImplementationProposal
  -> ApprovalDecision
  -> ApprovedWorkContract
  -> ExecutionRun
  -> VerificationResult
  -> HandoffArtifact
```

That model is a governance boundary. Future adapters can connect to tools such
as a UI, Codex SDK runner, Codex App Server bridge, CommonDB context source, or
GitHub Issues, but those adapters should not become the canonical state source
for the foundation.

## Non-Goals

This repo does not currently ship a production workflow UI, service, database,
queue, scheduler, or multi-user agent runtime. It also does not store raw
thread bodies, browser sessions, local runtime ledgers, broad logs, credentials,
vault contents, vector stores, or secrets.

The foundation is not a replacement for human review, CI, release management,
or repository ownership. It provides bounded contracts and checks that help
humans and agents collaborate with fewer hidden assumptions.

## Human Gates

Human approval remains required before high-impact actions, including:

- merging changes,
- direct App Server integration,
- real Codex SDK execution that can write files,
- CI/CD or dependency changes,
- release or deployment,
- credential, auth, billing, database, infrastructure, or secret handling,
- external writes outside an owned review branch or pull request.

Agents may prepare review branches and handoff evidence when scope, branch and
worktree ownership, verification, and allowed write targets are clear. Humans
decide whether to merge, release, deploy, or authorize gated integrations.

## Demo Artifact Outline

The small outline under `artifact/workflow-ui-commondb-20260608/output/demos/demo-foundation-overview/` is a sanitized
demo sketch for explaining the foundation without running external systems. It
shows the intended narrative:

1. define a bounded issue candidate,
2. approve a work contract with source refs and allowed writes,
3. execute in an owned agent branch/worktree,
4. record verification results,
5. hand off changed paths, evidence, residual risk, and human gates.

The demo is documentation-only today. It contains no secrets, runtime state,
external tool transcripts, or local machine-specific paths.
