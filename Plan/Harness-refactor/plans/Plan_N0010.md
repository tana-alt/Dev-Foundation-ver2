---
plan_id: Plan_N0010
project_id: Harness-refactor
status: completed
log_ref: Plan/Harness-refactor/logs/Plan_N0010.log.md
---

# Harness Agent Context Hook And Operational Manifest Cleanup

## Goal

Use hooks to give a harness-spawned agent the operational context it needs for
its assigned task, without relying on the agent to discover packet paths,
review requests, ACP commands, or handoff commands by itself.

The hook should answer, at session start:

- what `task_id` this agent owns
- what role and agent id it is running as
- where the task packet directory is
- where the tracked task contract is
- what the task `review_request` asks reviewers to check
- how to use ACP/local comm for this task
- where review verdict and certificate outputs go
- which role command manifest applies

## Non-Goals

- Do not create or expose a Harness skill manifest. Codex/Claude skill routing
  stays outside the harness packet contract.
- Do not inject skill bodies or skill paths through the SessionStart hook.
- Do not write agent-specific compact checkpoints into tracked `docs/`.
  Agent-specific memory is runtime state, not repo truth.
- Do not keep `report-rfc` or `report-metric` in the default role manifest.
  Escalation is through GitHub issues when escalation is needed, exposed as a
  guarded harness issue command rather than the retired report commands.
- Do not hide normal integrator responsibilities such as `land`, `push`, PR
  creation, compose, compose-push, or oracle diagnostics from the integrator
  operational manifest.
- Do not make the hook execute land, push, PR creation, or other write actions.
  The hook only tells the agent which commands and paths apply.
- Do not implement compact-checkpoint automation in this slice. The feasibility
  result is recorded, but automatic pre-compact design-judgment capture is
  deferred.

## Protected Invariants

- `AGENTS.md` remains the operational authority for ACP, review handoff, and
  harness role behavior.
- `.harness/tasks/<task_id>/task.yaml` remains the source for task-specific
  goal, review request, acceptance, and evidence expectations.
- The runtime packet directory remains under git common dir:
  `<git-common-dir>/harness-runtime/state/tasks/<task_id>`.
- Agent-specific compact checkpoints remain under the task runtime packet
  directory and never contain secrets, raw prompt bodies, credentials, browser
  state, or full transcripts.
- Hook output is bounded, deterministic, and fail-open.
- Messages are coordination records only; review verdicts, gate results, land
  results, push results, and completion authority remain artifact-backed.
- `HARNESS_ROLE` is orchestration context, not a security boundary.

## Selected Design

Extend the existing `scripts/hook_session_start.py` as the cold-start context
transport.

The hook should read from:

- environment: `FOUNDATION_TASK_ID`, `FOUNDATION_PROJECT_ID`,
  `FOUNDATION_AGENT_ID`, `HARNESS_ROLE`, `FOUNDATION_REVIEWER_ID`,
  `HARNESS_RUNTIME_ROOT`
- worktree marker: `.harness-worktree.json`
- tracked task file: `.harness/tasks/<task_id>/task.yaml`
- runtime packets:
  - `contract.lock.json`
  - `capsule.json`
  - `resume-capsule.json`
  - `agent-tools.json`
  - role session files such as `writer-session.json`,
    `reviewer-session-<id>.json`, `integrator-session.json`

The hook should print a compact block like:

```text
[harness assignment]
- task_id: <task_id>
- role: <writer|reviewer|integrator>
- agent_id: <agent id or unset>
- task yaml: .harness/tasks/<task_id>/task.yaml
- packet dir: <git-common-dir>/harness-runtime/state/tasks/<task_id>
- packets: contract.lock.json, capsule.json, resume-capsule.json, agent-tools.json, verifier-plan.json
- review request architecture: <task.yaml review_request.architecture_review.ask>
- review request code: <task.yaml review_request.code_review.ask>
- review output verdict: <packet dir>/reviews/<reviewer_id>.json
- review output certificate: <packet dir>/reviews/certificates/<hash>.json
- ACP local peers: FOUNDATION_AGENT_ID=<id> HARNESS_ROLE=<role> ./harness comm-peers <task_id>
- ACP local inbox: FOUNDATION_AGENT_ID=<id> HARNESS_ROLE=<role> ./harness comm-inbox <task_id> --agent-id <id>
- ACP local send: FOUNDATION_AGENT_ID=<id> HARNESS_ROLE=<role> ./harness comm-send <task_id> ...
- ACP strict list: ./harness --strict acp list <task_id> --agent-id <id>
- ACP strict send: ./harness --strict acp send <task_id> ...
- ACP strict request-action: ./harness --strict acp request-action <message_id> --body ...
- issue escalation: HARNESS_ROLE=writer ./harness issue-create <task_id> --reason escalation --title ... --body ... --execute
- role tools: <agent-tools.json role names>
- next action: <role-specific next action>
```

## Role Manifest Changes

