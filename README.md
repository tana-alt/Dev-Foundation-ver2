# Foundation

This repo distills a small development foundation for agents, humans, tools,
and automations. Keep it simple: active behavior belongs in three short docs,
and detailed source material belongs in routed references only.

The canonical entrypoint is `AGENTS.md`; active repo-wide behavior is kept in
the three short docs below.

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

## Contract Harness

The contract harness is the active agent execution path for task-oriented work.
It is intentionally small: the writer gets a bounded task packet and tool list,
the reviewer reads fresh machine evidence plus the candidate diff, and the
integrator performs review collection, integration checks, land, and optional
push under policy.

Minimal flow:

```sh
./harness prepare <task_id>
./harness launch-writer <task_id> --agent-command "codex --yolo"
```

`launch-writer` creates or resumes the writer worktree and prints the command
to run the interactive writer there. The writer should implement the task,
then run:

```sh
HARNESS_ROLE=writer ./harness verify <task_id>
HARNESS_ROLE=writer ./harness submit <task_id> --wait
```

`submit --wait` hands off to the integrator boundary. The integrator runs
missing reviewers, collects verdicts, and writes the integration result. Manual
inspection commands are still available when needed:

```sh
HARNESS_ROLE=reviewer ./harness review <task_id> --run <reviewer_id>
HARNESS_ROLE=integrator ./harness review <task_id> --collect
HARNESS_ROLE=integrator ./harness dispatch <task_id>
HARNESS_ROLE=integrator ./harness land <task_id>
HARNESS_ROLE=integrator ./harness push <task_id>
```

Use `./harness status <task_id>` for the current phase, role/mode, land status,
and next command. Use `./harness passport <task_id>` for a read-only proof
summary across contract, candidate diff, verifier evidence, reviewer verdicts,
gate/integration state, and the StateStore hash-chain head.

Architecture:

- `.harness/` is the control plane: task YAML, verifier config, review config,
  semantic reviewer wrapper, and policy. Policy YAML carries repo-wide
  invariants and scope semantics; task YAML carries task-specific goal,
  architecture, acceptance, adversarial checks, and review requests.
- `./harness` is the CLI entrypoint. Role checks happen at this CLI
  orchestration boundary; they are not a security boundary against a malicious
  local worker.
- Local orchestration mode runs reversible local commands directly with
  `HARNESS_ROLE`. Local-strict daemon mode uses `./harness daemon run
  --foreground`, `./harness --strict ...`, sessions, and capability tokens for
  protected actions. `HARNESS_ROLE` is still only an orchestration signal.
- `allowed_paths` is expected impact scope for planning and review, not a hard
  gate. `forbidden_paths` is blocking unless an explicit policy-exception task
  authorizes the change.
- `docs/reference/` is supplemental for deeper rationale. Completion-critical
  harness requirements belong in `.harness/policy.yaml`, task YAML, AGENTS.md,
  or generated packets.
- Harness runtime state is stored under the Git common directory at
  `harness-runtime/`, not in tracked `.harness/state`.
- Writer, reviewer, and integrator worktrees are task-owned under
  `harness-runtime/worktrees/<task_id>/`.
- Writer handoff evidence lives in
  `harness-runtime/state/tasks/<task_id>/`: `contract.lock.json`,
  `verify-result.json`, `candidate.diff`, `submission.json`, reviewer packets,
  verdicts, and `integration-result.json`.
- Semantic reviewers read `reviews/<reviewer>.review-packet.json` plus the
  sealed candidate workspace and write `reviews/<reviewer>.json`. After review,
  the integrator handoff is `review --collect`, `dispatch` or `integrate`, then
  `land`, then policy-controlled `push`.
- Task-scoped agent communication uses `comm-peers`, `comm-send`, and
  `comm-inbox` in local mode. The strict daemon exposes the same channel through
  `acp send`, `acp list`, and `acp request-action`; `acp list` is the candidate
  inbox list for the given task and agent id.
- Reviewer freshness is evidence-hash based. If diff, verifier output, quality
  evidence, scope map, metrics, mutation output, or reviewer-consumed artifacts
  change, stale reviewer lanes must be rerun instead of reusing old verdicts.
- Policy controls external writes. Land and push use integrator authority and
  write rescue, lock, sync, and result evidence where configured.

An `integrated` result means gated and ready to land; it does not mean merged
into the target branch. A `landed` result means the local land step completed.
Rework is a normal workflow result: the writer should receive the evidence and
continue unless the task is irreversible, policy-violating, or looping without
progress.

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
- `.agents/plugins/marketplace.json`: local plugin registry. It starts empty so
  optional plugin payloads are not advertised as installed. `plugins/` may hold
  local or downloaded payloads when present, but payloads are not required.
- `Plan/`: scoped planning notes for substantial or resumable work, not runtime
  state.
