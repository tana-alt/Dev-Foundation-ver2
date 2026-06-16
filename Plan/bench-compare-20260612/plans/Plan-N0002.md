# 定量評価ツールセット指示書 改訂差分 (v1 → v2)

適用方法: 本書は元指示書(v1)への**差分のみ**を記述する。
「置換」= 該当セクションを丸ごと差し替え / 「追加」= 新設 / 「追記」= 既存セクション末尾に加える。
v1 と本書が矛盾する場合は本書を優先する。

---

## 0. 改訂サマリ

| # | 区分 | 対象 | 内容 |
|----|------|------|------|
| R1 | 置換 | metrics store | `samples` テーブル追加。集約値は導出値とする |
| R2 | 置換 | verdict | 4値判定 + bootstrap CI による統計判定 |
| R3 | 追加 | abrun | worktree AB 実行オーケストレータ(新規ツール) |
| R4 | 追加 | check | 機能的正しさゲートランナー(新規ツール) |
| R5 | 追加 | gate | AND 条件ポリシー集約(新規ツール) |
| R6 | 置換 | 共通 | exit code 規約の固定 |
| R7 | 置換 | harness-eval | 3種ケース構成(regression / improvement / neutral) |
| R8 | 追記 | mutation | diff-scoped mutation の必須化 |
| R9 | 追記 | scaling | オフセット付きフィットと判定基準の明文化 |
| R10 | 追記 | sqlperf | クエリ捕捉機構の指定 |
| R11 | 追記 | bench | 決定的測定モード(命令数) + peak RSS |
| R12 | 追加 | 共通 | 耐ゲーミング要件 |
| R13 | 置換 | 共通 | env_fingerprint の定義 |
| R14 | 追加 | trace-collector | スキーマ定義 |
| R15 | 置換 | 実装順序 | Phase 構成の改訂と受け入れ基準 |

---

## R1. metrics store スキーマ改訂【置換: §全体設計原則 3】

集約値(p50/p95/stddev)のみの保存では統計的判定が実行不可能なため、**生サンプルを第一級データとして保存**する。集約値は samples からの導出値であり、手書きで書き込んではならない。

```sql
runs(
  run_id TEXT PRIMARY KEY,
  task_id TEXT,
  worktree TEXT,
  commit_sha TEXT,
  started_at TEXT,
  env_fingerprint TEXT,      -- R13 の定義に従う sha256
  config_hash TEXT,          -- 測定ツール設定ファイルの sha256
  tool_versions_json TEXT,   -- {"bench": "0.3.1", ...}
  metadata_json TEXT
);

samples(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  iteration INTEGER NOT NULL,
  value REAL NOT NULL,
  unit TEXT,
  recorded_at TEXT
);
CREATE INDEX idx_samples_run_metric ON samples(run_id, metric);

-- 集約キャッシュ。samples から `store aggregate` コマンドで再生成可能であること
metrics(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  name TEXT,
  value REAL,
  unit TEXT,
  n_samples INTEGER,
  p50 REAL, p95 REAL, stddev REAL,
  metadata_json TEXT
);

verdicts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  baseline_run_id TEXT,
  metric TEXT,
  statistic TEXT,            -- "median" | "p95" など
  delta_pct REAL,
  ci_low REAL, ci_high REAL, -- delta_pct の 95% CI
  n_base INTEGER, n_cand INTEGER,
  threshold REAL,
  result TEXT,               -- pass | regression | inconclusive | error
  reason TEXT,
  policy_hash TEXT
);
```

- 単発測定値しか持たないツール(envprobe 等)は samples を省略してよいが、時間・回数系メトリクスを持つツール(bench / scaling / loadtest / sqlperf / mutation)は samples 保存を必須とする。
- キャッシュキー: `(commit_sha, config_hash, env_fingerprint)` が一致する既存 run があれば再測定をスキップできる(`--no-cache` で強制再測定)。

