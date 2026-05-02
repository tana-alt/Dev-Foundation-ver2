---
status: active
owner: steward
last_validated_at: 2026-04-19
source_of_truth_level: secondary
supersedes: null
related_code:
  - docs/tasks
  - apps/obsidian-plugin
  - scripts/onyx
  - obsidian-vault
  - src/prompts
  - src/services/knowledge
  - src/services/obsidian
  - src/services/multica
---

# Documentation Index

## Canonical Docs
- `ARCHITECTURE.md`
- `docs/rules.md`
- `AGENTS.md`
- `docs/workflows/build-test-pr.md`
- `docs/workflows/git-test-policy.md`
- `docs/evals/regression.md`
- `docs/harness-contract.md`
- `docs/agent-map.md`

## Workflow Docs
- `docs/workflows/git-test-policy.md`: agent が読む短い git / test / log policy。詳細 docs と Makefile への index
- `docs/workflows/build-test-pr.md`: plan-only から repro、最小 test、lint、build、smoke、docs 更新、PR 生成までの標準フロー

## Harness v0.6.1 SNS / Project Operation
- `docs/company-operating-system.md`: decision maker の指示を並列自律レーンの organization structure、plan、research、execution management へ分解する company / organization operating mesh
- `artifacts/runtime/company-operating-system.yaml`: company operating mesh の machine-readable operating model
- `docs/idea-proposal-operating-loop.md`: ここで出たアイデアと agent 提案を candidate として intake / evaluation / routing する継続運用loop
- `artifacts/runtime/idea-proposal-loop.yaml`: chat idea / agent proposal -> proposal evaluation -> research / planning / execution / archive の machine-readable loop
- `docs/social-publish-executor-boundary.md`: SNS 認証と投稿実行を external executor / secret broker に分離する境界
- `artifacts/runtime/social-publish-executor-policy.yaml`: external SNS auth / publish executor の current / target policy
- `artifacts/runtime/concept-research/20260426-ai-systematize-monetization/`: `AI x systematize` と収益化しやすいSNS concept候補のresearch snapshot
- `artifacts/runtime/social-account-connector-registry.yaml`: 活動候補SNSアカウントの `account_ref` / `auth_status` / executor scope を secret なしで管理する registry
- `src/services/social_publish.py`: SNS external executor boundary の実装。X `POST /2/tweets` live path は明示flagと外部注入tokenがある場合だけ実行
- `src/schemas/social_publish.py`: social auth / publish API schema
- `GET /api/social/platforms`, `GET /api/social/connectors`, `POST /api/social/connect-requests`, `POST /api/social/publish-requests`: platform inventory確認、connector確認、外部認証request、投稿request実行API
- `artifacts/packets/decision-directive-packet.yaml`: decision maker 指示の packet template
- `artifacts/packets/idea-intake-packet.yaml`: chat idea を保存・正規化・routing する packet template
- `artifacts/packets/agent-proposal-packet.yaml`: agent research / reflection proposal を candidate として渡す packet template
- `artifacts/packets/proposal-evaluation-packet.yaml`: idea / proposal の evidence、owner、risk、next action を評価する packet template
- `artifacts/packets/organization-structure-packet.yaml`: 会社 / ecosystem / project / offer / channel 境界の構造化 packet template
- `artifacts/packets/execution-management-packet.yaml`: plan / research / execution の進捗管理 packet template
- `artifacts/packets/social-publish-request.yaml`: `channel_operator` から external executor へ渡す content_ref-only publish request
- `artifacts/packets/social-auth-connect-request.yaml`: main_lane から external executor へ渡す SNS account connection request。credential は含めない
- `organizations/_template/`: company / organization operating model starter template
- `organizations/_template/logs/{idea-inbox,proposal-log,social-connector-log}.md`: chat idea、agent proposal、SNS external auth connection の organization-local log template
- `docs/harness-contract.md`: ecosystem -> project / offer -> channel operation -> content registry -> packet -> feedback loop の正本
- `docs/content-generation-harness.md`: v0.7 Harness-complete dry_run。work diagnosis、capability routing、workflow / artifact evaluation、strategy / execution split、A/B/C dry_run dataset の repo mirror
- `docs/agent-map.md`: canonical v0.6.1 agent map。新規 agent は `project_supervisor` と `channel_operator` の2つだけ
- `docs/agent-inheritance-policy.md`: 既存 skill 再利用、重複禁止、agent 追加制限
- `docs/context-scope-policy.md`: repo 全体を読ませないための global / project / channel / shared scope
- `docs/skill-governance.md`: `.agents/skills` を repo-owned skill 正本にする skill freshness / archive policy
- `docs/gate-policy.md`: `content_publish_gate` と条件付き `compliance_gate`
- `docs/platform-nature-map.md`: SNSの固定ロールではなく platform nature と hypothesis edge で扱う方針
- `docs/secret-boundary-contract.md`: manual / safe limited execution と将来の brokered runtime access
- `docs/scheduled-jobs-policy.md`: daily planning、monitoring、weekly research、knowledge refresh と rate limit
- `docs/project-operation-harness.md`: project 管理ループと shared knowledge への知見共有ルール
- `docs/project-direction-strategy-policy.md`: 週次実行戦略と月次確認の固定方向性戦略を分け、`imagegen` / OSS research を project direction 候補として扱う policy
- `artifacts/runtime/project-direction-strategy-policy.yaml`: fixed-layer project direction strategy の machine-readable policy
- `artifacts/packets/project-direction-strategy-packet.yaml`: system introduction、OSS adoption、visual/system concept 候補の月次確認 packet template
- `artifacts/runtime/knowledge-sharing-policy.yaml`: strategy log の仮説 / 知見候補利用分離と shared candidate scoring policy
- `artifacts/project-orchestration/app-project-index.yaml`: app overlay から project-local repo への対応表
- `artifacts/project-orchestration/log-feedback-policy.yaml`: project-local log と shared lessons の分離 policy
- `knowledge/shared/agent-lessons-index.md`: 全 agent が参照できる再利用可能な教訓 index
- `artifacts/runtime/agent-activity-log-policy.yaml`: runtime による agent 使用log自動記録、直近3件参照、判断層の手順＋柔軟思考 policy
- `artifacts/runtime/agent-invocation-policy.yaml`: agent call の判断者、実行者、trigger source、call request contract
- `artifacts/runtime/runtime-session-policy.yaml`: direct Codex session resume / switch / attempt ledger policy
- `docs/ecosystem-project-content-alignment.md`: ecosystem -> project -> content の位置情報、runtime identity refs、project-local storage 方針
- `docs/agent-io-dependency-map.md`: agent input / output contract と依存edgeから workflow を導出する方針
- `artifacts/runtime/ecosystem-project-content-map.yaml`: agent が読む ecosystem / project / content 順序と runtime identity refs
- `artifacts/runtime/agent-io-contract-map.yaml`: agentごとの input contract、output contract、dependency edge
- `projects/_template/knowledge/premise-summary.md`: projectごとの前提知識summary ref
- `projects/_template/logs/strategy-log.md`: project-local hypotheses、knowledge candidate usage、effectiveness follow-up の記録先
- `projects/_template/logs/agent-activity-log.yaml`: runtime が自動追記する agent 使用履歴
- `projects/_template/logs/agent-recent-activity.yaml`: agent ごとの直近3件 activity index
- `projects/_template/runtime/session-ledger.yaml`: workflow run / Codex session / attempt linkage ledger
- `projects/_template/content/recent-posts.yaml`: 過去3投稿refの軽量index
- `artifacts/runtime/harness-alignment-gaps.yaml`: dataset 以外の alignment gap と残タスク
- `artifacts/runtime/project-registry.yaml`: `project_graph` registry
- `artifacts/runtime/ecosystem-registry.yaml`: ecosystem -> project / offer / channel grouping registry
- `artifacts/runtime/offer-registry.yaml`: offer promise, funnel refs, claim boundary, and owner registry
- `artifacts/runtime/agent-runtime-state.yaml`: agent location, scope, input/output docs, packet refs, and next owner registry
- `artifacts/runtime/skill-directory-map.yaml`: `target_skill` から skill directory と local `AGENTS.md` / `SKILL.md` を解決する map
- `artifacts/runtime/skill-call-request.yaml`: runtime が skill に渡す最小 request envelope
- `artifacts/runtime/runtime-policy.yaml`: preflight / postflight validator、model policy、secret policy
- `artifacts/runtime/agent-map.yaml`: canonical slot -> assigned agent / skill map
- `artifacts/runtime/context-scope.yaml`: main lane と specialist agent の最小 read scope registry
- `artifacts/runtime/skill-registry.yaml`: skill の canonical path、freshness、archive / replacement map
- `artifacts/runtime/agent-output-registry.yaml`: owner role ごとの read / write / output / next owner map
- `artifacts/runtime/workflow-loop.yaml`: main lane から channel / project monitor / ecosystem monitor へ戻る runtime loop
- `skills/analysis/{workflow-evaluator,artifact-evaluator,performance-analyst}/`: Harness-complete.md 準拠の分析レイヤー agent skill
- `artifacts/runtime/dry-run-smoke.yaml`: Harness-complete dry_run dataset と loop surface を確認する smoke assertion map
- `artifacts/runtime/dry-run-dataset-registry.yaml`: active dry_run dataset registry。現在は `harness_complete_v1`
- `artifacts/runtime/dry-run-datasets/harness-complete-v1/source-map.yaml`: ignored local `Harness-complete.md` から committed dataset への抽出対応表
- `artifacts/runtime/dry-run-datasets/harness-complete-v1/`: `Harness-complete.md` 準拠の A/B/C project configs、synthetic metric model、injection schedule、access matrix、analysis / strategy fixture
- `artifacts/runtime/capability-registry.yaml`: task name ではなく required capability で routing する registry
- `artifacts/runtime/content-generation-runtime.yaml`: workflow -> artifact -> analytics -> strategy -> execution brief loop の runtime map
- `artifacts/runtime/dry-run-policy.yaml`: Harness-complete dry_run policy、agent visibility、A/B/C dataset requirement、live transition minimum
- `artifacts/runtime/pattern-registry.yaml`: watchlist / validated separation and update cadence template
- `artifacts/runtime/escalation-rules.yaml`: cost、workflow loop、quality の escalation thresholds
- `artifacts/runtime/scheduled-jobs.yaml`: operation cron と per-channel rate limit
- `artifacts/runtime/platform-relationship-map.yaml`: evidence-backed channel relationship hypothesis
- `artifacts/packets/{handoff,evidence,rework,operation}-packet.yaml`: v0.6.1 packet templates。本文は持たず `content_ref` のみ渡す
- `artifacts/packets/{work-diagnosis,routing-decision,workflow-evaluation-record,artifact-outcome-record,strategy,execution-brief,pattern-registry,synthetic-metric-record,escalation-monitor-record}.yaml`: v0.7 dry_run foundation packet / record templates
- `artifacts/packets/{main-lane-loop-record,project-monitor-record,ecosystem-monitor-record}.yaml`: runtime loop / monitoring record templates
- `artifacts/packets/secret-access-request.yaml`: future executor / broker bridge。現状 agent は直接使用しない
- `projects/_template/`: project / channel / content registry starter template
- `ecosystems/_template/`: ecosystem overview, project index, ecosystem-level log starter template
- `knowledge/shared/`: validated / failed pattern、strategy knowledge candidates、platform / offer lessons
- `knowledge/shared/strategy-knowledge-candidates.yaml`: dry_run / strategy 用の知見候補ledger。score、use_count、effective_count を管理

