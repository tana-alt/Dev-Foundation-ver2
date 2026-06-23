以下は、前回の **Foundation Agent Workflow Architecture 実装仕様書 v0.1** を前提に、**local-strict まで拡張するための実装仕様書 v0.2
です。

目的は、v0.1 の local-lite 構成を、次の段階へ引き上げることです。

```text
local-lite:
  CLI が Coordinator を直接起動し、SQLite を操作する

local-strict:
  Coordinator daemon が唯一の状態遷移主体になる
  CLI / ACP / Agent は daemon に request を送るだけになる
  SQLite は daemon 専用の内部状態になる
  capability session により role/action を強制する
  external side effect は outbox / effect log で復旧可能にする
```

---

# Foundation Local Strict Extension 実装仕様書 v0.2

## 0. 目的

本仕様は、v0.1 で実装した local workflow architecture を、**local-strict mode** に拡張するためのものである。

v0.1 では、CLI が Coordinator を起動し、StateStore に直接アクセスしていた。v0.2 では、StateStore への書き込み権限を **Coordinator daemon** に閉じ込め、CLI・ACP handler・Agent は daemon に request を送るだけにする。

この変更により、以下を実現する。

```text
- CLI から SQLite を直接更新できない
- 状態遷移は daemon 内の Coordinator のみが実行する
- role / capability によって action を強制する
- 状態遷移、外部副作用、reconcile を outbox/event log で復旧可能にする
- ACP自由会話と workflow authority をより強く分離する
- local環境での改ざん耐性を「検出可能」から「通常経路では編集不能」に近づける
```

## 0.1 現行リポジトリへのスコープ補正

本Planは、N0001実装後の実体に合わせて **既存 `contract_harness` を拡張する**。
以降の詳細仕様で `workflow_core.foundation`、`foundation` CLI、`foundation-runtime`
と書かれている箇所がこの節と衝突する場合は、この節を正とする。

決定:

```text
- 実装方針: build new ではなく extend
- 主要CLI: 既存 `./harness`
- strict mode: `./harness --strict ...`
- daemon executable: ルート `foundationd` は許可するが、中身は `contract_harness` daemon の薄いwrapper
- 実装名前空間: `src/workflow_core/contract_harness/`
- runtime root: 既存 `<git-common-dir>/harness-runtime/`
- state DB: 既存 `state/workflow-state.db`
- evidence store: 既存 `objects/sha256/`
```

In scope:

```text
- `src/workflow_core/contract_harness/daemon/` の protocol / client / server / errors
- `src/workflow_core/contract_harness/domain/capabilities.py`
- `src/workflow_core/contract_harness/application/capability_service.py`
- `src/workflow_core/contract_harness/application/outbox.py`
- `src/workflow_core/contract_harness/application/recovery.py`
- `src/workflow_core/contract_harness/application/runtime_lock.py`
- 既存 `SQLiteStateStore` の sessions / external_effects 拡張
- 既存 `cli.py` への `--strict` routing と daemon command routing
- strict CLI が StateStore / EvidenceStore を直接生成しないことのテスト
- daemon 経由の prepare / submit / verify / review / gate / pr / land / push / status
- StateStore event hash、Evidence object hash、Git/PR観測値の一致による authority 判定
```

Out of scope:

```text
- `src/workflow_core/foundation/` という新しい並行実装名前空間
- 新規 `foundation` CLI の本実装
- remote GitHub API / GitHub App / 実PR作成
- container / OSユーザー分離 / Ed25519署名
- stale file の archive 移動そのもの
- N0001以前のPlanや古い運用メモの広範整理
```

Archive 方針:

```text
- N0002実装中は archive 移動を行わず、陳腐化候補を記録するだけにする
- strict happy path と StateStore integrity が通った後に、別作業として archive へ移動する
- archive 対象は、現行 `contract_harness` 実装と矛盾する古いPlan、重複仕様、運用メモに限定する
```

Scope pass の完了条件:

```text
- 実装対象パスが `contract_harness` 配下に限定されている
- `foundation` / `foundation-runtime` 前提が既存 `harness` / `harness-runtime` に補正されている
- strict CLI の禁止事項が `SQLiteStateStore` / `FilesystemEvidenceStore` 直接生成禁止として明記されている
- verification target が既存 `check-harness-*` と strict追加テストに対応している
```

---

# 1. アーキテクチャ前提

## 1.1 v0.1 から継承する前提

v0.2 は v0.1 の以下を継承する。

```text
- workflow state の正本は StateStore event log
- code content の正本は Git
- evidence の正本は content-addressed Evidence Store
- ACP message は自由会話であり、authority を持たない
- role prompt は行動誘導であり、権限境界ではない
- 完了は merge commit hash + COMPLETE event の一致でのみ成立する
```

## 1.2 v0.2 で追加する前提

v0.2 では以下を追加する。

```text
- Coordinator daemon が唯一の状態遷移実行主体である
- CLI は daemon client であり、StateStore を直接開いてはならない
- ACP action handler も daemon client であり、StateStore を直接開いてはならない
- StateStore DB file は daemon が所有する runtime file として扱う
- daemon は単一repoごとに1つ起動する
- daemon は Unix domain socket で request を受ける
- request は session_id + capability_token で認可される
- side effect は outbox / external_effects table を経由して実行される
- crash recovery は reconcile / resume-outbox により行う
```

