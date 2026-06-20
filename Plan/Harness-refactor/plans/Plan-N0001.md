# Foundation Agent Workflow Architecture 実装仕様書 v0.1

## 0. 目的

本仕様は、既存 `harness` の構造を破壊的に置き換えず、既存の writer / reviewer / integrator 分離、worktree 分離、candidate diff、machine evidence、review verdict、land / push policy を維持しながら、v0.1 で定義された StateStore / Evidence Store / local PR broker の利点を取り込むための v0.2 差し替え仕様である。

主目的は、新しい巨大な状態機械や追加の block check を作ることではない。  
既存実装にすでに存在する以下の構造を活かし、散在する JSON artifact を SQLite StateStore + content-addressed Evidence Store に束ね、CLI に集中している責任を domain / application / adapter 層へ分解する。

```text
- writer / reviewer / integrator role
- task contract / capsule
- scope-map-forward / scope-map-reverse
- affected-set
- candidate.diff
- verify-result.json
- review verdict
- gate-result.json
- land-result.json
- push-result.json
- worktree separation
- comm / session / rebind layer
```

本システムでは、エージェントは自由に実装・会話・協調できる。  
ただし、システムが権威として扱うのは自然文の発話ではなく、StateStore event、candidate diff、machine evidence、review verdict、merge / push observation、content hash によって束縛された証跡のみである。

完了は、エージェントの発話ではなく、landed / pushed hash と StateStore の `COMPLETE` event の一致によってのみ成立する。

---
# 1. アーキテクチャ前提

## 1.1 正本の分離

本システムでは、以下の正本を明確に分離する。

|対象|正本|
|---|---|
|ワークフロー上の権威ある進行|SQLite StateStore の append-only event log|
|コード内容|Git commit / tree / patch hash|
|candidate 内容|candidate diff hash|
|検証結果|machine evidence hash|
|レビュー判断|fresh review verdict|
|統合判断|gate / land / push evidence|
|エージェント会話|既存 comm / ACP 相当 layer|
|完了|landed / pushed hash + StateStore `COMPLETE` event|
|権限境界|role policy / application service guard|
|行動誘導|AGENTS.md、task capsule、role handoff prompt|

ACP / comm 上の会話、エージェントの発話、role prompt、CLI出力は、単独ではワークフロー状態の正本にならない。

## 1.2 MVPの実装範囲

v0.2 では、既存 `harness` を残したまま、責務分離と StateStore 化を段階的に実装する。

実装するもの:

```text
- 既存 ./harness CLI の薄い adapter 化
- src/workflow_core/contract_harness/application/
- src/workflow_core/contract_harness/domain/
- src/workflow_core/contract_harness/ports/
- src/workflow_core/contract_harness/adapters/
- SQLite StateStore
- Filesystem Evidence Store
- authority-bearing artifact の StateStore / Evidence Store への束縛
- diagnostic artifact の分類
- candidate / verify / review / gate / local PR / land / push の application service 化
- scope-map / affected-set の advisory 化
- allowed_paths hard block の撤去または互換的無効化
- forbidden_paths hard block の維持
- 既存 comm / session / rebind layer の再利用
- local PR broker / local merge broker
- status / reconcile の責務整理
- pytest suite
```

v0.2 で実装しないもの:

```text
- 新規 ACP bus の再実装
- 新規 foundation CLI の並行実装
- daemon 化された Coordinator
- 実 GitHub API による PR 作成
- 実 GitHub merge
- OS ユーザー分離
- container sandbox
- Ed25519 署名
- 分散 queue
- task scope expansion workflow
```

ただし、将来追加できるように port / adapter で分離する。

## 1.3 セキュリティ前提

v0.2 は local-strict-lite とする。

```text
- 同一 OS ユーザーによる直接ファイル編集 / SQLite 編集の完全防止は v0.2 の範囲外
- 通常経路では application service 経由で StateStore event と Evidence object を作る
- 改ざんや不整合は StateStore hash chain / reconcile / status / hash check で検出する
- role check は workflow guard であり、悪意ある local process に対する完全な security boundary ではない
```

v0.2 の目標は「すべてを block すること」ではなく、自由な実装を許容しながら、権威ある進行だけを StateStore event、content hash、machine evidence、fresh review、land / push observation で縛ることである。

---

## 2. 実装対象ディレクトリ

以下の構成で、既存 `contract_harness` 配下を段階的に整理する。

```text
.
├── harness
├── src/
│   └── workflow_core/
│       └── contract_harness/
│           ├── domain/
│           │   ├── __init__.py
│           │   ├── models.py
│           │   ├── states.py
│           │   ├── policy.py
│           │   ├── authority.py
│           │   └── errors.py
│           ├── application/
│           │   ├── __init__.py
│           │   ├── services.py
│           │   ├── candidate_service.py
│           │   ├── verify_service.py
│           │   ├── review_service.py
│           │   ├── gate_service.py
│           │   ├── pr_service.py
│           │   ├── land_service.py
│           │   ├── push_service.py
│           │   ├── status_service.py
│           │   └── reconcile_service.py
│           ├── ports/
│           │   ├── __init__.py
│           │   ├── state_store.py
│           │   ├── artifact_store.py
│           │   ├── evidence_store.py
│           │   ├── git_repository.py
│           │   ├── workspace_manager.py
│           │   ├── verifier_runner.py
│           │   ├── comm_bus.py
│           │   └── external_write_broker.py
│           ├── adapters/
│           │   ├── __init__.py
│           │   ├── sqlite_state_store.py
│           │   ├── filesystem_artifact_store.py
│           │   ├── filesystem_evidence_store.py
│           │   ├── git_cli_repository.py
│           │   ├── local_workspace_manager.py
│           │   ├── subprocess_verifier_runner.py
│           │   ├── existing_comm_bus.py
│           │   └── local_external_write_broker.py
│           ├── cli.py
│           └── ...
└── tests/
    └── workflow_core/
        ├── test_contract_harness.py
        └── contract_harness/
            ├── test_state_store.py
            ├── test_authority_boundaries.py
            ├── test_scope_advisory.py
            ├── test_candidate_service.py
            ├── test_verify_service.py
            ├── test_review_service.py
            ├── test_gate_service.py
            ├── test_land_push_service.py
            ├── test_comm_non_authority.py
            ├── test_reconcile_service.py
            └── test_cli_adapter.py
```

