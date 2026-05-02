---
status: active
owner: human
last_validated_at: 2026-04-12
source_of_truth_level: primary
supersedes: null
related_code:
  - Makefile
  - .github/workflows/ci.yml
  - .github/pull_request_template.md
  - apps
  - src
  - tests
---

# Build Test PR Workflow

## Purpose
- 実装から PR 生成までの標準フローを 1 か所にまとめる
- `AGENTS.md` の短い要約を実務手順へ展開する

## Standard Flow
1. Plan-only でスコープを確定する
2. repro 手順、対象ファイル、影響範囲を task docs に列挙する
3. 最小変更で実装する
4. 変更箇所に最も近い最小 suite を先に回す
5. lint、typecheck/build、smoke check を順に回す
6. repro を再実行して期待どおりに直ったことを確認する
7. docs/status を更新する
8. PR を作成し、要約、検証結果、既知リスクを書く

## Environment Bootstrap
- Python 環境は `uv sync --group dev` を使う
- API のローカル実行は `make run` または `make knowledge-up` を使う
- `apps/web/` と `apps/obsidian-plugin/` は必要時のみ package manager install を行う
- Docker 検証が必要な場合だけ `make compose-up` を使う

## Commands
### Install
- `uv sync --group dev`
- `cd apps/web && npm install`
- `cd apps/obsidian-plugin && npm install`

### Run
- `make run`
- `make knowledge-up`

### Build
- `cd apps/web && npm run build`
- `make knowledge-plugin-build`

### Lint And Typecheck
- `make lint`
- `make typecheck`

### Test
- 変更箇所に近い最小 suite を優先する
- `uv run pytest tests/unit/<target>`
- `uv run pytest tests/integration/<target>`
- repo 全体確認が必要な場合は `make test`

### Required Deterministic Checks
- `make check-architecture`
- `make check-doc-freshness`
- `make check-dangerous-diff`
- まとめて実行する場合は `make check-required`

## Verification Order
1. smallest relevant test suite
2. `make lint`
3. `make typecheck`
4. 必要なら app-local build
5. smoke check
6. `make test` または task が要求する suite
7. `make check-architecture`
8. `make check-doc-freshness`
9. `make check-dangerous-diff`

## Smoke Check
- API 変更時は対象 endpoint か画面の最小操作で疎通確認する
- `apps/web/` 変更時は affected page の表示と主要操作を確認する
- `apps/obsidian-plugin/` 変更時は plugin build と最短の command/view 動作を確認する
- smoke check は full E2E の代替ではなく、最短で壊れていないことを確認する目的で行う

## Repro And Scope Notes
- bug 修正時は再現手順を `Prompt.md` か `Implement.md` に残す
- 影響範囲は API、UI、DB、prompt、docs のどこに及ぶかを明示する
- scope 外の変更が必要になったら Plan を更新してから進める

## Docs And Status Updates
- canonical docs に影響があれば同ターンで更新する
- repo 構造変更時は `AGENTS.md` と `ARCHITECTURE.md` を同期する
- task 実行中の判断、コマンド、失敗、Verifier 結果は `docs/tasks/active/<task-id>/Log.md` に残す

## Branch And Commit
- AI の作業ブランチは `ai/task-*` を使う
- `main` へ直接 push しない
- commit は task 単位でレビュー可能な粒度に保つ
- commit message は scope が読める短い要約を使う

## PR Instructions
- `.github/pull_request_template.md` を埋める
- PR title は task か変更スコープが判別できる短い題名にする
- PR body には次を必ず入れる
  - Intent
  - Scope
  - Verifier Results
  - Docs
  - Risk
  - Human Review Focus
- risk summary には既知リスク、未検証部分、follow-up を短く書く

## Review And Merge Gate
- Copilot / Claude review は補助 signal として扱う
- merge gate は Human review + required CI pass とする
- 危険変更、依存追加、DB schema、auth / billing、CI/CD、GitHub Actions、secret / infra は別承認対象とする

## Done Criteria
- task docs の acceptance criteria を満たす
- repro が解消され、再現しない
- 必要な tests / checks / smoke が通る
- canonical docs と task status が同期されている
- PR に要約、検証結果、既知リスクが記載されている
