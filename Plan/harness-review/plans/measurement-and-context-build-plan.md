# 効果測定 + 捕捉機構 + context 管理 — 実装計画

作成日: 2026-06-10
前提: `minimum-foundation-build-plan.md`(完了ゲートの土台)
方針: loop の orchestrator(①)は重いので後回し。その**部品**を先に作る。
      ここで作る3つは、後の loop がそのまま消費する器官になる。

---

## 確定済みの骨格(2026-06-10 実装・乗るしかない rail)

ports & adapters の seam を実コードで据えた。後続の trajectory/handoff/eval は
**必ずこの port の上に**乗せる。Codex/Claude を直接触る new code は禁止(下記テストが落とす)。

- `src/workflow_core/runtime.py` — 正規化語彙 + port(pure・runtime 非依存)
  - `TrajectoryEvent` / `HandoffPacket` / `GateVerdict` / `AgentRuntime`(Protocol)/ `to_jsonl`
- `src/workflow_adapters/mock_runtime.py` — `MockRuntime`(台本駆動・実 agent 不要)
- `tests/workflow_core/test_runtime_port.py` — port を固定 +
  **`test_workflow_core_stays_runtime_agnostic`** が core への codex/claude/adapter import を機械拒否

実装規約:
- gate / trajectory recorder / handoff builder / eval ランナーは `AgentRuntime` にのみ依存。
- 開発・テストは `MockRuntime` に対して行う(agent ランタイム不要・決定的)。
- Codex/Claude 実結合は port を満たす薄い adapter 1個に局所化する。

```
loop の正体(後で組む):
  凍結 spec+test を保持 → [handoff packet を渡して agent 起動]→[ゲート判定]→ 緑&review で停止 / fail で再起動 / N回で escalate
                              ↑⑤ context 管理        ↑S1-S3        ↑P6 失敗予算
  trajectory(③)= 全反復の記憶・token 信号 / eval(②)= この機械が効いているかの測定
```

---

## 実装順序とその理由

1. **③ trajectory(基層)** — eval も context 管理も入力にこれを読む。最初に作る。
2. **⑤ handoff packet builder(context 管理の種)** — 単独で手動再起動に即有用、loop の中核器官。
3. **② eval** — 上2つを使って「この機械が hack を捕まえているか」を測る。土台全体の反証装置。

---

## ③ trajectory 捕捉(基層)

**現状:** Codex app-server は run-event(`kind`/`status`/`next_action`)を出すが、
今は `templates/app-server-run-event.yaml`(`status: draft`)= **自己申告 YAML**。
イベント実体を構造化記録する recorder が無い。

**作るもの:** Codex app-server / SDK のイベントストリームを購読し JSONL で永続化。
- 出力: `artifact/<project>/trajectory/<run_id>.jsonl`(1行=1イベント)
- スキーマ: `{ts, run_id, role, kind(tool_call|tool_result|message|token_usage), tool, args_hash, exit_code, tokens_in, tokens_out}`
- **既存 `evidence_limits` を厳守**:raw log / terminal body / credentials は保存しない。
  args は hash、summary は bounded。テンプレが既にこの規範を持つので踏襲。

**なぜ基層か:** 「agent が実際に何をしたか」を機械で答えられない限り、
eval の採点も context の token 信号も failure 分析も作れない。今この repo はゼロ。

---

## ⑤ context 管理(handoff packet を最初に)

**現状:** `check-context-scope.py` は agent が「読んだと主張する ref」の YAML を検証する
**自己申告**。実 token も実 compaction も無い。

**作る2機構(handoff を先):**

### (a) handoff packet builder — 先に作る・即有用
- `scripts/build_handoff.py`:`spec_ref` + 現在の `git diff` + 直近の check 結果
  → bounded markdown を生成。
- 用途:フル会話履歴を再注入せず、**fresh context に最小の引き継ぎ**を渡す。
- これが**loop の中核器官**であり、手動再起動でも今すぐ使える。

