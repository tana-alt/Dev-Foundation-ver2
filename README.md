# Foundation

This repo distills a small development foundation for agents, humans, tools,
and automations. Keep it simple: active behavior belongs in three short docs,
and detailed source material belongs in routed references only.

## Active Docs

- `AGENTS.md`: agent entrypoint and routing map.
- `docs/01-agent-operating-contract.md`: context, contracts, and rework.
- `docs/02-output-verification-contract.md`: evidence, verification, and gates.
- `docs/03-repo-boundary-and-storage-contract.md`: folders, storage, secrets,
  skills, and plugins.

## References

Detailed summaries live under `docs/reference/`. Open only the routed reference
needed for the current scope. Past-source material is kept out of the tracked
repo unless it has been distilled into current docs.

## Verification

After cloning, run:

```sh
uv sync --frozen --group dev
make check-foundation
```

`make check-foundation` runs the required local chain and the CD readiness
guard. It expects `shellcheck` and `gitleaks` on `PATH`. CI installs those OSS
check tools, then runs the same gate through `.github/workflows/ci.yml`. Run
`make doctor` for a read-only local environment inspection.

## Restore Agent Environment

This repo tracks the recipe for a local agent environment, not local runtime
state. To restore Serena, Context7, and Codex MCP wiring on a cloned machine,
run:

```sh
sh scripts/setup-agent-environment.sh
```

The script copies `templates/serena-project.yml` into local ignored
`.serena/project.yml`, keeps Serena's dashboard from opening on launch, adds
missing Serena and Context7 MCP blocks to `~/.codex/config.toml`, downloads
Context7 through `npx`, installs tracked Git hooks through `core.hooksPath`,
records the canonical repo root in local Git config, and runs a Serena health
check.

Do not commit `.serena/`, `~/.codex/config.toml`, auth files, API keys, logs,
caches, or downloaded language-server payloads. Keep only sanitized templates
and restore steps in this repo.

## Main Folders

- `app/`: future runnable app surfaces.
- `src/`: future shared implementation.
- `docs/`: active docs and references.
- `artifact/`: foundation outputs and fixtures.
- `templates/`: reusable templates.
- `scripts/`: repo bootstrap and verification helpers.
- `hooks/`: tracked Git hooks installed by the restore script.
- `tests/`: foundation contract and integrity checks.
- `.agents/skills/`: current repo-local Codex skills.
- `.agents/plugins/marketplace.json` and `plugins/`: local plugin registry and
  payloads.
- `Plan/`: scoped planning notes for substantial or resumable work, not runtime
  state.
