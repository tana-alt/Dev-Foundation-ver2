---
name: harness-tool-post-tool-use-hook
description: Use for the Harness `post-tool-use-hook` tool only.
---

# Harness Tool: post-tool-use-hook

## When
Record task-scoped trajectory events after tool use.

## How
Drain hook input safely and avoid storing secrets or raw unrelated context.

## What
Writes trajectory JSONL for later metrics.