## Repo Profiles
- `profiles/README.md`: shared kernel を維持したまま app / quant overlay を切り出すための運用入口
- `profiles/manifest.yaml`: shared / app / quant profile の継承関係と export 対象
- `scripts/repo_profiles/export_profile.py`: target repo へ profile overlay を流し込む export tool
- `scripts/repo_profiles/bootstrap_profile_repo.py`: split 先 repo を初期化し、overlay と最小 README / gitignore を作る bootstrap tool
- `scripts/repo_profiles/check_profile_contracts.py`: overlay が shared kernel code を直接持ち込んでいないかを検証する contract check

## Evaluation Docs
- `docs/evals/regression.md`: unit、deterministic、rubric、trace、online eval、offline regression の責務分離

## Local Instructions
- `.github/instructions/backend.instructions.md`: API、graph、services、db、schemas の局所ルール
- `.github/instructions/frontend.instructions.md`: web と Obsidian plugin の局所ルール
- `.github/instructions/infra.instructions.md`: CI/CD、Docker、GitHub Actions、secret 変更時の局所ルール
- `.github/instructions/docs.instructions.md`: docs 変更時の局所ルール

## Specs
- `docs/specs/knowledge-loop.md`: Onyx CE + Obsidian plugin + bridge service の lane / API / security surface
- `docs/specs/app-agentic-flow.md`: APP repo 向けの role / handoff / Obsidian app bundle / scaffold API の正本
- `docs/specs/app-planner-agent-contracts.md`: planner が使う agent I/O, write surface, progress packet の契約
- `docs/specs/app-planner-decision-matrix.md`: planner が slice ごとに固定すべき decision registry と全 current agent の decision / I-O / risk / improvement matrix
- `docs/specs/app-agent-io-alignment-report.md`: active agent の input/output inventory、handoff alignment、AGENTS hierarchy 監査
- `docs/specs/app-agent-harness-review.md`: harness の false-pass 修正、operator usability、token cost estimate をまとめた review report
- `docs/specs/app-agent-flow-open-issues-and-skill-candidates.md`: token 以外の未解決 flow 問題と skill 化候補の横断整理
- `docs/specs/app-skill-flow-effectiveness-2026-04-21.md`: DotTrail / QuietPulse の実行ベースで、どの skill chain が効いたか、どこが半自動のままか、どの lane が未実働かを整理した review
- `docs/specs/app-skill-registry.md`: app flow で使う skill の stage 別 registry。core mandatory flow、optional lane、main lane の差し戻し前提、keep / conditional / missing の整理を含む
- `docs/specs/app-agent-escalations-improvements.md`: human judgment が必要な workflow-language 論点と、承認後に進める改善案の整理
- `docs/specs/repo-profile-split.md`: shared kernel と app / quant overlay を分離する dependency map と split rule
- 追加時は `docs/specs/<feature>.md` を使用します
- 新規 spec は Human 承認後に primary として扱います