The default role manifest should describe operational harness commands, not
skills.

Writer default tools should include:

- `scope-map-forward`
- `explain`
- `context-audit`
- `status`
- `passport`
- `comm-peers`
- `comm-inbox`
- `comm-send`
- `acp-list`
- `acp-send`
- `acp-request-action`
- `issue-create`
- `verify`
- `submit`

Writer default tools should remove:

- `spawn-writer`
- `report-rfc`
- `report-metric`

Reviewer default tools should include:

- `scope-map-reverse`
- `context-audit`
- `status`
- `passport`
- `comm-peers`
- `comm-inbox`
- `comm-send`
- `acp-list`
- `acp-send`
- `acp-request-action`
- `review-verdict`
- `certify`

Integrator default tools should include:

- `review-collect`
- `scope-map-reverse`
- `affected`
- `context-audit`
- `status`
- `passport`
- `comm-peers`
- `comm-inbox`
- `comm-send`
- `acp-list`
- `acp-send`
- `acp-request-action`
- `spawn`
- `dispatch`
- `integrate`
- `gate`
- `land`
- `push`
- `pr-create`
- `pr-checks`
- `compose`
- `compose-push`
- `oracle`
- `context-scope-check`
- `lane-map-check`

Integrator `compose`, `compose-push`, and `oracle` stay visible. `push` already
uses oracle retry under remote drift, and integrator operators need explicit
diagnostic/revalidation commands when the normal land/push path needs
explanation or repair.

## Skill Manifest Removal

Remove the harness-generated skill manifest path from the cold-start context
contract:

- stop writing `agent-skills.json` from `prepare`
- remove `agent-skills.json` from diagnostic authority/packet exposure
- remove `role_agent_skills` from context-audit packet sizing
- remove `writer skills`, `reviewer skills`, and `integrator skills` output
  from `./harness explain`
- remove SessionStart `skills:` output

Repo-local skills may still exist and be used by Codex, but they are not part
of the harness role packet.

## Compact Checkpoint Feasibility Result

PreCompact/PostCompact hooks can participate in preserving subtle,
agent-specific design decisions, but the safe implementation is narrower than
"hook automatically writes the agent's design judgment at exactly 80% context."

Verified facts:

- The Codex manual for the current local CLI documents `PreCompact`,
  `PostCompact`, and `SessionStart` hook events. `PreCompact` and
  `PostCompact` match `manual` or `auto`; `SessionStart` matches `startup`,
  `resume`, `clear`, or `compact`.
- The manual documents `model_auto_compact_token_limit` and
  `model_context_window`, but does not document a hook payload field that gives
  reliable context usage ratio, current token count, or max-context capacity.
- A local `codex exec` probe confirmed that `SessionStart` stdout can become
  model-visible context.
- A local auto-compaction probe with a low `model_auto_compact_token_limit`
  confirmed that `PreCompact`, `PostCompact`, and then `SessionStart` fire
  around compaction.
- A local resume probe confirmed that `SessionStart` stdout on `resume` can be
  model-visible context.
- A local compact visibility probe confirmed that `PreCompact` and
  `PostCompact` stdout is not model-visible context.
- A local compact/resume matcher split confirmed that `SessionStart` stdout for
  both `compact` and `resume` can be model-visible context after compaction.
- A safe compact payload probe recorded only top-level keys and value types.
  The observed `PreCompact`/`PostCompact` payload keys were `cwd`,
  `hook_event_name`, `model`, `session_id`, `transcript_path`, `trigger`, and
  `turn_id`.

Selected behavior:

- Exact 80% triggering is not implementable from hooks alone unless a future
  documented hook payload exposes reliable usage/capacity. Approximate 80% can
  be configured by setting `model_auto_compact_token_limit` to 80% of the known
  model context window, but the harness should not claim it detected 80% from
  the hook payload.
- A command hook cannot reliably author the agent's subtle design decisions by
  itself. The active agent must maintain the checkpoint during normal work or
  through an explicit command such as `./harness checkpoint <task_id>`.
- Hooks can enforce and restore the checkpoint:
  - `PreCompact`/`PostCompact` can record the compaction event, validate that a
    checkpoint exists, and write small runtime metadata.
  - `SessionStart` with `startup|resume|compact` should inject the latest
    bounded checkpoint summary and the checkpoint path into model-visible
    context.
- The checkpoint should be agent-specific, task-scoped, and runtime-owned:
  `<packet dir>/agent-docs/<agent_id>/compact-checkpoint.md`.
- After compaction, SessionStart should inject a bounded summary from that
  checkpoint back into the agent context.
- The checkpoint should capture decisions such as:
  - why a tempting implementation path was rejected
  - unresolved ambiguity and who must decide it
  - invariants that are not obvious from the diff
  - reviewer warnings that are easy to lose in compacted summaries
  - local assumptions that must be revalidated before land/push/PR
- The checkpoint must not capture raw chat history, raw tool output, secrets,
  auth material, copied external content, or broad logs.

