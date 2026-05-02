---
status: active
owner: steward
last_validated_at: 2026-04-25
source_of_truth_level: primary
version: 0.6.2
---

# Skill Governance

Repo-owned common skills use one canonical home:

```yaml
canonical_skill_root: .agents/skills
runtime_compat_roots:
  - .codex/skills
```

`.agents/skills` is the source of truth for repo-owned common skills.
`.codex/skills` is allowed only for runtime/provider bundles or compatibility
mirrors needed by the Codex skill loader. Agents should prefer the canonical path
from `artifacts/runtime/skill-registry.yaml` when a repo-owned skill exists in
both places.

Project runtime skills are managed separately from common skills:

```yaml
project_runtime_skill_root: skills
active_runtime_skill_groups:
  - skills/orchestration
  - skills/content
  - skills/research
runtime_map: artifacts/runtime/skill-directory-map.yaml
```

These directories are callable execution targets for the v0.6.2 runtime. Each
callable target must own a local `AGENTS.md` and `SKILL.md`; the runtime starts
the call with that skill directory as the current working directory.

## Freshness Map

`artifacts/runtime/skill-registry.yaml` is the latest skill map. It is not a
routine read for every specialist agent. Main lane, steward, workflow planner,
and skill-integrity work read it when they need skill selection, freshness
review, migration, or deprecation decisions.

Each registry entry records:
- `skill_id`
- `canonical_path`
- `compatibility_paths`
- `status`
- `owner_agent`
- `last_validated_at`
- `freshness_state`
- `replacement`

## Staleness Policy

Skills can decay when app flow, platform APIs, project assumptions, or review
criteria change. Treat skills as current only when the registry says
`freshness_state: current`.

Allowed states:
- `current`: usable without special review.
- `watch`: usable, but review before high-impact work.
- `stale`: do not use until refreshed.
- `archived`: historical only.

## Archive Policy

Deprecated skills move out of active roots and into `archive/`. Archived skills
are historical only and must not be exposed as active runtime skills; use the
current app harness, context-scope, and project operation contracts instead.

## Update Rule

When a skill is added, moved, deprecated, or refreshed:
- update `artifacts/runtime/skill-registry.yaml`
- update `artifacts/runtime/skill-directory-map.yaml` if it is a callable runtime skill
- update `docs/specs/app-skill-registry.md` if the app flow uses it
- update `artifacts/runtime/context-scope.yaml` if role scopes change
- record material changes in the relevant app log or stewardship rollup
