---
status: active
owner: steward
last_validated_at: 2026-04-25
source_of_truth_level: primary
version: 0.6.2
---

# Harness Contract v0.6.2

This contract adds a thin SNS / project operation layer to the existing app-development harness. It does not replace the app harness, graph runtime, planner packets, release gates, or Obsidian app bundle.

## Design Principle
- Do not create a new large harness.
- Bind new operational roles into the existing agent / packet / gate / conditional reviewer model.
- Add only two agent roles: `project_supervisor` and `channel_operator`.
- Reuse existing research, content, launch, growth, compliance, security, and workflow skills.
- Keep content bodies out of packets. Packets pass `content_ref` only.
- Keep secrets outside agent context. Agents request execution; executors handle credentials.
- Keep metrics and gates simple. The harness should detect obvious risk and drift, not optimize creativity out of SNS operation.
- Keep the agent layer close to the human layer. Agents recommend, route, and prepare evidence; humans remain responsible for public commitments and irreversible decisions.
- Do not create content, strategy, requirements, or implementation assumptions from inference alone. If information is insufficient or new requirements appear, emit the smallest `rework_packet`, research handoff, implementation handoff, or human escalation.
- Foundation artifacts should be grounded in real project data when operation begins. Synthetic or template artifacts are allowed only for dry-run foundation checks and must stay clearly labeled.
- Each project keeps a premise summary and the latest three post refs available to content and channel agents. These are references, not constraints that freeze style or prevent useful variation.

## Overall Structure
```text
parallel operating mesh:
  organization function lanes
  ecosystem coordination
  project / offer operation
  channel operation
  content registry
  operation packets
  reaction evidence
  feedback loop
```

The control layer is limited to:
- `organization_graph`
- `decision_directive`
- `ecosystem_registry`
- `ecosystem_project_content_map`
- `project_graph`
- `offer_registry`
- `agent_runtime_state`
- `agent_inheritance_policy`
- `agent_contract`
- `context_scope`
- `content_registry`
- `packet`
- `gate`
- `scheduled_jobs`
- `secret_boundary`
- `platform_nature_map`
- `platform_relationship_map`
- machine-readable runtime scope: `artifacts/runtime/context-scope.yaml`
- skill directory runtime map: `artifacts/runtime/skill-directory-map.yaml`
- skill call request envelope: `artifacts/runtime/skill-call-request.yaml`
- agent invocation rule: `artifacts/runtime/agent-invocation-policy.yaml`
- direct Codex session rule: `artifacts/runtime/runtime-session-policy.yaml`
- runtime validator/model/secret policy: `artifacts/runtime/runtime-policy.yaml`
- company operating layer: `artifacts/runtime/company-operating-system.yaml`

## Organization Operating Mesh
The company / organization surface is a thin parallel governance mesh. The
human `decision_maker` issues direction, and `main_lane` converts it into
scoped structure, plan, research, and execution-management packets. These lanes
run beside the ecosystem / project / channel harness and coordinate with it
through refs and owner fields.

```text
decision_maker
  -> decision_directive_packet
  -> main_lane
  -> parallel lanes:
       organization_structure_packet
       plan handoff
       research handoff
       execution_management_packet
```

This layer is documented in `docs/company-operating-system.md`. It must not
promote a CEO agent or allow agents to make final company decisions from
inference.

## Project Graph
`project_graph` identifies a durable operation unit inside an ecosystem.

```yaml
project_graph:
  ecosystem_id: "ecosystem_id"
  project_id: "project_id"
  offer_id: "offer_id"
  channel_id: "channel_id"
  campaign_id: null
  owner_agent: "project_supervisor"
  human_owner: "human_owner"
  status: "active | paused | archived | testing"
  memo: "short context; never overrides structured fields"
```

Field meaning:
- `ecosystem_id`: linked coordination unit that can contain multiple channels and offers without being a command hierarchy.
- `project_id`: continuous publishing, product, or offer operation unit.
- `offer_id`: thing being sold, distributed, or routed toward.
- `channel_id`: X, TikTok, YouTube, note, newsletter, or another channel.
- `campaign_id`: optional short-term effort. Do not require it for continuous operation.

## Runtime Identity

Runtime identity is explicit. Agents do not infer their ecosystem or project from
folder names alone.

