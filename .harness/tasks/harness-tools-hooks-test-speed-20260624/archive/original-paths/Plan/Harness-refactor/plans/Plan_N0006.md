# Plan_N0006: エージェント役割別「可視性(visibility)」全体像とハーネス機能ギャップ監査

本書は **「各エージェント役割が、実際に何を・どの経路で見えるのか」** を、ACP のレビュー依頼・hook が与える scope・read-only facade・scope map・capsule まで全て洗い出し、その上で **実ハーネス機能に対して不足しているもの (gap)** を機械的に列挙する監査文書である。すべて実コードの `file:line` に基づく(2026-06-23 時点 `agent/contract-harness-stability` ブランチ)。

---

## 0. 結論サマリ

可視性は単一の経路ではなく、**互いに同期していない 6 つの surface** から成る。

| # | Surface | 何を決めるか | 実装 |
|---|---------|------------|------|
| S1 | Role command ACL | role が叩ける CLI サブコマンド | `roles.py:10-69` |
| S2 | Agent tools / skills | role に提示される tool/skill カタログ | `agent_tools.py` |
| S3 | Capability authority | role が実行「権限」を持つ操作 | `domain/capabilities.py:11-96` |
| S4 | Initial context / capsule | session 起動時に渡す静的 context | `launch.py`, `spawn.py`, `contract.py` |
| S5 | Reviewer packet (実体) | reviewer プロセスが実際に受け取る証拠束 | `semantic_review.py:113-161`, `review.py:108-134` |
| S6 | Read-only MCP facade | task artifact への読み取り境界 | `mcp_readonly.py:9-25` |
| 計測 | context-audit | 上記とは別に「context 圧」を推定する計測器 | `context_audit.py` |

**最重要の発見:** 「reviewer が見える」と一言で言っても、S5(実パケット) と 計測器(`context_audit._payload_context`) と S6(facade) の三者が**列挙対象でズレている**。さらに **ACP のレビュー依頼 (S2 の delegation) は review 実行に結線していない**。詳細は §6 ギャップ監査。

---

## 1. 役割の全体像

`roles.py:10-65` の `ALLOWED` で定義される役割は **3 つ** (+ `admin` capability ロール)。

| Role | 責務 | 起動 env | 主要 capability |
|------|------|----------|----------------|
| **writer** | 実装・自己検証・提出 | `HARNESS_ROLE=writer` (既定, `roles.py:68-69`) | `SUBMIT_CANDIDATE`, `RUN_VERIFY` |
| **reviewer** | 意味的/セキュリティ検証・verdict 記録 | `HARNESS_ROLE=reviewer` + `FOUNDATION_REVIEWER_ID` | `RUN_REVIEW` |
| **integrator** | worktree/gate/review収集/land/push | `HARNESS_ROLE=integrator` | `COLLECT_REVIEW`, `RUN_GATE`, `MERGE_LOCAL`, `COMPLETE_TASK`, `CREATE_PR`, `RUN_PR_CHECKS`, `RECONCILE` |
| (admin) | 全権限 | — | 全 capability (`capabilities.py:45-72`) |

`Capability` enum (`capabilities.py:11-25`): `READ_CONTEXT, READ_STATUS, SEND_ACP_MESSAGE, SUBMIT_CANDIDATE, RUN_VERIFY, RUN_REVIEW, COLLECT_REVIEW, RUN_GATE, CREATE_PR, RUN_PR_CHECKS, MERGE_LOCAL, COMPLETE_TASK, RECONCILE, ADMIN`。`read_context/read_status/send_acp_message` は全 role 共通。

---

## 2. 役割別「見えるもの」マトリクス

### 2.1 Writer に見えるもの

