以下を **実装仕様書 v0.1** として提案します。
結論は、**新しい architecture 専用 artifact 群を作らず、既存 harness の `verify-result.json` と `gate/oracle` の trust boundary を拡張する**実装です。

---

# 実装仕様書: Comment-triggered Review + Minimal Architecture Gate

## 0. 設計結論

この実装では、次を固定します。

```text
新規 JSON artifact:
  作らない

Agent が読むもの:
  原則増やさない

architecture gate の唯一の authority:
  verify-result.json

architecture_significance:
  task.yaml / writer 自己申告を読まない
  verify trust boundary 内で diff から機械導出する

hard-block predicate:
  significance に関係なく全 diff で無条件実行する

architecture advisory:
  散文ではなく、既存 oracle / verifier / mutation adequacy 要件へ写像する

scope-map-reverse:
  advisory only
  gate 値は置かない

architecture drift / DSM / EWMA:
  default path には入れない
  measurement profile / offline monitoring に隔離する
```

この repository は、active behavior を `AGENTS.md` と短い active docs に置き、詳細 reference は必要なものだけ開く方針です。また、contract harness は writer / reviewer / integrator の小さい実行経路を持ち、runtime evidence は `harness-runtime/state/tasks/<task_id>/` に置かれる構造です。([GitHub][1])

---

# 1. 既存アーキテクチャへの適合

## 1.1 既存の信頼境界

現在の repository では、agent は `AGENTS.md`、現在の request / task packet / explicit scope、named `source_refs`、3つの active docs を読む構成です。repo 全体、全 refs、全 skills、広い logs、archives、unrelated history を読むことはデフォルトで禁止されています。([GitHub][2])

`docs/01-agent-operating-contract.md` でも、goal、Done criteria、source refs、allowed write targets、denied context、verification command を最初に確定し、context expansion は必要時だけ行う方針です。([GitHub][3])

`docs/02-output-verification-contract.md` は、完了主張には実際の artifact / behavior、最小の relevant verification、失敗・skip の明示が必要だと定義しています。([GitHub][4])

`docs/03-repo-boundary-and-storage-contract.md` は、runtime state、credentials、logs、caches、secret-bearing files を repo truth ではないものとして扱い、skills は compact routing helper であり active contracts や storage rules を上書きできないとしています。([GitHub][5])

このため、architecture gate も **Agent に architecture 理論を解釈させる設計ではなく、verify/gate 側の機械 predicate として実装する**のが適切です。

---

## 1.2 既存 harness の利用箇所

既存 harness は、writer が `verify` で `candidate.diff` と machine evidence を作り、reviewer が fresh evidence と candidate diff を読み、integrator が review collection、integration checks、land、push を行う設計です。README でも、reviewer freshness は diff、verifier output、quality evidence、scope map、metrics、mutation output、reviewer-consumed artifacts の hash に基づくと説明されています。([GitHub][1])

現在の `verify.py` は、`candidate.diff` を作成し、`scope-map-reverse.json` を書き、scope violation、semantic reproducibility、quality artifacts、verifier results を集めて `verify-result.json` を書く構造です。([GitHub][6])

現在の `gate.py` は、`verify-result.json`、`candidate.diff` hash、contract semantic reproducibility、machine artifact hashes を検査してから completion check / review collection を行います。([GitHub][7])

したがって、architecture gate は新しい lane にせず、`verify.py` と `gate.py` に薄く差し込むべきです。

---

# 2. 全体システムアーキテクチャ

```text
GitHub commit comment
  "/review" | "/review arch" | "/review full"
        │
        ▼
Review Comment Adapter
  - command parse
  - auth check
  - idempotency lock
  - commit status pending
        │
        ▼
Existing Harness Task Flow
  ./harness prepare <task_id>
  ./harness dispatch <task_id>
        │
        ▼
Writer Boundary
  ./harness verify <task_id>
        │
        ├─ candidate.diff
        ├─ scope-map-reverse.json     advisory only
        ├─ quality-result.json        existing
        ├─ tool-candidates.json       existing
        ├─ verifiers                  existing
        └─ architecture_gate          new object inside verify-result.json
        │
        ▼
Reviewer Boundary
  - reads existing evidence
  - may use conditional architecture-check skill
  - cannot override architecture_gate
        │
        ▼
Integrator / Gate / Oracle Boundary
  - recompute architecture predicates
  - compare against verify-result
  - check oracle_requirements
  - collect fresh reviews
  - update commit status
```

重要なのは、**architecture gate は `scope-map-reverse` に置かない**ことです。既存の `scope_map.py` は `hard_constraint: False` を明示し、reverse map も “review evidence, not a complete dependency graph” として扱っています。([GitHub][8])

---

# 3. コンポーネント仕様

## 3.1 Review Comment Adapter

### 目的

GitHub commit comment によって既存 harness flow を起動する adapter です。
新しい `ReviewRun.json` は作りません。

GitHub には commit comment activity 用の `commit_comment` webhook event が存在します。([GitHub Docs][9])
commit status は外部サービスが commit に `error`、`failure`、`pending`、`success` を付けるための REST API として提供されています。([GitHub Docs][10])

