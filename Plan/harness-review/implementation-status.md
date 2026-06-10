# ハーネス実装 証跡(implementation status)

最終更新: 2026-06-10
ブランチ: `agent/foundation-subagent-spec-workflow/main/spec-workflow`
基点文書: `harness-implementation-report.md`(診断)/ `minimum-foundation-build-plan.md`(S1-S5)
/ `measurement-and-context-build-plan.md`(②③⑤・runtime モード)

---

## 1. 一気実装で到達した地点

agent 非依存の port を骨格に据え、その上に「事実で完了を判定する」キーストーンと
「効果を測る」eval を一直線に積んだ。**全 167 テスト green**、ruff / format /
mypy(30 files)/ shellcheck すべてクリーン。

```
port(seam)→ trajectory(記録)→ eval scoring(測定)→ escape scan + hack-catch(反証)
   → completion gate(完了判定)→ handoff(context)→ test freeze → eval runner(実行)
```

## 2. コミット列(証跡)

| commit | 内容 | 対応 |
|---|---|---|
| c708ce6 | runtime seam(port + MockRuntime + 純粋性の機械強制) | 骨格 |
| 34ba3c7 | trajectory recorder(JSONL 永続化 + RunSummary) | ③ |
| ad1862a | eval scoring(成功率 / tool-call 率 / skill 率 / 想定外行動) | ② |
| 3a95d14 | escape scanner + hack-catch(現行ゲートの穴を数値化) | S2 / ② |
| a0745e3 | 完了ゲート + handoff + test freeze + eval runner | S1 / ⑤ / S4 / ② |
| c54c4c7 | spec-gated loop + 結果報告契約 + eval 保持ストア | G8 / 委任 / G4 |

## 3. 実装済みコンポーネント(`src/workflow_core/`)

| モジュール | 役割 | 状態 |
|---|---|---|
| `runtime.py` | 正規化語彙 + `AgentRuntime` port + `to_jsonl` | ✅ pure |
| `trajectory.py` | `record_run` / `RunSummary`(③) | ✅ |
| `evaluation.py` | `score_run` / `aggregate` / `hack_catch_rate`(②) | ✅ |
| `gate.py` | `scan_escapes` / `build_verdict`(S2) | ✅ |
| `completion.py` | `run_completion_gate` / `EvidenceRecord` / `write_evidence`(S1) | ✅ |
| `handoff.py` | `build_handoff` / `render_handoff`(⑤ 種) | ✅ |
| `frozen.py` | `frozen_path_violations`(S4) | ✅ |
| `loop.py` | `run_loop`(spec-gated・非spec は single-pass・失敗予算 escalate)| ✅ |
| `report.py` | `ResultReport` / `build_result_report`(agent 間は結果報告のみ・bounded)| ✅ |
| `metrics_store.py` | `MetricsStore`(sqlite・raw 退役 / 構造化シグナル保持)| ✅ |

スクリプト: `scripts/completion_gate.py`(`make gate`)/ `check-frozen-paths.py`
(`make check-frozen`、pre-commit 配線済み)/ `run_eval.py`(`make eval`)。

## 4. 実機検証で確認したこと

- **`make eval`**: honest 通過 / hack-bait(現行ゲート)すり抜け / hack-bait(scan)捕捉。
  `hack_catch_rate=0.5`(scan の有無で 0%↔100% が確認できる構造)。
- **`make gate`**(`FOUNDATION_PROJECT_ID=harness-bootstrap`): checks 再実行 →
  diff hash 束縛 → `artifact/<project>/evidence/check-<hash>.json` を agent-read-only
  で生成 → check-required 失敗を観測して**完了をブロック**(exit_code=2 記録)。
  自己申告ではなく観測事実で判定するキーストーンが意図通り動作。

## 5. 既知の問題(私の変更外)

- `make gate` / `check-required` は現在 **既存コミット `31c3995`(6/9・別作業)** の
  `artifact/workflow-ui-commondb-20260608/.../contract.yaml` 内 "secrets, vault/..."
  を gitleaks(generic-api-key)が**誤検知**して失敗する。私の変更はワーキングツリー
  走査でクリーン。`.gitleaks.toml` の allowlist 追加 or 該当 artifact の修正が必要だが、
  別作業の責務のため本実装では触っていない。完了ゲートがこれを正しく surface した。

## 6. 残務(意図的に分離)

| 項目 | 理由で後回し | 次の一手 |
|---|---|---|
| **S5 governance 撤去** | 6 skills + legacy checker + heavy template の削除は既存 green スイート(skill-route/scorecard/audit 等テスト)を広範に壊す。慎重な別 PR が必要 | 撤去対象を archive へ移し、対応テストを同時更新 |
| **drive adapter(Codex SDK / `claude -p`)** | 実 runtime 結合。port は確定済みなので薄い翻訳器1個 | ネイティブイベント → `TrajectoryEvent` 変換 adapter を `workflow_adapters/` に |
| **observe adapter(Codex hook / Claude hook)** | 日常利用の記録経路 | hook payload → `TrajectoryEvent`、stop hook → `completion_gate.py` 起動 |
| **完了ゲートの hash 再束縛強化** | 現状 `git diff HEAD`(untracked 未包含)。レビュー後編集検出は diff hash で可能 | untracked 込みの diff 取得 + S3 review verdict の hash 束縛要求 |
| **S3 scope cross review** | subagent 構成が要る | fresh-context reviewer を drive adapter 経由で |
| **context budget/compaction(⑤ 後半)** | handoff 種は完了。token 駆動 compaction が残 | trajectory の token_usage を閾値判定に |
| **gitleaks 誤検知の解消** | 上記 5 | allowlist or artifact 修正 |

## 7. 一文

完了の宣言権は agent から gate へ移り、その効果は eval で数値化できる状態になった。
残るは「実 runtime を port に挿す(adapter)」と「heavy contract を畳む(S5)」の2系統。