## 1.3 v0.2 でまだ実装しないもの

v0.2 では以下は実装しない。

```text
- container sandbox
- OS別ユーザー実行の完全分離
- Ed25519署名
- remote GitHub API
- GitHub App token
- 分散daemon
- 複数repo横断scheduler
- Web UI
```

ただし、それらを将来追加できるように port / adapter を分離する。

---

# 2. 実装対象ディレクトリ

v0.1/N0001 の構成に、以下を追加または拡張する。

```text
.
├── harness
├── foundationd
├── src/
│   └── workflow_core/
│       └── contract_harness/
│           ├── daemon/
│           │   ├── __init__.py
│           │   ├── server.py
│           │   ├── client.py
│           │   ├── protocol.py
│           │   └── errors.py
│           ├── application/
│           │   ├── capability_service.py
│           │   ├── outbox.py
│           │   ├── recovery.py
│           │   └── runtime_lock.py
│           ├── domain/
│           │   └── capabilities.py
│           ├── adapters/
│           │   ├── sqlite_state_store.py
│           │   ├── filesystem_evidence_store.py
│           │   └── local_secret_store.py
│           └── cli.py
└── tests/
    └── workflow_core/
        └── contract_harness/
            ├── test_strict_daemon_lifecycle.py
            ├── test_strict_daemon_protocol.py
            ├── test_strict_cli.py
            ├── test_strict_capabilities.py
            ├── test_strict_outbox_recovery.py
            ├── test_strict_single_writer.py
            ├── test_strict_acp_action_requests.py
            ├── test_strict_status.py
            └── test_strict_happy_path.py
```

`foundationd` は新規programとして置いてよいが、daemon実装本体は
`workflow_core.contract_harness.daemon.server` に置く。新規
`workflow_core.foundation` tree は作らない。

---

# 3. 新規プログラム定義

## 3.1 `foundationd`

ルートに実行ファイル `foundationd` を追加する。

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

def main() -> int:
    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "src"))
    from workflow_core.contract_harness.daemon.server import main as daemon_main
    return daemon_main(sys.argv[1:])

if __name__ == "__main__":
    raise SystemExit(main())
```

`foundationd` は long-running process として動作する。

必須コマンド:

```sh
./foundationd run --repo <repo> [--foreground]
./foundationd status --repo <repo>
./foundationd stop --repo <repo>
```

MVPでは `run --foreground` を最優先で実装する。  
background daemon 起動は `harness daemon start` で実装してもよいが、テストでは foreground subprocess で十分とする。

## 3.2 `harness` strict mode

既存 `harness` CLI に strict mode を追加する。

```sh
./harness --strict prepare T-0001
./harness --strict submit T-0001
./harness --strict verify T-0001
```

strict mode では、CLI は SQLite を直接開いてはならない。  
必ず Unix domain socket 経由で daemon に request を送る。

環境変数でも指定可能にする。

```sh
FOUNDATION_MODE=strict ./harness status T-0001
```

`FOUNDATION_MODE` は既存の `FOUNDATION_*` 環境変数群との互換名として使う。
新規 `foundation` CLI は v0.2 の必須実装に含めない。

優先順位:

```text
1. CLI flag --strict / --local-lite
2. env FOUNDATION_MODE
3. default: local-lite
```

---

# 4. Runtime layout

v0.2 の runtime layout は以下とする。

```text
<git-common-dir>/harness-runtime/
  state/
    workflow-state.db
    workflow-state.db-wal
    workflow-state.db-shm
    tasks/
      <task_id>/
  daemon/
    foundation.sock
    foundation.pid
    daemon.json
    auth/
      root.token
      sessions/
        <session_id>.json
  objects/
    sha256/
      <prefix>/
        <sha256>
  acp/
  workspaces/
  outbox/
  logs/
    daemon.log
```

## 4.1 File permission

可能な範囲で以下を設定する。

```text
harness-runtime/           0700
state/                     0700
daemon/                    0700
daemon/auth/               0700
workflow-state.db          0600
foundation.sock            0600
root.token                 0600
session token files        0600
```

Windows対応は v0.2 対象外。  
v0.2 は POSIX / Unix domain socket 前提でよい。

## 4.2 Runtime metadata

`daemon/daemon.json` に daemon 情報を保存する。

```json
{
  "schema_version": 1,
  "repo_root": "/path/to/repo",
  "git_common_dir": "/path/to/repo/.git",
  "runtime_root": "/path/to/repo/.git/harness-runtime",
  "socket_path": "/path/to/repo/.git/harness-runtime/daemon/foundation.sock",
  "pid": 12345,
  "started_at": "2026-06-19T00:00:00Z",
  "mode": "local-strict"
}
```

---

# 5. Daemon protocol

## 5.1 Transport

v0.2 では Unix domain socket + newline-delimited JSON を使う。

1 request = 1 JSON object + `\n`  
1 response = 1 JSON object + `\n`

HTTPは使わない。  
JSON-RPC風の独自protocolでよい。

## 5.2 Request format

`daemon/protocol.py` に Pydantic model を定義する。

```python
class DaemonRequest(StrictModel):
    schema_version: int = 1
    request_id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    capability_token: str | None = None