```yaml
runtime_identity:
  ecosystem_registry: artifacts/runtime/ecosystem-registry.yaml
  project_registry: artifacts/runtime/project-registry.yaml
  offer_registry: artifacts/runtime/offer-registry.yaml
  agent_runtime_state: artifacts/runtime/agent-runtime-state.yaml
  ecosystem_project_content_map: artifacts/runtime/ecosystem-project-content-map.yaml
  project_local_runtime: projects/{project_id}/runtime-location.yaml
  project_local_position: projects/{project_id}/agent-position.yaml
  project_local_storage: projects/{project_id}/storage-map.yaml
```

`agent-runtime-state.yaml` tells an agent its `ecosystem_id`, `project_id`,
`offer_id`, `channel_id`, `current_scope`, `input_docs`, `output_docs`,
`skill_docs`, `packet_refs`, and `next_owner`.

`runtime_identity_refs` tells a specialist where it is inside the current
ecosystem and project. It names the ecosystem overview, project position map,
project state, runtime location, project storage map, and content registry. If a
specialist cannot resolve these refs, it returns a `rework_packet` instead of
reading unrelated project history.

## Skill Directory Runtime

Runtime does not inject a broad context bundle. `main_lane` resolves
`target_skill` in `artifacts/runtime/skill-directory-map.yaml`, sets current
working directory to the resolved `skill_dir`, and passes only
`skill_call_request`.

Call decision and invocation are separated:

- `main_lane` decides human, ambiguous, rework, monitor, and productization
  routing.
- `scheduled_jobs` decides only registered cron calls that already have
  project graph and identity refs.
- `project_supervisor`, `channel_operator`, monitor, analysis, research, and
  content skills request follow-up by packet; they do not directly start other
  agents.
- `runtime` is the actual invoker. It validates the call request, sets the
  skill directory as cwd, injects scoped refs, saves outputs, and writes the
  activity log.
- Runtime uses direct Codex execution, not Multica. First attempts start a new
  Codex session; same-agent rework and format repair resume the existing
  `runtime_session_id`; handoff to a different agent starts a linked new session.

```yaml
skill_call_request:
  invocation_source: cron
  call_decider: scheduled_jobs
  actual_invoker: runtime
  runtime_backend: codex_cli
  workflow_run_id: template_workflow_run
  attempt_id: template_attempt_001
  parent_attempt_id: null
  runtime_session_id: null
  session_strategy: start_new
  session_switch_reason: first_attempt
  target_skill: channel_operator
  task_intent: daily_channel_operation
  project_graph:
    ecosystem_id: template_ecosystem
    project_id: template_project
    offer_id: template_offer
    channel_id: template_channel
  runtime_identity_refs:
    ecosystem_summary_ref: ecosystems/_template/overview.md
    project_position_ref: projects/_template/agent-position.yaml
    project_state_ref: projects/_template/state.yaml
    runtime_location_ref: projects/_template/runtime-location.yaml
    storage_map_ref: projects/_template/storage-map.yaml
    content_registry_ref: projects/_template/content/registry.yaml
    project_premise_ref: projects/_template/knowledge/premise-summary.md
    recent_posts_ref: projects/_template/content/recent-posts.yaml
  source_refs: []
  instruction: "short task instruction"
  memo: "optional"
```

Skill-local `AGENTS.md` and `SKILL.md` are the detailed local instructions.
Root `AGENTS.md` remains the main_lane routing map.

## Agent Roles
`project_supervisor` owns project / offer health and makes bounded continue, fix, stop, research, or productization routing decisions.

`channel_operator` owns one SNS channel's continuous operation and manages cadence, spam risk, content-generation handoffs, reaction collection, and channel packets.

Do not create these v0.6.1 agents:
- `research_agent`
- `content_agent`
- `launch_ops_agent`
- `privacy_reviewer`
- `legal_reviewer`
- `knowledge_curator`
- `portfolio_supervisor`

## Content Registry
Content bodies live in the project content registry, not in packets.

```yaml
content_registry:
  path: "projects/{project_id}/content/{content_id}/"
  fields:
    content_id: "content_id"
    project_id: "project_id"
    offer_id: "offer_id"
    channel_id: "channel_id"
    content_type: "post | thread | video_script | newsletter | lp_copy | image_prompt"
    status: "draft | reviewed | scheduled | published | archived"
    body_ref: "projects/{project_id}/content/{content_id}/body.md"
    asset_refs: []
    evidence_refs: []
    reaction_refs: []
    created_by: "agent_or_human"
    reviewed_by: null
    scheduled_at: null
    published_at: null
    memo: "short context"
```

