# ハーネス完成系 — GOAL と実現 PLAN

作成日: 2026-06-11
基点: `harness-implementation-report.md`(診断)/ `implementation-status.md`(現状の証跡)
役割分担: 広範な読取り→Explore subagent / 実装→opus・sonnet agent / 設計と難所→main(私)

---

## 第1部: GOAL — ハーネスの完成系

> main agent が単独 writer として文脈を保ったまま実装し、read-only subagent が
> 圧縮可能な仕事(調査・レビュー・検証)を肩代わりし、**完了の宣言権は agent では
> なく gate が持つ**。その効果は eval で数値化され、改善が閉ループに入っている。

完成系は次の8性質を**機械的に観測できる**状態と定義する(= 受入条件)。

| # | 完成性質 | 受入条件(機械判定) |
|---|---|---|
| G1 | 完了は事実で判定 | runtime stop-hook が完了ゲート(checks 再実行 + escape scan + diff-hash 束縛 + 必須 review verdict)を通さない限り「完了」を拒否。自己申告 result state はコードベースに存在しない |
| G2 | runtime 差し替え可能 | Codex / Claude が同一 `AgentRuntime` port の薄い adapter として接続。observe / drive 両モードが port を満たす |
| G3 | 全 run が trajectory 化 | 各 run が tool-call/skill/token/write を構造化 JSONL で残し、再生・分析・eval 可能 |
| G4 | 効果が測定可能 | eval スイート(honest + hack-bait)が hack-catch-rate / 成功率 / 想定外行動 / tool・skill 使用率を出力。ゲート変更の前後で反証できる |
| G5 | context が機構管理 | handoff packet + token 駆動 compaction。自己申告 context-scope YAML は廃止 |
| G6 | 権限は実行層で強制 | human-gate(secrets/deploy/external)は散文でなく role 別 sandbox profile で。reviewer は read-only を OS が保証 |
| G7 | 表面積が薄い | 常駐文書 = 3契約 + フローのみ(< 行予算)。heavy contract と死に skill は archive。ゲートが事実を持つので作文契約は不要 |
| G8 | 直列フェーズ + loop | goal → spec(frozen tests)→ implement → gate →(fail は handoff 再起動 / N回で escalate)。1 writer + N read-only subagent |

**現状の達成度**(`implementation-status.md` 参照):
G1 中核実装済(stop-hook 未接続)/ G2 port 確定・adapter 未 / G3 recorder 済・実 run 未接続 /
G4 scoring + hack-catch 済 / G5 handoff 種のみ / G6 未 / G7 未(heavy 残存)/ G8 未。

---

## 第2部: PLAN — 完成系への経路(6フェーズ)

各フェーズに **[読取]→Explore / [実装]→opus|sonnet / [設計・難所]→main** を明記。
依存順に並べるが、Phase D(撤去)と C(eval 拡充)は独立で並行可。

### Phase A — 完了ゲートを実運用に接続(G1 完成)
キーストーンを「呼べば動く部品」から「逃げられない門」にする。
- **[設計・難所/main]** stop-hook 契約の設計:
  - diff-hash に **untracked 込み**(`git add -N` 相当 or `git status` 合成)を含める
  - 「pass 後に再編集」検出(verdict の diff-hash と現在の diff-hash 不一致で再ゲート)
  - evidence JSON の **agent-不可侵性**の担保方法(ゲート再実行モデルなので偽造は無意味だが、書込み経路を hook で弾く)
  - idempotency / 多重起動時の挙動
- **[実装/opus]** `scripts/completion_gate.py` の untracked diff 対応、stop-hook エントリ、`make gate` の tier 選択(G4 の check-tier 指定 = レポート P4)
- **[実装/sonnet]** 完了ゲートの統合テスト(pass/block/再編集後 block の3系統)
- 完了判定: hack-bait diff で stop-hook が「完了」を実際に拒否する e2e テスト

### 判断(確定 2026-06-11): hook vs SDK — 負荷の分岐点

Claude Code / Codex とも同一の hook schema(`Stop` / `PostToolUse` / `PreToolUse` /
`UserPromptSubmit`)を持ち、**Stop hook が `{"decision":"block","reason"}` で完了を
ブロックし同一セッションで継続**できる。よって:

- **日常の spec 付き業務(完了ゲート + trajectory + in-session loop)= HOOK だけで実現。**
  agent が hook 経由でハーネスを呼ぶ逆制御。プロセス管理・stream 解析・SDK 不要 = 低負荷。
  実装済(2026-06-11): `hook_events.py`(両ランタイム共通の payload→TrajectoryEvent 翻訳)
  + `scripts/hook_post_tool_use.py`(記録)+ `scripts/hook_stop.py`(spec-gated 差し戻し)
  + 設定テンプレ `templates/{claude-hooks-settings.json,codex-hooks.json}`。
- **SDK / headless が要るのは2点のみ**: per-turn token 計測、無人・再現可能な eval 起動。
  → 下記 Phase B は **eval/automation 専用の drive 経路**に限定(全 runtime 化はしない)。

