# Plan_N0005: Agent Visibility / ACP / Hook Scope / Harness Gap Audit

## 0. 目的

このメモは、現在の contract harness で **agent が role ごとに何を見える形で受け取るか**を棚卸しし、次の経路まで含めて実装済み機能との不足を確認する。

- `prepare` が生成する role packet / capsule / contract
- `spawn` / `launch-writer` が agent に渡す env、worktree、initial context、handoff
- non-strict CLI の role allowlist
- strict daemon / ACP session の capability と task scope
- ACP/agent comm からの依頼、特に review 依頼
- GitHub commit comment `/review` adapter
- hook で agent session に与えられる project/task/scope 情報
- review / gate / architecture gate / read-only facade の authority 境界

結論:

```text
role packet, role tool visibility, review freshness, architecture gate,
strict daemon capability enforcement は概ね実装済み。

不足または未接続:
  1. /review commit comment adapter は parser + create-only lock までで、
     webhook 実行、権限確認、harness dispatch、commit status 更新がない。
  2. ACP request-action は「提案のみ」で review/verify/gate を実行しない。
     ACP からの review 依頼は message として保存されるだけで、review lane 起動には
     reviewer / integrator が harness command を別途実行する必要がある。
  3. strict session.create は capability を返すが、spawn と同等の role initial_context
     / handoff / worktree packet は返さない。
  4. hook が渡す scope は project/task/env と worktree marker までで、
     allowed_paths/forbidden_paths の hard scope は hook ではなく contract.lock.json 側。
  5. hook_stop は observational fail-open で、完了ブロックの authority ではない。
```

## 1. 読んだ実装 refs

Primary implementation refs:

- `src/workflow_core/contract_harness/contract.py`
- `src/workflow_core/contract_harness/agent_tools.py`
- `src/workflow_core/contract_harness/roles.py`
- `src/workflow_core/contract_harness/spawn.py`
- `src/workflow_core/contract_harness/agent_comm.py`
- `src/workflow_core/contract_harness/context_audit.py`
- `src/workflow_core/contract_harness/domain/capabilities.py`
- `src/workflow_core/contract_harness/daemon/server.py`
- `src/workflow_core/contract_harness/cli.py`
- `src/workflow_core/contract_harness/review.py`
- `src/workflow_core/contract_harness/semantic_review.py`
- `src/workflow_core/contract_harness/review_comment_adapter.py`
- `src/workflow_core/contract_harness/verify.py`
- `src/workflow_core/contract_harness/gate.py`
- `src/workflow_core/contract_harness/architecture_gate.py`
- `src/workflow_core/contract_harness/architecture_predicates.py`
- `src/workflow_core/contract_harness/oracle_requirements.py`
- `src/workflow_core/contract_harness/worktree.py`
- `src/workflow_core/contract_harness/scope_map.py`
- `src/workflow_core/contract_harness/mcp_readonly.py`
- `scripts/hook_session_start.py`
- `scripts/hook_post_tool_use.py`
- `scripts/hook_stop.py`
- `scripts/completion_gate.py`

Primary proof refs:

- `tests/workflow_core/test_contract_harness.py`
- `tests/workflow_core/contract_harness/test_comm_delegation.py`
- `tests/workflow_core/contract_harness/test_strict_capabilities.py`
- `tests/workflow_core/contract_harness/test_strict_happy_path.py`
- `tests/workflow_core/contract_harness/test_strict_acp_action_requests.py`
- `tests/workflow_core/contract_harness/test_review_comment_adapter.py`
- `tests/workflow_core/contract_harness/test_architecture_gate.py`
- `tests/workflow_core/contract_harness/test_architecture_gate_integration.py`
- `tests/workflow_core/contract_harness/test_policy_task_compile.py`
- `tests/test_hook_scripts.py`

確認コマンド:

```bash
git status --short
./harness tools multicollinearity-feature-independence-20260616 --role all
PYTHONPATH=src python3 - <<'PY'
from workflow_core.contract_harness.domain.capabilities import ROLE_CAPABILITIES
from workflow_core.contract_harness.roles import _ALLOWED
from workflow_core.contract_harness.agent_tools import role_agent_tools, role_agent_skills, role_optional_tools
PY
```

