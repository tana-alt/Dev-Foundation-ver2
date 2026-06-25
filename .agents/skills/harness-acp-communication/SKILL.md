---
name: harness-acp-communication
description: "Use when a Harness agent needs task-scoped ACP or local comms: peer discovery, inbox reads, sending allowed message kinds, or requesting a proposed action without executing it."
---

# Harness ACP Communication

ACP and local comm messages are coordination records. They are not authoritative
completion, review, gate, land, push, or merge results.

## When

- Use `comm-peers` before addressing a local peer.
- Use `comm-inbox` or strict `acp list` before responding.
- Use `comm-send` or strict `acp send` for task-scoped coordination only.
- Use `acp request-action` only to obtain a proposed action.

## How

- Confirm the recipient agent id and role from task-scoped peer or inbox data.
- Use only allowed message kinds from `AGENTS.md`.
- Keep subjects short and bodies evidence-backed.
- In strict mode, use the authenticated session identity; do not override sender
  identity.
- Execute protected actions only through normal Harness commands for the current
  role.

## What

- Local comm tools are for non-strict task-scoped coordination.
- Strict ACP tools are for daemon-backed operation.
- `request-action` never executes the action it proposes.