---

## R2. verdict 改訂【置換: §ツール 1. verdict】

### 判定値(4値)

`pass` / `regression` / `inconclusive` / `error`

`inconclusive` の新設が本改訂の核。分散が大きく判定不能な場合に regression と誤報すると、エージェントが偽回帰を延々と「修正」するループに入る。判定不能は判定不能として返し、再測定を要求する。

### 判定手順(mode: non_regression, lower_is_better の場合)

1. metrics store の `samples` から両 run の生値を取得する。**delta_pct と閾値の単純比較は禁止**。
2. 片側 n < 7 の場合 → `error` (reason: `insufficient_samples`)。
3. 外れ値処理: 両側 MAD 5σ 超を除外。除外率が 10% を超えたら `inconclusive` (reason: `excessive_outliers`)。
4. 統計量 T を計算(デフォルト median。`--statistic p95` 等で指定可)。
5. percentile bootstrap(resamples=10000, seed 固定・記録)で Δ% = (T_cand − T_base) / T_base の 95% CI を推定。
6. 判定:
   - CI 下限 > threshold_pct → `regression`
   - CI 上限 < threshold_pct → `pass`
   - CI が threshold_pct を跨ぐ → `inconclusive`
7. `inconclusive` 時は CI 幅 ∝ 1/√n の仮定で `suggested_additional_iterations` を出力に含める。

### 出力例(改訂)

```json
{
  "tool": "verdict",
  "metric": "bench.sort_large.wall_ms",
  "statistic": "median",
  "baseline_run_id": "base_001",
  "candidate_run_id": "cand_001",
  "n_base": 20, "n_cand": 20,
  "delta_pct": 11.3,
  "ci": [4.1, 18.9],
  "threshold_pct": 5.0,
  "result": "inconclusive",
  "reason": "95% CI [4.1, 18.9] straddles threshold 5.0",
  "suggested_additional_iterations": 25,
  "repro": "verdict compare --baseline base_001 --candidate cand_001 --policy policies/default.json"
}
```

### 制約

- threshold は CLI 引数では受けず、**policy file 経由でのみ**指定する(R12 参照)。
- comparison mode は v1 の4種(lower_is_better / higher_is_better / equal_required / non_regression)を維持。

---

## R3. abrun — AB 実行オーケストレータ【追加: 新規ツール 0】

### 目的

baseline / candidate の worktree 準備・依存同期・**インターリーブ測定**・run 記録を一手に引き受ける共通レイヤー。v1 ではこの責務がどのツールにも割り当てられていなかった。

### 背景

逐次測定(A を全部 → B を全部)はサーマルドリフト・コンテナ負荷変動による系統誤差が乗る。ABAB のインターリーブ(またはランダム化順序)で交互測定することで、時間的ドリフトを両群に均等に分配する。

### 責務

1. `git worktree add` で baseline / candidate を所定 ref から作成(既存なら検証して再利用)
2. worktree 毎の依存同期(`uv sync --frozen` / `pnpm install --frozen-lockfile` 等。envprobe の発見結果を利用可)
3. env_fingerprint の採取と runs への記録
4. 測定ツール(bench / loadtest 等)を **ABAB スケジュール**で交互起動し、samples を run_id 別に書き込む
5. サーバ型対象のライフサイクル管理: 起動 → healthcheck 待機 → 測定 → teardown。ポートは worktree 毎に分離
6. 完了時に `{baseline_run_id, candidate_run_id}` を返す

### 設定例

```json
{
  "baseline": {"ref": "main", "worktree": ".ab/base"},
  "candidate": {"ref": "HEAD", "worktree": ".ab/cand"},
  "setup": ["uv sync --frozen"],
  "measure": {"tool": "bench", "config": "bench.target.json"},
  "iterations": 20,
  "warmup": 3,
  "schedule": "interleaved",
  "cooldown_sec": 1,
  "server": {
    "start": "uv run uvicorn app:app --port {port}",
    "healthcheck": {"method": "GET", "path": "/health", "timeout_sec": 30}
  }
}
```