## 2. Authority / visibility の全体像

Harness には「agent に見えるもの」と「authority として採用されるもの」が分かれている。

```text
.harness/tasks/<task_id>/task.yaml
  + .harness/owners.yaml
  + .harness/verifiers.yaml
  + .harness/review.yaml
  + optional .harness/policies/<policy>.yaml
        |
        v
harness prepare <task_id>
        |
        +-- contract.lock.json         authority
        +-- verifier-plan.json         authority
        +-- capsule.json               writer-facing compact packet
        +-- resume-capsule.json        writer resume packet
        +-- agent-tools.json           role -> visible tool list
        +-- agent-skills.json          role -> visible skill list
        +-- scope-map-forward.json     advisory, not authority
        |
        v
harness verify <task_id>
        |
        +-- candidate.diff             authority candidate snapshot
        +-- scope-map-reverse.json     advisory, review evidence
        +-- verify-result.json         authority machine evidence
        +-- architecture_gate object   authority inside verify-result.json
        |
        v
harness submit / review / gate / land / push
```

Important boundaries:

- `scope-map-forward.json` and `scope-map-reverse.json` both set `hard_constraint: False`; they are routing / review evidence, not completion authority.
- completion authority is derived from state store events plus authority artifacts such as `contract.lock.json`, `verify-result.json`, `submission.json`, `gate-result.json`, `land-result.json`, `push-result.json`.
- agent comm / ACP messages cannot claim completion, review verdict, gate result, mergeability, land result, or push result.
- hook scripts are mostly observational and fail-open, except `scripts/completion_gate.py` if wired separately as a blocking stop hook.

## 3. Role ごとに agent が見えるもの

### 3.1 Writer

Writer default visible packet:

- `capsule.json`
  - `task_id`
  - `scope`
  - `intent`
  - `scope_contract.allowed_paths`
  - `scope_contract.forbidden_paths`
  - `verifier_plan`
  - writer `agent_tools`
  - writer `agent_skills`
  - `contract_semantic_sha256`
- `resume-capsule.json`
  - `role: writer`
  - `task_goal`
  - optional `policy`
  - `locked_acceptance`
  - `current_phase`
  - `latest_evidence`
  - `unresolved`
  - `next_expected_action`
  - writer tools / skills
- `context-audit` payload for writer
  - `capsule`
  - `scope_map_forward`
  - available artifact booleans

Writer default tools:

```text
scope-map-forward
explain
context-audit
status
comm-peers
comm-send
comm-inbox
spawn-writer
verify
submit
report-rfc
report-metric
```

Writer default skills:

```text
tdd-scope
implementation-slice-verification
scope-routing-governance
```

Writer optional measurement tools:

```text
post-tool-use-hook
nfr-metric
bench-compare
abrun
check-runner
verdict
quality-gate
measure-eval
surface-issues
```

Writer non-strict CLI allowlist:

```text
prepare
explain
verify
report
submit
scope-map
spawn
status
tools
context-audit
launch-writer
comm-send
comm-inbox
comm-peers
```

Writer strict daemon capabilities:

```text
read_context
read_status
send_acp_message
submit_candidate
run_verify
```

Writer spawn/session visibility:

- worktree kind: `writer`
- base: `contract.lock.json.prepared_base_sha`
- env:
  - `FOUNDATION_REPO_ROOT`
  - `FOUNDATION_PROJECT_ID`
  - `FOUNDATION_TASK_ID`
  - `FOUNDATION_AGENT_ID`
  - `HARNESS_ROLE=writer`
- handoff commands:
  - `verify`
  - `submit`
  - `submit_and_wait`
  - `status`
- `comm/rebind/<agent_id>.json`
  - contains role, brief, cwd, env, handoff
  - `transcript_included: False`

Writer cannot, by role boundary:

