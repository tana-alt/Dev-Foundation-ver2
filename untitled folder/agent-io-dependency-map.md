---
status: active
owner: steward
last_validated_at: 2026-04-25
source_of_truth_level: primary
version: 0.7.3
---

# Agent I/O Dependency Map

Agent workflow is derived from contracts:

```text
agent A output packet/ref
  -> agent B input packet/ref
  -> next owner
```

The machine-readable source is
`artifacts/runtime/agent-io-contract-map.yaml`.

## Runtime Loop

```text
main_lane
  -> channel_operator
  -> project_supervisor
  -> ecosystem_monitor
  -> main_lane
```

`ecosystem_monitor` is a monitor lane distinct from `main_lane`; it is not a
new `portfolio_supervisor`. Main lane owns task routing and human-facing
accountability. Monitor lanes detect anomalies and return scoped findings.

## Contract Rules

- `main_lane` may read global maps and resolves target skill, project graph,
  runtime identity refs, and source refs.
- Specialist agents receive only input docs, output docs, local skill docs,
  packet templates named by the handoff, and `runtime_identity_refs`.
- Output packets must include `next_owner` so the workflow can continue.
- `operation_packet.result.metric_type` remains required for monitoring.
- Content body text stays in `content/{content_id}/body.md`; packets carry
  `content_ref` or `body_ref` only.
- Missing context returns a `rework_packet`; the agent must not read unrelated
  projects or broad repo history.
- Agents may classify uncertainty, but they must not resolve it by inventing
  content, strategy, requirements, implementation assumptions, or metrics.
- Project premise and latest three post refs are grounding refs. They reduce
  incoherence and repetition but must not make posts stale or over-constrained.

## Cron Rule

Cron calls are not special. A scheduled job creates the same scoped
`skill_call_request` as a human or main lane call.

Cron request templates live in:

```text
projects/{project_id}/runtime/cron/scheduled-call-requests.yaml
```

Each cron request must name:

- `target_skill`
- `task_intent`
- `project_graph`
- `runtime_identity_refs`
- `source_refs`
- `expected_outputs`
- `write_targets`

This keeps scheduled agents oriented inside the correct ecosystem and project
without injecting repo-wide context.

## Derived Workflows

Company directive workflow:

```text
decision_maker.decision_directive_packet
  -> main_lane.organization_structure_packet
  -> project_supervisor.plan_or_research_handoff
  -> background_researcher.evidence_packet
  -> project_supervisor.strategy_or_direction_packet
  -> main_lane.execution_management_packet
  -> decision_maker.review
```

`decision_maker` is a human authority role, not an agent. The workflow derives
from packet compatibility and must preserve scoped handoffs.

Idea / agent proposal loop:

```text
decision_maker.chat_idea
  -> main_lane.idea_intake_packet
  -> project_supervisor.proposal_evaluation_packet
  -> main_lane.routing_or_execution_management
  -> research / planning / execution / archive / decision_maker.review
```

```text
proposing_agent.agent_proposal_packet
  -> project_supervisor.proposal_evaluation_packet
  -> main_lane.routing_or_execution_management
  -> scoped next owner
```

This keeps ideas and agent recommendations as candidates. Strategy, content, or
system adoption must not be inferred directly from an attractive idea or a
research-side proposal.

Daily channel operation:

```text
main_lane.routing_decision_packet
  -> channel_operator.execution_brief
  -> channel_operator.operation_packet
  -> project_supervisor.project_monitor_record
  -> ecosystem_monitor.ecosystem_monitor_record
  -> main_lane
```

Social publish handoff:

```text
main_lane.social_auth_connect_request
  -> external_social_publish_executor
  -> connector_record_ref / auth_status
  -> main_lane

channel_operator.social_publish_request
  -> external_social_publish_executor
  -> publish_result_ref / evidence_packet / operation_packet
  -> channel_operator
```

`external_social_publish_executor` and the secret broker are not agents. Agents
send only refs and gate results; credentials, OAuth tokens, cookies, API keys,
and browser sessions stay outside prompts, packets, logs, and repo files.

Weekly research refresh:

```text
scheduled_jobs.skill_call_request
  -> background_researcher.evidence_packet
  -> project_supervisor.strategy_packet
  -> channel_operator.execution_brief
```

Monthly project direction review:

```text
scheduled_jobs.skill_call_request
  -> project_supervisor.project_direction_strategy_packet
  -> project_state_update / scoped handoff / human_owner review
```

`imagegen` concept refs and OSS research refs are inputs to the monthly
fixed-layer review. They are not promoted to new agent roles, and they must not
be exposed to `channel_operator` unless converted into a scoped
`execution_brief` constraint or `content_ref`.

The workflow can change by changing compatible input / output contracts, not by
creating extra agents.
