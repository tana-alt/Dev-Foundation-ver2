# Demo Foundation Overview

This artifact is a documentation-only outline for presenting the foundation to
external readers. It does not execute tools, store runtime state, or represent a
completed product workflow.

## Scenario

A maintainer wants an agent to make a small documentation improvement without
opening unrelated repo context or weakening review gates.

## Outline

1. Issue candidate: "Explain the foundation for external readers."
2. Source refs: `AGENTS.md`, `README.md`, and the three active contracts.
3. Allowed writes: overview docs and this sanitized artifact directory.
4. Execution boundary: one owned `agent/*` branch and one external worktree.
5. Verification: inspect changed docs and run the narrowest available local
   check, starting with `make check-fast`.
6. Handoff: report changed files, checks, unverified surfaces, residual risk,
   blockers, and human gates.

## Non-Contents

This artifact intentionally excludes raw agent transcripts, local filesystem
inventories, browser sessions, credentials, logs, queues, lock ledgers, and
external service payloads.