- run `gate`
- collect or write reviewer verdicts
- land / push / complete
- create PR or run PR checks
- use integrator-only merge/oracle/compose tools

### 3.2 Reviewer

Reviewer default visible packet:

- `context-audit` reviewer context
  - `scope_map_reverse`
  - `submission`
  - review packet filenames under `reviews/*.review-packet.json`
  - available artifact booleans
- semantic command reviewer packet, when configured
  - `capsule`
  - `contract`
  - reviewer tools / skills
  - `writer_handoff`
  - `review_workspace`
  - reverse scope map
  - bounded or external `candidate.diff`
  - candidate diff index
  - `verify_result`
  - `mutation_result`
  - `quality_result`
  - `tool_candidates`
  - `metric_evidence`
  - reviewer policy
  - test interpretation

Reviewer default tools:

```text
scope-map-reverse
context-audit
status
review-verdict
certify
```

Reviewer default skills:

```text
security-check
implementation-slice-verification
scope-routing-governance
```

Reviewer optional measurement tools:

```text
post-tool-use-hook
nfr-metric
bench-compare
verdict
quality-gate
surface-issues
```

Reviewer non-strict CLI allowlist:

```text
certify
review:run
review:write-verdict
scope-map
spawn
status
tools
context-audit
comm-send
comm-inbox
comm-peers
```

Reviewer strict daemon capabilities:

```text
read_context
read_status
send_acp_message
run_review
```

Reviewer spawn/worktree visibility:

- `--reviewer-id` is required.
- worktree kind: `reviewer`
- base: `contract.lock.json.prepared_base_sha`
- candidate diff is applied to reviewer worktree.
- env includes:
  - `FOUNDATION_REVIEWER_ID`
  - `HARNESS_ROLE=reviewer`
  - common task/root/agent vars
- handoff commands:
  - `review_approve`
  - `review_block`
  - `status`

Reviewer freshness model:

- `reviews/<reviewer_id>.json` is authority only when `written_by: harness`.
- Each verdict records `evidence_seen`.
- basic readers must match:
  - `candidate_diff_sha256`
  - `machine_evidence_sha256`
- semantic command reviewers additionally bind:
  - `mutation_result_sha256`
  - `quality_result_sha256`
  - `tool_candidates_sha256`
  - `metric_evidence_sha256`
  - `scope_map_reverse_sha256`
- stale verdicts are excluded from quorum.

Reviewer cannot, by role boundary:

- submit candidate
- collect reviews
- run gate
- land / push / complete
- create PR

### 3.3 Integrator

Integrator default visible packet:

- `context-audit` integrator context
  - `submission`
  - `integration_result`
  - available artifact booleans
- `status`
  - artifact-backed phase
  - state-store summary
  - authority source
  - health warnings
- `review.collect`
  - fresh/stale/unknown reviewers
  - blocking verdicts
  - quorum state
  - semantic-review requirement state

Integrator default tools:

```text
review-collect
scope-map-reverse
affected
context-audit
status
spawn
dispatch
integrate
gate
land
compose
compose-push
oracle
push
context-scope-check
lane-map-check
```

Integrator default skills:

```text
implementation-slice-verification
scope-routing-governance
```

Integrator optional measurement tools:

```text
post-tool-use-hook
measure-eval
surface-issues
```

Integrator non-strict CLI allowlist:

```text
review:collect
gate
dispatch
integrate
worktree
affected
scope-map
spawn
status
tools
context-audit
launch-writer
land
compose
compose-push
manual-resolution-check
oracle
pr:create
pr:checks
push
comm-send
comm-inbox
comm-peers
```

Integrator strict daemon capabilities:

```text
read_context
read_status
send_acp_message
collect_review
run_gate
create_pr
run_pr_checks
merge_local
complete_task
reconcile
```

Integrator spawn/worktree visibility:

- worktree kind: `integrator`
- base: fetched integration target from policy
- branch: `agent/<task_id>/integrator/land`
- env includes `HARNESS_ROLE=integrator`.
- handoff commands:
  - `dispatch`
  - `gate`
  - `land`
  - `push`
  - `status`

