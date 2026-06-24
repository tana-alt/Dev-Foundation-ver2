# Plan_N0003: Policy-Driven Task Architecture

## Goal

Harnessを実際に動かす際のBottleneckを減らす。特に、policy level
の目標から task を作り、agent が task の受け入れ条件を設計し、
Harness がそれを監査して実行可能な contract として固定する流れを作る。

## Design Position

人間は policy level の目標と制約を設定する。
task は policy に準じた実行単位として存在する。
task の acceptance は agent が設計してよい。
ただし Harness は agent の acceptance をそのまま信じず、policy coverage
と proof coverage を監査してから `contract.lock` する。

```text
User
  -> policy-level goal
  -> task intent
  -> agent acceptance proposal
  -> harness acceptance audit
  -> contract.lock
  -> implementation / verification / gate
```

## Core Architecture

```text
AGENTS.md
  repo common rules

.harness/policies/{policy_id}.yaml
  policy-level goal, invariants, required proof shape, human gates, metrics

.harness/tasks/{task_id}/task.yaml
  policy ref, task goal, scope, source refs, requested outcome

.harness/agents/{role}.md
  role profile source of truth

.harness-runtime/state/tasks/{task_id}/contract.lock.json
  compiled policy + task + acceptance + verifier plan

.harness-runtime/state/tasks/{task_id}/state.sqlite
  current phase, evidence, bottleneck events, artifact pointers

compact hook
  role profile + contract lock + runtime state
  -> Compact Resume Capsule
```

## Policy Shape

Policy は task の詳細ではなく、守るべき目標と制約を持つ。

```yaml
id: harness-bottleneck-reduction
goal: "Harnessが実行途中で止まる原因を減らし、rework可能な状態として観測可能にする"

invariants:
  - id: no_silent_block
    statement: "Harness停止理由は state に記録される"
  - id: prefer_rework_over_block
    statement: "機械的に改善可能な不足は blocked ではなく rework_required に分類する"
  - id: proof_required
    statement: "task completion は proof と紐づく"

acceptance_requirements:
  - every_criterion_has_proof
  - policy_invariants_are_mapped
  - human_gates_are_explicit
  - scope_is_bounded

verifiers:
  required:
    - make check-harness-arch-all

human_gates:
  - external_write
  - destructive_action
  - secret_required

metrics:
  - blocked_event_count
  - rework_reason_count
  - acceptance_audit_failure_count
```

## Task Shape

Task は軽く保つ。acceptance は最初から人間が詳細に書かない。

```yaml
id: T-0003
policy: harness-bottleneck-reduction
goal: "compact hook によって再開時の必要文脈を機械生成できるようにする"
scope: contract-harness
source_refs:
  - Plan/Harness-refactor/plans/Plan_N0003.md
acceptance:
  mode: agent_generated
```

## Agent Acceptance Proposal

Agent は task goal と policy を読んで acceptance を設計する。

```yaml
criteria:
  - id: AC-1
    statement: "role profile, contract lock, runtime state から resume capsule を生成できる"
    policy_refs:
      - proof_required
    proof:
      kind: test
      command: "uv run pytest tests/workflow_core/contract_harness/test_resume_capsule.py"

  - id: AC-2
    statement: "blocked/rework の分類理由が state に記録される"
    policy_refs:
      - no_silent_block
      - prefer_rework_over_block
    proof:
      kind: test
      command: "uv run pytest tests/workflow_core/contract_harness/test_bottleneck_events.py"
```

## Harness Acceptance Audit

Harness は acceptance の意味が正しいかを完全には判断しない。
代わりに、実行可能性と policy coverage を機械的に監査する。

監査する点:

- policy invariant が acceptance criteria に map されているか
- 各 criterion に proof があるか
- proof が command / test / artifact check として実行可能か
- task scope と allowed paths を超えていないか
- human gate が必要なものを隠していないか
- 不足を `blocked` ではなく `rework_required` として返せるか

Audit result:

```text
acceptance.audit_passed
  -> contract.lock.json を生成

acceptance.audit_failed
  -> rework_required
  -> reason: weak_acceptance | missing_proof | unmapped_policy | unknown_scope
```

## Runtime State Flow