Every handoff, evidence, rework, and operation packet uses `content_ref` instead of embedding raw content.

## Project Premise And Recent Posts
Each active project keeps two short grounding surfaces:

- `projects/{project_id}/knowledge/premise-summary.md`: the current project premise, audience, offer, claims boundary, known facts, and stale assumptions.
- `projects/{project_id}/content/recent-posts.yaml`: refs to the latest three published or scheduled posts.

Agents use these surfaces as refs. They must avoid unsupported contradictions
with the premise, and they should avoid repeating the latest three posts too
closely. They may still explore new angles, formats, and hooks; entropy is
allowed as long as factual claims remain grounded.

## Strategy Knowledge Candidate Loop
Strategy logs must not collapse local hypotheses into shared knowledge.

- `projects/{project_id}/logs/strategy-log.md` stores project-local hypotheses,
  knowledge candidate usage, and effectiveness follow-up.
- `knowledge/shared/strategy-knowledge-candidates.yaml` stores reusable but
  provisional knowledge candidates with score, use count, effective count,
  ineffective count, evidence refs, and usage refs.
- `knowledge/shared/validated-patterns.md` receives only candidates that have
  repeated evidence, pass the score threshold, and receive human review.

When `project_supervisor` uses a knowledge candidate, it records the use in the
strategy log and later records whether it was effective. Scores move only after
evidence-backed follow-up. Single buzz outliers cannot validate a candidate.

## Two-Layer Strategy
`project_supervisor` owns two strategy layers:

- `weekly_operational_layer`: updates weekly or per project-health review from
  workflow, artifact, performance, operation, and evidence records. It emits the
  normal `strategy_packet` and cuts the `execution_brief` visible to
  `channel_operator`.
- `project_direction_fixed_layer`: tracks project direction, system
  introduction, OSS adoption, and visual/system concept candidates. It may
  progress in parallel during weekly operation, but it is confirmed monthly and
  emits `project_direction_strategy_packet`.

`imagegen` output is a skill input for concept exploration, not a new agent.
Generated images, image prompts, and visual variants must be saved as
`asset_ref`, `image_prompt_ref`, or `content_ref`; packets pass refs only. OSS
or open-source adoption candidates must come from existing research skills and
include evidence refs for license, maintenance, integration impact, and risk
before monthly confirmation.

Weekly strategy must not finalize fixed project direction. If a weekly signal
suggests a new system, OSS adoption, or project pivot, `project_supervisor`
records a fixed-layer candidate, requests missing research if needed, and waits
for monthly confirmation or human-owner escalation. See
`docs/project-direction-strategy-policy.md` and
`artifacts/runtime/project-direction-strategy-policy.yaml`.

## Agent Activity Memory
Every runtime agent call is recorded by runtime, not manually by the agent.

- Append-only activity log: `projects/{project_id}/logs/agent-activity-log.yaml`
- Recent scoped index: `projects/{project_id}/logs/agent-recent-activity.yaml`

Agents read their own latest three activity entries before acting. Strategy and
analysis agents also read the latest three relevant strategy / analysis records
named by handoff. Full activity logs are not read by default; they require a
scoped main lane handoff when repeated failure or missing context requires it.

Judgment agents follow fixed runtime steps while preserving flexible reasoning
inside the decision boundary. They must choose research, rework, escalation, or
bounded strategy changes when evidence is incomplete rather than inventing facts.

## Packet Types
The project operation layer uses four packet families:
- `handoff_packet`: request to an agent, skill, human, or executor.
- `evidence_packet`: claim and supporting references.
- `rework_packet`: smallest concrete revision request.
- `operation_packet`: channel, funnel, content reaction, or project health result.

`operation_packet.result.metric_type` is required and must be one of:
- `content_reaction`
- `channel_health`
- `revenue_funnel`
- `project_health`

## Feedback Loop
```text
published content
  -> reaction evidence
  -> operation_packet
  -> channel_operator
  -> next content hypothesis
  -> generate-channel-content
  -> content_registry
```