Current repo finding:

- Existing tracked hooks cover `SessionStart`, `PostToolUse`, and `Stop`; there
  is no current `PreCompact` or `PostCompact` script.
- The normalized trajectory model has `tokens_in` and `tokens_out`, but current
  hook translation sets them to zero for tool-call events. No current path
  proves a context usage ratio or exact 80% threshold.
- The implementation should treat `SessionStart` as the only proven injection
  path and `PreCompact`/`PostCompact` as runtime file/metadata hooks.

Suggested checkpoint output shape:

```markdown
# Compact Checkpoint

task_id: <task_id>
agent_id: <agent_id>
role: <role>
written_at: <timestamp>
source: PreCompact|manual-checkpoint

## Fragile Decisions
- ...

## Rejected Paths
- ...

## Must Revalidate After Compact
- ...

## Needs Human Decision
- ...
```

## Acceptance Criteria

- Given a harness task has been prepared, when SessionStart runs with
  `FOUNDATION_TASK_ID` and `HARNESS_ROLE`, then stdout includes the task id,
  role, packet directory, task yaml path, review request, ACP commands, review
  output paths, role tools, and next action.
- Given SessionStart runs outside a harness task, then it exits 0 and does not
  emit misleading task context.
- Given task yaml has a review request, then the architecture and code review
  asks are visible in hook output.
- Given a role manifest is generated, then writer `agent-tools.json` includes
  ACP commands, the GitHub issue escalation command, and no `report-rfc`,
  `report-metric`, or skill manifest entries.
- Given the integrator manifest is generated, then `land`, `push`,
  `pr-create`, `pr-checks`, `compose`, `compose-push`, and `oracle` are visible.
- Given `./harness explain <task_id>` runs, then it reports runtime packet and
  role tool context without skill manifest output.
- Given compact-checkpoint automation is considered, then this plan records
  that exact 80% hook-side detection and automatic judgment capture are
  deferred from the implementation slice.

## Adversarial Checks

- Malformed or missing task yaml: hook exits 0 and omits only unavailable
  review-request lines.
- Missing runtime packet directory: hook exits 0 without false assignment
  claims.
- Missing `FOUNDATION_AGENT_ID`: hook still prints task and role context and
  marks agent id as unset.
- Reviewer without `FOUNDATION_REVIEWER_ID`: hook still prints the verdict path
  template and does not invent a concrete reviewer id.
- Stale runtime containing `agent-skills.json`: hook does not print it.
- Integrator tools remain visible even when external write policy is dry-run.
- `issue-create` is used for routine TODOs, ordinary bugs, missing tests, or
  directly fixable rework: this is a process defect; issue creation is reserved
  for escalation and non-algorithmically resolvable problems.
- Compact checkpoint attempts to include secrets, tokens, raw prompt bodies, or
  full transcripts: no implementation writes or injects it in this slice.

## Implementation Steps

1. Update `agent_tools.py`:
   - remove `write_agent_skills`, `agent_skill_groups`, and `role_agent_skills`
     from the generated harness packet path
   - add ACP command specs for each role
   - add writer-owned `issue-create` command specs for escalation
   - add `pr-create` and `pr-checks` for integrator
   - remove writer `spawn-writer`, `report-rfc`, and `report-metric`
2. Update `contract.py`:
   - stop writing `agent-skills.json` during `prepare`
3. Update `context_audit.py`, `gate.py`, `domain/authority.py`, and `cli.py`:
   - remove generated skill packet assumptions
   - keep tool exposure metrics
4. Update `hook_session_start.py`:
   - print assignment, packet dir, task yaml, review request, ACP commands,
     review output paths, role tools, and next action
   - stop printing `skills:`
5. Update tests:
   - hook script tests for packet path, review request, ACP commands, and no
     skill output
   - contract harness tests for role tool manifest changes
   - context audit/gate packet exposure tests for no skill manifest
6. Defer compact-checkpoint automation:
   - keep the feasibility finding in this plan
   - do not add `./harness checkpoint`, PreCompact/PostCompact scripts, or
     SessionStart checkpoint injection in this implementation
   - revisit only if the runtime exposes reliable usage/capacity or the agent
     workflow explicitly asks for manual checkpoint files

## Verification Plan

- `pytest -q tests/test_hook_scripts.py`
- `pytest -q tests/workflow_core/test_contract_harness.py`
- `pytest -q tests/workflow_core/contract_harness/test_strict_capabilities.py`
- targeted tests that cover `context-audit`, `gate` packet exposure, and role
  manifest generation
- `uv run ruff check` and `uv run ruff format --check` on changed Python files

## Open Decisions

- Whether `comm-*` should remain alongside `acp-*` permanently, or be retired
  after ACP strict/local naming is unified.
- Whether compact checkpoints should be agent-private by default, or whether
  selected entries can be promoted to task-level packet notes after reviewer or
  integrator approval.