```text
task.created
  -> acceptance.proposed
  -> acceptance.audit_passed
  -> contract.locked
  -> implementation.running
  -> verification.running
  -> gate.passed / rework_required / blocked
```

`blocked` は狭く使う。

```text
rework_required:
  acceptance が弱い
  proof が足りない
  verifier command が存在しない
  scope が曖昧
  goal が機械検証に落ちていない
  test / verifier / review が失敗した

blocked:
  user approval が必要
  credential / secret がない
  external service が使えない
  destructive / protected action が必要
```

## Bottleneck Measurement

Harness が止まる箇所は gate を増やして隠さず、state に event として残す。

```text
bottleneck_event:
  task_id
  phase
  status: rework_required | blocked
  reason
  first_seen_at
  elapsed_ms
  required_input
  suggested_rework
```

目的は「止まったこと」を失敗として扱うことではなく、どの設計不足が
Harness の実行を妨げたかを測定できるようにすること。

## Compact Hook

Compact hook は判断しない。再開に必要な文脈を機械生成するだけにする。

Input:

```text
role profile
contract.lock.json
state.sqlite latest phase/evidence/bottleneck
```

Output:

```text
Compact Resume Capsule:
  role
  task goal
  locked acceptance
  current phase
  latest evidence
  unresolved rework/block reason
  next expected action
```

これにより、context compaction 後も agent が task/policy/phase を再推論
せずに継続できる。

## Conversation and Delegation

Orchestrator は作らない。人間との会話を受ける coordinating writer が、
policy/task を編集し、必要な writer を呼び出し、handoff を読んで
次の goal を渡す。これは writer の capability extension であり、
terminal supervisor, queue, scheduler, heartbeat ではない。

```text
Human
  -> coordinating writer
  -> policy/task update
  -> writer spawn or existing peer selection
  -> delegation message
  -> child writer handoff reply
  -> integrate / rework / next delegation
```

### Peer Discovery

Agent は送信先を手で覚えない。Harness が task-scoped runtime state から
送信先候補を投影する。

```text
comm/sessions/{agent_id}.json
  agent_id
  role
  brief
  status
  cwd
```

`comm-peers <task_id>` はこの projection を返すだけにする。
新しい registry は作らない。

```json
{
  "task_id": "T-0003",
  "peers": [
    {
      "agent_id": "writer.codex.T-0003.infra",
      "role": "writer",
      "brief": "インフラエンジニアとして環境構築を行う",
      "status": "ready"
    }
  ]
}
```

### Existing Agent Message

すでに存在する agent にメッセージを送る時、user-facing CLI は
送信先、主題、本文だけを受け取る。

```text
harness comm-send T-0003 \
  --to writer.codex.T-0003.infra \
  --subject "環境構築の確認" \
  --body "Goal: ..."
```

送信者は入力させない。Harness が現在の session/env から補完する。
送信先 role も `comm/sessions/{to_agent_id}.json` から解決する。
通常メッセージの kind は runtime が default を付ける。

```text
from_agent_id = current session or FOUNDATION_AGENT_ID
from_role     = current session or HARNESS_ROLE
to_role       = peer session projection
kind          = clarification by default
```

Envelope には audit のため `from` を保存するが、CLI の利用者が毎回指定する
ものではない。

### Delegation Message

Delegation は会話 native に扱う。正本は message envelope であり、
別の重い delegation schema は作らない。

Delegation として区別したい場合だけ、brief を付ける。

```text
harness comm-send T-0003 \
  --to writer.codex.T-0003.infra \
  --subject "環境構築" \
  --body "Goal: ..."
  --delegation-brief "インフラエンジニアとして環境構築を行う"
```

Envelope:

```json
{
  "message_sha256": "sha256:...",
  "kind": "action_request",
  "from": {"agent_id": "writer.codex.T-0003.coordinator", "role": "writer"},
  "to": {"agent_id": "writer.codex.T-0003.infra", "role": "writer"},
  "delegation": {
    "role": "writer",
    "brief": "インフラエンジニアとして環境構築を行う"
  },
  "body_markdown": "Goal: ..."
}
```

`delegation.id` は持たない。`message_sha256` が delegation id になる。

### Handoff Reply