Integrator may spawn:

- writer
- reviewer
- integrator

Writer can only spawn writer. Reviewer can only spawn reviewer. Admin can spawn all normal roles.

### 3.4 Admin

Admin is present in strict daemon capability model but is not a normal agent role packet.

Admin capabilities:

```text
all capabilities, including admin
```

Admin authority:

- `session.create`
- `session.revoke`
- `session.list`
- daemon shutdown
- integrity verification
- bypass of capability-specific checks inside daemon authorization

Notable gap:

- There is no `role_agent_tools(..., "admin")` or spawn target for admin.
- This is probably intentional for local authority control, but if admin is expected to be an agent lane, it lacks a visible role packet.

## 4. Scope がどこから来るか

### 4.1 Hard scope

Hard implementation scope is compiled by `contract.prepare`:

```text
.harness/tasks/<task_id>/task.yaml.scope
  -> .harness/owners.yaml
  -> scope_contract.allowed_paths
  -> scope_contract.forbidden_paths
  -> contract.lock.json
```

Global forbidden paths are added by `contract.py`:

```text
.harness/bottleneck.yaml
.harness/owners.yaml
.harness/verifiers.yaml
.harness/review.yaml
.harness/rfc-decisions/**
.harness/tasks/*/task.yaml
.harness/generated/**
```

Task-local forbidden paths from `owners.yaml` are appended after the global list.

### 4.2 Advisory scope maps

Forward map:

- generated during `prepare`
- visible to writer
- contains `path_hints`, `forbidden_path_hints`, verifier hints, likely tests
- `hard_constraint: False`

Reverse map:

- generated during `verify`
- visible to reviewer and integrator
- contains observed changed paths from diff, likely affected verifiers/tests/review topics
- `hard_constraint: False`

### 4.3 Hook-provided scope

Hook scripts do **not** pass allowed/forbidden paths directly.

They infer project/task/root from:

- `FOUNDATION_REPO_ROOT`
- `FOUNDATION_PROJECT_ID`
- `FOUNDATION_TASK_ID`
- `HARNESS_RUNTIME_ROOT`
- current working directory
- `.harness-worktree.json`

`.harness-worktree.json` gives:

```json
{
  "task_id": "...",
  "kind": "writer|reviewer|integrator",
  "reviewer_id": "...",
  "base_ref": "...",
  "source_repo_common_dir": "...",
  "state": "active"
}
```

The hook-level scope is therefore **task identity and role/worktree identity**, not path authority. Path authority remains `contract.lock.json`.

## 5. ACP / agent comm の実体

There are two related surfaces:

1. non-strict `comm-*` CLI
2. strict daemon `acp` methods

Both write/read the task-scoped comm store under harness runtime:

```text
harness-runtime/state/tasks/<task_id>/comm/
  inbox/<agent_id>/<message_sha256>.json
  threads/<correlation_handle>.json
  sessions/<agent_id>.json
  rebind/<agent_id>.json
```

Allowed message intents:

```text
action_request
status_query
status_response
proposal
clarification
rework_hint
artifact_summary
test_request
review_question
handoff_note
```

Forbidden authority claims:

```text
completion_claim
done_claim
review_verdict
gate_result
land_result
push_result
mergeable_claim
```

Auto-attached basis refs are added for status-like intents:

- `candidate.diff`
- `verify-result.json`
- `submission.json`
- `gate-result.json`
- `land-result.json`
- `oracle-result.json`
- `push-result.json`
- `rework-request.json`

ACP strict methods:

```text
acp.send            requires send_acp_message
acp.list            requires read_status
acp.request_action  requires read_status
```

`acp.request_action` current behavior:

```text
body contains "verify" -> proposed_action: candidate.verify
otherwise              -> proposed_action: task.status
executed: false
```

This means ACP action requests do **not** execute `verify`, `review`, `gate`, or `submit`.

### ACP からの review 依頼

Current implementation supports this only as communication:

- an agent can send `kind=review_question` or `kind=action_request`
- another agent can read it through `comm-inbox` or `acp.list`
- the message itself cannot become a review verdict
- the daemon does not turn ACP review requests into `review.run`
- reviewer/integrator still must run:
  - reviewer: `harness review <task_id> --run <reviewer_id>` or `--write-verdict`
  - integrator: `harness review <task_id> --collect` or `harness gate <task_id>`

Gap:

```text
ACP review request orchestration is not implemented.
Only task-scoped messaging and non-authoritative proposal are implemented.
```

## 6. Review request / review execution

### 6.1 Harness review lane

Implemented review profiles:

- `reader-scope` / `reader-impact`
  - checks candidate hash
  - checks scope impact status
  - blocks forbidden path / scope violations
- `reader-correctness`
  - checks candidate hash
  - recomputes machine evidence
  - checks verify status and verifiers
  - checks contract semantic reproducibility
- command profile reviewers from `.harness/review.yaml`
  - get a full semantic review packet
  - run in candidate workspace
  - cannot mutate candidate workspace without being blocked

Review collection:

- reads configured reviewers from `.harness/review.yaml`
- ignores unknown reviewers
- marks stale reviewers by evidence mismatch
- requires quorum
- requires semantic approval when configured or when quality/tool evidence demands semantic review

Gate auto-review:

- `gate_task` can auto-run stale/missing reviewers in-process when `review.background_auto_run` is true.

### 6.2 GitHub commit comment `/review`

Implemented:

- parse exact commands:
  - `/review`
  - `/review arch`
  - `/review full`
- normalize to modes:
  - `normal`
  - `arch`
  - `full`
- create-only lock:
  - `refs/harness/locks/<sha>-<mode>`
- status mapping helper:
  - exit code `0` -> `success`
  - nonzero -> `failure`

Missing:

- webhook handler for `commit_comment`
- actor authorization / repo permission check
- task selection or task creation from commit SHA
- pending/success/failure/error commit status write
- actual harness invocation
- result-to-comment/status rendering
- lock cleanup or run record beyond Git ref

Current state:

```text
review_comment_adapter is a small parser/lock library, not a complete adapter.
```

## 7. Hook surfaces

### 7.1 SessionStart hook

Script: `scripts/hook_session_start.py`

Input:

- drains stdin, ignores payload
- env:
  - `FOUNDATION_PROJECT_ID`
  - `FOUNDATION_REPO_ROOT`

Visible output:

- prints up to 5 open issues from:
  - `artifact/<project>/metrics/open-issues.json`

Authority:

- none
- always exits 0

### 7.2 PostToolUse hook

Script: `scripts/hook_post_tool_use.py`

Input:

- JSON payload:
  - `session_id`
  - `tool_name`
  - `tool_input`
  - `tool_response`
- env:
  - `HARNESS_ROLE`
  - `FOUNDATION_AGENT_ROLE`
  - `FOUNDATION_REPO_ROOT`
  - `FOUNDATION_PROJECT_ID`
  - `FOUNDATION_TASK_ID`

Fallback inference:

- nearest `.harness-worktree.json`
- Git common dir

Output:

- appends trajectory event to:
  - `artifact/<project>/trajectory/<session_id>.jsonl`

Scope:

- project/task identity only
- role in trajectory event
- no hard allowed-path scope

Authority:

- measurement evidence only
- always exits 0

### 7.3 Stop hook

Script: `scripts/hook_stop.py`

Input:

- JSON payload with loop guard:
  - `stop_hook_active: true` means exit 0
- env:
  - `FOUNDATION_REPO_ROOT`
  - `FOUNDATION_PROJECT_ID`
  - `FOUNDATION_TASK_ID`
  - `FOUNDATION_SPEC_PRESENT`
  - `FOUNDATION_GATE_TIER`
  - `FOUNDATION_GATE_TIMEOUT_S`
  - `HARNESS_RUNTIME_ROOT`

Gating detection:

- active `Plan/<project>/plans/Plan_N*.md`
- legacy `Plan/<project>/spec.md`
- `FOUNDATION_SPEC_PRESENT=1`

