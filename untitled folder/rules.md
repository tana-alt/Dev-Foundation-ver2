---
status: active
owner: steward
last_validated_at: 2026-04-24
source_of_truth_level: primary
supersedes: null
related_code:
  - src/prompts
  - docs/index.md
  - src/services/docs/freshness.py
---

# Rules

# AI Coding Principles

この文書は、AI に読ませるための **短いコーディング方針** をまとめたもの。
詳細な実装手順やタスク固有仕様は別文書に分離する。

## Purpose
AI 生成コードの速度を活かしつつ、変更容易性・検証容易性・事故率低下を優先する。

## Core Principles
- **KISS**: 実装は可能な限り単純に保つ
- **YAGNI**: 今必要なものだけ実装する
- **DRY**: 重複は抽象化または共通化で減らす
- **SOLID**: 変更に強い責務分離を意識する

## Function And State Rules
- 副作用を最小化する
- 可能な限り純粋関数を優先する
- 状態は局所化し、広域の可変状態を増やさない
- state / status / mode などの canonical 値はコード側の enum / schema に固定する
- 自然言語メモを state の正本として扱わない

## Coding Rules
- 既存の canonical docs と architecture 境界に従う
- 小さく変更し、小さく検証する
- 無関係な差分を混ぜない
- 仮実装や一時しのぎの分岐を増やしすぎない
- 例外処理は握りつぶさず、失敗理由が追跡できるようにする
- I/O, API, DB, UI は境界を明確に分離する
- 型・schema・契約を先に固定し、その後に実装する
- repo 外文書を source of truth にしない

## AI Generated Code Policy
- AI はゼロから広く書き換える前に、既存コードと依存方向を確認する
- UI 変更は見た目だけでなく状態遷移と例外系も確認する
- バックエンド変更は API 契約・schema・永続化・検証への影響を確認する
- 不明点がある場合でも勝手に state や role を増やさない

## Implementation Tooling Policy
- 実装前に Serena で codebase を探索し、symbol overview, definition, references を優先して、ファイル構造・主要シンボル・依存関係・変更影響範囲を要約してから編集する
- 実装が現在の外部 API / library 挙動に依存する場合は Context7 または公式 docs を確認する。repo 内 docs / contract の整理だけで閉じる場合は、不要に外部調査へ広げない
- package や directory が存在することだけを workflow 組み込み済みの根拠にしない。特に LangGraph / `src/graph/` は現時点の Obsidian app workflow 正本ではなく、runtime contract が明示的に接続した場合だけ実行フローとして扱う
- 変更は小さく保ち、最小の意味ある検証で閉じる

## Verification Policy
変更後は少なくとも以下を確認する。
- lint
- type check
- unit / integration test
- 回帰しやすい箇所の手動確認

verifier fail 時は、広範囲な作り直しではなく局所修正を優先する。

## Reference
必要な canonical docs へ辿るための案内先リストである。
各項目のリンク先は必要時にだけ読む。

## Coding
- [ARCHITECTURE.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/ARCHITECTURE.md)
- [src/prompts/manifests/orchestrator.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/orchestrator.yaml)
- [src/prompts/manifests/builder.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/builder.yaml)
- [src/prompts/manifests/verifier.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/verifier.yaml)
- [src/prompts/manifests/steward.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/steward.yaml)
- [src/prompts/manifests/wiki-steward.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/wiki-steward.yaml)

## Graph / Harness Compatibility
Read these only when the task explicitly touches the existing graph harness or a runtime contract wires it into the current flow.
- [src/graph/state.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/graph/state.py)
- [src/graph/hooks.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/graph/hooks.py)

## Testing
- [docs/workflows/git-test-policy.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/workflows/git-test-policy.md)
- [docs/workflows/build-test-pr.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/workflows/build-test-pr.md)
- [docs/evals/regression.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/evals/regression.md)

## Review
- [docs/workflows/build-test-pr.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/workflows/build-test-pr.md)
- [archive/Contact-session.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/archive/Contact-session.md)

## Git
- [docs/workflows/git-test-policy.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/workflows/git-test-policy.md)
- [docs/workflows/build-test-pr.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/workflows/build-test-pr.md)
- [.github/pull_request_template.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/pull_request_template.md)
- [.github/instructions/docs.instructions.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/instructions/docs.instructions.md)

## CI/CD
- [.github/workflows/ci.yml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/workflows/ci.yml)
- [src/services/verification/cli.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/services/verification/cli.py)
- [src/services/git/dangerous_diff.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/services/git/dangerous_diff.py)
- [src/services/docs/freshness.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/services/docs/freshness.py)

## Prompt Operations
- [src/prompts/base/global.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/base/global.md)
- [src/prompts/roles/orchestrator.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/roles/orchestrator.md)
- [src/prompts/roles/builder.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/roles/builder.md)
- [src/prompts/roles/verifier.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/roles/verifier.md)
- [src/prompts/roles/steward.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/roles/steward.md)
- [src/prompts/roles/wiki-steward.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/roles/wiki-steward.md)
- [src/prompts/manifests/orchestrator.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/orchestrator.yaml)
- [src/prompts/manifests/builder.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/builder.yaml)
- [src/prompts/manifests/verifier.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/verifier.yaml)
- [src/prompts/manifests/steward.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/steward.yaml)
- [src/prompts/manifests/wiki-steward.yaml](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/prompts/manifests/wiki-steward.yaml)

## Docs And Specs
- [AGENTS.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/AGENTS.md)
- [ARCHITECTURE.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/ARCHITECTURE.md)
- [docs/index.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/index.md)
- [docs/specs/knowledge-loop.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/specs/knowledge-loop.md)
- [docs/tasks/active/_template/](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/tasks/active/_template/)
- [docs/tasks/templates/](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/tasks/templates/)
- [.github/instructions/backend.instructions.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/instructions/backend.instructions.md)
- [.github/instructions/frontend.instructions.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/instructions/frontend.instructions.md)
- [.github/instructions/infra.instructions.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/instructions/infra.instructions.md)
- [.github/instructions/docs.instructions.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/.github/instructions/docs.instructions.md)

## Doc Freshness
- [docs/rules.md](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/docs/rules.md)
- [src/services/docs/freshness.py](/Users/yamamotokaito/Desktop/MODEL-APP-FLOW/src/services/docs/freshness.py)