```

## 5.3 Response format

```python
class DaemonResponse(StrictModel):
    schema_version: int = 1
    request_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
```

Error format:

```python
class DaemonErrorPayload(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
```

## 5.4 Error code

```text
usage_error
daemon_unavailable
unauthorized
forbidden
invalid_state
integrity_error
not_found
conflict
side_effect_failed
internal_error
```

## 5.5 Required methods

Daemon は以下の method を実装する。

```text
daemon.ping
daemon.status
daemon.shutdown

session.create
session.revoke
session.list

task.prepare
task.context
task.status

candidate.submit
candidate.verify

review.run
review.collect

gate.run

pr.create
pr.checks
merge.local
task.complete

acp.send
acp.list

reconcile.task
outbox.resume
integrity.verify
```

CLI command と daemon method の対応は明示的に mapping する。

---

# 6. Daemon server

## 6.1 Server lifecycle

`daemon/server.py` に実装する。

起動手順:

```text
1. repo root を解決
2. git common dir を解決
3. runtime_root を作成
4. permission を設定
5. workflow-state.db を初期化
6. root token を作成または読み込み
7. socket file が残っていれば stale check
8. pid file を作成
9. Unix domain socket listen
10. request loop 開始
```

停止手順:

```text
1. daemon.shutdown request を受ける
2. in-flight request 完了を待つ
3. socket close
4. socket file 削除
5. pid file 削除
6. daemon.json 更新または削除
```

## 6.2 Single writer

v0.2 では daemon process 内で request を逐次処理してよい。  
並列処理は不要。

実装制約:

```text
- StateStore write は常に daemon main request loop で直列に行う
- 同時requestが来ても、状態遷移は1つずつ処理する
- read-only request は将来並列化してよいが v0.2 では不要
```

## 6.3 Runtime lock

同一repoに複数daemonが起動しないようにする。

`application/runtime_lock.py`

```text
lock file:
  <runtime_root>/daemon/daemon.lock
```

POSIXでは `fcntl.flock` を使う。  
実装が難しければ、v0.2 MVPでは pid file + socket ping で代替してよい。ただしテストで二重起動拒否を確認する。

二重起動時:

```json
{
  "ok": false,
  "error": {
    "code": "conflict",
    "message": "foundationd already running for this repository"
  }
}
```

---

# 7. Capability設計

## 7.1 原則

role prompt は権限ではない。  
権限は session capability によって Coordinator が強制する。

## 7.2 Session model

`domain/capabilities.py`

```python
class Capability(StrEnum):
    READ_CONTEXT = "read_context"
    READ_STATUS = "read_status"
    SEND_ACP_MESSAGE = "send_acp_message"

    SUBMIT_CANDIDATE = "submit_candidate"
    RUN_VERIFY = "run_verify"

    RUN_REVIEW = "run_review"
    COLLECT_REVIEW = "collect_review"

    RUN_GATE = "run_gate"
    CREATE_PR = "create_pr"
    RUN_PR_CHECKS = "run_pr_checks"
    MERGE_LOCAL = "merge_local"
    COMPLETE_TASK = "complete_task"
    RECONCILE = "reconcile"

    ADMIN = "admin"
```

```python
class Session(StrictModel):
    schema_version: int = 1
    session_id: str
    task_id: str | None = None
    role: Literal["writer", "reviewer", "integrator", "admin"]
    agent_id: str
    capabilities: list[Capability]
    token_hash: str
    status: Literal["active", "revoked", "expired"] = "active"
    created_at: str
    expires_at: str | None = None
```

## 7.3 Role capability mapping

Default mapping:

```python
WRITER_CAPABILITIES = {
    READ_CONTEXT,
    READ_STATUS,
    SEND_ACP_MESSAGE,
    SUBMIT_CANDIDATE,
    RUN_VERIFY,
}

REVIEWER_CAPABILITIES = {
    READ_CONTEXT,
    READ_STATUS,
    SEND_ACP_MESSAGE,
    RUN_REVIEW,
}

INTEGRATOR_CAPABILITIES = {
    READ_CONTEXT,
    READ_STATUS,
    SEND_ACP_MESSAGE,
    COLLECT_REVIEW,
    RUN_GATE,
    CREATE_PR,
    RUN_PR_CHECKS,
    MERGE_LOCAL,
    COMPLETE_TASK,
    RECONCILE,
}

ADMIN_CAPABILITIES = {
    ADMIN,
    READ_CONTEXT,
    READ_STATUS,
    SEND_ACP_MESSAGE,
    SUBMIT_CANDIDATE,
    RUN_VERIFY,
    RUN_REVIEW,
    COLLECT_REVIEW,
    RUN_GATE,
    CREATE_PR,
    RUN_PR_CHECKS,
    MERGE_LOCAL,
    COMPLETE_TASK,
    RECONCILE,
}
```

## 7.4 Session creation

CLI:

```sh
harness --strict session create --role writer --task T-0001 --agent writer.codex.T-0001
harness --strict session create --role reviewer --task T-0001 --agent reviewer.scope.T-0001
harness --strict session create --role integrator --task T-0001 --agent integrator.codex.T-0001
```

Daemon method:

```text
session.create
```

Session create は admin token なしでも許可するかどうかをモードで分ける。

v0.2 MVP:

```text
- daemon起動時に root.token を作成
- session.create は root token が必要
```

ただし、テスト容易性のために以下を許可する。

```sh
foundationd run --repo <repo> --foreground --dev-open-session-create
```

この場合、session.create は root token なしで可能。  
本番想定では使わない。

## 7.5 Token handling

session token は生成時に1回だけ返す。

Response:

```json
{
  "ok": true,
  "result": {
    "session_id": "sess_...",
    "capability_token": "ftok_...",
    "role": "writer",
    "agent_id": "writer.codex.T-0001"
  }
}
```

StateStore には token そのものを保存せず、sha256 のみ保存する。

Request時:

```text
- session_id が存在する
- session.status == active
- sha256(capability_token) == token_hash
- requested method に必要な capability がある
```

失敗時:

```text
unauthorized
forbidden
```

## 7.6 CLI token source

CLIは token を以下の順で読む。

```text
1. --session-id / --capability-token
2. env FOUNDATION_SESSION_ID / FOUNDATION_CAPABILITY_TOKEN
3. daemon/auth/sessions/<role-or-agent>.json
```

v0.2 では、session create 結果を任意で file に保存できるようにする。

```sh
harness --strict session create \
  --role writer \
  --task T-0001 \
  --agent writer.codex.T-0001 \
  --write-env .foundation/sessions/writer.env
```

---

# 8. CLI strict behavior

## 8.1 Strict client

`daemon/client.py` に daemon client を実装し、既存 `cli.py` からのみ呼び出す。

責務:

```text
- repo root 解決
- socket path 解決
- daemon に接続
- request_id 生成
- NDJSON request送信
- response受信
- JSON出力
```

## 8.2 CLIが直接DBを開かない制約

strict mode の CLI 実装では以下を import してはならない。

```text
workflow_core.contract_harness.adapters.sqlite_state_store.SQLiteStateStore
workflow_core.contract_harness.adapters.filesystem_evidence_store.FilesystemEvidenceStore
```

テストで monkeypatch を使って、strict CLI が `SQLiteStateStore` /
`FilesystemEvidenceStore` を直接生成しないことを確認する。

許可:

```text
- daemon client
- protocol model
- git root resolver
- token loader
```

禁止:

```text
- StateStore direct write
- EvidenceStore direct write
- Coordinator direct instantiation
```

## 8.3 Daemon unavailable

strict CLI 実行時に daemon が起動していなければ、以下を返す。

```json
{
  "ok": false,
  "error": {
    "code": "daemon_unavailable",
    "message": "foundationd is not running for this repository"
  }
}
```

exit code:

```text
1
```

自動起動は v0.2 では任意。  
MVPでは自動起動しない。

---

# 9. Coordinator変更

v0.1 の Coordinator を daemon 内で使えるようにする。

## 9.1 Coordinator instantiation

daemon 起動時に以下を生成する。

```text
StateStore
EvidenceStore
GitRepository
WorkspaceManager
VerifierRunner
AcpBus
ExternalWriteBroker
CapabilityService
OutboxService
Coordinator
```

CLI は Coordinator を生成しない。

## 9.2 Request authorization

Coordinator method の入口で capability check を行う。

例:

```text
candidate.submit requires SUBMIT_CANDIDATE
candidate.verify requires RUN_VERIFY
review.run requires RUN_REVIEW
review.collect requires COLLECT_REVIEW
gate.run requires RUN_GATE
pr.create requires CREATE_PR
task.complete requires COMPLETE_TASK
```

Read-only:

```text
task.context requires READ_CONTEXT
task.status requires READ_STATUS
acp.send requires SEND_ACP_MESSAGE
```

Admin:

```text
integrity.verify requires ADMIN
session.create requires ADMIN unless dev-open-session-create
daemon.shutdown requires ADMIN
```

## 9.3 Actor identity

すべての event の `actor` は session から決める。

```text
actor = "<role>:<agent_id>"
```

CLI の `--actor` は strict mode では原則使わない。  
actor は session に由来する。

---

# 10. Outbox / side effect仕様

## 10.1 目的

外部副作用は DB transaction と完全には一体化できない。  
そのため、v0.2 では outbox pattern を導入する。

対象 side effect:

```text
- verifier run
- local PR ref create
- PR checks
- local merge
- ACP message write
```

v0.2 では local-only だが、将来の GitHub API に備えて同じ構造にする。

## 10.2 external_effects table 拡張

既存 `external_effects` に以下を追加する。

```sql
ALTER TABLE external_effects ADD COLUMN requested_event_sha256 TEXT;
ALTER TABLE external_effects ADD COLUMN result_event_sha256 TEXT;
ALTER TABLE external_effects ADD COLUMN attempt_count INTEGER DEFAULT 0;
ALTER TABLE external_effects ADD COLUMN last_error TEXT;
ALTER TABLE external_effects ADD COLUMN updated_at TEXT;
```

新規構築時はDDLに含める。

## 10.3 Effect status

```text
requested
running
succeeded
failed
needs_reconcile
```

## 10.4 Effect flow

例: PR create

```text
1. Coordinator validates guards
2. append PR_CREATE_REQUESTED event
3. insert external_effects row:
   effect_type = create_pr
   status = requested
   idempotency_key = create_pr:<task_id>:<candidate_id>
4. OutboxService executes effect
5. if success:
   append PR_CREATED event
   update external_effects status=succeeded
6. if failure:
   append PR_CREATE_FAILED event
   update external_effects status=failed
```

## 10.5 Idempotency

同じ idempotency_key の effect は二重実行しない。

```text
create_pr:<task_id>:<candidate_id>
pr_checks:<task_id>:<candidate_id>:<pr_head_sha>
merge_local:<task_id>:<candidate_id>:<target_branch>
complete:<task_id>:<candidate_id>:<merge_commit_sha>
```

すでに succeeded の effect がある場合、再実行 request は既存 result を返す。

## 10.6 Resume outbox

CLI:

```sh
harness --strict outbox resume
```

Daemon method:

```text
outbox.resume
```

動作:

```text
- status in requested, running, needs_reconcile の effect を探す
- idempotency_key に基づいて外部状態を観測
- 成功済みなら result event を補完
- 未実行なら実行
- 失敗なら failed にする
```

---

# 11. Reconciliation強化

v0.2 では reconcile を daemon 内の正式機能にする。

## 11.1 Reconcile対象

```text
- StateStore projection
- event hash chain
- candidate patch object
- verify result object
- review verdict object
- PR ref
- PR head hash
- local merge commit
- target branch contains merge
- external_effects pending/running states
```

## 11.2 Reconcile result

```python
class ReconcileFinding(StrictModel):
    severity: Literal["info", "warn", "error", "critical"]
    code: str
    message: str
    recoverable: bool
    details: dict[str, Any] = Field(default_factory=dict)

class ReconcileResult(StrictModel):
    schema_version: int = 1
    task_id: str
    status: Literal["consistent", "recovered", "inconsistent"]
    findings: list[ReconcileFinding]
    repaired_event_sha256: str | None = None
```

## 11.3 Inconsistent transition

以下の場合は `INCONSISTENT` event を append する。

```text
- StateStore says PR_CREATED but PR ref missing
- StateStore says REMOTE_CHECKS_PASSED but PR head no longer matches candidate
- StateStore says MERGED but target branch does not contain merge commit
- COMPLETE exists but merge observation is missing or mismatched
- event hash chain is invalid
```

ただし、event hash chain invalid の場合は原則として新event appendも信用できないため、`integrity_error` として daemonを read-only degraded mode に移す。

---

# 12. Daemon degraded mode

## 12.1 目的

StateStore integrity が壊れた場合、通常の状態遷移を止める。

## 12.2 Behavior

daemon起動時に `StateStore.verify_integrity()` を実行する。

失敗時:

```text
- daemon は起動してよい
- mode = degraded
- read-only methods のみ許可
- 状態遷移 method は integrity_error を返す
- integrity.verify は詳細を返す
```

read-only methods:

```text
daemon.status
task.status
task.context
integrity.verify
acp.list
```

write methods:

```text
すべて拒否
```

Response:

```json
{
  "ok": false,
  "error": {
    "code": "integrity_error",
    "message": "StateStore integrity check failed; daemon is in degraded read-only mode"
  }
}
```

---

# 13. ACP action requestの扱い

## 13.1 v0.2で追加するもの

ACP message は authority を持たない。  
ただし、ACP action request を daemon request に変換する handler を追加してよい。

v0.2 MVPでは、自動実行はしない。  
代わりに以下を実装する。

```sh
harness --strict acp request-action <message_id>
```

このコマンドは、ACP message の `kind == action_request` を読み、対応する daemon method を提案するだけである。

自動状態遷移は禁止。

## 13.2 Action request proposal

`acp request-action` の出力例:

```json
{
  "ok": true,
  "message_id": "...",
  "authoritative": false,
  "proposed_action": {
    "method": "candidate.verify",
    "params": {
      "task_id": "T-0001"
    }
  },
  "executed": false
}
```

実行するには明示的に CLI command を叩く。

---

# 14. Strict role prompt追加

v0.2 では role prompt に session / daemon 前提を含める。

## 14.1 writer strict prompt

含める内容:

```text
- You are connected to foundationd through a capability session.
- Your role prompt is not authority.
- Your allowed actions are enforced by the daemon.
- You cannot complete the task.
- ACP messages are non-authoritative.
- Use only strict CLI commands.
```

使用可能コマンド:

```text
harness --strict context <task_id>
harness --strict submit <task_id>
harness --strict verify <task_id>
harness --strict status <task_id>
harness --strict acp send ...
```

禁止:

```text
harness --strict gate
harness --strict pr create
harness --strict merge local
harness --strict complete
```

## 14.2 reviewer strict prompt

使用可能:

```text
harness --strict review run <task_id> --reviewer <reviewer_id>
harness --strict status <task_id>
harness --strict acp send ...
```

禁止:

```text
candidate modification
review collect
gate
complete
```

## 14.3 integrator strict prompt

使用可能:

```text
harness --strict review collect <task_id>
harness --strict gate <task_id>
harness --strict pr create <task_id>
harness --strict pr checks <task_id>
harness --strict merge local <task_id> --target <branch>
harness --strict complete <task_id>
harness --strict reconcile <task_id>
```

注意文:

```text
Completion is not a statement.
Completion is only the observed merged hash plus COMPLETE event recorded by foundationd.
```

---

# 15. Daemon command仕様

## 15.1 harness daemon commands

既存 `harness` CLI に追加する。

```sh
harness daemon run --foreground
harness daemon start
harness daemon stop
harness daemon status
harness daemon ping
```

MVP必須:

```text
run --foreground
status
ping
stop
```

`start` は任意。  
テストは `run --foreground` subprocess を使う。

## 15.2 session commands

```sh
harness --strict session create --role writer --task T-0001 --agent writer.codex.T-0001
harness --strict session revoke <session_id>
harness --strict session list
```

`session create` は root token が必要。

root token 指定:

```sh
harness --strict session create ... --root-token <token>
```

または:

```sh
FOUNDATION_ROOT_TOKEN=<token>
```

## 15.3 outbox commands

```sh
harness --strict outbox resume
harness --strict outbox status
```

`outbox status` は pending/running/failed effects を返す。

---

# 16. Program interfaces

## 16.1 `DaemonClient`

`daemon/client.py`

```python
class DaemonClient:
    def __init__(self, socket_path: Path, timeout_s: float = 30.0) -> None: ...

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        capability_token: str | None = None,
    ) -> DaemonResponse: ...