| 区分 | 内容 | 出典 |
|------|------|------|
| Tools (12) | `scope-map-forward`, `explain`, `context-audit`, `status`, `comm-peers`, `comm-send`, `comm-inbox`, `spawn-writer`, `verify`, `submit`, `report-rfc`, `report-metric` | `agent_tools.py:131-204` |
| Skills (3) | `tdd-scope`, `implementation-slice-verification`, `scope-routing-governance` (全て default routing) | `agent_tools.py:83-95` |
| Capsule | `task_id, scope, intent, scope_contract, verifier_plan, agent_tools, agent_skills, contract_semantic_sha256` | `contract.py:195-205` |
| Initial context | `task_id, scope_contract, verifier_ids, agent_tools, agent_skills` | `launch.py:122-130` |
| Scope (advisory) | `scope-map-forward.json` (path_hints / forbidden_path_hints / verifier_hints / likely_tests, `hard_constraint:false`) | `scope_map.py:14-51` |
| 強制境界 | `scope_contract.allowed_paths/forbidden_paths` (capsule内) + `GLOBAL_FORBIDDEN` | `contract.py:34-42` |
| facade で読める | §2.4 共通リスト (verify-result 等) | `mcp_readonly.py:9-25` |

writer は実装前に `scope-map-forward` で薄い発見マップを見るが、これは**助言**であり、実際の許可パスは `contract.lock.json` の `scope_contract` と `GLOBAL_FORBIDDEN`(`.harness/*.yaml`, `rfc-decisions/**`, `tasks/*/task.yaml`, `generated/**`) で決まる。

### 2.2 Reviewer に見えるもの（**実体は packet**）

reviewer の「見える」には 2 系統があり、**実際に受け取るのは S5 の packet**。

**(a) 実パケット `semantic_review._packet` (`semantic_review.py:113-161`)** — semantic reviewer が受け取る全体:
```
task_id, capsule, contract, agent_tools, agent_skills, writer_handoff,
review_workspace, scope_map.reverse, candidate_diff(bounded inline),
candidate_diff_path, candidate_diff_sha256, candidate_diff_index,
diff_instruction, omitted_required_evidence, requires_artifact_read,
verify_result, mutation_result, quality_result, tool_candidates,
metric_evidence, reviewer_policy, test_interpretation
```
組み込み reader (`reader-scope`/`reader-impact`/`reader-correctness`) は `verify_result`(candidate_diff_sha256, machine_evidence_sha256), `scope`(violation_count), `impact_result`, `contract`(semantic_reproducible) を見る (`review.py:108-134`)。

**(b) Tools (5) / Skills (3)** (`agent_tools.py:365-403`, `46-128`):
`scope-map-reverse`, `context-audit`, `status`, `review-verdict`, `certify` / `security-check`, `implementation-slice-verification`, `scope-routing-governance`。

reverse scope map (`scope_map.py:54-89`): `observed_scope.changed_paths`, `likely_affected.{verifiers,tests,review_topics}`, `hard_constraint:false`、明示注記「review evidence であって完全な依存グラフではない」。

### 2.3 Integrator に見えるもの