既存ファイルを一度に移動しない。  
v0.2 では、既存 public behavior を維持しながら application service / StateStore / Evidence Store を導入する。

---

# 3. プログラム定義

## 3.1 `harness` CLI

既存 `./harness` は維持する。

CLI の責務は以下に限定する。

```text
- argv parse
- role env の読み取り
- application service の呼び出し
- JSON response の整形
- exit code の返却
```

CLI が直接持たない責務:

```text
- workflow authority の判断
- candidate freshness 判定
- review freshness 判定
- merge / push policy 判定
- scope hard block 判定
- comm / session の状態機械化
```

CLI は状態遷移そのものではない。  
CLI は application service への adapter である。

## 3.2 Application Service / Coordinator

Application Service / Coordinator は、権威ある workflow action の実行主体である。  
CLI は Coordinator を直接置き換えず、application service への adapter に留める。

責務:

```text
- StateStore projection の読み取り
- role / policy check
- candidate hash check
- machine evidence check
- review freshness check
- Git / workspace / verifier adapter 呼び出し
- Evidence Store への証跡保存
- StateStore event append
- authority-bearing artifact の互換出力
- diagnostic artifact の作成
- status / reconcile
```

禁止事項:

```text
- agent 発話を完了根拠として扱ってはならない
- comm / ACP message を直接状態遷移にしてはならない
- Git 状態のみから workflow completion を推定してはならない
- allowed_paths 外という理由だけで candidate を hard reject してはならない
- CLI から StateStore を直接編集してはならない
```
```

## 3.3 Artifact Store

既存 runtime directory を維持する。

保存先:

```text
<git-common-dir>/harness-runtime/state/tasks/<task_id>/
```
v0.1 では SQLite を必須にしない。  
既存の JSON artifact を authority-bearing / diagnostic に分類し、必要に応じて hash chain / manifest を追加する。

## 3.4 Evidence Store / Compatibility Artifact

Evidence Store は content-addressed store とする。

保存先:

```text
<git-common-dir>/harness-runtime/objects/sha256/<first2>/<sha256>
```

以下は authority-bearing artifact として Evidence Store に保存し、StateStore event から参照する。

```text
- contract.lock.json
- candidate.diff
- verify-result.json
- submission.json
- reviews/<reviewer_id>.json
- gate-result.json
- integration-result.json
- land-result.json
- push-result.json
- completion certificate
```

既存パスにも互換ファイルを出力してよい。  
ただし互換ファイル単独では正本ではない。
## 3.5 Diagnostic artifact

以下は workflow authority を持たない。

```text
- scope-map-forward.json
- scope-map-reverse.json
- affected-set.json
- context-audit output
- agent-tools.json
- agent-skills.json
- writer-session.json
- reviewer-session-*.json
- integrator-session.json
- comm/sessions/*.json
- comm/rebind/*.json
- status output
```

Diagnostic artifact は判断材料として使ってよい。  
ただし、単独では workflow phase を進めず、StateStore event の authority source にしてはならない。

## 3.6 Git Repository Adapter

Git CLI を薄くラップする。

責務:

```text
- repo root / git common dir 取得
- head sha 取得
- base ref 解決
- canonical diff 生成
- changed paths 取得
- worktree 作成 / 再利用
- ref 作成
- merge 実行
- target branch 観測
```

## 3.7 Workspace Manager

candidate patch を隔離された worktree に materialize する。

責務:

```text
- writer worktree の作成 / 再利用
- reviewer worktree の作成 / candidate 適用
- integrator worktree の作成
- candidate workspace sealing
- workspace hash 照合
```

## 3.8 Verifier Runner

typed verifier spec を実行する。

責務:

```text
- command verifier 実行
- timeout handling
- stdout/stderr/log capture
- result 作成
```

shell verifier は既存仕様を維持する。  
新規実装では shell=True を default にしない。

## 3.9 Reviewer Runner

v0.1 では既存 built-in reviewer を維持しつつ、名称と責務を整理する。

```text
reader-correctness:
  machine verification が pass
  machine evidence hash が一致
  candidate hash が一致
  contract semantic hash が一致
  すべて満たせば approve

reader-impact:
  candidate diff と impact evidence を確認する
  forbidden path violation があれば block
  outside expected scope は block ではなく review signal として扱う
```

互換性のため、既存 `reader-scope` 名は alias として残してよい。  
ただし意味は「candidate impact reader」であり、「allowed_paths 外を機械的に block する reviewer」ではない。

## 3.10 Comm Bus

v0.1 では既存 comm / session / rebind layer を使う。  
新規 ACP bus は実装しない。

責務:

```text
- writer session 間の rebind / handoff 補助
- agent_id / role / cwd / env の記録
- comm session packet の保存
```

comm message / session は状態遷移 authority を持たない。

## 3.10 External Write Broker

v0.1 では local broker を実装する。

責務:

```text
- local PR ref 作成
- local PR ref の head sha 観測
- local CI相当として verifier再実行
- local merge 実行
- merge commit sha 観測
```

local PR は以下の Git ref として表現する。

```text
refs/foundation/pr/<task_id>/<candidate_id>
```

これは実GitHub PRの代替である。  
将来の GitHub adapter は同じ port を実装する。

---

# 4. ドメインモデル

`src/workflow_core/contract_harness/domain/models.py` に定義する。

Pydantic v2 を使う場合は、すべて `extra="forbid"` にする。  
既存 JSON artifact との互換性を壊さない範囲で段階導入する。

## 4.1 共通

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

## 4.2 Workflow Phase

状態は増やしすぎない。  
session、scope-map、context-audit、comm、status は workflow phase にしない。

```python
class WorkflowPhase(StrEnum):
    DEFINED = "defined"
    PREPARED = "prepared"
    WRITER_ACTIVE = "writer_active"
    VERIFIED = "verified"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    GATED = "gated"
    PR_CREATED = "pr_created"
    PR_CHECKED = "pr_checked"
    INTEGRATED = "integrated"
    LANDED = "landed"
    PUSHED = "pushed"
    COMPLETE = "complete"
    REWORK_REQUIRED = "rework_required"
    BLOCKED = "blocked"
    INCONSISTENT = "inconsistent"
    UNKNOWN = "unknown"
```

`WRITER_ACTIVE` は既存互換の status 表示として残してよい。  
ただし authority-bearing transition ではなく、writer worktree artifact または StateStore の diagnostic event から得られる表示上の phase とする。

---

## 4.3 TaskContract 補足

既存 `TaskContract` の定義は v0.1 を維持する。  
ただし以下を追加・修正する。

```python
class TaskContract(StrictModel):
    schema_version: int = 1
    task_id: str
    goal: str | None = None
    scope: str | None = None
    base_sha: str
    scope_hints: ScopeHints
    source_refs: list[str] = Field(default_factory=list)
    verifiers: list[VerifierSpec]
    review_policy: ReviewPolicy = Field(default_factory=ReviewPolicy)
    external_write_policy: ExternalWritePolicy = Field(default_factory=ExternalWritePolicy)
    semantic_hash: str
```

互換性のため、既存 `scope_contract.allowed_paths` は読み込んでよい。  
ただし内部意味は `expected_paths` または `routing_paths` として扱う。  
`allowed_paths` 外の変更は、candidate reject の根拠にしない。

`semantic_hash` は既存仕様を維持し、実行時 base sha と semantic payload の扱いを分離する。  
`prepared_base_sha` は StateStore に記録する。  
contract artifact には互換性のため残してよいが、semantic hash の再現性判定では既存挙動を壊さない。

## 4.4 Candidate

```python
class Candidate(StrictModel):
    schema_version: int = 1
    candidate_id: str
    task_id: str
    base_sha: str
    patch_sha256: str
    changed_paths: list[str]
    submitted_by: str | None = None
    submitted_at: str
    status: Literal[
        "submitted",
        "verified",
        "reviewed",
        "gate_passed",
        "landed",
        "pushed",
        "rework_required",
    ] = "submitted"
```

`candidate_id` は以下で生成する。

```text
cand_<patch_sha256_first12>
```

既存 `candidate.diff` が正本であり、Candidate model はその metadata として扱う。

## 4.5 ImpactResult

Scope check は hard block ではなく impact / diagnostic として扱う。

```python
class ImpactFinding(StrictModel):
    path: str
    severity: Literal["info", "warning", "block"]
    reason: str

class ImpactResult(StrictModel):
    status: Literal["ok", "review_required", "blocked"]
    findings: list[ImpactFinding] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    expected_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)
```

判定方針:

```text
- forbidden_paths に一致する変更は block
- expected_paths が空でも block しない
- warning は verifier 実行を止めない
- warning は review topic / status summary に出す
```

## 4.6 VerifyResult

```python
class VerifierResult(StrictModel):
    id: str
    status: Literal["pass", "fail", "timeout", "error"]
    exit_code: int
    duration_ms: int
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    timed_out: bool = False

class VerifyResult(StrictModel):
    schema_version: int = 1
    task_id: str
    candidate_id: str | None = None
    candidate_patch_sha256: str
    base_sha: str
    impact_result: ImpactResult
    verifier_results: list[VerifierResult]
    status: Literal["pass", "fail"]
    machine_evidence_sha256: str
```

既存 `verify-result.json` との互換性のため、出力キーは当面既存形式を維持してよい。  
ただし `scope.violation_count` は forbidden violation のみを fail に使う。  
outside expected scope はadvisoryでAgentに思考を行わせるために存在する。

## 4.7 ReviewVerdict 補足

`ReviewVerdict` は v0.1 定義に `evidence_seen_sha256` を追加する。

```python
class ReviewVerdict(StrictModel):
    schema_version: int = 1
    task_id: str
    candidate_id: str | None = None
    reviewer_id: str
    verdict: Literal["approve", "block"]
    labels: list[str] = Field(default_factory=list)
    reason: str = ""
    evidence_seen: dict[str, Any]
    evidence_seen_sha256: str | None = None
    created_at: str
    written_by: Literal["harness"] = "harness"
```

Review verdict は fresh evidence に束縛される。  
ACP / comm message 本文は evidence_seen に含めない。

## 4.8 GateResult

```python
class ReviewSummary(StrictModel):
    quorum: int
    fresh_approves: int
    fresh_blocks: int
    fresh_reviewers: list[str]
    blocking_reviewers: list[str]
    review_pass: bool

class GateResult(StrictModel):
    schema_version: int = 1
    task_id: str
    candidate_id: str | None = None
    status: Literal["pass", "fail"]
    reason: str
    candidate_patch_sha256: str
    machine_evidence_sha256: str
    review_summary: ReviewSummary
```

## 4.9 Land / Push Observation 補足

`LandObservation` と `PushObservation` は v0.1 定義に `state_event_sha256` を追加する。

```python
class LandObservation(StrictModel):
    schema_version: int = 1
    task_id: str
    candidate_id: str | None = None
    status: Literal["landed", "rework_required", "blocked"]
    reason: str
    landed_commit: str | None = None
    target_base_sha: str | None = None
    candidate_patch_sha256: str
    machine_evidence_sha256: str
    state_event_sha256: str | None = None

class PushObservation(StrictModel):
    schema_version: int = 1
    task_id: str
    candidate_id: str | None = None
    status: Literal["pushed", "blocked", "failed"]
    reason: str
    remote_sha_before: str | None = None
    remote_sha_after: str | None = None
    landed_commit: str | None = None
    rescue_ref: str | None = None
    lock_ref: str | None = None
    state_event_sha256: str | None = None
``````

## 4.10 Comm Message

新規 ACP message model は必須実装しない。  
既存 comm packet を使う。

必要な最低制約:

```text
- comm packet は authoritative=false 相当として扱う
- comm packet から workflow phase を進めない
- comm packet の done / complete / LGTM / merged 等の語を authority にしない
- 稼働中のwriterの`agent_id`をエージェントが読めるようにする必要がある。
```

---

# 5. StateStore schema / Authority Manifest

v0.2 では SQLite StateStore を導入する。  
authority-manifest.json は互換・デバッグ用に残せるが、正本ではない。

## 5.1 SQLite schema

`sqlite_state_store.py` に初期化 DDL を実装する。

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    candidate_id TEXT,
    event_type TEXT NOT NULL,
    from_phase TEXT,
    to_phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    previous_event_sha256 TEXT,
    event_sha256 TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    current_phase TEXT NOT NULL,
    current_candidate_id TEXT,
    current_event_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    patch_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    sha256 TEXT PRIMARY KEY,
    task_id TEXT,
    artifact_type TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    storage_uri TEXT NOT NULL,
    compatibility_path TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS external_effects (
    effect_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    candidate_id TEXT,
    effect_type TEXT NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    external_ref TEXT,
    observed_hash TEXT,
    created_at TEXT NOT NULL
);
```

## 5.2 Event hash

`event_sha256` は以下の canonical JSON から計算する。

```json
{
  "task_id": "...",
  "candidate_id": "...",
  "event_type": "...",
  "from_phase": "...",
  "to_phase": "...",
  "payload_sha256": "...",
  "previous_event_sha256": "...",
  "actor": "...",
  "created_at": "..."
}
```

canonical JSON は以下を満たす。

```text
- sort_keys=True
- separators=(",", ":")
- UTF-8
```

## 5.3 Integrity check

`StateStore.verify_integrity()` を実装する。

検証内容:

```text
- events.id 順に previous_event_sha256 が直前 event と一致する
- payload_json の sha256 が payload_sha256 と一致する
- event_sha256 が再計算値と一致する
- tasks.current_event_sha256 が該当 task の最新 event と一致する
- tasks.current_phase が最新 event.to_phase と一致する
- artifact sha256 が Evidence Store object と一致する
```

失敗時は `IntegrityError` を投げる。

## 5.4 authority-manifest.json

保存先:

```text
<harness-runtime>/state/tasks/<task_id>/authority-manifest.json
```

authority-manifest.json は互換・デバッグ用に残せる。  
ただし v0.2 では StateStore event と Evidence Store object が正本である。

## 5.5 Compatibility integrity check

`reconcile_service.verify_task_integrity()` を実装する。

検証内容:

```text
- manifest が参照する authority artifact が存在する
- manifest 上の sha256 と現在ファイル hash が一致する
- candidate.diff hash と verify-result の candidate_diff_sha256 が一致する
- verify-result の machine_evidence_sha256 が再計算値と一致する
- submission の hash 群が現在 artifact と一致する
- review verdict の evidence_seen が現在期待値と一致する
- gate-result が参照する candidate / machine evidence が一致する
- land-result が landed の場合、landed_commit が存在する
- push-result が pushed の場合、remote_sha_after または synced target が landed_commit と対応する
- StateStore が参照する artifact sha256 が Evidence Store object と一致する
```

失敗時は status / reconcile で `INCONSISTENT` 相当を返し、StateStore に観測 event を追加する。  
v0.2 では不整合検出を優先し、過剰な自動修復は行わない。

---

# 6. Evidence / Artifact Store仕様

Evidence Store は必須とする。  
既存 runtime JSON path は compatibility artifact として扱う。

## 6.1 API

既存 `ArtifactStore` API は維持する。

```python
class ArtifactStore(Protocol):
    def write_json(self, task_id: str, name: str, data: dict[str, Any]) -> ArtifactRef: ...
    def read_json(self, task_id: str, name: str) -> dict[str, Any]: ...
    def write_text(self, task_id: str, name: str, data: str) -> ArtifactRef: ...
    def read_text(self, task_id: str, name: str) -> str: ...
    def hash_file(self, task_id: str, name: str) -> str: ...
    def exists(self, task_id: str, name: str) -> bool: ...
```

新規 `EvidenceStore` API を追加する。

```python
class EvidenceStore(Protocol):
    def put_bytes(self, data: bytes, media_type: str) -> ArtifactRef: ...
    def put_json(self, data: StrictModel | dict[str, Any], media_type: str = "application/json") -> ArtifactRef: ...
    def get_bytes(self, sha256: str) -> bytes: ...
    def get_json(self, sha256: str) -> dict[str, Any]: ...
    def exists(self, sha256: str) -> bool: ...
```

## 6.2 Atomic write

Authority-bearing artifact と Evidence object は atomic write にする。

```text
tmp file に書く
fsync 可能なら fsync
rename
```

Diagnostic artifact は既存の write_json helper を使ってよい。

---

# 7. Task定義ファイル

既存 `.harness/tasks/<task_id>/task.yaml` を維持する。  
新規 `.foundation/tasks` は作らない。

例:

```yaml
id: T-0001
scope: app
intent:
  goal: "Update src/app.txt and keep tests passing"
acceptance:
  mode: generated
```

scope から owners / verifiers / review settings を引く既存構造を維持する。  
owners に含まれる path 情報は `scope_hints.expected_paths` として扱う。

## 7.1 owners.yaml の扱い

既存 `owners.yaml` の `allowed_paths` は互換性のため読み込む。

ただし v0.1 以降の意味は以下とする。

```text
旧名:
  allowed_paths

新しい意味:
  expected_paths / routing_paths / scope_hints

用途:
  - scope-map-forward
  - likely tests
  - review topics
  - context boundary hints
  - affected-set 補助
  - status summary

禁止:
  - allowed_paths 外という理由だけで submit / verify / review を hard block すること
```

`forbidden_paths` は hard block として維持する。

---

## 8.1 Phase projection

状態は StateStore event から projection する。  
既存 artifact からの projection は migration / compatibility / reconcile 用に限定する。

```python
PHASE_PRECEDENCE = [
    "push-result.json",
    "land-result.json",
    "integration-result.json",
    "gate-result.json",
    "submission.json",
    "verify-result.json",
    "writer-worktree.json",
    "contract.lock.json",
    "task.yaml",
]
```

Compatibility phase projection は表示であり、権威そのものではない。  
各 action は StateStore event、Evidence object、必要な authority artifact を個別に検証する。

---

## 8.2 Authority action

v0.2 の authority action は以下に限定する。

```text
prepare
verify
submit
review write-verdict
review collect
gate
dispatch / integrate
pr create
pr checks
land
push
certify
reconcile
```

以下は authority action ではない。

```text
scope-map
affected
tools
context-audit
launch-writer
spawn
status
report
comm / ACP send
```

ただし `report` は durable evidence を作ることはできる。  
workflow phase を進める authority action ではない。

---

## 8.3 Guard conditions の方針

Guard は最小限にする。

Hard guard として維持するもの:

```text
- missing required StateStore event
- missing required authority artifact
- stale candidate hash
- machine evidence mismatch
- verifier failure
- forbidden path edit
- stale review evidence
- blocking review verdict
- gate not mergeable
- dirty destructive worktree reuse
- candidate apply failure
- local PR hash mismatch
- remote lock / CAS failure
- external write policy violation
```

Hard guard にしないもの:

```text
- allowed_paths 外の変更
- scope-map の不在
- affected-set の PARTIAL 分類
- comm / ACP message の有無
- writer session の有無
- context-audit warning
```


---

# 9. CLI仕様

`harness` は JSON を標準出力に返す。  
失敗時も JSON を返す。

成功:

```json
{
  "ok": true,
  "task_id": "T-0001",
  "phase": "verified",
  "artifact": "verify-result.json"
}
```

失敗:

```json
{
  "ok": false,
  "reason": "verify-result.json is required before submit",
  "phase": "prepared"
}
```

CLI exit code:

```text
0: success
1: expected workflow failure
2: usage error
3: integrity error
```


## 9.1 既存コマンド

既存コマンドは維持する。  
ただし local PR 用のコマンドを追加する。

```text
harness prepare <task_id>
harness explain <task_id>
harness verify <task_id>
harness submit <task_id> [--wait]
harness dispatch <task_id>
harness integrate <task_id>
harness gate <task_id>
harness pr create <task_id>
harness pr checks <task_id>
harness review <task_id> --run <reviewer_id>
harness review <task_id> --write-verdict <reviewer_id> approve|block
harness review <task_id> --collect
harness worktree <task_id> --writer|--reviewer <id>|--integrator
harness affected <task_id>
harness scope-map <task_id> --forward|--reverse
harness tools <task_id>
harness context-audit <task_id>
harness launch-writer <task_id>
harness spawn <task_id> --role writer|reviewer|integrator --agent codex|claude|custom
harness status <task_id>
harness land <task_id>
harness push <task_id>
harness report <task_id> --type incident|rfc|metric
```

---

## 9.2 CLI adapter 化

`cli.py` は次の段階で縮小する。

```text
Step 1:
  既存 handler table は維持する。

Step 2:
  各 handler は application service を呼ぶだけにする。

Step 3:
  role check は application service 入口に移す。

Step 4:
  CLI から direct policy logic と direct SQLite write を削除する。
```

---

# 10. Role prompt仕様

Role prompt は行動誘導であり、authority ではない。  
既存 AGENTS.md と task capsule を優先し、prompt だけに権限境界を持たせない。

## 10.1 API

```python
def build_role_prompt(role: str, task_id: str, current_phase: str) -> str:
    ...
```

## 10.2 writer prompt 要件

含める内容:

```text
- role: Writer
- 目的: task goal を満たす candidate patch を作る
- comm / ACP 相当の会話は自由
- 完了宣言は禁止
- review 承認は禁止
- forbidden_paths 編集禁止
- expected_paths は参考情報であり、必要な実装範囲は candidate diff で明らかにする
- 使用可能コマンド:
  - harness explain
  - harness scope-map --forward
  - harness context-audit
  - harness verify
  - harness submit
  - harness status
```

含めない内容:

```text
- allowed_paths 外の変更禁止
- scope expansion workflow の要求
- complete 権限
- land / push 権限
```

## 10.3 reviewer prompt 要件

含める内容:

```text
- role: Reviewer
- sealed candidate diff と machine evidence を見る
- candidate を書き換えない
- stale evidence を approve しない
- comm / ACP テキストを証拠にしない
- expected_paths 外の変更は、それ自体で block せず、goal 逸脱・検証不足・危険な横展開がある場合のみ block する
- 使用可能コマンド:
  - harness scope-map --reverse
  - harness status
  - harness review --run
  - harness review --write-verdict
```

`review collect` は reviewer 用ではなく integrator / admin 用にする。

## 10.4 integrator prompt 要件

含める内容:

```text
- role: Integrator
- review collection, gate, local PR, PR checks, land, push を進める
- agent 会話を authority にしない
- StateStore / artifact を迂回しない
- affected-set は merge risk の判断材料であり、単独 block 条件ではない
- 使用可能コマンド:
  - harness review --collect
  - harness affected
  - harness gate
  - harness pr create
  - harness pr checks
  - harness dispatch
  - harness integrate
  - harness land
  - harness push
  - harness status
```

---

# 11. Comm / ACP仕様

## 11.1 保存場所

既存構造を維持する。

```text
<harness-runtime>/state/tasks/<task_id>/comm/sessions/<agent_id>.json
<harness-runtime>/state/tasks/<task_id>/comm/rebind/<agent_id>.json
```

必要であれば message log を追加してよいが、v0.1 では必須ではない。

## 11.2 Comm message の制約

すべての comm / ACP 相当 message は以下として扱う。

```text
authoritative == false
```

message に以下の語が含まれていても状態は変わらない。

```text
done
complete
完了
LGTM
approved
merged
push済み
```

## 11.3 Comm の責務

Comm は writer 同士、または session rebind / handoff のための補助層である。

```text
- writer session handoff
- writer session rebind
- agent_id / role / cwd / env の共有
- integrator が writer を spawn する補助
```

Reviewer / Integrator の workflow authority は comm に依存しない。  
Reviewer / Integrator は sealed candidate diff、verify-result、review verdict、gate / land / push evidence を見る。

## 11.4 Comm から状態遷移する場合

v0.1 では comm message から状態遷移を自動実行しない。  
将来実装する場合も、comm handler は application service に request を渡すだけにする。

---

# 12. PR / Land / Push仕様

## 12.1 Candidate sealing

submit 時に candidate workspace を seal する。

```text
1. verify-result.json が pass であることを確認
2. candidate.diff の hash が verify-result と一致することを確認
3. machine evidence hash を再計算して一致確認
4. candidate workspace を sealed_for_review にする
5. submission.json を atomic write する
6. submission evidence を Evidence Store に保存する
7. StateStore に SUBMITTED 相当の event を append する
```

## 12.2 Gate

gate は以下を確認する。

```text
- candidate hash が一致する
- machine evidence hash が一致する
- required verifier が pass
- fresh review quorum を満たす
- blocking verdict がない
- completion check が pass
```

gate は `allowed_paths` 外の変更を block しない。  
ただし impact warning は gate-result に含めてよい。

GateResult は Evidence Store に保存し、StateStore event に束縛する。

## 12.3 Local PR

local PR は `refs/harness/pr/<task_id>/<candidate_id>` で表現する。

```text
1. candidate.diff を base_sha に適用した temp worktree を作る
2. commit を作る
3. commit を refs/harness/pr/<task_id>/<candidate_id> に設定する
4. pr_head_sha を StateStore external_effects に記録する
5. pr_head_sha と candidate.patch_sha256 の diff hash binding を確認する
6. pr observation を Evidence Store に保存する
7. PR_CREATED event を append する
```

commit message:

```text
harness pr <task_id> <candidate_id>
```

`refs/foundation/pr/**` は使用しない。

## 12.4 PR checks

```text
1. PR ref head に対して verifiers を再実行する
2. pass なら PR_CHECKED / REMOTE_CHECKS_PASSED 相当の event を append する
3. fail なら REWORK_REQUIRED 相当の event を append する
```

v0.2 の PR checks は local CI substitute であり、実 GitHub checks ではない。

## 12.5 Land

land は integrator worktree で行う。

```text
1. validate_submission
2. affected-set を作成
3. gate-result が mergeable であることを確認
4. local PR checks が pass していることを確認
5. local lock を取得
6. integrator worktree を作成
7. candidate.diff を適用
8. machine gate を再実行
9. commit を作成
10. land-result.json を互換出力する
11. land evidence を Evidence Store に保存する
12. StateStore に LANDED 相当の event を append する
```

`affected-set` の `REBASE` は rework の判断材料として使ってよい。  
`PARTIAL` は block しない。

## 12.6 Push

push は既存 policy を維持する。

```text
- land-result.status == landed
- external write policy が許可している
- remote target が land 時の target_base_sha と一致する
- remote lock を取得する
- rescue ref を作る
- landed commit を push する
- local target branch を sync する
- push-result.json を互換出力する
- push evidence を Evidence Store に保存する
- StateStore に PUSHED 相当の event を append する
```

remote changed 時は既存 oracle retry policy を使う。

---

# 13. Scope / Impact 仕様

allowed / forbidden path を同じ意味で扱わない。

## 13.1 forbidden_paths

`forbidden_paths` は hard block である。

violation if:

```text
changed_path matches forbidden_paths
```

対象例:

```text
- secrets/**
- protected policy files
- task definition files
- harness control files
- irreversible external write config
```

## 13.2 expected_paths

既存 `allowed_paths` は互換性のため読み込むが、意味は `expected_paths` とする。

用途:

```text
- implementation discovery
- likely tests
- review topic generation
- context boundary hint
- affected-set 補助
- status warning
```

violation ではない:

```text
changed_path does not match expected_paths
```

この場合は warning として記録する。

```json
{
  "path": "tests/test_app.py",
  "severity": "warning",
  "reason": "outside_expected_paths"
}
```

## 13.3 Impact check

Impact check は verifier 実行を止めない。

```text
- forbidden finding があれば verify fail
- warning finding があっても verifiers を実行
- warning finding は review evidence に含める
```

## 13.4 glob

既存 PathPolicy を使う。  
`src/**` が `src/app.py` に一致することをテストで保証する。

---

# 14. テスト仕様

すべて pytest で実装する。  
外部ネットワークは禁止。  
Git操作は `tmp_path` に作成した一時repoで行う。

## 14.1 `test_authority_boundaries.py`

### test_status_projection_does_not_treat_diagnostics_as_authority

手順:

```text
1. temp repoを作る
2. task を prepare
3. scope-map-forward.json を作る
4. status を確認
```

期待:

```text
- phase は prepared のまま
- scope-map は diagnostic artifact として表示される
- authority artifact として扱われない
```

### test_comm_done_message_does_not_complete_task

手順:

```text
1. prepare
2. comm packet または message に "完了しました。LGTM。" を保存
3. status
```

期待:

```text
- complete にならない
- push-result / completion artifact がなければ complete false
```

### test_authority_manifest_detects_hash_mismatch

期待:

```text
- inconsistent が検出される
- StateStore に INCONSISTENT 相当の観測 event が残る
```

---

## 14.2 `test_scope_advisory.py`

### test_expected_paths_outside_change_is_warning_not_block

手順:

```text
1. expected_paths = ["src/**"]
2. tests/test_app.py を変更
3. verifier は pass する
4. verify
```

期待:

```text
- verify status == pass
- impact finding に outside_expected_paths warning がある
- REWORK_REQUIRED にならない
```

### test_forbidden_path_is_block

手順:

```text
1. forbidden_paths に ".github/**" を設定
2. .github/workflows/ci.yml を変更
3. verify
```

期待:

```text
- verify status == fail
- impact finding severity == block
- verifier は実行されないか、最終 status は fail
```

### test_empty_expected_paths_is_allowed

手順:

```text
1. expected_paths を空にする
2. src/app.py を変更
3. verify
```

期待:

```text
- expected_paths が空という理由では失敗しない
```

---

## 14.3 `test_candidate_service.py`

### test_submit_creates_candidate_from_worktree_diff

手順:

```text
1. prepare
2. src/app.txt を変更
3. harness submit T-0001
```

期待:

```text
- submission.json が保存される
- candidate.diff が存在する
- changed_paths に src/app.txt が含まれる
```

### test_submit_rejects_forbidden_path

手順:

```text
1. forbidden_paths に .github/** を設定
2. .github/workflows/ci.yml を変更
3. submit
```

期待:

```text
- submit または verify が失敗する
- forbidden finding が記録される
```

### test_submit_does_not_reject_outside_expected_paths

手順:

```text
1. expected_paths = ["src/**"]
2. tests/test_app.py を変更
3. submit
```

期待:

```text
- allowed_paths 外という理由では submit 失敗しない
```

---

## 14.4 `test_verify_service.py`

### test_verify_passes_candidate

手順:

```text
1. verifier command は成功する
2. prepare
3. src/app.txt 変更
4. verify
```

期待:

```text
- verify-result.status == pass
- machine_evidence_sha256 が存在
```

### test_verify_fails_on_verifier_failure

手順:

```text
1. verifier command は exit 1
2. verify
```

期待:

```text
- verify-result.status == fail
```

### test_verify_records_impact_warning_without_blocking

手順:

```text
1. expected_paths 外の変更
2. verifier pass
3. verify
```

期待:

```text
- verify pass
- impact warning が保存される
```

---

## 14.5 `test_review_service.py`

### test_reader_correctness_approves_fresh_machine_evidence

手順:

```text
1. verify pass
2. review run reader-correctness
```

期待:

```text
- approve
- evidence_seen が candidate hash と machine evidence に束縛される
```

### test_reader_impact_does_not_block_warning_only_scope

手順:

```text
1. expected_paths 外の変更
2. forbidden violation はなし
3. verify pass
4. review run reader-impact
```

期待:

```text
- approve または review_required label
- block しない
```

### test_reader_impact_blocks_forbidden_path

手順:

```text
1. forbidden path 変更
2. verify fail または impact blocked
3. review run reader-impact
```

期待:

```text
- block
```

### test_stale_review_does_not_count

手順:

```text
1. candidate A verify
2. reviewer approve
3. candidate B verify
4. review collect
```

期待:

```text
- A の review は B に対して fresh ではない
```

---

## 14.6 `test_gate_service.py`

### test_gate_passes_after_fresh_review_approved

手順:

```text
1. verify pass
2. required reviewers approve
3. review collect
4. gate
```

期待:

```text
- gate-result.mergeable == true
```

### test_gate_blocks_stale_machine_evidence

手順:

```text
1. verify pass
2. candidate.diff を改ざん
3. gate
```

期待:

```text
- candidate_hash_mismatch
```

### test_gate_does_not_block_outside_expected_paths_warning

手順:

```text
1. expected_paths 外変更
2. verifier pass
3. reviews approve
4. gate
```

期待:

```text
- gate pass
- warning は gate-result に残る
```

---

## 14.7 `test_land_push_service.py`

### test_land_uses_integrator_worktree

手順:

```text
1. submit -> verify -> review -> gate
2. land
```

期待:

```text
- integrator worktree が使われる
- landed_commit が保存される
```

### test_land_blocks_gate_not_mergeable

期待:

```text
- gate-result missing または mergeable false なら land blocked
```

### test_push_requires_landed_commit

期待:

```text
- land-result.status != landed なら push blocked
```

### test_remote_changed_uses_policy

期待:

```text
- remote changed 時に configured retry / oracle policy が使われる
```

### test_local_pr_ref_binds_to_candidate_hash

期待:

```text
- refs/harness/pr/<task_id>/<candidate_id> が作られる
- PR ref と base_sha の diff hash が candidate.patch_sha256 と一致する
- refs/foundation/pr/** は作られない
```

---

## 14.8 `test_comm_non_authority.py`

### test_comm_session_does_not_change_phase

手順:

```text
1. prepare
2. spawn --comm
3. status
```

期待:

```text
- comm session は存在
- phase は session だけでは complete / verified / submitted にならない
```

### test_comm_rebind_does_not_authorize_review

期待:

```text
- rebind packet があっても review verdict がなければ review pass しない
```

---

## 14.9 `test_reconcile_service.py`

### test_reconcile_detects_missing_candidate_diff

手順:

```text
1. verify-result.json まで作る
2. candidate.diff を削除
3. reconcile
```

期待:

```text
- inconsistent
- reason includes missing_candidate_diff
```

### test_reconcile_detects_stale_submission

期待:

```text
- submission hash と candidate hash 不一致を検出
```

### test_reconcile_does_not_treat_scope_map_as_required

期待:

```text
- scope-map がなくても authority integrity は fail しない
```

---

## 14.10 `test_cli_adapter.py`

### test_cli_returns_json_on_success

期待:

```text
- stdout is valid JSON
- ok == true
```

### test_cli_returns_json_on_failure

期待:

```text
- stdout is valid JSON
- ok == false
- exit code == 1
```

### test_cli_delegates_to_application_service

期待:

```text
- CLI handler が policy 判定を直接持たない
- service の結果を JSON 化するだけ
```

---

# 15. Makefile追加

既存 Makefile に以下を追加する。

```make
check-harness-architecture:
	$(UV) run pytest -q tests/workflow_core/contract_harness

check-harness-state:
	$(UV) run pytest -q tests/workflow_core/contract_harness/test_state_store.py
```

既存 `check-required` へ混ぜるかどうかは v0.2 では任意。  
まずは新ターゲットで独立させる。

---

# 16. 実装順序

Codex は以下の順番で実装すること。

## Step 1: domain model / authority classification

実装:

```text
src/workflow_core/contract_harness/domain/models.py
src/workflow_core/contract_harness/domain/authority.py
src/workflow_core/contract_harness/domain/errors.py
src/workflow_core/contract_harness/ports/state_store.py
src/workflow_core/contract_harness/adapters/sqlite_state_store.py
```

対象:

```text
- authority-bearing artifact の分類
- diagnostic artifact の分類
- expected_paths / forbidden_paths の意味分離
- StateStore event / artifact ref の model 定義
```

## Step 2: StateStore / Evidence Store

実装:

```text
src/workflow_core/contract_harness/ports/evidence_store.py
src/workflow_core/contract_harness/adapters/filesystem_evidence_store.py
src/workflow_core/contract_harness/adapters/sqlite_state_store.py
```

対象:

```text
- event append
- event hash chain
- artifact ref 記録
- content-addressed evidence 保存
- compatibility artifact path 記録
```

## Step 3: application service skeleton

実装:

```text
src/workflow_core/contract_harness/application/services.py
src/workflow_core/contract_harness/application/status_service.py
src/workflow_core/contract_harness/application/reconcile_service.py
```

対象:

```text
- CLI から呼べる service interface
- 既存関数への委譲
- status / reconcile の責務整理
- StateStore projection の読み取り
```

## Step 4: scope advisory refactor

実装:

```text
src/workflow_core/contract_harness/application/verify_service.py
src/workflow_core/contract_harness/snapshot.py
src/workflow_core/contract_harness/scope_map.py
```

変更:

```text
- allowed_paths 外を hard violation にしない
- forbidden_paths のみ hard violation
- outside expected paths を warning として保存
- scope-map は advisory であることを維持
```

テスト:

```text
test_scope_advisory.py
```

## Step 5: candidate / verify service

実装:

```text
application/candidate_service.py
application/verify_service.py
```

変更:

```text
- candidate hash check を service に集約
- verify-result 作成を service に集約
- verify-result を Evidence Store に保存し StateStore event に束縛
- CLI は service 呼び出しに縮小
```

テスト:

```text
test_candidate_service.py
test_verify_service.py
```

## Step 6: review service

実装:

```text
application/review_service.py
```

変更:

```text
- reader-scope を reader-impact 相当に整理
- forbidden path は block
- outside expected paths warning は block しない
- freshness check を service に集約
- evidence_seen_sha256 を StateStore / Evidence Store hash に束縛
```

テスト:

```text
test_review_service.py
```

## Step 7: gate service

実装:

```text
application/gate_service.py
```

変更:

```text
- candidate hash / machine evidence / review freshness を service に集約
- impact warning は gate result に残す
- GateResult を Evidence Store に保存し StateStore event に束縛
```

テスト:

```text
test_gate_service.py
```

## Step 8: local PR / land / push service

実装:

```text
application/pr_service.py
application/land_service.py
application/push_service.py
```

変更:

```text
- refs/harness/pr/<task_id>/<candidate_id> を local PR として扱う
- PR ref と candidate hash を binding する
- existing land / push behavior を維持
- policy 判定を service に集約
- affected-set は merge risk evidence として扱う
```

テスト:

```text
test_land_push_service.py
```

## Step 9: comm non-authority tests

実装:

```text
adapters/existing_comm_bus.py
application/status_service.py
```

変更:

```text
- comm session / rebind は diagnostic
- status に表示しても phase を進めない
```

テスト:

```text
test_comm_non_authority.py
```

## Step 10: CLI adapter cleanup

実装:

```text
cli.py
```

変更:

```text
- handler は application service を呼ぶだけにする
- role check / policy check は service 側へ移す
- JSON response は維持
- CLI から direct policy logic と direct SQLite write を削除する
```

テスト:

```text
test_cli_adapter.py
```

---

# 17. 完了条件

実装完了条件は以下。

```text
- ./harness の既存コマンドが引き続き動く
- make check-harness-architecture が pass
- make check-harness-state が pass
- 既存 make test が壊れない
- すべての CLI 成功/失敗が JSON を返す
- StateStore integrity check が pass
- authority-bearing artifact が StateStore event と Evidence object に束縛される
- allowed_paths 外の変更だけでは submit / verify / gate が block されない
- forbidden_paths の変更は block される
- scope-map / affected-set は advisory / diagnostic として扱われる
- comm / ACP 相当 message では状態が変わらない
- candidate -> verify -> review -> gate -> land -> push の happy path が通る
- candidate -> verify -> review -> gate -> local PR -> PR checks -> land -> push の happy path が通る
- complete / pushed は push-result または landed/pushed hash と StateStore event がない限り成立しない
- CLI に workflow policy が集中していない
```

---

# 18. 設計上の禁止事項

Codex は以下を実装してはならない。

```text
- allowed_paths 外の変更を機械的に block する
- task scope expansion workflow を新設する
- ACP / comm message の本文から完了状態を推定する
- role prompt を権限チェックとして扱う
- CLI に policy 判定を追加する
- CLI から StateStore を直接編集する
- scope-map を authority-bearing artifact にする
- affected-set だけで rework_required にする
- writer session の存在だけで workflow phase を進める
- review collect を reviewer の通常責務にする
- verifier を default shell=True で実行する
- Git状態だけで workflow state を決める
- 既存 harness 実装を破壊的に変更する
- 新規 foundation CLI を既存 harness と並行して重複実装する
- refs/foundation/pr/** を新規に作る
- StateStore なしで authority-bearing JSON だけを正本として扱う
```

---

# 19. 最小実装の期待フロー

Codex が実装後、以下のコマンド列が一時repoで成立すること。

```sh
./harness prepare T-0001
./harness launch-writer T-0001
./harness scope-map T-0001 --forward
./harness verify T-0001
./harness submit T-0001
./harness review T-0001 --run reader-impact
./harness review T-0001 --run reader-correctness
./harness review T-0001 --collect
./harness gate T-0001
./harness pr create T-0001
./harness pr checks T-0001
./harness land T-0001
./harness push T-0001
./harness status T-0001
```

最終 `status` は以下を返す。

```json
{
  "ok": true,
  "task_id": "T-0001",
  "phase": "pushed",
  "state_store": {
    "integrity": "pass",
    "current_event_sha256": "..."
  },
  "authority": {
    "complete": true,
    "source": "StateStore COMPLETE event + push-result.json status=pushed"
  },
  "refs": {
    "local_pr": "refs/harness/pr/T-0001/cand_..."
  }
}
```

---

# 20. 仕様の中核文

この実装の中核原則は次の一文である。

> エージェントの実装範囲を事前 allowed_paths で閉じ込めず、既存の worktree 分離・candidate diff・machine evidence・fresh review・local PR・land / push policy を維持しながら、scope-map / affected-set / comm を補助層に落とし、権威ある進行だけを application service、SQLite StateStore、Evidence Store、content hash で管理する。

この原則に反する実装は不採用とする。