```

## 16.2 `DaemonServer`

`daemon/server.py`

```python
class DaemonServer:
    def __init__(
        self,
        repo_root: Path,
        *,
        foreground: bool = False,
        dev_open_session_create: bool = False,
    ) -> None: ...

    def serve_forever(self) -> int: ...
    def shutdown(self) -> None: ...
```

## 16.3 `CapabilityService`

`application/capability_service.py`

```python
class CapabilityService:
    def create_session(
        self,
        *,
        role: str,
        agent_id: str,
        task_id: str | None,
        expires_at: str | None = None,
    ) -> tuple[Session, str]: 
        """Returns session model and plaintext capability token once."""

    def authorize(
        self,
        *,
        session_id: str | None,
        token: str | None,
        required: Capability,
    ) -> Session:
        """Raises UnauthorizedError or ForbiddenError."""
```

## 16.4 `OutboxService`

`application/outbox.py`

```python
class OutboxService:
    def request_effect(
        self,
        *,
        effect_type: str,
        task_id: str,
        candidate_id: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
        requested_event_sha256: str,
    ) -> dict[str, Any]: ...

    def run_effect(self, effect_id: str) -> dict[str, Any]: ...
    def resume(self) -> dict[str, Any]: ...
    def status(self) -> dict[str, Any]: ...
