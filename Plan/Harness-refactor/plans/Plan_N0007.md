# Dev-Foundation-ver2 — 改善タスクブリーフ（Codex 向け）

Repo: https://github.com/tana-alt/Dev-Foundation-ver2

このドキュメントは、2つの独立レビュー（アーキテクチャ整合性レビュー＋戦略改善案）を、エージェントが着手できる作業指示に統合したものです。各タスクは「対象 → やること → 完了確認」で記述しています。

---

## 0. リポジトリ前提（共有コンテキスト）

このリポジトリは Web アプリや CLI 製品ではなく、**エージェントの開発作業を「契約・証拠・権限・レビュー」に変換する基盤**。

- 起点: `AGENTS.md` ＋ 3 つの契約ドキュメント（`docs/01`〜`docs/03`）
- 実行経路: `./harness` CLI（`workflow_core.contract_harness.cli`）
- フロー: `prepare → verify → submit → review → gate → integrate → land → push`
- 状態/証跡: tracked repo ではなく Git common dir 配下 `harness-runtime/`（object store ＋ SQLite event chain）
- 完了判定: 成果物の有無ではなく「検証・レビュー・証跡が揃っているか」

**作業原則（このリポジトリ自身のルールに従うこと）**
- 記録は成果物ではなく道具。records-only / mock / dry-run は未完了扱い。
- 実装は証拠に従い、保護すべき不変条件を先に述べ、検証手段を明示する。
- 既存の制御プレーン・state・evidence 構造を壊さないこと（特に P0/P1）。

> 注意: 一部の指摘は「公開リポジトリ内容から確認できなかった」前提で書かれている。**着手前に実ファイルの有無を必ず確認**し、既に存在する場合はタスクを skip して報告すること。

---

## P0 — 整合性の穴（最優先・基盤が成立するために必須）

### P0-1. `.harness` 制御プレーンの最小構成を追加
- **対象**: `.harness/owners.yaml`, `.harness/verifiers.yaml`, `.harness/policy.yaml`, `.harness/bottleneck.yaml`, `.harness/tasks/example/task.yaml`
- **背景**: `config.py` の `CONFIG_FILES = ("bottleneck.yaml", "owners.yaml", "verifiers.yaml", "review.yaml")` を `prepare` が必須読み込みする。現状 tracked なのは `review.yaml` と `semantic_ai_reviewer.py` 中心で、他が見当たらない。これが無いと通常の harness flow が成立しない（テスト fixture は一時生成している）。
- **やること（いずれか）**:
  - (a) 最小サンプルを tracked repo に追加する、または
  - (b) 意図的に generated とするなら README の Architecture 節に「tracked ではなく setup/generated」と明記し、`./harness init` 初期化コマンドを用意する。
- **完了確認**: クリーンな clone で `./harness prepare <example_task>` が config 不足で失敗しないこと。

### P0-2. `check-foundation` に harness の architecture/state/strict チェックを組み込む
- **対象**: `Makefile`
- **背景**: `check-harness-architecture` / `check-harness-state` / `check-harness-strict` / `check-harness-arch-all` は存在するが、`check-required` / `check-ci` / `check-foundation` の経路に含まれていない。中核が Contract Harness である以上、foundation gate に入っていないのはリスク。
- **やること**: `check-ci`（または `check-required`）に `check-harness-arch-all` を組み込む。CI 時間が問題なら、`architecture` と `state` は常時、`strict` は別 job に分離。
  ```make
  check-ci: check-toolchain check-required check-harness-arch-all check-cd
  ```
- **完了確認**: `make check-foundation` が harness architecture/state を実行する。

### P0-3. mypy strict を `src` 本体に拡張
- **対象**: `pyproject.toml`
- **背景**: `mypy.strict = true` だが `files = ["tests"]` のみ。state/evidence/policy/daemon という壊れると危険な本体が strict 対象外。
- **やること**: 段階的でよいので `src` を対象に含める。一括が無理なら `domain` / `application` / `adapters` / `config.py` / `contract.py` / `verify.py` / `gate.py` から順に。
  ```toml
  [tool.mypy]
  files = ["src", "tests"]
  ```
