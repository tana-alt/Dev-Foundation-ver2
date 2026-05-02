---
status: active
owner: steward
last_validated_at: 2026-04-25
source_of_truth_level: primary
version: 0.6.2
---

# Context Scope Policy v0.6.2

Agents must not read the whole repository for routine SNS/project operation.

Machine-readable runtime scope lives in `artifacts/runtime/context-scope.yaml`.

## Main Lane vs Specialist Agents

```yaml
main_lane:
  may_read:
    - AGENTS.md
    - ARCHITECTURE.md
    - docs/agent-map.md
    - docs/context-scope-policy.md
    - agent-contracts.yaml
    - packet-contracts.yaml
    - 11-agent-map.md
    - 12-agent-evals.md
  reason: "Main lane owns routing, agent map awareness, handoff graph, and contract drift."

specialist_agents:
  may_read:
    - input_docs
    - output_docs
    - skill_docs
    - packet_templates_named_by_handoff
  denied_by_default:
    - broad_repo_history
    - AGENTS.md
    - ARCHITECTURE.md
    - docs/agent-map.md
    - 11-agent-map.md
    - 12-agent-evals.md
  escalation_rule: "If missing context blocks execution, emit rework_packet or ask main_lane/steward for a scoped handoff."
```

The older broad read paths in prompt templates and compatibility maps are audit
surfaces. Runtime execution should follow `artifacts/runtime/context-scope.yaml`
unless a handoff packet explicitly widens the visible scope.

## Skill-Local Runtime Scope

v0.6.2 runtime keeps root `AGENTS.md` as a small main-lane routing map. Callable
skills keep local execution rules in their own `AGENTS.md`, colocated with
`SKILL.md`.

```yaml
runtime_call:
  resolve:
    - artifacts/runtime/skill-directory-map.yaml
  cwd:
    - target_skill.skill_dir
  inject_only:
    - target_skill
    - task_intent
    - project_graph
    - source_refs
  must_not_inject:
    - repo_whole_context
    - all_project_logs
    - all_agent_maps
    - secrets
```

```yaml
context_scope:
  global:
    - docs/harness-contract.md
    - docs/agent-map.md
    - docs/context-scope-policy.md
    - artifacts/runtime/project-registry.yaml
  project:
    - projects/{project_id}/state.yaml
    - projects/{project_id}/brief.md
    - projects/{project_id}/logs/
    - projects/{project_id}/content/
  channel:
    - projects/{project_id}/channels/{channel_id}/state.yaml
    - projects/{project_id}/channels/{channel_id}/content-log.md
  shared:
    - knowledge/shared/validated-patterns.md
    - knowledge/shared/failed-patterns.md
    - knowledge/shared/platform-lessons.yaml
  app_harness:
    read_only_when_triggered:
      - app/productization
      - UI/UX design
      - software release
      - security review
```

Routine SNS operation reads project and channel surfaces only. App-specific harness surfaces are read when `project_supervisor` or the main lane triggers app/productization, UI/UX, release, or security work.

## Knowledge Sharing Scope

Project operation may share distilled lessons into `obsidian-vault/shared/`, but
only from operation logs and evidence / operation packets. Do not copy content
bodies, credentials, private project memos, or full raw reaction dumps into shared
knowledge.