```

---

# 17. StateStore拡張

## 17.1 Required methods

`ports/state_store.py` に追加する。

```python
def create_session(self, session: Session) -> None: ...
def get_session(self, session_id: str) -> Session: ...
def update_session_status(self, session_id: str, status: str) -> None: ...
def list_sessions(self, task_id: str | None = None) -> list[Session]: ...

def insert_external_effect(self, effect: ExternalEffect) -> None: ...
def update_external_effect(self, effect_id: str, **fields: Any) -> None: ...
def get_external_effect_by_idempotency_key(self, key: str) -> ExternalEffect | None: ...
def list_external_effects(self, statuses: list[str] | None = None) -> list[ExternalEffect]: ...
```

## 17.2 Write enforcement

v0.3では、StateStore class自体に daemon enforcement は入れなくてよい。  
ただし、strict CLIがStateStoreを直接生成しないことをテストで保証する。

将来、`DaemonStateStore` adapter を作り、daemon process id check を入れてもよい。

---

# 18. テスト仕様

新規テストは `tests/workflow_core/contract_harness/` に `test_strict_*.py`
として置く。

外部ネットワークは禁止。  
daemon は subprocess で `foundationd run --foreground --repo <tmp_repo>` として起動する。

テストヘルパーを作る。

```python
def start_daemon(repo: Path) -> DaemonProcess:
    ...