Dispatch behavior:

- if `submission.json` exists:
  - runs `HARNESS_ROLE=integrator ./harness dispatch <task_id>`
- if no submission:
  - does not dispatch

Output:

```json
{
  "decision": "allow",
  "dispatch_returncode": 0,
  "reason": "ok"
}
```

Failure mode:

- missing harness / timeout / environment failure writes observation when possible
- exits 0

Authority:

- observational fail-open
- does not enforce completion
- does not provide path scope

### 7.4 Completion gate script

Script: `scripts/completion_gate.py`

This is a separate blocking gate entrypoint if wired as a hook.

Input:

- env:
  - `FOUNDATION_GATE_TIER`
  - `FOUNDATION_PROJECT_ID`
  - `FOUNDATION_REPO_ROOT`

Behavior:

- computes `git diff HEAD` hash
- runs `make <tier>`
- writes completion evidence under `artifact/<project>/evidence`
- exits nonzero when completion should be blocked

Current `hook_stop.py` does not call this script.

## 8. Read-only MCP facade

`mcp_readonly.py` exposes read-only runtime resources:

```text
contract.lock.json
verifier-plan.json
candidate.diff
verify-result.json
quality-result.json
scope-map-forward.json
scope-map-reverse.json
submission.json
reviews/*.json
gate-result.json
affected-set.json
land-result.json
oracle-result.json
push-result.json
rework-request.json
```

It exposes no write tools:

```text
WRITE_TOOLS = ()
```

This is aligned with the authority boundary: external readers can inspect evidence but cannot mutate harness state through this facade.

## 9. Architecture gate / Plan_N0004 実装差分

Plan_N0004 の core decision は mostly implemented:

- no new standalone architecture artifact
- `architecture_gate` is inside `verify-result.json`
- significance is derived from diff paths, not from `task.yaml`
- hard-block predicates run during `verify`
- gate recomputes architecture gate and blocks mismatch
- advisory codes map to oracle requirements
- `scope-map-reverse` remains advisory

Implemented hard-block predicate codes:

```text
ACTIVE_DOC_EXPANSION
NEW_STORAGE_ROOT
TRACKED_RUNTIME_STATE
BROAD_REPO_SCAN_DEFAULT_TRUE
UNINDEXED_SKILL
SKILL_COMPACT_LIMIT_EXCEEDED
POSSIBLE_EXTERNAL_WRITE_PATH
ARCH_PREDICATE_INCONCLUSIVE
```

Implemented advisory codes:

```text
POLICY_TOUCH
ROUTING_OR_CONTEXT_BOUNDARY_CHANGED
HARNESS_ROLE_BOUNDARY_CHANGED
VERIFICATION_GATE_CHANGED
REVIEW_FRESHNESS_CHANGED
```

Implemented oracle requirements:

```text
T_UNION_COVERS_BEHAVIORAL_BOUNDARY
MUTATION_ADEQUACY_COVERS_CHANGED_CODE
```

Gap relative to Plan_N0004:

- The `/review` comment-trigger adapter remains incomplete as described in section 6.2.

## 10. 不足確認