### 入力

```text
/review
/review arch
/review full
```

### 正規化

```python
ReviewMode = Literal["normal", "arch", "full"]
```

```text
/review       -> normal
/review arch  -> arch
/review full  -> full
```

### idempotency

二重投稿、コメント編集、webhook 再送による二重起動は、Git ref lock で潰します。

```text
refs/harness/locks/<sha>-<mode>
```

GitHub の Git references API は GitHub 上の Git database refs を読み書きする API です。([GitHub Docs][11])

### create-only lock

```text
lock_ref = refs/harness/locks/<sha>-<mode>

create lock_ref -> sha
if already exists:
  no-op
else:
  run harness
```

GitHub API を使う場合は `POST /git/refs` の create operation を使います。
local bare repo 内で処理する場合は次でよいです。

```bash
git update-ref "refs/harness/locks/${sha}-${mode}" "$sha" ""
```

空の old SHA を指定することで、既存 ref があれば失敗させます。

### 出力 status

```text
pending:
  lock 作成成功、harness 実行開始

success:
  gate pass / integrated

failure:
  verify fail / architecture block / review block / oracle requirement unmet

error:
  adapter infrastructure error
```

---

## 3.2 Architecture Gate Evaluator

### 目的

architecture に関する最小 policy predicate を `verify-result.json` に埋め込みます。

この evaluator は Agent-facing tool ではありません。
`verify` と `gate/oracle` の trust boundary 内で呼ばれる純粋関数です。

```python
def evaluate_architecture_gate(
    root: Path,
    base_sha: str,
    diff_text: str,
    changed_paths: list[str],
) -> ArchitectureGate:
    ...
```

### 出力先

出力先は `verify-result.json` のみです。

```json
{
  "architecture_gate": {
    "status": "pass",
    "derived_significance": "none",
    "reason_codes": [],
    "advisory_codes": [],
    "oracle_requirements": [],
    "requires_human_review": false,
    "predicate_version": "architecture-gate/v1",
    "check_kinds": {}
  }
}
```

`status` は必ず enum です。

```text
pass | advisory | block
```

散文 summary を authority として扱ってはいけません。
人間向け note が必要なら、`notes` などの非 authority field に分離します。

---

## 3.3 Hard-block Predicate Runner

### 目的

significance に関係なく、全 diff に対して無条件に実行する predicate 群です。

### hard-block 対象

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

### 決定可能性

```text
比較的決定的:
  ACTIVE_DOC_EXPANSION
  NEW_STORAGE_ROOT
  TRACKED_RUNTIME_STATE
  BROAD_REPO_SCAN_DEFAULT_TRUE
  UNINDEXED_SKILL
  SKILL_COMPACT_LIMIT_EXCEEDED

保守的 heuristic:
  POSSIBLE_EXTERNAL_WRITE_PATH
```

external write path 検出は完全ではありません。
network / fs-write / subprocess / publish / push / upload / sync 系 import または call pattern の新規導入を保守的に block し、明示 allowlist で解除する設計にします。

---

## 3.4 Significance Deriver

### 目的

`architecture_significance` を機械導出します。
`task.yaml` / `work-contract.yaml` / writer 自己申告値は読みません。

既存 template には `design_gate.architecture_significance` が存在しますが、この値を gate 判定に使う設計は廃止します。([GitHub][12])

### 出力

```text
none | local | significant | unknown
```

### 用途

```text
使ってよい:
  semantic skill routing の hint
  reviewer packet の表示情報
  measurement profile の優先度

使ってはいけない:
  hard-block predicate の実行条件
  gate pass/fail の根拠
```

### 導出例

```python
def derive_significance(changed_paths: list[str], diff_text: str) -> str:
    if predicate_inconclusive:
        return "unknown"

    if touches_active_contracts(changed_paths):
        return "significant"

    if touches_gate_or_trust_boundary(changed_paths):
        return "significant"

    if touches_harness_runtime_behavior(changed_paths):
        return "local"

    if touches_skill_routing_or_context(changed_paths):
        return "local"

    return "none"
```

---

# 4. `verify-result.json` schema 追加仕様

## 4.1 pass

```json
{
  "architecture_gate": {
    "status": "pass",
    "derived_significance": "none",
    "reason_codes": [],
    "advisory_codes": [],
    "oracle_requirements": [],
    "requires_human_review": false,
    "predicate_version": "architecture-gate/v1",
    "check_kinds": {}
  }
}
```

## 4.2 advisory

```json
{
  "architecture_gate": {
    "status": "advisory",
    "derived_significance": "local",
    "reason_codes": [],
    "advisory_codes": [
      "ROUTING_OR_CONTEXT_BOUNDARY_CHANGED"
    ],
    "oracle_requirements": [
      "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
      "MUTATION_ADEQUACY_COVERS_CHANGED_CODE"
    ],
    "requires_human_review": false,
    "predicate_version": "architecture-gate/v1",
    "check_kinds": {}
  }
}
```

## 4.3 block