def strict_cli(repo: Path, *args: str, session: SessionInfo | None = None) -> CompletedProcess[str]:
    ...
```

---

## 18.1 `test_daemon_lifecycle.py`

### test_daemon_ping

手順:

```text
1. temp repo 作成
2. foundationd run --foreground を subprocess 起動
3. harness --strict daemon ping
```

期待:

```text
- ok true
- result.status == running
```

### test_daemon_stop

手順:

```text
1. daemon起動
2. harness --strict daemon stop
3. process終了を確認
```

期待:

```text
- socket file が消える
- pid file が消える
```

### test_second_daemon_is_rejected

手順:

```text
1. daemon起動
2. 同じrepoで2つ目のdaemon起動
```

期待:

```text
- 2つ目は exit code != 0
- error code conflict
```

---

## 18.2 `test_daemon_protocol.py`

### test_protocol_returns_json_error_for_unknown_method

手順:

```text
1. daemon起動
2. raw client で method=no.such.method
```

期待:

```text
- ok false
- error.code == usage_error
```

### test_malformed_json_does_not_crash_daemon

手順:

```text
1. socket に不正JSONを送る
2. daemon ping
```

期待:

```text
- daemonは生存している
```

---

## 18.3 `test_cli_uses_daemon.py`

### test_strict_cli_fails_when_daemon_unavailable

手順:

```text
1. daemonを起動しない
2. harness --strict status T-0001
```

期待:

```text
- exit code 1
- error.code == daemon_unavailable
```

### test_strict_cli_does_not_construct_sqlite_state_store

手順:

```text
1. monkeypatch SQLiteStateStore.__init__ to raise
2. daemonを起動
3. strict CLI status を実行
```

期待:

```text
- CLI側では SQLiteStateStore.__init__ が呼ばれない
- request は daemon 経由で成功する
```

---

## 18.4 `test_capabilities.py`

### test_writer_cannot_gate

手順:

```text
1. daemon起動
2. writer session 作成
3. writer tokenで gate.run request
```

期待:

```text
- ok false
- error.code == forbidden
```

### test_integrator_can_gate

手順:

```text
1. happy pathをREVIEW_APPROVEDまで進める
2. integrator sessionで gate
```

期待:

```text
- ok true
- state == LOCAL_GATE_PASSED
```

### test_invalid_token_rejected

期待:

```text
- error.code == unauthorized
```

### test_revoked_session_rejected

手順:

```text
1. session作成
2. revoke
3. same tokenでstatus以外または任意request
```

期待:

```text
- unauthorized
```

---

## 18.5 `test_db_not_opened_by_cli.py`

### test_cli_cannot_modify_db_file_without_daemon

手順:

```text
1. daemon停止
2. strict CLI prepare
```

期待:

```text
- daemon_unavailable
- workflow-state.db が新規作成されない
```

### test_state_db_permissions_are_restrictive

手順:

```text
1. daemon起動
2. workflow-state.db の mode を確認
```

期待:

```text
- POSIXなら 0600
```

---

## 18.6 `test_outbox_recovery.py`

### test_pr_create_effect_is_idempotent

手順:

```text
1. LOCAL_GATE_PASSEDまで進める
2. pr create 実行
3. 同じ pr create を再実行
```

期待:

```text
- PR ref は同じ
- duplicate event は作らない、または idempotent reused として返す
- state remains PR_CREATED
```

### test_resume_requested_effect

手順:

```text
1. external_effects に requested effect を直接fixtureとして挿入
2. outbox resume
```

期待:

```text
- effect が succeeded または failed に更新される
- result event が作られる
```

### test_failed_effect_is_reported

期待:

```text
- outbox status に failed effect が出る
```

---

## 18.7 `test_daemon_single_writer.py`

### test_concurrent_submit_requests_are_serialized

手順:

```text
1. daemon起動
2. 同じtaskに対して2つのsubmit requestを並行送信
```

期待:

```text
- 片方のみ成功
- もう片方は invalid_state または conflict
- StateStore integrity は pass
```

### test_event_chain_valid_after_concurrent_requests

期待:

```text
- verify_integrity ok
```

---

## 18.8 `test_acp_action_requests.py`

### test_acp_action_request_does_not_execute_transition

手順:

```text
1. CONTRACT_PREPARED
2. ACP action_request body="please verify"
3. status
```

期待:

```text
- state == CONTRACT_PREPARED
```

### test_acp_request_action_outputs_proposal_only

手順:

```text
1. acp request-action <message_id>
```

期待:

```text
- proposed_action が返る
- executed == false
- state unchanged
```

---

## 18.9 `test_strict_status.py`

### test_status_includes_daemon_mode

期待:

```json
{
  "mode": "local-strict",
  "daemon": {
    "running": true
  }
}
```

### test_degraded_mode_blocks_writes

手順:

```text
1. daemon停止
2. workflow-state.db を改ざん
3. daemon起動
4. status
5. submit
```

期待:

```text
- status は返る
- submit は integrity_error
```

---

## 18.10 `test_strict_happy_path.py`

### test_strict_happy_path_to_complete

手順:

```text
1. temp repo作成
2. daemon起動
3. admin/root token取得
4. writer/reviewer/integrator sessions作成
5. prepare
6. file変更
7. writer submit
8. writer verify
9. reviewer reader-scope run
10. reviewer reader-correctness run
11. integrator review collect
12. integrator gate
13. integrator pr create
14. integrator pr checks
15. integrator merge local --target main
16. integrator complete
17. status
```

期待:

```text
- final state == COMPLETE
- completion.complete == true
- merge_commit_sha exists
- StateStore integrity pass
- ACP messages がなくても成立する
```

---

# 19. Makefile追加

既存 Makefile に追加する。

```make
check-harness-strict:
	$(UV) run pytest -q tests/workflow_core/contract_harness -k strict