- **完了確認**: 対象拡張後に `make typecheck` が通る（段階導入なら対象モジュールのみ）。

### P0-4. verifier evidence hash の強化
- **対象**: `verifier.py`, `machine_evidence_hash()`, `command_runner.py`
- **背景**: `verifier.py` は command を `shell=True` で実行。evidence hash は verifier の id と status 中心で、command string / exit code / stdout/stderr を含まない。config 生成が広がると injection・改ざん検知の穴になる。
- **やること**:
  - verifier command schema を argv list 対応にし、shell 実行を opt-in 化。
  - evidence hash に `command`, `exit_code`, `timed_out`, `stdout_sha256`, `stderr_sha256` を含める（`command_runner.py` は既に stdout/stderr/tail を取得しているので拡張は自然）。
- **完了確認**: 同一 command でも exit code / 出力が変われば evidence hash が変わること。

---

## P1 — 運用ハードニング（次点）

### P1-1. CLI の god object 分割
- **対象**: `src/workflow_core/contract_harness/cli.py`
- **やること**: command registration を `commands/task.py`, `commands/review.py`, `commands/integration.py`, `commands/daemon.py`, `commands/session.py`, `commands/acp.py` に分割。`cli.py` は parser composition と top-level error handling に限定。
- **完了確認**: 既存サブコマンドの挙動を変えずにリファクタ（テストが全通過）。

### P1-2. `daemon start` の未実装状態を解消
- **対象**: `cli.py` の parser ／ `_daemon_command()`
- **背景**: parser に `daemon start` があるが、handler は `run/ping/status/stop` のみ解決し `start` は `_deferred()` に落ちる。
- **やること（いずれか）**: `start` を実装する／MVP 外なら parser から削除する／実行時に `daemon run --foreground` 等の明確な案内を返す。

### P1-3. strict / non-strict 境界の明確化
- **対象**: `roles.py`（`current_role()` のデフォルト `writer`）, `./harness status`, README
- **やること**:
  - destructive / external-write 系 command では `HARNESS_ROLE` の明示を必須化。
  - `./harness status` に current role と strict/non-strict mode を出力。
  - README に「local orchestration mode」と「local-strict daemon mode」の比較表を追加。
- **注意**: role check は security boundary ではない（README 明記）。capability protection は daemon strict mode 側。

### P1-4. worktree reset の安全性・UX
- **対象**: `worktree.py`
- **背景**: 既存 worktree 再利用時に `git reset --hard` ＋ `git clean -fd`。writer/reviewer は dirty 破壊的再利用を拒否するが、integrator は reset されやすく事故が分かりにくい。
- **やること**: reset 前の対象 path/kind/marker/dirty を `--dry-run` で確認可能にする。integrator でも marker が想定外なら reset 拒否。`worktree reset` と `worktree create` を分離して暗黙 reset を減らす。

### P1-5. `integrated` / `landed` の意味の明確化
- **対象**: `integration.py`（`integrate_task()`）, status 出力, README
- **背景**: `integrate_task()` は review/gate を通して `integration-result.json` を書くだけで land commit は作らない。利用者が `integrated`=「main に入った」と誤解しうる。
- **やること**: `integrated` を `gated` / `ready_to_land` 寄りの名称へ（互換が必要なら `land_status = not_landed` を併記）。`./harness status` で phase と次の推奨 command を表示。

### P1-6. CI タイムアウト見直し
- **対象**: CI workflow（`.github/workflows/...`）
- **背景**: job timeout 10 分。gitleaks / shellcheck / pytest / CD readiness ＋将来の harness strict を含めると不足の恐れ。
- **やること**: check を job 分割（harness tests を別 job）、timeout を 15〜20 分へ、fast/full を matrix 化。

---

## P2 — 戦略的機能（独自性の強化・基盤を「信頼の生成装置」にする）

> いずれも既存の state/evidence/policy 構造の上に **read-only から段階導入**すること。enforcement をいきなり強くしない。