### 注意

- `.ab/` 配下の worktree はタスク終了時に `abrun clean` で破棄可能であること。
- 測定ツール単体でも動くこと(abrun 必須にしない)。ただし baseline 比較を行う場合は abrun 経由を標準経路とする。

---

## R4. check — 機能的正しさゲートランナー【追加: 新規ツール】

### 目的

envprobe が**発見**した検証コマンド(test / lint / typecheck / build)を**実行**し、構造化結果を metrics store に記録する。性能比較は candidate が機能的に正しいことが前提条件であり、check はその前提を機械化する。

### 機能

- envprobe の出力(または明示 config)からコマンド系列を取得し、指定 worktree で実行
- 各コマンドの pass/fail、所要時間、失敗詳細(失敗テスト名のリスト等)を記録
- 全コマンド AND で overall を決定

### 出力例

```json
{
  "tool": "check",
  "worktree": ".ab/cand",
  "results": {
    "test":      {"status": "pass", "duration_s": 41.2, "command": "uv run pytest"},
    "lint":      {"status": "pass", "duration_s": 3.1,  "command": "uv run ruff check"},
    "typecheck": {"status": "fail", "duration_s": 12.8, "command": "uv run pyright",
                  "failures": ["src/core/pricing.py:120: error: ..."]}
  },
  "overall": "fail"
}
```

---

## R5. gate — ポリシー集約【追加: 新規ツール】

### 目的

v1 は「メトリクスは AND 条件のゲート」と書きながら、AND を集約するツールが存在しなかった。gate は policy file に列挙された条件をすべて評価し、**単一の exit code と構造化レポート**に集約する。エージェントの最終分岐点はここ 1 箇所になる。

### policy file 例

```json
{
  "policy_version": 1,
  "conditions": [
    {"tool": "check",    "metric": "overall",              "require": "pass"},
    {"tool": "verdict",  "metric": "bench.core.wall_ms",   "mode": "non_regression", "threshold_pct": 5.0},
    {"tool": "verdict",  "metric": "loadtest.search.p95",  "mode": "non_regression", "threshold_pct": 10.0},
    {"tool": "mutation", "metric": "mutation_score",       "mode": "non_regression", "threshold_pct": -3.0},
    {"tool": "sqlperf",  "metric": "user_list.query_count","mode": "equal_required"}
  ],
  "on_inconclusive": "retry_then_fail",
  "max_retries": 2
}
```

### 出力

条件毎の verdict 一覧 + 最終 result + `policy_hash`。inconclusive を含む場合の扱いは policy の `on_inconclusive` に従う(`retry_then_fail` / `fail` / `pass_with_warning`)。

---

## R6. exit code 規約【置換: §各ツールに必須のインターフェース 内「exit codeで成功/失敗を表現」】

全ツール共通で以下に固定する。**品質判定の否(1)とツール自体の実行失敗(3)を厳密に区別**する。

```
0 = pass(non-regression / improvement を含む)
1 = regression または gate fail(品質判定としての否)
2 = inconclusive(再測定を要求)
3 = tool error(測定不能・設定不正・前提条件欠落・依存欠落)
```

エージェントの分岐規約: 1 → 修正を試みる / 2 → iterations を増やして再測定 / 3 → 測定系の問題としてエスカレーション(コード修正に向かわない)。

---

## R7. harness-eval 改訂【置換: §ツール 8. harness-eval の「機能」】

seeded regression のみのスイートでは false positive 率が測定できない。ケース種別を 3 種で構成する。

