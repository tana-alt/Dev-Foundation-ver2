---
name: obsidian-handoff
description: Use when a task is being handed from one role to another and you need a structured, searchable handoff packet for Obsidian.
---

Use this skill when work moves from one owner to another.

Read path:
- start from `Project-App/AGENTS.md` and the app runtime packets
- read `Apps/<app-slug>/artifacts/runtime/current-state.yaml` first
- read `Apps/<app-slug>/artifacts/runtime/latest-delta.yaml` second
- only expand to `10-log.md`, `11-agent-map.md`, or `12-agent-evals.md` when the runtime packets explicitly flag them

Required output:
1. handoff_from
2. handoff_to
3. objective
4. inputs
5. expected_output
6. verification
7. blocked_by
8. depends_on
9. target_note_ids

Rules:
- convert vague requests into a concrete output schema
- keep the packet short and operational
- include specific note ids when available
- if evidence is missing, say so explicitly instead of inventing it
- summarize only the latest state or changed surfaces; do not restate full bundle history
- for repair handoffs, point to changed surfaces first and widen scope one surface at a time only if still blocked

Do not:
- restate the full history
- merge handoff with final approval