`channel_operator` reads `recent_reaction_refs`, channel health, audience voice, and conversion signal. It emits `next_content_hypothesis`, `content_plan_update`, or `rework_packet`, and escalates project-level decisions to `project_supervisor`.

## Gate Policy
`content_publish_gate` is a lightweight readiness gate for scheduled posting. It checks `content_ref`, evidence refs, channel validity, schedule validity, rate limit, and compliance flags.

`compliance_gate` is conditional. It is skipped for routine posts and triggers only for legal ambiguity, regulatory risk, affiliate disclosure, financial claim, health claim, paid ad claim, refund policy, or privacy issue.

`content_grounding_gate` stays lightweight. It checks only that factual claims
have evidence refs or are marked as unsupported assumptions, that the content
does not contradict the project premise without an explicit reason, and that the
latest three post refs were considered for repetition risk. It does not reject
novel positioning or creative divergence by default.

## Secret Boundary
Current state is `manual_or_safe_limited_execution`.

Agents must not place credentials in env files, prompts, logs, packets, or content metadata. Agents may emit `content_ref`, `handoff_packet`, and operation requests only. A future executor may use brokered runtime access through Infisical or equivalent, with least privilege, per-project identity, per-platform scope, access logging, and rotation.

## Context Scope
Main lane, steward, and workflow planner may read maps because they own routing,
handoff graph, and contract drift. Specialist agents read only input docs, output
docs, skill docs, and packet templates named by handoff. If context is missing,
they return a `rework_packet` or ask main lane for a scoped handoff instead of
reading broad history.

## Scheduled Jobs
Cron-like jobs support operation but do not permit unlimited posting. Every channel job must carry rate limits:
- `per_channel_per_day`
- `per_channel_per_hour`
- `minimum_gap_minutes`

The default daily posting ceiling is 2 to 3 posts per channel unless project evidence and platform nature justify a lower rate.

## Completion Contract
Harness v0.6.1 is complete when:
- `project_supervisor` and `channel_operator` are contract-visible agents.
- Existing skills are reused instead of duplicated.
- Content bodies are stored in the content registry and packets use `content_ref`.
- Reaction evidence feeds operation packets and future content generation.
- Compliance is conditional, not routine.
- Secret access is brokered or manual; agents never read secrets.
- Specialist agents follow `artifacts/runtime/context-scope.yaml` and do not read broad maps by default.
- Scheduled jobs include spam/rate-limit controls.
- `portfolio_supervisor` remains deferred to v0.7 or later.

## v0.7 Content Generation Foundation
`docs/content-generation-harness.md` extends this project / channel contract with
content-operation dry-run records. It keeps the v0.6.2 runtime boundary and adds:

- `work_diagnosis_packet` for artifact type, probable failure modes, required
  capabilities, uncertainty, evidence requirement, and risk.
- `routing_decision_packet` for selected and rejected agent candidates.
- `workflow_evaluation_record` and `artifact_outcome_record` to keep workflow
  quality separate from SNS artifact performance.
- `workflow_evaluator`, `artifact_evaluator`, and `performance_analyst` as
  analysis-layer agents that produce evaluation and metric-analysis records.
- `strategy_packet` owned by `project_supervisor`.
- `execution_brief` passed to `channel_operator` instead of the full strategy.
- `pattern_registry` with `watchlist` and `validated` separation.
- `synthetic_metric_record` and `escalation_monitor_record` for dry-run
  foundation without committing concrete datasets.
- `main_lane_loop_record`, `project_monitor_record`, and
  `ecosystem_monitor_record` for dataset-free runtime loop smoke.
- `agent_output_registry` to keep every owner role's read / write / output /
  next-owner surfaces discoverable.

The v0.7 foundation does not promote new daily channel execution agents.
Workflow evaluation, artifact evaluation, and performance analysis are visible
analysis-layer agents. They hand evidence-backed records to `project_supervisor`,
which remains the strategy owner. Escalation monitoring remains a `main_lane`
responsibility. Main lane owns task routing; monitor lanes detect anomalies.

`ecosystem_monitor` is a monitoring lane implemented by `main_lane` / steward in
this foundation. It aggregates project monitor output and ecosystem registry
surfaces, but it is not `portfolio_supervisor` and does not make cross-project
resource-allocation decisions.