```
ケース種別(各 1/3 程度):
- regression  : 既知の劣化を注入。検出されるべき
- improvement : 既知の改善を注入。改善として報告されるべき
- neutral     : 無変更または性能無関係のリファクタ。pass されるべき

集計指標:
- recall            (regression ケースの検出率)
- false_positive_rate (neutral を regression と誤判定した率)
- inconclusive_rate (全ケース中の判定不能率)
- sign_accuracy     (improvement を改善方向として正しく報告した率)

suite pass 基準例: recall ≥ 0.90 AND FPR ≤ 0.05
```

neutral ケースは閾値・デフォルト iterations の**較正(calibration)**にも使用する。inconclusive_rate が高すぎる場合は iterations のデフォルトを引き上げる。

---

## R8. mutation 改訂【追記: §ツール 6. mutation】

フル mutation は数十分〜数時間かかり、エージェントの修正ループ内では使用不能。**diff-scoped mutation を必須機能**とする。

```
1. git diff baseline..candidate で変更行を特定
2. 変更行に重なる mutant のみ生成(mutmut: paths_to_mutate + 行フィルタ)
3. time budget(default 600s)を設ける。超過見込みなら mutant を乱択サンプリング
   (seed を記録)し、score は推定値 + CI として報告する
4. フル mutation は nightly / harness-eval 用とし、エージェントループでは diff-scoped のみ
```

---

## R9. scaling 改訂【追記: §ツール 3. scaling】

素朴な log-log 回帰は小さい n での固定オーバーヘッド(プロセス起動・import 等)で指数推定がバイアスする。以下を仕様化する。

```
モデル   : t(n) = a + b·n^k(a = 固定オーバーヘッド項)を非線形最小二乗でフィット
データ   : 各サイズ r 回繰り返し、中央値系列に対してフィット。
           k の CI は繰り返しに対する bootstrap で推定
判定     : Δk = k_cand − k_base。Δk の CI 下限 > 0.25 → regression
品質ガード: 適合度 R² < 0.98 またはサイズ系列 < 4 点 → inconclusive
実行ガード: per-size timeout(超過したらそのサイズ以降を打ち切り、censored として記録)
           + 全体 wall budget
```

---

## R10. sqlperf 改訂【追記: §ツール 5. sqlperf】

v1 はクエリ捕捉機構が未指定で、ここが実装の大半を占める。以下を指定する。

```
捕捉機構(最低限 sqlite3 + SQLAlchemy を実装。他は段階的に追加):
- SQLAlchemy : event.listen(engine, "before_cursor_execute" / "after_cursor_execute")
- Django     : test.utils.CaptureQueriesContext
- sqlite3    : connection.set_trace_callback
- Postgres   : pg_stat_statements スナップショット差分(+ 任意で auto_explain)

N+1 検出:
- SQL のリテラルを除去して正規化 → テンプレート単位でカウント
- 1 operation(1 リクエスト / 1 関数呼び出し)内で同一テンプレートが
  閾値(default 10)以上 → flag

EXPLAIN ANALYZE の注意:
- 実クエリを実行するため、トランザクション内で実行し ROLLBACK する
- 書込系クエリはデフォルトで EXPLAIN のみ(ANALYZE は --allow-write-analyze 明示時のみ)
```

---

## R11. bench 改訂【追記: §ツール 2. bench】

### 決定的測定モード

wall-clock はコンテナ環境でノイズが大きい。CPU バウンドな対象には命令数カウントによる決定的測定モードを追加する。

```
--mode wallclock(default)| instructions

instructions モード:
- perf stat -e instructions:u が使えればそれを優先
- 使えない環境(コンテナで perf_event 不可)では valgrind --tool=cachegrind の Ir を使用
- 決定的なので iterations=1〜3 で足り、threshold_pct を 1% 程度まで絞れる
- I/O・並行性が支配的な対象には不適(wallclock を使うこと)
```

### peak RSS

全モード共通で `getrusage(RUSAGE_CHILDREN)` または `/usr/bin/time -v` から peak RSS を採取し、`*.peak_rss_mb` として samples に記録する。loadtest も同様にサーバプロセスの RSS を記録する。