| Area | Current implementation | Gap / risk | Priority |
| --- | --- | --- | --- |
| Role tool packet | `agent-tools.json`, `agent-skills.json`, `capsule.json`, spawn `initial_context` exist for writer/reviewer/integrator. | Admin has no agent packet. Likely acceptable unless admin is intended as an agent role. | P2 |
| Role command enforcement | non-strict `roles.py` allowlist and strict daemon capabilities exist. Tests cover writer/reviewer forbidden actions. | `HARNESS_ROLE` defaults to writer, so unset env becomes writer. This is convenient but not fail-closed. | P2 |
| Strict daemon session | session token, task scope, capabilities, revocation, integrity are implemented. | `session.create` returns capabilities but not spawn-style `initial_context`, handoff, worktree, or role packet. ACP-only agents need another call/path to learn tools. | P1 |
| ACP send/list | task-scoped messages, allowed intents, forbidden authority claims, basis refs are implemented. | ACP messages cannot trigger review execution. Review requests are only messages. | P1 |
| ACP request-action | returns proposed action and `executed: false`. | No dispatcher to run proposed `candidate.verify`, `review.run`, or `gate.run` under capability checks. | P1 |
| Harness review lane | `review.run`, `review.write-verdict`, `review.collect`, freshness checks, semantic packets are implemented. | Manual/ACP review request queue semantics are not modeled; only configured reviewers and existing verdicts are collected. | P2 |
| `/review` commit comment | exact parser, mode normalization, create-only Git ref lock implemented. | No webhook server/entrypoint, auth check, pending status, harness run, result status/comment, or task mapping. | P0 if comment-triggered review is required |
| Hook project/task scope | hooks infer repo/project/task from env or `.harness-worktree.json`. | Hooks do not pass allowed/forbidden paths; hard path scope exists only in contract artifacts. This is correct but should not be described as hook-provided path scope. | P1 documentation/expectation |
| Hook Stop | detects submissions and delegates `dispatch` as integrator; fail-open observation is tested. | Not a blocking gate; failure still allows session stop. If completion enforcement is required, wire `completion_gate.py` separately or move enforcement into harness authority path. | P1 |
| Context audit | validates required role tools/skills and estimates packet pressure. | It writes current audit but does not enforce launch blocking outside explicit command/test use. | P2 |
| Read-only facade | exposes runtime evidence and no write tools. | Not role-specific; any caller with facade access sees all listed resources. Access control must be provided outside this module if needed. | P2 |
| Architecture gate | verify embeds, gate recomputes, tests cover mismatch/block/advisory. | Predicate set is intentionally narrow; no DSM/drift/offline monitor in default path. This matches Plan_N0004. | No gap |

## 11. Required next implementation if the goal is full ACP/comment-triggered review

Minimum missing slice:

1. Add a comment/webhook entrypoint around `review_comment_adapter`.
2. Validate actor permission before acquiring lock.
3. Map commit SHA + mode to task id / harness task creation strategy.
4. Set pending status on lock acquisition.
5. Run existing harness flow:
   - `prepare`
   - `verify` or review mode equivalent
   - `submit`
   - reviewer dispatch / `gate`
6. Update commit status:
   - `success`
   - `failure`
   - `error`
7. Write a small runtime record under harness runtime, not repo docs, if resumability is needed.
8. Add tests that prove duplicate comments do not rerun and that failed review maps to failure status.

Minimum missing slice for ACP review orchestration:

1. Add an ACP action resolver for `review.run` and/or `review.collect`.
2. Ensure resolver only executes actions that the authenticated session capability allows.
3. Preserve current `executed: false` behavior for dry-run/proposal mode, or add explicit `--execute`.
4. Record the action result as normal harness artifacts, not message authority.
5. Add tests proving ACP review request cannot bypass reviewer/integrator role boundaries.

## 12. Verification status

Evidence inspected:

- current source files listed in section 1
- focused tests listed in section 1
- live projection from:
  - `./harness tools multicollinearity-feature-independence-20260616 --role all`
  - `PYTHONPATH=src` imports of `ROLE_CAPABILITIES`, `_ALLOWED`, `role_agent_tools`, `role_agent_skills`, `role_optional_tools`

Commands run:

```bash
uv run pytest -q \
  tests/workflow_core/contract_harness/test_review_comment_adapter.py \
  tests/workflow_core/contract_harness/test_strict_acp_action_requests.py \
  tests/workflow_core/contract_harness/test_architecture_gate.py \
  tests/workflow_core/contract_harness/test_architecture_gate_integration.py \
  tests/workflow_core/contract_harness/test_comm_delegation.py \
  tests/test_hook_scripts.py
```

Result:

```text
35 passed
```

Not run:

- full pytest suite
- live daemon strict happy path
- real GitHub webhook / commit status integration

Reason:

- this plan is a current-state audit doc, not a code change.
- the GitHub webhook/status path is not implemented locally, so it cannot be runtime-smoked without adding implementation.