Handoff は自由文でよい。構造化成果物が必要な場合は handoff schema ではなく、
task goal / acceptance / contract に書く。

返信関係だけを持つ。

```json
{
  "kind": "handoff_note",
  "in_reply_to": "sha256:<delegation-message>",
  "body_markdown": "環境構築は完了。検証は..."
}
```

## Thin CLI Boundary

CLI は workflow language にしない。args を application/service に渡して
JSON を出すだけにする。

```text
CLI
  -> parse args
  -> comm service / spawn service
  -> JSON output

Application service
  -> resolve current sender
  -> resolve target peer role
  -> build message envelope
  -> validate delegation/handoff refs
  -> write inbox/thread/session projection
```

追加してよい CLI は薄いものだけにする。

```text
harness comm-peers <task_id>
harness comm-send <task_id> --to <agent-id> --subject <subject> --body <body>
harness comm-send <task_id> --to <agent-id> --subject <subject> --body <body> --delegation-brief <brief>
harness comm-send <task_id> --to <agent-id> --subject <subject> --body <body> --in-reply-to <message_sha256>
```

避けるもの:

```text
harness delegate
harness handoff
harness orchestrate
harness route
```

専用コマンドを増やすほど CLI が orchestration layer になるため、
delegation/handoff は message envelope の optional fields として扱う。

## Tool Skillization

tool の使い方は runtime に埋め込みすぎない。まず skill として
「いつ使うか」を置く。

例:

```text
latency-measurement
  command latency or agent wait time が bottleneck になりそうな時に使う

complexity-measurement
  code churn, module boundary, dependency growth を測りたい時に使う

bottleneck-analysis
  rework_required / blocked が反復している時に使う
```

実際の測定 command は Harness CLI 側に寄せる。
skill は tool の仕様ではなく、呼び出し条件と期待する evidence の形を持つ。

## Implementation Slices

1. Policy/task schema
   - `.harness/policies/{policy_id}.yaml`
   - `.harness/tasks/{task_id}/task.yaml`
   - policy ref and task goal validation

2. Acceptance proposal artifact
   - agent が acceptance proposal を生成
   - runtime に proposal を保存

3. Acceptance audit
   - policy invariant coverage
   - proof coverage
   - scope/human-gate check
   - failed audit は `rework_required`

4. Contract lock
   - policy + task + acceptance + verifier plan を固定
   - semantic hash を付与

5. Bottleneck events
   - audit failure, verifier failure, blocked gate を state に記録
   - summary command で理由別に集計

6. Compact resume capsule
   - role profile + contract lock + state から生成
   - hook から再注入可能にする

7. Conversation delegation
   - `spawn --brief` で session projection に role brief を保存
   - `comm-peers` は `comm/sessions/*.json` を読むだけ
   - `comm-send` は既存 peer への送信時に `to`, `subject`, `body`
     だけを user-facing required fields にする
   - sender は current session/env から補完
   - target role は peer session projection から補完
   - delegation は optional `delegation.brief`
   - handoff は optional `in_reply_to`

## Verification Plan

最初の検証は小さくする。

```text
tests/workflow_core/contract_harness/test_policy_task_compile.py
tests/workflow_core/contract_harness/test_acceptance_audit.py
tests/workflow_core/contract_harness/test_bottleneck_events.py
tests/workflow_core/contract_harness/test_resume_capsule.py
tests/workflow_core/contract_harness/test_comm_delegation.py
```

Make target:

```text
make check-harness-architecture
```

## Open Questions

- acceptance proposal は writer が作るか、専用の acceptance-designer role
  を作るか。
- proof command の存在確認をどこまで strict にするか。
- policy inheritance を許すか。最初は許さず、1 task 1 policy ref がよい。
- acceptance の semantic quality を reviewer が見るか、初期は機械監査だけにするか。

## Selected Option

`Policy Goal + Task Intent + Agent Acceptance Proposal + Harness Audit`
を採用する。

完全に人間が acceptance を書く方式は重い。
完全に agent に任せる方式は弱い acceptance を作れてしまう。
agent が acceptance を設計し、Harness が policy coverage と proof coverage
を監査してから `contract.lock` するのが最も単純で運用しやすい。