check-harness-arch-all: check-harness-architecture check-harness-state check-harness-strict
```

v0.2 完了条件には `check-harness-arch-all` passing を含める。

---

# 20. 実装順序

Codex は以下の順番で実装すること。

## Step 1: daemon protocol / client

実装:

```text
src/workflow_core/contract_harness/daemon/protocol.py
src/workflow_core/contract_harness/daemon/client.py
```

テスト:

```text
test_daemon_protocol.py の protocol model 単体部分
```

## Step 2: daemon server minimal ping

実装:

```text
foundationd
src/workflow_core/contract_harness/daemon/server.py
harness daemon ping
harness daemon status
harness daemon stop
```

テスト:

```text
test_daemon_lifecycle.py
test_daemon_protocol.py
```

## Step 3: strict CLI client path

実装:

```text
src/workflow_core/contract_harness/cli.py
src/workflow_core/contract_harness/daemon/client.py
--strict flag
FOUNDATION_MODE=strict
```

テスト:

```text
test_cli_uses_daemon.py
```

## Step 4: capability service

実装:

```text
domain/capabilities.py
application/capability_service.py
session.create / session.revoke / session.list
```

テスト:

```text
test_capabilities.py の token/session 部分
```

## Step 5: daemon-hosted Coordinator

実装:

```text
daemon/server method routing
Coordinatorをdaemon内で生成
task.prepare / task.status / task.context
```

テスト:

```text
strict prepare/status smoke
```

## Step 6: strict workflow methods

実装:

```text
candidate.submit
candidate.verify
review.run
review.collect
gate.run
```

テスト:

```text
test_capabilities.py
test_daemon_single_writer.py
```

## Step 7: outbox service

実装:

```text
application/outbox.py
external_effects extension
outbox.status
outbox.resume
```

テスト:

```text
test_outbox_recovery.py
```

## Step 8: local PR / merge through outbox

実装:

```text
pr.create
pr.checks
merge.local
task.complete
```

テスト:

```text
test_strict_happy_path.py
```

## Step 9: ACP action request proposal

実装:

```text
acp.send strict route
acp.request-action
```

テスト:

```text
test_acp_action_requests.py
```

## Step 10: degraded mode / reconcile

実装:

```text
daemon startup integrity check
degraded mode
reconcile.task
```

テスト:

```text
test_strict_status.py
test_reconcile strict additions
```

---

# 21. 完了条件

v0.2 local-strict 完了条件は以下。

```text
- foundationd が foreground daemon として起動できる
- harness --strict が daemon 経由で動く
- strict CLI は StateStore を直接開かない
- session capability により writer/reviewer/integrator のactionが強制される
- writer は gate / pr / merge / complete を実行できない
- reviewer は candidate submit / gate / complete を実行できない
- integrator は gate / pr / merge / complete を実行できる
- StateStore integrity check が起動時に実行される
- integrity failure 時は daemon が degraded read-only mode になる
- external_effects outbox が idempotent に動く
- ACP action_request は自動状態遷移しない
- strict happy path が COMPLETE まで通る
- make check-harness-arch-all が pass
```

---

# 22. 設計上の禁止事項

Codex は v0.2 実装において以下をしてはならない。

```text
- strict CLI から SQLiteStateStore を直接生成する
- strict CLI から Coordinator を直接生成する
- session token を平文でDBに保存する
- ACP message によって自動で COMPLETE にする
- role prompt を authorization として扱う
- capability check をCLI側だけで済ませる
- daemonを迂回してStateStore eventをappendする
- external side effect を event/outbox なしで直接実行する
- daemon起動時の integrity check を省略する
- integrity failure 後もwrite transitionを許可する
- PR作成だけで COMPLETE にする
- merge hash 観測なしに COMPLETE にする
```

---

# 23. v0.2 の最小動作例

## 23.1 daemon起動

```sh
./foundationd run --repo . --foreground
```

別シェル:

```sh
./harness --strict daemon ping
```

期待:

```json
{
  "ok": true,
  "result": {
    "status": "running",
    "mode": "local-strict"
  }
}
```

## 23.2 session作成

```sh
export FOUNDATION_ROOT_TOKEN="$(cat .git/harness-runtime/daemon/auth/root.token)"

