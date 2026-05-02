---
status: active
last_validated_at: 2026-04-27
source_of_truth_level: primary
owner: steward
orchestration_spec: "0.8.0-project-scoped"
---

# AGENTS.md

`AGENTS.md`は親エージェントのためのmain_lane routing mapであり、全てのprojectを管理するためにあります。
親エージェントと指示されたら必ず以下の役割を負って下さい。

## Main Lane Role

親エージェントはサブエージェントを`artifacts/runtime/skill-directory-map.yaml`から選びます。この path は互換のため残る legacy map location であり、実行 runtime の存在を意味しません。
親エージェントはサブエージェントを用いてPDCAサイクルを回し、最終的な成果物の責任を負います。

成果物、handoff、logs、metrics、reports は常に `projects/{project_id}/...` の project-local repo に保存します。`obsidian-vault/Apps/{app_slug}` は必要な場合の閲覧・同期 overlay であり、全成果物を集約する正本ではありません。

- requested `expected_outputs`
- evidence refs
- changed paths
- verification results
- blockers, rework requests, and next owner

サブエージェントは指定された作業を担当します。親エージェントはサブエージェントを呼び出し、次のハンドオフを作成またはレビューします。親エージェントはサブエージェントを中間報告を全て読みません。入力とhandoffを担当します。

## Parent Orchestration Rule

```text
main_lane
  -> reads AGENTS.md first
  -> reads orchestration maps when target_skill, owner, or expected output is unclear
  -> reads ARCHITECTURE.md when workflow principles or flow shape are unclear
  -> resolves target_skill in the legacy skill-directory map
  -> sends a minimal skill_call_request to a skill-bearing subagent
  -> receives expected outputs, evidence refs, blockers, and verification
  -> checks handoff compatibility and final quality
  -> stores packet / log / registry refs under projects/{project_id}/...
```

親は全てのマップをエージェントに読み込ませるべきではありません。親はルーティング、ハンドオフ、または品質保証に必要なコンテキストを決定するために`agent-map.yaml`,
`skill-directory-map.yaml`, または `ARCHITECTURE.md`のみを開くべきです。

主な実行はサブエージェントを使用します。CLIサブプロセスは明示的なランタイムスモークテスト、自動化チェック、または別のプロセスがテスト対象である場合に予約されています。

## Subagent Call Envelope

サブエージェントを呼び出す際、親は作業に必要なスコープフィールドのみを指定します：

- `target_skill`
- `ARCHITECTURE.md`
- skill directory and local instruction surface
- `task_intent`
- `project_graph`
- `project_identity_refs` or legacy `runtime_identity_refs` while maps migrate
- `source_refs`
- `expected_outputs`
- allowed `write_targets`
- `instruction`
- `memo`

サブエージェントには最小の範囲を指定して下さい。

## Map And Architecture Index

以下のreferenceはPrimary referencesですが、参照する際はポイントとして扱うべきで、詳細に書きすぎるとアーキテクチャが硬直してしまうので注意してください。

## Active Project Alias Routing

If a user or terminal agent says `3dtaskproject`, `3dtask project`, `3Dtask`, `3dtask`, `project_app_3dtask`, or `3dtask_app_project`, resolve that alias to `projects/project_app_3dtask/` first.

Minimal 3Dtask read order:

1. `projects/project_app_3dtask/AGENTS.md`
2. `projects/project_app_3dtask/project-manifest.yaml`
3. `projects/project_app_3dtask/storage-map.yaml`
4. `projects/project_app_3dtask/state.yaml`
5. `projects/project_app_3dtask/notes/00-hub.md`
6. `projects/project_app_3dtask/artifacts/registry/agent-readable-index.yaml`

For implementation work, prefer `apps/3dtask-swift/` as the current surface. Treat `apps/web/src/3dtask/` as legacy/reference unless the user explicitly asks for web.

Primary references:

- `ARCHITECTURE.md`: principle of how agents perform
- `docs/workflows/git-test-policy.md`: short git, verification, log, and
  shared lesson policy for agents.
- `artifacts/runtime/agent-map.yaml`: active owner slots, app flow, SNS flow,
  and review posture.
- `artifacts/runtime/skill-directory-map.yaml`: `target_skill` to cwd, local
  `AGENTS.md`, `SKILL.md`, callable owners, and expected outputs.
- `artifacts/runtime/agent-io-contract-map.yaml`: input/output contracts and
  dependency edges.
- `artifacts/runtime/context-scope.yaml`: parent vs specialist read surfaces.
- `artifacts/runtime/agent-output-registry.yaml`: writable outputs and next
  owner expectations.
- `artifacts/runtime/capability-registry.yaml`: capability-based routing.
- `artifacts/runtime/runtime-policy.yaml`: preflight, postflight, model, and
  secret policy.
- `artifacts/project-orchestration/project-boundary-policy.yaml`: project-local
  artifact/log boundary and legacy runtime deprecation policy.
- `artifacts/project-orchestration/app-project-index.yaml`: app overlay to
  project-local repository map.
- `artifacts/project-orchestration/log-feedback-policy.yaml`: project-local logs
  and shared lesson promotion policy.

Project, SNS, and organization state maps:

- `artifacts/runtime/project-registry.yaml`
- `artifacts/runtime/ecosystem-registry.yaml`
- `artifacts/runtime/offer-registry.yaml`
- `artifacts/runtime/social-publish-executor-policy.yaml`
- `artifacts/runtime/social-account-connector-registry.yaml`
- `artifacts/runtime/scheduled-jobs.yaml`
- `artifacts/runtime/project-direction-strategy-policy.yaml`

Skill entry points:

- Full current skill list: `artifacts/runtime/skill-directory-map.yaml`.
- Active skill roots: `skills/orchestration`, `skills/content`,
  `skills/research`, `skills/dynamic-research-pack`, `skills/analysis`,
  `skills/monitoring`, `skills/app-research-skill-pack`,
  `skills/app-workflow-planning`, `skills/workflow-planning`,
  `skills/planner-skill-suite`, `skills/ui-ux-skill-suite`,
  `skills/implementation-agent-skill-pack`, `skills/security-review`,
  `skills/compliance_privacy_legal_review`, `skills/reviewer-layer-skill`,
  and `skills/social-launch-execution-deliverables`.
- Compatibility local instruction example: `skills/orchestration/channel-operator/AGENTS.md`.
- Archived skills are historical only:
  `archive/2026-04-27-skill-pruning/skills`.

## Root Boundary

Keep this file short. It should describe routing, active maps, and parent /
subagent responsibility. Do not add skill-specific procedure here.
