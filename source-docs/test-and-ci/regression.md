---
status: active
owner: human
last_validated_at: 2026-04-12
source_of_truth_level: primary
supersedes: null
related_code:
  - .github/workflows/ci.yml
  - src/services/verification
  - tests
---

# Regression And Evaluation

## Purpose
- 通常 CI と AI eval を混同せず、回帰検知の責務を分ける
- unit / deterministic / rubric / trace の 4 層を定義する

## Evaluation Layers

## Unit Test
- repo の通常 test runner を使う
- 変更箇所に最も近い最小 suite を優先する
- Python テストは `pytest` を基準とする
- 失敗時は局所修正を優先し、不要な広域変更で逃がさない

## Deterministic Checks
- 機械的に pass/fail が確定する検査を置く
- 現在の required deterministic checks は次とする
  - `ruff`
  - `mypy`
  - `architecture`
  - `doc-freshness`
  - `dangerous-diff`
- 必要に応じて次を追加してよい
  - JSON parse
  - schema validate
  - compilation / build
  - function-call accuracy
  - exact match
  - custom Python checks

## Rubric Eval
- LLM judge または adaptive rubric を使って instruction following、quality、grounding、安全性を採点する
- rubric eval は通常 CI と分離して運用する
- rubric は task ごとに変えてよいが、採点軸は明文化する
- rubric の結果は merge gate の唯一条件にしない

## Trace And Online Eval
- tracing は常時オンを原則とする
- production traces に online evaluators を適用する
- anomaly、safety、format failure を抽出する
- failing traces は dataset 化し、再現可能な失敗例として保存する

## Offline Regression
- failing traces と既知回帰ケースから評価 dataset を作る
- failure cluster ごとに targeted evaluator を追加する
- offline regression experiment で改善候補を比較する
- pass した変更だけを再 deploy 候補とする

## GitHub And CI Split
- 通常 CI は lint / unit / build / smoke を担当する
- AI eval CI は deterministic checks + rubric batch eval を担当する
- PR review の AI コメントは補助 signal として扱う
- merge gate は Human review + CI pass とする
- 本番後は traces を回収し、dataset を更新する

## Current Repo Mapping
- unit: `uv run pytest` と task 単位の最小 suite
- deterministic: `make lint`, `make typecheck`, `make check-architecture`, `make check-doc-freshness`, `make check-dangerous-diff`
- rubric: まだ未実装。導入時は CI と job を分離する
- trace: まだ未実装。導入時は production trace 収集先と dataset 化ルールを明示する

## Implementation Notes
- CI は自己申告ではなく機械判定を正とする
- rubric と trace は signal を増やす目的であり、通常 CI を置き換えない
- evaluator を追加したら、対象 failure class と期待検知内容を docs に残す