./harness --strict session create \
  --role writer \
  --task T-0001 \
  --agent writer.codex.T-0001 \
  --root-token "$FOUNDATION_ROOT_TOKEN"
```

返却された `session_id` と `capability_token` を以後使う。

## 23.3 writer

```sh
FOUNDATION_SESSION_ID=<writer_session> \
FOUNDATION_CAPABILITY_TOKEN=<writer_token> \
./harness --strict submit T-0001

FOUNDATION_SESSION_ID=<writer_session> \
FOUNDATION_CAPABILITY_TOKEN=<writer_token> \
./harness --strict verify T-0001
```

## 23.4 reviewer

```sh
FOUNDATION_SESSION_ID=<reviewer_session> \
FOUNDATION_CAPABILITY_TOKEN=<reviewer_token> \
./harness --strict review run T-0001 --reviewer reader-scope
```

## 23.5 integrator

```sh
FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict review collect T-0001

FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict gate T-0001

FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict pr create T-0001

FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict pr checks T-0001

FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict merge local T-0001 --target main

FOUNDATION_SESSION_ID=<integrator_session> \
FOUNDATION_CAPABILITY_TOKEN=<integrator_token> \
./harness --strict complete T-0001
```

Final status:

```json
{
  "ok": true,
  "result": {
    "task_id": "T-0001",
    "state": "COMPLETE",
    "mode": "local-strict",
    "completion": {
      "complete": true,
      "source": "merged_hash_and_complete_event",
      "merge_commit_sha": "..."
    }
  }
}
```

---

# 24. v0.2 の中核原則

v0.2 の中核原則は以下である。

> local-strict では、状態遷移の唯一の実行主体を foundationd 内の Coordinator に限定し、CLI・ACP・Agent は capability session を通じて request を送るだけにする。SQLite StateStore は daemon の内部状態として扱い、workflow authority は event log、evidence hash、Git/PR観測結果の一致によってのみ成立する。

この原則に反する実装は不採用とする。