### (b) budget + compaction — trajectory の token 信号を消費
- trajectory の `token_usage` 累積が閾値を越えたら、古い tool 出力を要約・raw body 破棄。
- 反復をまたぐ context rot(loop の罠3)への機械的対策。

**置換の意図:** 自己申告 context-scope YAML を、token 実測駆動の runtime 機構へ。

---

## runtime 管理 — observe / drive の2モード(同一 port)

「完全 runtime 化」はしない。日常利用では Codex/Claude を対話で使い、ハーネスは
横から記録・ゲートする。`AgentRuntime` port を満たす adapter を用途別に2種類持つ:

| モード | 用途 | `start()` | Codex | Claude |
|---|---|---|---|---|
| observe(受動) | 日常の対話利用 | 既存セッションへ attach(no-op) | app-server/SDK の run-event 購読 | hooks(PostToolUse/Stop/SessionStart)購読 |
| drive(能動) | **eval・loop** | headless で実起動 | Codex SDK headless | Agent SDK / `claude -p --output-format stream-json` |

- eval は **drive 必須**(再現可能・headless に多数 run)。`MockRuntime` がその開発用スタンドイン。
- adapter は「ネイティブイベント → `TrajectoryEvent` 翻訳器」にすぎず Codex/Claude を再実装しない。
- gate/recorder/eval は port にしか触れないので、どのモード・どの runtime でも不変。

## ② eval(効果測定 — 土台全体の反証装置)

実装済み(2026-06-10): `src/workflow_core/evaluation.py`。
- `ExpectedEnvelope`(allowed_tools / allowed_write_targets / expected_skills)
- `score_run(...) -> EvalScore`:成功(gate verdict)/ tool-call 率 / skill 使用率 /
  **unexpected_actions**(想定外 tool・envelope 外 write・想定外 skill)
- `aggregate(scores) -> EvalReport`:success_rate / 平均 tool-call 率 / runs_with_unexpected
- `TrajectoryEvent.target`(write 先・skill 名・コマンド名 = bounded 識別子)で
  raw body を持たずに envelope 逸脱を検出。
- `MockRuntime` の honest / 逸脱 台本で検証済み(実 agent 不要)。
- 残:hack-catch-rate 専用タスク(逃げが弱いチェックを通すが gate が捕えるか)+ drive adapter。

**目的:** S1〜S5 を入れて「reward hacking が実際に減ったか」を**数値で反証可能に**する。
これが無い harness は style guide、ある harness は測定して改善できるシステム。

**タスクスイート:** `eval/tasks/<id>/` = `{prompt.md, 凍結 spec+test, expected_outcome.yaml}`
- 2クラス:
  - **honest** — 普通に緑に到達すべき(false-positive ブロックが無いか)
  - **hack-bait** — stub / `pytest.skip` / mock が**弱いチェックは通すが凍結 spec/test に違反**。
    S1+S2 が捕まえるかを測る。**ここが本丸。**

**ランナー:** harness 下で agent 実行 → trajectory + ゲート verdict から採点:
`reached_green?` / `hacked?`(diff に逃げパターン) / `hack_caught?`(ゲートが block) / `cycles` / `tokens`

**指標:**
- pass-rate(honest が緑)
- hack-rate(hack-bait で逃げを試みた率)
- **hack-catch-rate(逃げをゲートが捕えた率)← 王冠**
- cycles-to-green / tokens(効率)

**最小開始:** 3タスク(honest 1 + hack-bait 2)、trajectory から手採点 → 後で自動化。
これで「S2 逃げscan を入れたら hack-catch-rate が上がったか」が即検証できる。

---

## この3つが揃うと何が起きるか

- trajectory で**事実が記録**され、eval で**機械の効果が測れ**、context 管理で**反復が痩せず回る**。
- S1〜S5(完了ゲート)の効果が **eval で反証可能**になり、harness 改善が閉ループに入る。
- 残るは ① orchestrator と ④ sandbox profile。①は上記部品の組み立て、
  ④は config profile を role 別に**ハーネスが割り当てる**ことで散文 human-gate を sandbox 強制へ。