```json
{
  "architecture_gate": {
    "status": "block",
    "derived_significance": "none",
    "reason_codes": [
      "UNINDEXED_SKILL"
    ],
    "advisory_codes": [],
    "oracle_requirements": [],
    "requires_human_review": false,
    "predicate_version": "architecture-gate/v1",
    "check_kinds": {
      "UNINDEXED_SKILL": "deterministic"
    }
  }
}
```

## 4.4 判定不能

```json
{
  "architecture_gate": {
    "status": "block",
    "derived_significance": "unknown",
    "reason_codes": [
      "ARCH_PREDICATE_INCONCLUSIVE"
    ],
    "advisory_codes": [],
    "oracle_requirements": [],
    "requires_human_review": true,
    "predicate_version": "architecture-gate/v1",
    "check_kinds": {
      "ARCH_PREDICATE_INCONCLUSIVE": "fail_closed"
    }
  }
}
```

判定不能時に `advisory-pass` に倒すことは禁止です。

---

# 5. Program 構成

## 5.1 追加ファイル

```text
src/workflow_core/contract_harness/
  review_comment_adapter.py
  architecture_gate.py
  architecture_predicates.py
  oracle_requirements.py

.agents/skills/
  architecture-check/
    SKILL.md
```

## 5.2 変更ファイル

```text
src/workflow_core/contract_harness/
  verify.py
  gate.py
  evidence.py
  verifier.py
  review.py
  agent_tools.py
  context_audit.py

scripts/
  check-skill-routes.py
  check-context-scope.py

tests/
  test_architecture_gate.py
  test_architecture_gate_verify_integration.py
  test_review_comment_adapter.py
  test_architecture_skill_routing.py
```

`agent_tools.py` は現在、writer / reviewer / integrator ごとに tool と skill を分けており、`scope-map-reverse` は advisory only、`oracle` は submitted candidate を target head に再適用して machine validation する tool として定義されています。([GitHub][13])

---

# 6. `architecture_gate.py`

## 6.1 Public API

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ArchitectureGateStatus = Literal["pass", "advisory", "block"]
ArchitectureSignificance = Literal["none", "local", "significant", "unknown"]

@dataclass(frozen=True)
class ArchitectureGate:
    status: ArchitectureGateStatus
    derived_significance: ArchitectureSignificance
    reason_codes: tuple[str, ...]
    advisory_codes: tuple[str, ...]
    oracle_requirements: tuple[str, ...]
    requires_human_review: bool
    predicate_version: str
    check_kinds: dict[str, str]

def evaluate_architecture_gate(
    root: Path,
    *,
    base_sha: str,
    diff_text: str,
    changed_paths: list[str],
) -> ArchitectureGate:
    ...
```

## 6.2 Evaluation order

```text
1. diff / changed_paths parse
2. hard-block predicates
3. fail-closed conversion
4. significance derivation
5. advisory code derivation
6. oracle requirement mapping
7. status finalization
```

## 6.3 Status rule

```python
if reason_codes:
    status = "block"
elif advisory_codes:
    status = "advisory"
else:
    status = "pass"
```

---

# 7. `architecture_predicates.py`

## 7.1 ACTIVE_DOC_EXPANSION

### 仕様

active docs は以下に固定します。

```text
AGENTS.md
docs/01-agent-operating-contract.md
docs/02-output-verification-contract.md
docs/03-repo-boundary-and-storage-contract.md
```

`docs/04-*`、`docs/system-design.md`、`docs/architecture-principles.md`、`docs/adr/`、`docs/design/` の追加は block します。

既存 test でも、`system-design` skill は compact かつ conditional であること、active docs を増やさないことが検査されています。([GitHub][14])

### 判定

```python
def active_doc_expansion(changed_paths, diff_text) -> PredicateResult:
    if added_path_matches_forbidden_active_doc(changed_paths):
        return block("ACTIVE_DOC_EXPANSION")
    if agents_md_adds_new_always_read_doc(diff_text):
        return block("ACTIVE_DOC_EXPANSION")
    return pass_()
