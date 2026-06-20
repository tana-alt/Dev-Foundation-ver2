必要な部分だけに削ると、アーキテクチャはこれで足ります。

```text
Runtime Kernel
├─ Identity Loader
├─ State Boundary
├─ Event Store
├─ View Projector
└─ Agent Runner
```

## 1. Identity Loader

AGENTS.md 的な常時読み込み層。

役割は、agent が自分の role を忘れないようにすること。

```text
Identity Loader
  -> common identity
  -> role identity
  -> current view
```

role は routing map で選ばない。
agent は **role-bound process** として起動される。

```text
spawn writer
  -> common + writer identity を必ず注入

spawn reviewer
  -> common + reviewer identity を必ず注入

spawn integrator
  -> common + integrator identity を必ず注入
```

必要なのはこれだけ。

```text
.agent/identity/common.md
.agent/identity/writer.md
.agent/identity/reviewer.md
.agent/identity/integrator.md
```

## 2. State Boundary

strict mode の本体。

SQLite を agent から直接書けないようにする。

```text
Agent
  -> runtime command
  -> State Boundary
  -> SQLite
```

禁止するもの。

```text
agent -> sqlite direct write
agent -> state file rewrite
agent -> runtime state manual edit
```

許可するもの。

```text
agent -> propose action
agent -> append evidence through runtime
agent -> request state transition through runtime
```

strict mode は Block を増やすものではなく、**state mutation の所有者を Runtime Kernel に固定するもの**。

## 3. Event Store

SQLite を直接 truth にしない。

truth は append-only event。

```text
Event Store
  -> ObjectiveCreated
  -> AgentRunStarted
  -> ActionProposed
  -> CommandExecuted
  -> EvidenceObserved
  -> StateCommitted
  -> ReviewReturned
  -> ReworkRequested
  -> ObjectiveClosed
```

SQLite は event から作られる materialized state。

```text
event log = source of truth
SQLite    = queryable state view
```

## 4. View Projector

task envelope は誰かが作らない。

runtime が現在状態から agent 用 view を作る。

```text
Current View =
  identity
  + objective
  + capabilities
  + evidence
  + pending state
```

agent はこれだけ読む。

```text
You are: writer
Current objective: ...
Allowed actions: ...
Current evidence: ...
Next unresolved state: ...
```

これで task envelope author も routing map も不要になる。

## 5. Agent Runner

agent process は短命でよい。

```text
trigger
  -> Agent Runner
  -> identity 注入
  -> current view 注入
  -> agent 実行
  -> event 記録
  -> exit
```

常時存在するのは agent process ではない。

```text
常時存在:
  identity
  event store
  SQLite state
  objective
  current view projection

常時不要:
  scheduler
  queue
  heartbeat
  agent daemon
```

## 最小フロー

```text
1. objective が作られる
2. runtime が writer を起動する
3. writer identity + current view が注入される
4. writer が action/evidence を runtime に返す
5. runtime が event store に append する
6. runtime が SQLite view を更新する
7. 必要なら reviewer / integrator を同じ方式で起動する
```

## 必要な実装単位

```text
runtime_kernel/
  identity_loader.py
  state_boundary.py
  event_store.py
  view_projector.py
  agent_runner.py
```

## 必要な CLI

```sh
harness objective create
harness agent run --role writer --objective O-001
harness view show --role writer --objective O-001
harness event append
harness strict check
```

これだけでよいです。

## 削るもの

今は不要。

```text
scheduler
runtime queue
heartbeat
routing map
task envelope artifact
agent-level lock
常駐 agent daemon
大量の docs/reference
```

## 最小の設計文

```text
Agent は role を推論しない。
Runtime が role identity を毎回注入する。

Agent は SQLite を書かない。
Runtime だけが state mutation する。

Task envelope は保存しない。
Runtime が current view として投影する。

Agent は常駐しない。
Identity と state だけが常駐する。
```

この5部品だけで、今の目的には足ります。
