---
status: active
owner: orchestrator
last_validated_at: 2026-04-16
source_of_truth_level: primary
supersedes: null
related_code:
  - apps/api/main.py
  - src/services/workflows/service.py
  - src/services/llm/factory.py
  - src/services/knowledge/service.py
  - profiles/manifest.yaml
  - scripts/repo_profiles/export_profile.py
  - scripts/repo_profiles/bootstrap_profile_repo.py
  - scripts/repo_profiles/check_profile_contracts.py
---

# Repo Profile Split

## Purpose
- app / quant の repo を分けても shared kernel の dependency direction を崩さない
- code fork ではなく overlay export で domain difference を表現する
- split の判断材料として、現在の import / call dependency を固定する

## Current Dependency Map

### Shared Kernel Entry
- `apps/api/main.py` は `src.services.knowledge`, `src.services.llm`, `src.services.obsidian`, `src.services.workflows` を束ねる API entrypoint
- `apps/web` と `apps/obsidian-plugin` は architecture 上 `apps/api` と HTTP / JSON 契約で接続する

### Workflow Lane
- `src/services/workflows/service.py` は `src.db.models`, `src.graph.routing`, `src.graph.state`, `src.schemas.workflows`, `src.schemas.multica`, `src.services.llm`, `src.services.multica`, `src.services.verification` に依存する
- `WorkflowService/list_role_presets` と `WorkflowService/list_prompt_templates` は `src/prompts/roles` と `src/prompts/templates` を repo root から読む
- `src/services/llm/factory.py` の `build_workflow_runtime_adapter` は runtime backend を切り替え、`multica` 選択時だけ `src.services.multica` を読む

### Knowledge Lane
- `src/services/knowledge/service.py` は `src.db.models` と `src.schemas.knowledge` に依存する
- `KnowledgeService` の主な consumer は `apps/api/main.py` で、knowledge lane は workflow lane から独立している

## Split Rule
- core repo は `apps/api`, `apps/web`, `apps/obsidian-plugin`, `src/*`, shared prompts, canonical docs を保持する
- app repo は app delivery 用の `AGENTS.md`, repo-scoped skills, app-specific spec を保持する
- quant repo は quant research 用の `AGENTS.md`, repo-scoped skills, quant-specific spec を保持する
- app / quant repo は core repo の Python module を import しない
- app / quant repo は shared kernel と HTTP / CLI で接続する

## Exportable Overlay Assets
- canonical source は `profiles/manifest.yaml`
- shared repo-scoped skills は `profiles/templates/shared/`
- app overlay は `profiles/templates/app/`
- quant overlay は `profiles/templates/quant/`
- 共通 docs / prompt / instructions は `vendor_paths` として core repo から copy する
- standalone workflow repo に必要な PR template と task template も shared vendor に含める
- quant overlay は `knowledge-loop` spec, Obsidian vault skeleton, `scripts/onyx` を vendor し、knowledge-first workflow を repo 内で完結できるようにする
- export tool は `scripts/repo_profiles/export_profile.py`
- bootstrap tool は `scripts/repo_profiles/bootstrap_profile_repo.py`
- contract check は `scripts/repo_profiles/check_profile_contracts.py`

## Why This Preserves Dependency Direction
- domain-specific difference を code path ではなく instructions / skill / contract layer に押し上げる
- shared runtime と schema を 1 つの repo に残すので API drift が起きにくい
- `WorkflowService` と `KnowledgeService` は app / quant repo に持ち出さず、core repo の single implementation を再利用できる
- cross-folder 参照が難しい箇所は docs / prompt / workflow skeleton を vendor copy し、runtime implementation だけを shared kernel に残す

## Next Split Step
1. app repo と quant repo を新規作成する
2. `scripts/repo_profiles/bootstrap_profile_repo.py` で overlay を流し込み、repo を初期化する
3. `scripts/repo_profiles/check_profile_contracts.py` を通して overlay 契約を確認する
4. domain repo から core repo の API / CLI 接続設定だけを追加する
5. split 後に contract test と handoff smoke test を回す