## Active Tasks
- `docs/tasks/active/_template/`: active task 配下の正規レイアウトを示す参照用テンプレート
- 各実 task は `docs/tasks/active/<task-id>/` に `Prompt.md` `Plan.md` `Implement.md` `Log.md` の 4 ファイルだけを置きます
- `docs/tasks/active/KNOWLEDGE-loop-foundation/`: knowledge loop と Obsidian-native Knowledge Desk bridge/plugin を追加する active task
- `docs/tasks/active/MULTICA-agent-loop/`: Multica runtime adapter と agent loop 統合を追加する active task
- `docs/tasks/active/APP-agentic-flow/`: APP repo 用 agent instructions、Obsidian app bundle、scaffold API を整備する active task
- `docs/tasks/templates/`: `_template/` と同内容を保持する複製用テンプレート置き場。内容差分を作らず同期します

## Completed Tasks
- 現在登録済みの completed task はありません
- 完了後は `docs/tasks/completed/<task-id>/` へ移動します

## Prompt Structure
- `src/prompts/base/global.md`
- `src/prompts/roles/orchestrator.md`
- `src/prompts/roles/builder.md`
- `src/prompts/roles/verifier.md`
- `src/prompts/roles/steward.md`
- `src/prompts/roles/wiki-steward.md`
- `src/prompts/manifests/{orchestrator,builder,verifier,steward}.yaml`
- `src/prompts/manifests/wiki-steward.yaml`

## Knowledge Surfaces
- `knowledge/`: lane-oriented filesystem mirror for LLM wiki content and operator-facing structure
- `obsidian-vault/`: local vault for inbox, summaries, hypotheses, lessons, and reviews
- `obsidian-vault/Apps/`: app ごとの project hub、phase note、progress log を束ねる overlay
- `apps/obsidian-plugin/`: Obsidian native UI で Knowledge Desk view と command surface を提供する plugin
- `scripts/onyx/`: Multica と競合しない `localhost:3001` 用の Onyx local startup helper
- `src/services/knowledge/`: knowledge records, search, relation, and Onyx sync services
- `src/services/obsidian/`: vault listing, note read/write, path security, and vault health services
- local bridge の既定 port は `8011`。必要なら `make knowledge-up BRIDGE_PORT=<port>` で変更する

## Stale Candidates
- 現時点の stale candidate はありません
- stale 判定は `docs/rules.md` の文書鮮度管理ルールに従います
