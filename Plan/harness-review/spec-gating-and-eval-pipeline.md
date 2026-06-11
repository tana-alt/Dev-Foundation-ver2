# spec 判定 と hook→eval の仕組み(言語化)

作成日: 2026-06-11
対象実装: `src/workflow_core/{loop,hook_events,completion,measure,metrics_store,evaluation}.py`,
`scripts/{hook_stop,hook_post_tool_use,measure_eval}.py`

---

## 1. spec 判定 — 「loop を回すか、一発で終えるか」の唯一の分岐

### 1.1 何を判定しているか

ハーネスは **「この仕事は仕様書付きか?」** だけを見て、完了時の挙動を二分する。

| 判定 | 完了時の挙動 | 意図 |
|---|---|---|
| spec あり | **loop**: writer 完了 → review+test → fail なら差し戻し → N 回で escalate | 仕様を満たすまで締める |
| spec なし | **single-pass**: 一度で終了、ゲートで縛らない | 雑談・調査・小修正で使いやすさを保つ |

「全てで loop が回ると使いにくい」を避けるための、ただ一つのスイッチ。

### 1.2 どこで・どう判定するか(2 箇所、同一概念)

runtime モードが2つあるため、spec 判定も2箇所に現れる。**判定基準は同じ、差し戻しの手段だけが違う。**

**(A) observe 経路(hook・日常利用)** — `scripts/hook_stop.py` の `_spec_present()`:

```
FOUNDATION_SPEC_PRESENT=1  なら spec あり
さもなくば Plan/<project>/spec.md が存在すれば spec あり
```

- spec なし → Stop hook は何もせず `return 0`(agent はそのまま終了 = single-pass)。
- spec あり → 完了ゲートを再実行し、fail なら `{"decision":"block","reason":...}` を出力。
  これで **同一セッションの agent が継続**する(= loop の差し戻し)。
- `stop_hook_active=true`(連続ブロック)は無限ループ防止のため即 `return 0`。

**(B) drive 経路(headless/eval・SDK 保留中)** — `src/workflow_core/loop.py` の `run_loop(..., spec_present: bool, ...)`:

```
spec_present=False → runtime.start(handoff) を1回だけ → status="single_pass"
spec_present=True  → for attempt in 1..max_attempts:
                       runtime.start(handoff(spec, diff, last_failure))
                       verdict = gate()
                       passed → status="completed"
                       fail   → last_failure=verdict.feedback; runtime.signal_block(...)
                     ループ尽きたら status="escalated"
```

- ここでは「差し戻し」= 失敗 feedback を載せた **handoff packet を作って再起動**(full 履歴は渡さない)。

### 1.3 要点

- 判定は **bool 一個**。複雑な条件分岐ではない。spec ファイルの有無(or 明示フラグ)。
- observe は「Stop hook の block が継続を生む」逆制御、drive は「ハーネスが再起動する」順制御。
  **どちらも spec 有り時のみ loop**、という規約は共通。
- 失敗予算(`max_attempts` / `stop_hook_active`)で、どちらの経路でも焼き付きを防ぐ。

---

## 2. hook→eval の仕組み — 書き込みは hook、計測は後追い

制御方向が逆の2フェーズに分かれる。**hook が trajectory を書き、eval がそれを読む。**

```
[実行時 / push 型: agent が hook 経由でハーネスを呼ぶ]
  agent が tool 使用
    └─ PostToolUse hook → scripts/hook_post_tool_use.py
         └─ from_post_tool_use(payload)  ← Claude/Codex 共通の翻訳器
              payload(tool_name/tool_input/tool_response) → TrajectoryEvent
              (kind=tool_call, tool, target=書込先/skill名/コマンド, args_hash, exit_code)
         └─ artifact/<project>/trajectory/<session>.jsonl に1行 append
  agent が終了しようとする
    └─ Stop hook → scripts/hook_stop.py(spec 判定 §1.2A)
         └─ spec あり: completion.run_completion_gate(diff, diff_hash, check, ts)
              = make check 再実行 + scan_escapes、diff-hash に束縛
              → evidence JSON を artifact/<project>/evidence/ に書く(agent 不可侵)
              → fail なら block+reason で差し戻し

[計測時 / pull 型: ハーネスが蓄積データを読む] — make measure / scripts/measure_eval.py
  artifact/<project>/trajectory/*.jsonl を走査
    └─ load_trajectory(path) → TrajectoryEvent 列
    └─ envelope を決める:
         Plan/<project>/eval-envelope.json があれば固定 envelope(想定外検出ON)
         なければ default_envelope(events)= 観測物を whitelist(計数のみ)
    └─ measure_trajectory(run_id, events, envelope)
         = score_run: 成功(tool 失敗ゼロ) / tool_call_rate / skill_usage_rate / unexpected_actions
    └─ MetricsStore.record_run(score, raw, created_at)
         run_metrics(構造化=保持)  +  raw_runs(raw=退役対象)
    └─ enforce_retention(max_raw_runs):
         raw が閾値超過 → 古い raw を削除、構造化シグナルは残す
    └─ aggregate(scores) → success_rate / 平均 tool・skill 率 / runs_with_unexpected を出力
```

### 2.1 なぜ2フェーズか

- **hook(書き込み)は安い・即時**: agent の停止/tool ごとに薄いスクリプトが走るだけ。
  SDK もプロセス駆動も要らない(= runtime 接続が低負荷)。
- **eval(計測)は後追い・バッチ**: 蓄積された trajectory を任意のタイミングで読み、
  数値化する。実 agent を再実行しないので再現も速い。

### 2.2 正規化が要(かなめ)

Claude も Codex も payload 形がほぼ同一なので、`from_post_tool_use` 一つで両対応。
以降の eval/store/gate はすべて `TrajectoryEvent` という共通語彙にしか触れない。
→ どの runtime の記録でも同じ計測パイプラインが流れる。

### 2.3 保持ポリシーの意味

- 残すのは **構造化シグナル**(成功・tool/skill 使用・想定外動き)= 傾向分析の素。
- 捨てるのは **raw trajectory** = 嵩むが、距離化された後は不要。
- これで store は「際限なく膨らむ運用ログ」にならず、bounded に保たれる。

### 2.4 envelope の役割

- envelope を渡さない = 計測モード(観測物を全許可、想定外は出ない)。
- `eval-envelope.json` を置く = 強制モード(allowed_tools / write_targets / expected_skills の
  外を `unexpected_actions` として検出)。**逸脱監視を opt-in で段階導入できる。**

---

## 3. 一文ずつ

- **spec 判定**: 仕様書(or 明示フラグ)が有るときだけ完了 loop を回す。無ければ一発で終える。
- **hook→eval**: hook が実行のたびに正規化 trajectory を書き、`make measure` が後からそれを
  読んで tool/skill/想定外/成功を数値化し、構造化シグナルだけを保持する。
