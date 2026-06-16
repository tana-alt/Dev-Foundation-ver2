---
name: scope-routing-governance
description: Keep agent context bounded to selected skills, named source refs, denied context, and explicit expansion reasons.
---

# Scope Routing Governance

## Purpose

Keep agents inside named source refs, selected skills, allowed write targets,
and denied context.

## Use When

- Task asks what to read or what not to read.
- Source refs are missing, broad, or ambiguous.
- Nearby file expansion may be needed.
- Context budget or denied context must be recorded.

## Do Not Use When

- Task already has complete narrow source refs.
- No context expansion is needed.
- The task is fully governed by another selected skill and scope is recorded.

## Read First

- `AGENTS.md`
- `docs/01-agent-operating-contract.md`

## Context Budget

```yaml
max_selected_skills: 2
max_source_refs: 6
max_reference_docs: 2
broad_repo_scan_allowed: false
```

## Method

1. Classify task intent.
2. Select at most two skills.
3. List named source refs.
4. List allowed write targets.
5. Declare denied context: broad_repo_scan, secrets, runtime_state, all_docs,
   all_tests.
6. Record nearby-file expansion only with a concrete reason.
7. Carry missing scope as residual risk or rework request.

## Output

For ordinary work, output an inline scope decision:

- source refs used
- allowed write targets
- denied context
- any context expansion reason
- next action

Create a durable scope record only when the user explicitly asks for one or a
later worker needs it. Prefer an inline scope decision or the current Plan log;
do not require a template file for ordinary work.

## Stop / Carryover Conditions

Stop and request scope clarification when source refs are broad enough to imply
a full repo scan and no safe local assumption exists.