### Phase B — runtime adapter(G2/G3 完成)※eval/automation 専用の drive 経路
- **[設計・難所/main]** 既存 `codex_app_server_adapter` の EventKind は**ワークフロー粒度**で
  `TrajectoryEvent`(tool 粒度)に直接 map できない。Codex の**実イベントストリーム**
  (exec/SDK の tool-call レベル)を消費する変換層の設計が要。observe/drive で
  `start()` の意味が分岐する点の抽象も確定する。
- **[読取/Explore]** Codex SDK / app-server の実イベント schema を調査(どの粒度の
  tool イベントが取れるか)、Claude Code hook payload schema(PostToolUse/Stop)を調査
- **[実装/opus]** `workflow_adapters/codex_drive_adapter.py`(Codex SDK headless →
  `TrajectoryEvent`)と `claude_hook_adapter.py`(hook payload → `TrajectoryEvent`、
  stop hook → `completion_gate`)。MockRuntime が満たす契約に一致させる
- **[実装/sonnet]** 各 adapter の翻訳テスト(ネイティブ event 固定 → 期待 TrajectoryEvent)
- 完了判定: 実 Codex run 1本が trajectory JSONL に落ち、eval が採点できる

### Phase C — eval を実 agent に接続 + hack-bait 拡充(G4 強化)
- **[設計/main]** hack-bait タスクの分類設計(空関数体・`return None` スタブ・mock 固定・
  テスト改変・assert 削除 …)と scanner の取りこぼし測定
- **[実装/sonnet]** eval タスクを実 drive adapter で回す runner、hack-bait を 5–8 本に拡充、
  scanner のパターン追加(catch-rate を継続的に締める)
- **[実装/sonnet]** eval レポートの artifact 永続化 + 経時比較
- 完了判定: `make eval` が実 agent run で hack-catch-rate を継続的に出力

### Phase D — heavy-contract / 死に skill 撤去(G7 完成)※カスケード注意
依存マップ(本セッションの Explore 棚卸し)に厳密に沿う。
- **[読取/Explore]** 撤去対象ごとの参照テストを再確認(`test_foundation_integrity.py` /
  `test_clean_checkout_reproducibility.py` / 各 `test_*_check.py`)
- **[実装/sonnet]** 段階撤去(自己完結→カスケード順):
  1. retired skills 3個(traceability-gate / residual-risk-carryover / review-fix-convergence)
     + `RETIRED_GOVERNANCE_SKILLS` set
  2. legacy checker 4種(residual-risk / review-convergence / audit-provenance / scorecard)
     と対応 template、`agent_operational_checks.py` の該当 validator、Makefile 配線
  3. 参照テスト(`test_*_check.py` / integrity / reproducibility)を同時更新
  4. 死に skill の棚卸し(24 個の「other」skill の使用頻度 = レポート P8)
- **[設計/main]** 何を残し何を畳むかの線引き(ゲートが代替する作文契約のみ撤去、
  実 check は残す)。各段階で `make check-required` green を維持する撤去順序の確定
- 完了判定: active docs/skills が行予算内、全テスト green

### Phase E — context 機構 + scope review(G5 + S3)
- **[設計・難所/main]** token 駆動 compaction の閾値設計、handoff 再シードの境界、
  one-hop scope review の参照集合を機械列挙する規則(レポート P3)
- **[実装/opus]** trajectory の token_usage を消費する compaction、`build_handoff` の loop 統合
- **[実装/opus]** fresh-context reviewer を drive adapter 経由で起動、型付き verdict を
  ゲートの必須入力に(G1 の review verdict 要求と合流)
- 完了判定: 反復 run で context が予算内に収まり、review verdict が無い完了は block

### Phase F — sandbox profile + loop orchestrator(G6 + G8)※最終・最難所
- **[設計・難所/main]** role 別 sandbox profile の割当規則(reviewer=read-only,
  implementer=workspace-write+allowed_paths, human-gate=never)。loop orchestrator の
  状態機械(spec→implement→gate→handoff 再起動→N回 escalate)、失敗予算(P6)
- **[実装/opus]** Codex `config.toml` profile をハーネスが spawn 時に選択する層、
  loop driver(port + gate + handoff + 失敗予算の組み立て)
- 完了判定: goal を渡すと frozen test 緑 or escalate まで自律で回る e2e

---

## 第3部: 委任の運用ルール

- **広範な読取りは必ず Explore subagent へ**(本体 context を実装関連に保つ = G5 の精神)。
- **実装委任**: 難所(adapter 変換・stop-hook 契約・loop・sandbox)は **opus**、
  境界の明確な機械作業(撤去・テスト追加・パターン拡充)は **sonnet**。
- **main(私)が保持**: 各 Phase の設計仕様、port/契約の決定、統合レビュー、難所の実装。
- **各委任は task packet 形式**: goal / frozen Done 条件 / allowed write / source refs を渡し、
  返りは完了ゲート(`make gate`)で機械検証してから取り込む(自己申告を受け取らない)。

---

## 一文

完成系は「完了の宣言権が gate にあり、その効果が eval で測れ、実 runtime が port 越しに
差し替わり、context・権限・表面積が機構で抑えられた」状態。残る難所は
**adapter 変換(B)・loop と sandbox(F)** で、ここに私の設計を集中する。
