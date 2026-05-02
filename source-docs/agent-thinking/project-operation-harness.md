---
status: active
owner: steward
last_validated_at: 2026-04-25
source_of_truth_level: primary
version: 0.6.2
---

# Project Operation Harness

This document explains how project management and knowledge sharing run on top
of the existing app-development harness. It does not replace the app flow.

## Company Operating Mesh

Company-level operation starts with the decision maker, not an agent. The
company operating mesh converts a human directive into scoped structure,
planning, research, and execution-management packets. These are parallel
autonomous function lanes that coordinate with the ecosystem / project / channel
harness by refs; they are not a command hierarchy.

```text
decision_maker
  -> decision_directive_packet
  -> main_lane
  -> parallel function lanes:
       organization_structure_packet
       plan handoff
       research handoff
       execution_management_packet
  -> packet-ref sync
```

The source policy is `docs/company-operating-system.md`. The runtime map is
`artifacts/runtime/company-operating-system.yaml`.

## Operating Loop
```text
project_supervisor
  -> reads project state, operation packets, evidence packets, content refs
  -> decides continue / fix / stop recommendation / research / productization
  -> emits operation_packet, rework_packet, handoff_packet, or project_state_update

channel_operator
  -> reads channel state, scheduled jobs, platform nature, content refs, reactions
  -> requests existing content / launch / feedback skills
  -> emits evidence_packet and operation_packet

workflow_evaluator
  -> reads work diagnosis, routing decisions, gate attempts, rework refs
  -> writes workflow-evaluation-record.yaml

artifact_evaluator
  -> reads content refs, workflow evaluation, and artifact outcome metrics
  -> writes artifact-outcome-record.yaml

performance_analyst
  -> reads workflow / artifact records and visible metric layers
  -> writes synthetic-metric-record.yaml, pattern-registry-packet.yaml, and derived signal summaries

project monitor
  -> is owned by project_supervisor
  -> reads workflow / artifact / performance / operation records
  -> writes project-monitor-record.yaml, strategy_packet, and execution_brief

monthly project direction review
  -> is owned by project_supervisor
  -> reads fixed-layer candidates, imagegen asset refs, OSS research refs, and productization signals
  -> writes project-direction-strategy-packet.yaml and project_state_update

ecosystem monitor
  -> is implemented by main_lane / steward as a monitoring lane
  -> reads ecosystem, project, offer, platform relationship, and project monitor refs
  -> writes ecosystem-monitor-record.yaml and shared platform / offer lessons

weekly knowledge sharing
  -> reads operation logs and packets
  -> writes knowledge candidates and distilled lessons into knowledge/shared/
```

## Runtime Identity Resolution

Before a project or channel agent acts, it resolves location in this order:

```text
artifacts/runtime/ecosystem-registry.yaml
  -> artifacts/runtime/ecosystem-project-content-map.yaml
  -> artifacts/runtime/agent-io-contract-map.yaml
  -> artifacts/runtime/project-registry.yaml
  -> artifacts/runtime/offer-registry.yaml
  -> artifacts/runtime/agent-runtime-state.yaml
  -> artifacts/runtime/skill-directory-map.yaml
  -> projects/{project_id}/runtime-location.yaml
  -> projects/{project_id}/agent-position.yaml
  -> projects/{project_id}/storage-map.yaml
  -> projects/{project_id}/runtime/cron/scheduled-call-requests.yaml when scheduled
  -> project/channel state
```

This lets an agent answer:
- Which ecosystem am I inside?
- Which project / offer / channel am I operating?
- Which state file is my owner document?
- Which input docs, output docs, skill docs, and packets are in scope?
- Who receives my next packet?
- Which skill directory is my current working directory?
- Where is my recent activity memory?

## Agent Invocation Rule
Agent calls have three separate layers:

- Trigger source: human request, cron, rework packet, monitor signal, or project
  supervisor handoff.
- Call decider: `main_lane` for ambiguous / human / rework / monitor work, or
  `scheduled_jobs` for a pre-registered cron request.
- Actual invoker: `runtime`.

Specialist agents do not start other agents directly. They request the next
agent by emitting `next_owner`, `handoff_packet`, `rework_packet`,
`operation_packet`, or `execution_brief`. `main_lane` or the registered cron
request resolves `target_skill`; runtime validates the request, starts the
skill directory as current working directory, injects only `skill_call_request`,
and records the activity log.

The canonical machine-readable rule is
`artifacts/runtime/agent-invocation-policy.yaml`.

## Runtime Session Rule
The operation runtime calls Codex directly. It does not route through Multica.

- First attempt: `codex exec` starts a new direct Codex session.
- Same-agent rework or additional instruction: `codex exec resume
  {runtime_session_id}` keeps the session.
- Footer or output-shape repair: same-session repair is required.
- Different-agent handoff: start a new session, keep `workflow_run_id`, and link
  `parent_attempt_id`.
- Project, channel, scope, model-policy, or secret-boundary changes require a
  new session with `session_switch_reason`.

Runtime records session continuity in
`projects/{project_id}/runtime/session-ledger.yaml`. The canonical policy is
`artifacts/runtime/runtime-session-policy.yaml`.