---

## R12. 耐ゲーミング要件【追加: §全体設計原則に「6」として追加】

エージェントが指標を直接最適化対象にして閾値や測定系を改変する事態を構造的に防ぐ。

1. **policy file と閾値はエージェント書込領域の外に置く**(read-only mount または worktree 外の harness 専用ディレクトリ。例: `/harness/policies/`)。gate は許可ディレクトリ外の policy を拒否する。
2. **ツールは harness 環境にインストールし絶対パスで起動する。** worktree 内の同名スクリプトを PATH 経由で拾わない。
3. **runs に config_hash / tool_versions / policy_hash を必須記録**し、trace-collector で追跡可能にする(R1, R14)。
4. verdict / gate は threshold を CLI 引数で受けない(R2)。

---

## R13. env_fingerprint の定義【置換: runs.env_fingerprint の内容】

以下のフィールドを持つ canonical JSON(キーソート・空白なし)の sha256 とする。

```json
{
  "cpu_model": "...",
  "nproc": 8,
  "cgroup_cpu_quota": "400000/100000",
  "cgroup_mem_limit_mb": 8192,
  "kernel": "...",
  "os_image": "ubuntu:24.04",
  "runtime_versions": {"python": "3.12.4", "node": "22.3.0"},
  "lockfile_hashes": {"uv.lock": "sha256:...", "pnpm-lock.yaml": "sha256:..."},
  "cpu_governor": "performance | unknown",
  "virtualized": true
}
```

fingerprint が baseline / candidate 間で不一致の場合、verdict は warning を出力に含める(判定は続行するが trace に記録)。

---

## R14. trace-collector スキーマ【追加: §ツール 9. trace-collector に「形式」として追加】

```
形式: セッション毎の JSONL(append-only)。SQLite への取り込みは別コマンド(trace ingest)

イベント封筒:
{
  "ts": "2026-06-12T10:31:04.512Z",
  "session_id": "sess_8f2a",
  "seq": 412,
  "actor": "subagent:reader-2",
  "event": "tool_call",
  "payload": { ... },
  "refs": {"run_id": "cand_001", "policy_hash": "sha256:...", "config_hash": "sha256:..."}
}

event 列挙:
tool_call, tool_result, command, diff_applied, file_touched, decision,
check_result, metric_recorded, verdict, gate_result, escalation
```

---

## R15. 実装順序の改訂【置換: §実装順序】

```
Phase 1a: metrics store(samples 含む)→ abrun → verdict
Phase 1b: envprobe → check → gate → trace-collector
Phase 2 : bench(wallclock + instructions)→ scaling → mutation(diff-scoped)
Phase 3 : loadtest → sqlperf
Phase 4 : harness-eval(3種ケース)→ calibration → FP/FN 分析
```

### Phase 1 受け入れ基準

> seeded regression 1 件 + neutral 1 件のミニスイートに対し、
> `abrun → verdict → gate` が end-to-end で動作し、
> regression ケースに exit 1、neutral ケースに exit 0 を返すこと。
> inconclusive 発生時は exit 2 と suggested_additional_iterations を返すこと。

### 成果物リストへの追加

v1 の成果物リストに以下を追加する。

```
tools/abrun
tools/check
tools/gate
policies/default.json(エージェント書込領域外に配置)
docs/exit_codes.md(R6 の規約)
```

---

## 改訂後の最重要方針(v1 §最重要方針の末尾に追記)

最初に作るべき中核は v1 の `verdict + metrics store + envprobe` から
**`metrics store(samples)+ abrun + verdict + check + gate`** に改める。
測定(abrun)・統計判定(verdict)・前提条件(check)・集約(gate)の 4 点が揃って初めて、
人間レビューを外した自動ループが成立する。envprobe は check の入力供給源として Phase 1b に置く。