### P2-1. Proof Passport（最初に着手すべき P2）
- **コマンド**: `./harness passport <task_id>`
- **目的**: 分散した証拠（`contract.lock.json` / `verify-result.json` / `candidate.diff` / review verdict / `gate-result.json` / integration result）を**再実行せずに 1 枚へ正規化**した read-only 証明書を出す。新しいログを増やすのではなく「この成果物は読む価値があるか」の入口にする。
- **出力イメージ（JSON ＋ Markdown）**:
  ```text
  Task / Goal / Scope(allowed,forbidden)
  Candidate: diff sha, base sha
  Machine proof: pass/fail + command + evidence hash
  Review proof: quorum, fresh/stale, blockers
  Policy proof: human gate? external write? protected action?
  State proof: current phase, event hash chain head
  Next action: continue / rework / ask human / land / push blocked
  ```
- **実装方針**: `status` ＋ `gate-result.json` ＋ StateStore の integrity 検証（event payload hash / previous event hash / artifact hash）を集約。改ざん検知の上に乗せる。最小実装は集約と整形のみ。
- **なぜ最初か**: 既存構造を壊さず read-only で追加でき、既知リスク（stale artifacts、generic exit 1、blocked 過負荷、task intent 欠落など）に対し「今この task は何待ちか」を 1 枚で示せる。後続改善の土台になる。

### P2-2. Counterfactual Reviewer
- **対象**: review lane（`reader-correctness` / `reader-scope` / `semantic-ai` の隣に追加）
- **目的**: レビューを「承認」から「反証探索」へ。「この candidate が正しいなら何が壊れてはいけないか」を 3 つ以内で生成し、可能なら軽量検査する。
  ```text
  例) 境界条件を1つ変えても verifier が通る → 検証が弱い
      allowed_paths 外への影響が diff index に出る → scope が弱い
      acceptance criterion に対応する proof.command が無い → 未証明
  ```
- **段階導入**: ①read-only で反証候補を出すだけ → ②temp worktree で最大 3 probe 実行 → ③high-risk scope のみ gate 投入。
- **整合**: acceptance audit（criterion ごとの runnable proof）と eval 側 metrics（unexpected actions / tool-call rate / hack catch rate）の土台に乗る。

### P2-3. Capability Economy
- **対象**: `prepare` 時の tool 露出, `agent-tools.json`, daemon capability token, gate metrics
- **目的**: 最初から全ツールを渡さず、scope/acceptance/expected envelope から最小ツールセットのみ付与。追加が必要になったら理由＋証拠つきで escalation 申請させる。
  ```json
  { "request": "capability.escalate", "task_id": "...",
    "need": "run broader verifier",
    "reason": "changed shared behavior under src/workflow_core",
    "evidence": ["candidate_diff_sha256", "scope_map"] }
  ```
- **段階導入**: 現状 `.harness/review.yaml` は `reject_unexpected_actions: false`。**observe-only → warning → high-confidence scope のみ block** の順で。いきなり enforcement を強めると harness が重くなる。
- **最終形**: agent が「何をしたか」だけでなく「なぜその能力が必要だったか」まで証拠化される。

---

## 対象外（やらないこと・優先度を上げないこと）

- **dashboard の追加**: storage contract が runtime queue / lock ledger / dashboard / broad operational logs を repo truth に入れない方針。違反。
- **repo 内 scheduler / keep-alive loop**: operational boundary。まず status / next-action を改善し、必要なら外部 continuation runner にする方針。
- **ドキュメント増量**: active docs は短く詳細は routed reference という思想が既にできている。増やすべきは説明量でなく「状態を迷わず読める機械的な出口」。

---

## 推奨着手順

1. **P0-1〜P0-4**（基盤が成立・安全に回るための整合性）
2. **P2-1 Proof Passport**（read-only で土台になる独自機能）
3. **P1-1〜P1-6**（運用ハードニング）
4. **P2-2 Counterfactual Reviewer → P2-3 Capability Economy**（observe-only から）

各タスク着手前に、レビュー記載の「未確認」前提を実ファイルで検証し、既に解決済みなら skip して報告すること。

semantic reviewへのHandoffやreview後のintegrate機械処理へのHandoffの方法やACP通信の方法やACP候補一覧などの情報をエージェントに与えれられていることを確認してください。
エージェントに与える情報量は多大になりすぎないようにしてAGENTS.mdなどで確認できるようにしておいてください。