```

---

## 7.2 NEW_STORAGE_ROOT

### 仕様

新しい runtime queue、lock ledger、dashboard、unowned project storage を tracked repo に導入する変更を block します。

`docs/03` は、runtime state、caches、logs、credentials などを repo truth ではないものとして扱い、runtime queues / lock ledgers / dashboards / unowned project storage を導入しない方針です。([GitHub][5])

### 判定

```python
FORBIDDEN_STORAGE_ROOTS = {
    "harness-runtime/",
    ".harness/state/",
    ".serena/",
    ".codex/",
    "logs/",
    "cache/",
    ".cache/",
}
```

---

## 7.3 TRACKED_RUNTIME_STATE

### 仕様

以下を tracked diff に含めたら block します。

```text
harness-runtime/**
*.log
*.sqlite
*.db
*.session
*.cookie
*.token
*.secret
.env
```

### 判定

```python
if any(path_matches_runtime_state(path) for path in changed_paths):
    block("TRACKED_RUNTIME_STATE")
```

---

## 7.4 BROAD_REPO_SCAN_DEFAULT_TRUE

### 仕様

`broad_repo_scan_allowed: true` を default にする変更を block します。

既存の context scope test は、`denied_context` に `broad_repo_scan`、`secrets`、`runtime_state` が必要であり、broad source ref には expansion reason が必要だと検査しています。([GitHub][15])

### 判定

```python
if diff_adds("broad_repo_scan_allowed: true") and not explicit_test_fixture_override:
    block("BROAD_REPO_SCAN_DEFAULT_TRUE")
```

---

## 7.5 UNINDEXED_SKILL

### 仕様

`.agents/skills/<name>/SKILL.md` を追加した場合、`.agents/skills/SKILL_INDEX.md` に index entry が必要です。

既存 test は、unindexed operational skill を reject することを確認しています。([GitHub][16])

### 判定

```python
def unindexed_skill(root, changed_paths):
    added_skills = detect_added_skill_dirs(changed_paths)
    index = read_skill_index(root)
    missing = [skill for skill in added_skills if skill not in index]
    if missing:
        block("UNINDEXED_SKILL")
```

---

## 7.6 SKILL_COMPACT_LIMIT_EXCEEDED

### 仕様

skill は compact routing helper であり、active contract を上書きできません。([GitHub][5])

既存 `system-design` skill test では 80 lines 以下が要求されています。([GitHub][14])
この実装でも、operational skill の hard limit は 80 lines に固定します。

### 判定

```python
if skill_line_count(skill_path) > 80:
    block("SKILL_COMPACT_LIMIT_EXCEEDED")
```

---

## 7.7 POSSIBLE_EXTERNAL_WRITE_PATH

### 仕様

これは完全な保証ではありません。
保守的 heuristic として、外部書き込みの新規導入らしき diff を block し、明示 allowlist がある場合のみ通します。

### 検出対象例

```text
requests.post
requests.put
httpx.post
urllib.request.urlopen
subprocess.run(["git", "push"])
subprocess.run(... "curl" ...)
boto3.client(...).put_object
open(..., "w")  # repo 外 path に対するもの
Path(...).write_text  # repo 外 path に対するもの
shutil.copy / move  # repo 外 path に対するもの
```

### check kind

```json
{
  "POSSIBLE_EXTERNAL_WRITE_PATH": "conservative_heuristic"
}
```

---

# 8. `verify.py` 変更仕様

現在の `verify_task` は `candidate.diff`、`scope-map-reverse`、quality artifacts、verifiers、`verify-result.json` を作ります。([GitHub][6])

ここに `architecture_gate` を追加します。

## 8.1 変更後 flow

```python
def verify_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    lock = ensure_prepared(root, task_id)
    plan = load_verifier_plan(root, task_id)

    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)

    out_dir = task_dir(root, task_id)
    (out_dir / "candidate.diff").write_text(diff_text, encoding="utf-8")

    write_reverse_scope_map(root, task_id, diff_text=diff_text)

    violations = scope_violations(paths, lock)
    semantic_ok = _semantic_ok(root, task_id, lock)

    architecture_gate = evaluate_architecture_gate(
        root,
        base_sha=str(lock["prepared_base_sha"]),
        diff_text=diff_text,
        changed_paths=paths,
    )

    quality, tool_candidates = write_quality_artifacts(root, task_id, paths, plan)

    if not violations and semantic_ok and architecture_gate.status != "block":
        verifiers = run_verifiers(root, plan)
    else:
        verifiers = []

    verifiers.extend([
        quality_gate_verifier(quality),
        tool_candidate_gate_verifier(tool_candidates),
    ])

    status = "pass" if _passed(
        violations,
        semantic_ok,
        architecture_gate,
        verifiers,
    ) else "fail"

    result = _result(
        root,
        task_id,
        lock,
        diff_text,
        violations,
        semantic_ok,
        architecture_gate,
        verifiers,
        status,
    )

    write_json(out_dir / "verify-result.json", result)
    return result, 0 if status == "pass" else 1
```

## 8.2 `_passed`

```python
def _passed(
    violations: list[dict[str, str]],
    semantic_ok: bool,
    architecture_gate: ArchitectureGate,
    verifiers: list[dict[str, Any]],
) -> bool:
    return (
        not violations
        and semantic_ok
        and architecture_gate.status != "block"
        and all_passed(verifiers)
    )
```

---

# 9. machine evidence hash 変更仕様

現在の `machine_evidence_hash` は、task id、candidate diff hash、contract semantic hash、scope violation count、verifier statuses を hash 化しています。([GitHub][17])

ここに `architecture_gate` の canonical payload を追加します。

## 9.1 canonical payload

```json
{
  "status": "advisory",
  "derived_significance": "local",
  "reason_codes": [],
  "advisory_codes": ["ROUTING_OR_CONTEXT_BOUNDARY_CHANGED"],
  "oracle_requirements": [
    "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
    "MUTATION_ADEQUACY_COVERS_CHANGED_CODE"
  ],
  "requires_human_review": false,
  "predicate_version": "architecture-gate/v1"
}
```

`check_kinds` は説明用なので hash に入れてもよいですが、最小化するなら authority field だけを hash に入れます。

## 9.2 `recompute_machine_evidence`

```python
def recompute_machine_evidence(verify_result: dict[str, Any]) -> str:
    scope = mapping(verify_result.get("scope"))
    return machine_evidence_hash(
        task_id=str(verify_result["task_id"]),
        candidate_diff_sha256=str(verify_result["candidate_diff_sha256"]),
        contract_semantic_sha256=str(verify_result["contract_semantic_sha256"]),
        scope_violation_count=int(scope.get("violation_count", 0)),
        architecture_gate=canonical_architecture_gate(
            verify_result.get("architecture_gate")
        ),
        verifiers=[...],
    )
```

これにより、architecture gate が変わった場合、review freshness が自然に stale になります。既存の `review.py` は reviewer verdict に `candidate_diff_sha256` と `machine_evidence_sha256` を保存し、expected evidence と比較して fresh/stale を判定しています。([GitHub][18])

---

# 10. `gate.py` / oracle 変更仕様

## 10.1 gate preflight

現在の `gate.py` は、candidate hash、contract semantic reproducibility、`verify-result.status`、machine artifact hash、current diff hash を検査します。([GitHub][7])

ここに architecture predicate の再実行を追加します。

```python
def _preflight_reason(...):
    if candidate_sha != verify_result.get("candidate_diff_sha256"):
        return "candidate_hash_mismatch"

    if not semantic_reproducible(root, task_id, lock):
        return "contract_semantic_mismatch"

    if verify_result.get("status") != "pass":
        return "machine_gate_failed"

    if not _architecture_gate_matches_current_diff(root, task_id, verify_result, lock):
        return "architecture_gate_mismatch"

    if not _oracle_requirements_satisfied(root, task_id, verify_result):
        return "oracle_requirement_unmet"

    if not _matches_machine_artifact_hashes(root, task_id, verify_result):
        return "evidence_hash_mismatch"

    if _current_diff_hash(root, lock) != verify_result.get("candidate_diff_sha256"):
        return "candidate_hash_mismatch"

    return "ok"
```

## 10.2 architecture gate mismatch

```python
def _architecture_gate_matches_current_diff(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
    lock: dict[str, Any],
) -> bool:
    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)

    recomputed = evaluate_architecture_gate(
        root,
        base_sha=str(lock["prepared_base_sha"]),
        diff_text=diff_text,
        changed_paths=paths,
    )

    return canonical_architecture_gate(recomputed) == canonical_architecture_gate(
        verify_result.get("architecture_gate")
    )
```

## 10.3 writer self-report 無効化

writer が `architecture pass` と書いても、gate は信用しません。
これは test 再実行と同じ扱いです。

```text
writer が「tests passed」と書く
  → authority ではない

verify/gate/oracle が test を実行する
  → authority

writer が「architecture pass」と書く
  → authority ではない

verify/gate/oracle が architecture predicate を実行する
  → authority
```

---

# 11. Advisory → Oracle Requirement 写像

## 11.1 原則

advisory を散文一行で Agent に読ませません。
既存 merge-oracle / verifier / mutation adequacy に機械要件として写像します。

添付メモでも、scope advisor は「inspect せよ / scope に入れるか explicit exclude せよ」、architecture monitor は drift を advisory / monitoring として扱い、アルゴリズムは authority ではなく観測器・ranker・検出器に留めるべきだと整理されています。

## 11.2 advisory code

```text
ROUTING_OR_CONTEXT_BOUNDARY_CHANGED
HARNESS_ROLE_BOUNDARY_CHANGED
VERIFICATION_GATE_CHANGED
REVIEW_FRESHNESS_CHANGED
POLICY_TOUCH
```

## 11.3 oracle requirements

```text
T_UNION_COVERS_BEHAVIORAL_BOUNDARY
MUTATION_ADEQUACY_COVERS_CHANGED_CODE
```

## 11.4 mapping

```python
ADVISORY_REQUIREMENT_MAP = {
    "ROUTING_OR_CONTEXT_BOUNDARY_CHANGED": {
        "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
        "MUTATION_ADEQUACY_COVERS_CHANGED_CODE",
    },
    "HARNESS_ROLE_BOUNDARY_CHANGED": {
        "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
    },
    "VERIFICATION_GATE_CHANGED": {
        "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
        "MUTATION_ADEQUACY_COVERS_CHANGED_CODE",
    },
    "REVIEW_FRESHNESS_CHANGED": {
        "T_UNION_COVERS_BEHAVIORAL_BOUNDARY",
    },
}
```

---

# 12. `oracle_requirements.py`

## 12.1 Public API

```python
def oracle_requirements_satisfied(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> tuple[bool, list[str]]:
    ...
```

## 12.2 `T_UNION_COVERS_BEHAVIORAL_BOUNDARY`

最小実装では、以下を満たせば pass とします。

```text
- changed_paths に対して relevant verifier が少なくとも 1 つある
- または verifier が always=true
- かつ completion gate が該当 verifier を実行済み
```

`scope_map.py` は changed paths から likely affected verifiers / tests / review topics を出す実装を持っていますが、これは advisory です。([GitHub][8])
gate 側では `verify-result.verifiers` と `verifier-plan` を authority として扱います。

## 12.3 `MUTATION_ADEQUACY_COVERS_CHANGED_CODE`

既存の `mutation.py` は、mutation profile がある場合に `mutation-result.json` を作り、candidate hash と一致していること、mutation command が candidate を変更しないこと、survivor count / status を正規化する構造です。([GitHub][19])

最小仕様は次です。

```text
mutation profile がある:
  mutation-result.status == pass を要求

mutation profile がない:
  advisory requirement unmet
  requires_human_review または gate block
```

最初から mutation が全 repo で有効でないなら、導入初期は `T_UNION_COVERS_BEHAVIORAL_BOUNDARY` のみを hard oracle requirement にし、mutation は configured profile がある task に限定してもよいです。ただし、その場合は `MUTATION_ADEQUACY_COVERS_CHANGED_CODE` を出さないようにします。出した requirement を満たさずに通す設計は禁止です。

---

# 13. Agent-facing tool output

`verify` command の terminal output は数行にします。
JSON をそのまま長く出さず、key-value のみ表示します。

## pass

```text
ARCH_STATUS=pass
ARCH_SIGNIFICANCE=none
ARCH_REASON_CODES=-
ARCH_ORACLE_REQUIREMENTS=-
```

## advisory

```text
ARCH_STATUS=advisory
ARCH_SIGNIFICANCE=local
ARCH_ADVISORY_CODES=ROUTING_OR_CONTEXT_BOUNDARY_CHANGED
ARCH_ORACLE_REQUIREMENTS=T_UNION_COVERS_BEHAVIORAL_BOUNDARY
```

## block

```text
ARCH_STATUS=block
ARCH_REASON_CODES=UNINDEXED_SKILL
ARCH_REQUIRES_HUMAN_REVIEW=false
```

## inconclusive

```text
ARCH_STATUS=block
ARCH_REASON_CODES=ARCH_PREDICATE_INCONCLUSIVE
ARCH_REQUIRES_HUMAN_REVIEW=true
```

Agent はこれを解釈して architecture 判定をするのではなく、`verify-result.json` の authority に従うだけです。

---

# 14. Skill 仕様

## 14.1 `architecture-check` skill

```text
.agents/skills/architecture-check/SKILL.md
```

この skill は default skill ではありません。
`verify-result.architecture_gate.status != "pass"` または `derived_significance in {"local", "significant"}` のときだけ reviewer / integrator に routing します。

既存の skill index は、skills を discovery layer と compact execution contract として扱い、heavy-contract routes を default workflow で使わないと明示しています。([GitHub][20])

## 14.2 SKILL.md 案

```markdown
---
name: architecture-check
description: Interpret verify-result architecture_gate without expanding context.
---

## Purpose

Use existing machine evidence to respond to architecture_gate advisory or block states.

## Use when

- verify-result.architecture_gate.status is advisory or block
- verify-result.architecture_gate.derived_significance is local or significant

## Read

- verify-result
- candidate.diff only when already part of the reviewer packet
- existing named source_refs only

## Do not

- infer architecture_significance
- override architecture_gate.status
- scan the whole repo
- create architecture docs
- treat scope-map-reverse as a hard gate
- use architecture score or health score

## Output

- approve, block, or needs_human_review
- one-line reason code
- required next action
```

80 lines 以下に保ちます。

---

# 15. Context Audit 仕様

既存 `context_audit.py` は、role ごとの tools、skills、available artifacts、context payload を計測し、`capsule.json`、`contract.lock.json`、`verifier-plan.json`、`scope-map-forward.json`、`scope-map-reverse.json`、`verify-result.json` などの有無を見ます。([GitHub][21])

この実装では、新しい artifact を増やさないため、`_available_artifacts` の list は原則変更しません。

変更する場合も、以下のみです。

```python
# no new artifact names
# verify-result.json remains the only carrier
```

role packet に新しい source ref を追加しません。
reviewer はすでに `verify-result.json` を見るため、その中の `architecture_gate` を読むだけです。

---

# 16. Review / freshness 仕様

`review.py` は、reviewer verdict を harness-written な evidence-bound record として保存し、expected evidence と一致しない verdict を stale とします。([GitHub][18])

この実装では、`machine_evidence_sha256` に `architecture_gate` canonical payload を含めるため、次の変更で reviewer verdict は stale になります。

```text
- architecture_gate.status が変わった
- reason_codes が変わった
- advisory_codes が変わった
- oracle_requirements が変わった
- derived_significance が変わった
- predicate_version が変わった
```

新しい review freshness artifact は作りません。

---

# 17. Fail-closed 仕様

以下は `block + requires_human_review=true` に倒します。

```text
diff parse failure
changed path extraction failure
SKILL_INDEX parse failure
active docs detection failure
context-scope config parse failure
external write detection parse failure
baseline unavailable
predicate version mismatch
architecture_gate schema invalid
```

`pass` や `advisory-pass` に倒してはいけません。

```python
try:
    gate = evaluate_architecture_gate(...)
except Exception:
    gate = ArchitectureGate(
        status="block",
        derived_significance="unknown",
        reason_codes=("ARCH_PREDICATE_INCONCLUSIVE",),
        advisory_codes=(),
        oracle_requirements=(),
        requires_human_review=True,
        predicate_version="architecture-gate/v1",
        check_kinds={"ARCH_PREDICATE_INCONCLUSIVE": "fail_closed"},
    )
```

---

# 18. Program-level file structure

```text
src/workflow_core/contract_harness/
  review_comment_adapter.py
    parse_review_command()
    normalize_review_mode()
    acquire_review_lock()
    run_review_flow()
    update_commit_status()

  architecture_gate.py
    ArchitectureGate
    evaluate_architecture_gate()
    canonical_architecture_gate()
    architecture_gate_from_json()
    architecture_gate_to_json()

  architecture_predicates.py
    check_active_doc_expansion()
    check_new_storage_root()
    check_tracked_runtime_state()
    check_broad_repo_scan_default()
    check_unindexed_skill()
    check_skill_compact_limit()
    check_possible_external_write_path()

  oracle_requirements.py
    oracle_requirements_satisfied()
    check_t_union_covers_behavioral_boundary()
    check_mutation_adequacy_covers_changed_code()

  verify.py
    integrate architecture_gate into verify-result

  gate.py
    recompute architecture_gate
    check oracle_requirements

  verifier.py
    include architecture_gate in machine_evidence_hash

  review.py
    no major logic change
    benefits from updated machine_evidence_sha256

  agent_tools.py
    optionally route architecture-check skill for reviewer/integrator

  context_audit.py
    no new artifact exposure
```

---

# 19. GitHub adapter implementation detail

## 19.1 Function layout

```python
@dataclass(frozen=True)
class ReviewCommand:
    sha: str
    mode: Literal["normal", "arch", "full"]
    comment_id: str
    actor: str

def parse_review_command(body: str, sha: str, comment_id: str, actor: str) -> ReviewCommand | None:
    ...

def acquire_review_lock(repo: str, sha: str, mode: str) -> bool:
    ...

def run_review_flow(command: ReviewCommand) -> int:
    ...

def update_commit_status(sha: str, state: str, description: str) -> None:
    ...
```

## 19.2 Command parsing

```python
VALID_COMMANDS = {
    "/review": "normal",
    "/review arch": "arch",
    "/review full": "full",
}
```

コメント編集時は、同じ `(sha, mode)` lock が存在すれば no-op です。
明示 rerun を許す場合は、`/review rerun` ではなく integrator authority で lock を削除する方が安全です。

---

# 20. Gate reason mapping

`verify-result.architecture_gate.status == block` のとき。

```text
gate.reason = machine_gate_failed
```

または、より診断しやすくするなら。

```text
gate.reason = architecture_gate_block
```

ただし、gate status の authority は `verify-result.architecture_gate.status` のみです。
`gate-result.json` に別の architecture status object を複製しません。

`oracle_requirements` が満たされない場合。

```text
gate.reason = oracle_requirement_unmet
```

---

# 21. Tests

## 21.1 Unit tests

```text
tests/test_architecture_gate.py
```

検査項目。

```text
- active doc expansion を block
- new storage root を block
- tracked runtime state を block
- broad_repo_scan default true を block
- unindexed skill を block
- compact limit 超過を block
- external write heuristic を block + requires_human_review
- parse failure を ARCH_PREDICATE_INCONCLUSIVE に倒す
- ordinary implementation diff は pass
- harness routing change は advisory
```

## 21.2 verify integration

```text
tests/test_architecture_gate_verify_integration.py
```

検査項目。

```text
- verify-result に architecture_gate が存在する
- architecture_gate.status は enum
- block の場合 verify-result.status == fail
- advisory の場合 verify-result.status は verifier 次第で pass 可能
- task.yaml の architecture_significance を無視する
- machine_evidence_sha256 が architecture_gate 変更で変わる
```

## 21.3 gate/oracle

```text
tests/test_architecture_gate_oracle.py
```

検査項目。

```text
- gate が architecture predicate を再実行する
- recomputed gate と verify-result gate が違えば block
- oracle_requirements 未充足なら block
- scope-map-reverse に gate 値がなくても動く
```

## 21.4 GitHub adapter

```text
tests/test_review_comment_adapter.py
```

検査項目。

```text
- /review を normal に parse
- /review arch を arch に parse
- unknown command は no-op
- refs/harness/locks/<sha>-<mode> が存在する場合 no-op
- lock create 成功時のみ harness flow 起動
- status pending/success/failure/error mapping
```

## 21.5 skill / context

既存の skill route check は unindexed skill を拒否します。([GitHub][16])
既存の context scope check は broad source ref や missing denied_context を拒否します。([GitHub][15])

追加 test。

```text
- architecture-check skill は SKILL_INDEX にある
- architecture-check skill は 80 lines 以下
- architecture-check skill は default writer skill ではない
- context-audit の artifact list は増えない
- reviewer source_refs は増えない
```

---

# 22. Migration plan

## Phase 1: Internal architecture gate

```text
- architecture_gate.py
- architecture_predicates.py
- unit tests
- no CLI exposure
- no GitHub adapter
```

## Phase 2: verify-result integration

```text
- verify.py に architecture_gate を追加
- verifier.py の machine_evidence_hash を拡張
- review freshness test を追加
```

## Phase 3: gate/oracle integration

```text
- gate.py で predicate 再実行
- oracle_requirements.py を追加
- advisory → oracle requirement mapping
```

## Phase 4: compact skill

```text
- .agents/skills/architecture-check/SKILL.md
- SKILL_INDEX へ conditional route 追加
- writer default skill には入れない
```

## Phase 5: GitHub comment adapter

```text
- review_comment_adapter.py
- refs/harness/locks/<sha>-<mode>
- commit status integration
```

## Phase 6: Measurement profile only

```text
- DSM / propagation / Reflexion / smell / EWMA は default path に入れない
- 必要なら measurement profile / offline analysis として追加
```

添付メモでは、task scope と architecture monitoring は混ぜるべきではなく、scope 側は ranking、architecture 側は時系列 detection として扱うべきだと整理されています。また、DSM / Reflexion / smell / EWMA は有効な監視候補ですが、権威ではなく観測器・検出器として使うべきです。

---

# 23. 明示的に採用しないもの

以下は default implementation では採用しません。

```text
architecture_health_score
architecture graph 永続化
architecture-drift.json
architecture-constraints-result.json
DSM / EWMA / CUSUM の default 実行
LLM judge による architecture score
smell count の絶対閾値 gate
repo 全体 context injection
scope-map-reverse への gate 値配置
writer self-reported architecture_significance
```

添付メモでも、single architecture health score、LLM による architecture score、end-to-end scope optimizer、smell count absolute threshold gate は、説明可能性や authority 化の危険があるため弱い案として整理されています。

---

# 24. 最終的な実行フロー

```text
1. GitHub commit comment receives /review arch
2. Review Comment Adapter parses mode=arch
3. Adapter creates refs/harness/locks/<sha>-arch
4. Adapter posts commit status pending
5. Existing harness prepare/dispatch starts
6. Writer runs ./harness verify <task_id>
7. verify creates candidate.diff
8. verify creates scope-map-reverse.json as advisory only
9. verify runs architecture_gate inside trust boundary
10. verify writes architecture_gate into verify-result.json
11. verify machine_evidence_sha256 includes architecture_gate
12. reviewer sees existing evidence only
13. integrator/gate recomputes architecture_gate
14. gate rejects mismatch, block, or unmet oracle requirement
15. gate collects fresh reviews
16. adapter posts commit status success/failure/error
```

---

# 25. 実装上の不変条件

```text
Agent は architecture を判定しない。
Agent は verify-result の機械判定を読むだけ。

writer の self-report は authority ではない。
task.yaml の architecture_significance は読まない。

hard-block predicate は全 diff に無条件実行する。
significance は semantic skill routing の hint に限定する。

gate authority は verify-result.json のみ。
scope-map-reverse は advisory only。

advisory は散文でなく oracle_requirements に写像する。
判定不能は fail-closed で block / human review に倒す。

external write path detection は保守的 heuristic であり、完全保証ではない。
```

この仕様なら、Agent が harness の内部知識を持たなくても、既存の `verify` / `gate` / `oracle` の機械証跡に従って安定して動きます。JSON file 数は増やさず、Agent-facing context も増やさず、architecture は policy-level predicate と既存 oracle requirement に閉じます。

[1]: https://github.com/tana-alt/Dev-Foundation-ver2 "GitHub - tana-alt/Dev-Foundation-ver2: For general development environment. · GitHub"
[2]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/AGENTS.md "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/docs/01-agent-operating-contract.md "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/docs/02-output-verification-contract.md "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/docs/03-repo-boundary-and-storage-contract.md "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/verify.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/gate.py "raw.githubusercontent.com"
[8]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/scope_map.py "raw.githubusercontent.com"
[9]: https://docs.github.com/en/webhooks/webhook-events-and-payloads?utm_source=chatgpt.com "Webhook events and payloads"
[10]: https://docs.github.com/rest/commits/statuses?utm_source=chatgpt.com "REST API endpoints for commit statuses"
[11]: https://docs.github.com/rest/git/refs?utm_source=chatgpt.com "REST API endpoints for Git references"
[12]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/templates/work-contract.yaml "raw.githubusercontent.com"
[13]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/agent_tools.py "raw.githubusercontent.com"
[14]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/tests/test_system_design_integrity.py "raw.githubusercontent.com"
[15]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/tests/test_context_scope_check.py "raw.githubusercontent.com"
[16]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/tests/test_skill_route_check.py "raw.githubusercontent.com"
[17]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/verifier.py "raw.githubusercontent.com"
[18]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/review.py "raw.githubusercontent.com"
[19]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/mutation.py "raw.githubusercontent.com"
[20]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/.agents/skills/SKILL_INDEX.md "raw.githubusercontent.com"
[21]: https://raw.githubusercontent.com/tana-alt/Dev-Foundation-ver2/main/src/workflow_core/contract_harness/context_audit.py "raw.githubusercontent.com"