## Project Management Rule
- `project_supervisor` is the health owner for one project / offer.
- `channel_operator` is the operation owner for one SNS channel.
- `ecosystem-registry.yaml` owns cross-project grouping.
- `offer-registry.yaml` owns offer promise, funnel refs, and claim boundary.
- `agent-runtime-state.yaml` owns current agent location and next owner.
- `agent-output-registry.yaml` owns owner role -> read / write / output / next owner.
- `agent-io-contract-map.yaml` owns agent input contracts, output contracts, and dependency edges.
- `ecosystem-project-content-map.yaml` owns the ecosystem -> project -> content read order.
- `workflow-loop.yaml` owns main lane -> channel -> project monitor -> ecosystem monitor loop order.
- `project-direction-strategy-policy.yaml` owns the monthly fixed-layer project direction strategy rule.
- `skill-directory-map.yaml` owns `target_skill -> skill_dir -> local AGENTS.md / SKILL.md`.
- `runtime-policy.yaml` owns preflight, postflight, model escalation, and secret checks.
- `projects/{project_id}/runtime-location.yaml` is the project-local view of the same location contract.
- `projects/{project_id}/agent-position.yaml` is the first project-local role-position file a specialist reads.
- `projects/{project_id}/storage-map.yaml` owns project-local output, result log, packet, report, metric, research, and content buckets.
- `projects/{project_id}/logs/agent-activity-log.yaml` is the append-only runtime log of agent calls.
- `projects/{project_id}/logs/agent-recent-activity.yaml` is the scoped latest-three activity index each agent reads before acting.
- `projects/{project_id}/runtime/cron/scheduled-call-requests.yaml` owns scoped cron call envelopes for scheduled agents.
- Existing app-development roles are triggered only for app/productization, UI/UX,
  release, security, or implementation work.
- Routine SNS operation should not read the full app bundle.
- Weekly strategy can collect system / OSS / `imagegen` concept candidates, but
  fixed project direction is confirmed monthly through
  `project_direction_strategy_packet`, not changed by weekly execution briefs.

## Knowledge Sharing Rule
Shared knowledge is a distilled layer, not a log mirror.

Strategy-stage memory has two levels:

- Project-local hypotheses live in `projects/{project_id}/logs/strategy-log.md`.
- Reusable knowledge candidates live in `knowledge/shared/strategy-knowledge-candidates.yaml`.

Do not mix these. A hypothesis is a local assumption. A knowledge candidate is a
reusable but still provisional pattern that can be scored over repeated use.

Allowed inputs:
- `projects/{project_id}/logs/ops-log.md`
- `projects/{project_id}/logs/decision-log.md`
- `projects/{project_id}/logs/strategy-log.md`
- `artifacts/packets/evidence-packet.yaml`
- `artifacts/packets/operation-packet.yaml`

Allowed outputs:
- `knowledge/shared/strategy-knowledge-candidates.yaml`
- `knowledge/shared/validated-patterns.md`
- `knowledge/shared/failed-patterns.md`
- `knowledge/shared/platform-lessons.yaml`
- `knowledge/shared/offer-lessons.yaml`

When `project_supervisor` uses a shared knowledge candidate in strategy, it must
log the usage in `strategy-log.md` with `candidate_id`, `used_for`,
`strategy_packet_ref`, `execution_brief_ref`, expected effect, outcome window,
effectiveness result, and score delta. The shared candidate score changes only
after effectiveness is recorded with evidence refs:

- effective: `+1`
- ineffective: `-1`
- inconclusive: `0`

A candidate becomes validated only after repeated evidence and human review. A
single buzz event cannot validate a candidate.

## Agent Activity Memory Rule
Runtime records every agent call automatically. Agents do not write their own
activity log directly.

Default read:
- `projects/{project_id}/logs/agent-recent-activity.yaml`

Default write by runtime:
- `projects/{project_id}/logs/agent-activity-log.yaml`
- `projects/{project_id}/logs/agent-recent-activity.yaml`

Each agent reads its own latest three activity entries before acting. Strategy
and analysis agents also read the latest three relevant strategy / analysis
records named by the handoff. If three recent entries are insufficient, the
agent returns `rework_packet` or asks `main_lane` for a scoped full-log read.

Decision-layer agents such as `main_lane` and `project_supervisor` follow the
fixed runtime procedure first, then reason flexibly within the allowed decision
space. They may choose rework, research, escalation, strategy update, or
productization, but must not invent missing facts or hide uncertainty.

Do not share:
- raw credentials
- private project memos
- raw content bodies
- full user reaction dumps
- claims without evidence refs
- hypotheses that have not been converted to knowledge candidates

## Handoff Back To App Development
When operation evidence indicates app/productization work, `project_supervisor`
emits a `handoff_packet` to `workflow_planner`, `commercial_workflow_planner`, or
the app-development main lane. That handoff must name the exact input docs and
expected output docs, so downstream agents do not need broad project history.

## Project-Local Storage Rule
Concrete project outputs are stored under `projects/{project_id}/` by default:

- `logs/`: decision, ops, and QA/release logs.
- `content/`: content registry, recent index, body refs, and metadata.
- `artifacts/packets/`: project-local packet exports.
- `artifacts/handoffs/`: inbound and outbound handoff records.
- `artifacts/reports/`: project health, review, productization, or release reports.
- `artifacts/metrics/`: reaction summaries and normalized metric refs.
- `artifacts/research/`: background watch manifests, watch runs, and summaries.
- `runtime/cron/`: scheduled call requests with project graph, runtime identity refs, source refs, expected outputs, and write targets.

Root `artifacts/packets/` remain packet templates and foundation examples.
Concrete project instance folders are local by default unless deliberately
productized.
