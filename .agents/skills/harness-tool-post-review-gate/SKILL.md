---
name: harness-tool-post-review-gate
description: Use for the Harness `post-review-gate` tool only.
---

# Harness Tool: post-review-gate

## When
Run after required review lanes pass and before PR creation.

## How
Use from the integrator role as a deterministic lifecycle hook. It must not
invoke AI review.

## What
Writes post-review-gate-result evidence, runs the mechanical gate, and
classifies failures as writer rework, integrator fallback, or Harness error.