| 区分 | 内容 | 出典 |
|------|------|------|
| Tools (15) | `review-collect`, `scope-map-reverse`, `affected`, `context-audit`, `status`, `spawn`, `dispatch`, `integrate`, `gate`, `land`, `compose`, `compose-push`, `oracle`, `push` (+ reviewer系の scope-checker lane) | `agent_tools.py:206-291`, `roles.py:60` |
| Skills (2) | `implementation-slice-verification`, `scope-routing-governance` | `agent_tools.py:113-124` |
| 主に読む artifact | `submission.json`, `integration-result.json`, `affected-set.json`, `gate-result.json`, reviews/*, candidate.diff | `context_audit.py:84-87`, `mcp_readonly.py` |
| 影響分類 | `affected.py:14-48` が FAST / PARTIAL / REBASE を `affected-set.json` に書く | `affected.py` |
| Gate 権威再計算 | §4 preflight | `gate.py:156-181` |

### 2.4 Read-only MCP facade（**役割非依存・全 role 共通**）

`mcp_readonly.READ_ONLY_RESOURCES` (`mcp_readonly.py:9-25`) は **role でフィルタされない単一リスト**:
```
contract.lock.json, verifier-plan.json, candidate.diff, verify-result.json,
quality-result.json, scope-map-forward.json, scope-map-reverse.json,
submission.json, reviews/*.json, gate-result.json, affected-set.json,
land-result.json, oracle-result.json, push-result.json, rework-request.json
```
`WRITE_TOOLS=()`(書込ツール無し)。`_ensure_allowed`(`:68-73`) はこの集合のみ許可。**role 引数を取らない** → reviewer も writer も同じ集合が読める。

---

## 3. ACP（エージェント間通信）と「レビュー依頼」

### 3.1 メッセージ語彙 (`agent_comm.py:12-33`)

- `ALLOWED_INTENTS` (10): `action_request, status_query, status_response, proposal, clarification, rework_hint, artifact_summary, test_request, review_question, handoff_note`
- `FORBIDDEN_AUTHORITY_CLAIMS` (7): `completion_claim, done_claim, review_verdict, gate_result, land_result, push_result, mergeable_claim` — **エージェント間では権威主張を送れない**(`_validate_kind`)。

エンベロープ: `schema_version, message_sha256, correlation_handle, task_id, from{agent_id,role}, to{...}, kind, subject, body_markdown, in_reply_to, basis_refs, artifact_refs, warnings, expires_at, written_by="agent-comm-switchboard"`、`delegation_brief` 指定時のみ `delegation{role, brief}` を付加 (`agent_comm.py:96-100`)。inbox は `{task_dir}/comm/inbox/{agent_id}/{sha}.json`。

### 3.2 「レビュー依頼」の表現と実行の経路

- **依頼 (advisory)**: `comm-send --to <agent> --delegation-brief "..."` → kind=`action_request` + `delegation{role:"reviewer", brief}` (`cli.py:443-476`, `agent_comm.py:106-143`)。これは**非権威の inbox メッセージ**。
- **ACP request-action**: `acp request-action <message_id> --body` → daemon `_acp_request_action`(`server.py:492-499`) は `proposed_action`("candidate.verify" or "task.status") を返すのみで **`executed:False`**(スタブ)。
- **review の実起動**: integrator の `gate`/`dispatch` 内 `_auto_review`(`gate.py:53,278`) → `run_missing_reviewers`(`review_runner.py:28-39`) → `stale_or_missing` の reviewer を起動。**ACP の依頼メッセージとは独立**。

→ **ACP のレビュー依頼は「調整シグナル」であり、reviewer 実行を起動しない**(§6 Gap-4)。

### 3.3 verdict と freshness

verdict 構造 (`review.py:149-171`): `verdict(approve|block), labels, reason, evidence_seen{candidate_diff_sha256, machine_evidence_sha256, (+semantic: mutation/quality/tool_candidates/scope_map_reverse/metric)}, evidence_seen_sha256, written_by="harness"`。
freshness (`review.py:196-239`, `evidence.py:30-50`): verdict が記録した `evidence_seen` と現 `verify-result` 由来の expected hash を全キー一致比較。一致=fresh、不一致=stale。
収集 (`review.py:81-98, 251-281`): `written_by=="harness"` 行のみ採用 → fresh/stale/unknown 分類 → `review_pass = approves>=quorum AND no blocks AND (semantic_required→semantic_approve>=1)`。quorum 既定 2 (`config.py:88-101`)。

---

## 4. Gate の権威再計算（writer 自己申告を信用しない仕組み）

`gate.py:156-181` `_preflight_reason` の検査順:
1. `candidate_hash_mismatch` — candidate.diff hash 一致
2. `contract_semantic_mismatch` — contract 再コンパイル hash 一致 (`contract.py:144-154`)
3. `machine_gate_failed` — `verify-result.status=="pass"`
4. `architecture_gate_mismatch` — 現 diff で architecture gate 再計算し verify-result と一致
5. `architecture_gate_block` — `architecture_gate.status=="block"`
6. `oracle_requirement_unmet`
7. `evidence_hash_mismatch` — quality/tool_candidates/scope_map_reverse の SHA256 一致 (`evidence.py:21-27`)
8. `candidate_hash_mismatch` (最終)

**writer の自己申告は authority にならない**: reviews 収集は `written_by=="harness"` 行のみ採用 (`review.py:86`)。architecture gate も verify と gate の **両方で機械再計算**され、不一致は block。Plan_N0004 の「architecture gate を verify-result に埋め込み、gate で再計算」は **実装済み**(`verify.py:10-14,53-77`, `gate.py:169-173`)。

---

## 5. Hook が与える scope（観測中心・強制なし）

`scripts/` の hook は 3 つのみ。**PreToolUse は存在しない**(grep 結果ゼロ)。

| Hook | モード | 役割 / scope | 出典 |
|------|--------|-------------|------|
| `hook_post_tool_use.py` | 観測のみ・常に exit0 | 全 tool call を `artifact/<proj>/trajectory/<session>.jsonl` に追記。role は `HARNESS_ROLE`/`FOUNDATION_AGENT_ROLE` から(既定 implementer) | `hook_post_tool_use.py` |
| `hook_stop.py` | 観測 + fail-open | `submission.json` 検出時に `HARNESS_ROLE=integrator` で `harness dispatch` を自動委譲。強制ブロックは無 | `hook_stop.py` |
| `hook_session_start.py` | 観測・情報提示 | `open-issues.json` を最大5件 stdout 復帰 | `hook_session_start.py` |

scope の宣言(allowed/forbidden_paths, `denied_context`={broad_repo_scan, secrets, runtime_state}, `GLOBAL_FORBIDDEN`)はあるが、**tool 呼び出し時にブロックする hook は無い**。runtime state / broad scan / external write の禁止は `architecture_predicates.py`(verify/gate 内 predicate)で**事後**に block される設計であり、agent の読み取り行為自体を hook で止めてはいない。`templates/claude-hooks-settings.json` は **archive にしか存在しない**(稼働テンプレ未整備, §6 Gap-3)。

---

## 6. ギャップ監査（実機能に対して不足しているもの）

> 判定: ⛔=機能欠落 / ⚠=不整合・未結線 / ✅=設計どおり健全

### ⚠ Gap-1: context-audit の計測対象が reviewer 実パケットと乖離
`context_audit._payload_context`(`context_audit.py:78-83`) は reviewer を `{scope_map_reverse, submission, review_packets}` でしか計測しないが、実パケット `_packet` は `verify_result, mutation_result, quality_result, tool_candidates, metric_evidence, candidate_diff, capsule, contract, writer_handoff, test_interpretation` まで含む(`semantic_review.py:113-161`)。
**影響:** `estimated_tokens` / `bytes` / `missing_required` が実際の context 圧を**過小評価**。context-audit が「pass」でも実 reviewer は遥かに重い束を受ける。
**修正方針:** `_payload_context` の reviewer 分岐を `semantic_review._packet` と同一供給源に統一するか、計測を packet builder から逆算する。

### ⚠ Gap-2: read-only facade が役割非依存（denied_context を facade で強制していない）
`mcp_readonly.READ_ONLY_RESOURCES` は role を引数に取らず、全 role が同一集合を読める(`mcp_readonly.py:30-73`)。docs の「role 別 denied_context」「reviewer は capsule/forward-map を見ない」は facade レベルで強制されていない。さらに facade のリストと実パケットも不一致(facade に `capsule.json` / `mutation-result.json` / `tool-candidates.json` / `metric-evidence.json` / `integration-result.json` が**無い**一方、packet はこれらを供給)。
**影響:** 「role に見せたくない artifact」を facade が遮断できない。可視境界の単一の真実が無い。
**修正方針:** `list_resources/read_resource/_ensure_allowed` に `role` を導入し、`context_audit` / `_packet` / facade を **1 本の role→artifact 表**から導出する。

### ⛔ Gap-3: read-boundary を強制する hook が無い（scope は宣言のみ）
PreToolUse 等の**ブロッキング hook が存在しない**。scope/denied_context/forbidden_paths は契約として宣言されるが、agent の読み取り tool を起動時に止める層が無い。違反は verify/gate の `architecture_predicates` で**事後**検出されるのみ。加えて稼働 hook 設定テンプレートが archive にしか無い(`templates/claude-hooks-settings.json` 不在)。
**影響:** 「hook が与える scope」はユーザ期待に反し、現状ほぼ trajectory 記録に留まる。read 隔離は worktree 物理分離と運用規約に依存。
**修正方針:** (a) PreToolUse hook で role×path/denied_context を enforce、または (b) read を全て read-only facade 経由に限定し facade を唯一の入口にする。最低限、稼働 `claude-hooks-settings.json` テンプレを `templates/` に復活。

### ⛔ Gap-4: ACP の「レビュー依頼」が review 実行に結線していない
`comm-send --delegation-brief` の `action_request`+`delegation` は非権威 inbox メッセージで、reviewer を起動しない。`acp request-action` は `executed:False` の proposed_action スタブ(`server.py:492-499`)。実 review は integrator の `_auto_review` が起動するのみ(`gate.py:278`)。
**影響:** 「ACP からレビュー依頼」が UX 上は存在するが、依頼→実行の橋が無い。delegation_brief は reviewer packet にも伝播しない。
**修正方針:** `acp request-action` を `delegation.role=="reviewer"` のとき `review --run`/`run_missing_reviewers` に結線し、結果 verdict を correlation_handle で返す。または delegation を `stale_or_missing` の起動トリガに含める。

### ⛔ Gap-5: review_comment_adapter が CLI 未配線（GitHub `/review` 入口が無い）
`parse_review_command`/`acquire_review_lock`/`ReviewMode(normal|arch|full)` は実装+テスト済みだが、`cli.py` にサブコマンドが無く `scripts/` にも呼び出しが無い(grep: 自己定義のみ)。`update_commit_status` 等の GitHub 連携も未実装。
**影響:** Plan_N0004 §3.1/§19/§24 の「commit comment → harness 起動 → commit status」フローが宙吊り。`arch`/`full` モードを起動する経路が無い。
**修正方針:** `harness review-comment <event.json>` サブコマンドを追加し adapter を結線、commit status 更新を実装。または webhook→`acp request-action` に統合。

### ⚠ Gap-6: `acp send`(strict/daemon 経路) が delegation-brief を非公開
`acp send` は `--kind`(ALLOWED_INTENTS)のみで delegation を渡せない(`cli.py:762-778`)。delegation は `comm-send` 経路だけ。正規 ACP(daemon) と coordination(comm) で機能差。
**修正方針:** `acp send` に `--delegation-brief` を追加し両経路を揃える。

### ✅ 健全（設計どおり）
- writer 自己申告の排除(`written_by=="harness"` フィルタ + gate 機械再計算)。
- architecture gate の verify/gate 二重再計算と fail-closed。
- scope-map の `hard_constraint:false`(advisory) と contract/`GLOBAL_FORBIDDEN` による実強制の分離。
- freshness の evidence-hash 連動 stale 化。

---

## 7. 是正の優先順位（推奨）

| 優先 | Gap | 理由 |
|------|-----|------|
| P0 | Gap-4, Gap-5 | 「ACP からレビュー依頼」「`/review` 起動」というユーザ目的の中核機能が未結線 |
| P1 | Gap-3 | hook の scope 強制が無く、可視境界が運用依存。稼働テンプレ不在 |
| P2 | Gap-2 | 可視境界の単一真実(role→artifact 表)を欠く |
| P3 | Gap-1, Gap-6 | 計測精度・ACP 経路差。観測性と一貫性の改善 |

**根治策:** 「role × artifact の単一可視性表」を 1 箇所に定義し、`context_audit` / `semantic_review._packet` / `mcp_readonly` / `denied_context` を全てそこから導出する。その上で ACP delegation と review 実行、review_comment_adapter を CLI/daemon に結線する。これにより S1〜S6 と ACP 依頼が同期し、「役割が見えるもの」と「ハーネスが強制するもの」が一致する。
