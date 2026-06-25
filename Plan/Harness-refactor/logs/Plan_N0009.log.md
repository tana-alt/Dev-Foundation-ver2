# Plan_N0009 discussion log

Topic: make a hook event or skill so an agent spawned by the harness gains
proper, task-specific context automatically (cold-start context delivery).

Grounding facts (from current code):
- The harness already computes a compact, policy-compliant context packet per
  role in `spawn.py:_initial_context` / `launch.py:_initial_context`
  (`task_id, role, task_goal, scope_contract, verifier_ids, acceptance, policy,
  artifact_refs, next_action, agent_tools`) and persists it to
  `{role}-session.json`.
- The agent is launched via `launch._shell_command`:
  `cd <worktree> && FOUNDATION_*=... codex --yolo` (or claude). The packet is on
  disk but is NOT delivered into the spawned agent's context window.
- Existing hooks: `scripts/hook_session_start.py` (SessionStart -> prints open
  issues), `hook_post_tool_use.py` (trajectory), `hook_stop.py` (dispatch).
  Wired for Claude via `templates/claude-hooks-settings.json`. No Codex hook
  config is wired yet.
- Policy from refactor.md (deleted, but binding): initial session context must
  be COMPACT; skills are routed by identifier/path, never injected as bodies;
  AGENTS.md is ambient, not synced; scope_contract is the boundary carrier;
  completion authority is artifact-backed, not router-injected.

## discussion-1

### Claude idea (round 1)

Problem statement
- A harness-spawned agent starts COLD. The harness knows the correct
  task-specific context but has no transport that puts it into the agent's
  actual context window. Today an operator must tell the agent out-of-band to
  read JSON files. That is the "proper context" gap.

Options surveyed (broad)
- A) AGENTS.md only. Reject: AGENTS.md is static/ambient and carries no
  per-task scope_contract, next_action, handoff, or verifier_ids. It cannot be
  the task-context transport.
- B) Prompt injection into the launch command (pass packet as initial prompt
  arg). Reject: couples the harness to each runtime's prompt format, is fragile,
  and does not re-fire on resume/compaction.
- C) Harness context SessionStart event (RECOMMENDED). A SessionStart hook runs
  inside the agent process, detects a harness role session via
  FOUNDATION_TASK_ID / HARNESS_ROLE, loads the harness-computed context packet,
  and prints a compact deterministic block to stdout, which lands in the agent
  context automatically. Works for both Codex and Claude (both expose a
  SessionStart hook). Idempotent, re-fires on resume, respects refactor.md.
- D) Pull-style skill (agent invokes a `harness-context` skill). Reject for the
  primary path: a cold agent does not know to pull; SessionStart pushes
  automatically. (A skill can still document the packet for manual re-pull.)

Recommended sophisticated plan: Option C — "Harness context event"
1. Single source of truth (projection): the harness writes a runtime-agnostic
   projection at prepare/spawn time so the hook reads ONE canonical file
   regardless of role/runtime. Candidate: reuse the existing per-role
   `initial_context` (resolve file from HARNESS_ROLE) OR emit a dedicated
   `context-event.json`. Projection logic stays in core (testable); the hook
   stays dumb. This is the "routed context" of the context-routing branch; the
   hook is only the delivery transport.
2. Delivery transport: a SessionStart hook script that
   - reads FOUNDATION_REPO_ROOT / FOUNDATION_TASK_ID / HARNESS_ROLE /
     FOUNDATION_AGENT_ID (+ FOUNDATION_REVIEWER_ID),
   - no-ops (exit 0) when not in a harness session (preserves current behavior),
   - emits a compact markdown block: task_id, role, goal, scope_contract
     (allowed/forbidden), next_action, verifier_ids, handoff commands, policy
     summary, acceptance audit status, and agent_tools/skills routing
     (name+phase+path+purpose only, NO bodies),
   - is non-blocking, fail-open, always exit 0 (matches existing hooks).
3. Wire both runtimes:
   - Claude: extend the SessionStart array in the hooks-settings template.
   - Codex: add a Codex hook config (the plan's hook-event table is Codex's)
     wiring SessionStart -> the same script. This is the "make hook event"
     deliverable.
4. Tests: (a) projection builder contains scope_contract + next_action + handoff
   and no skill bodies; (b) hook prints the block inside a harness session,
   no-ops outside, stays silent on missing/malformed packet.
5. Policy compliance: compact, no skill bodies, scope_contract present,
   artifact-backed (hook only reads harness-written artifacts; invents no
   authority).

Why event over skill: push vs pull. Cold-start agents need context pushed at
session start; SessionStart fires automatically and re-fires on resume, robust
across compaction. This is exactly the "Harness context event" candidate.

Open questions for Codex
- Q1 Projection source: reuse per-role `{role}-session.json:initial_context`
  (no new artifact, but hook must resolve role file) vs a dedicated canonical
  `context-event.json` written once by the harness (one stable read, small new
  artifact). Which is the cleaner contract?
- Q2 Compose vs separate: fold harness-context emission into the existing
  `hook_session_start.py` (one SessionStart entry, open-issues + harness
  context) vs a separate `hook_session_start_harness.py` (single
  responsibility, two SessionStart entries). The plan note says "do not persist
  use hook by event above" — does that argue for one composed hook?
- Q3 Codex wiring: where does Codex read hook config in this repo's convention
  (`~/.codex/config.toml [hooks]`, repo `.codex/`, or a tracked template under
  `templates/`)? Need the tracked, repo-local form so it is reviewable.
- Q4 Scope: is delivering the EXISTING packet enough, or should this plan also
  add new fields (e.g., handoff commands, denied_context) to the projection?

### Codex opinion (round 1)

Decision
- Use Option C, but keep the first implementation slice smaller than the broad
  wiring proposal: extend the existing `scripts/hook_session_start.py` rather
  than adding a second hook script or a new context artifact.
- Reuse current harness artifacts as the context projection:
  `contract.lock.json`, `capsule.json`, `resume-capsule.json`,
  `agent-tools.json`, and `agent-skills.json`.
- Do not persist raw hook event payloads or event-specific install state. The
  hook drains stdin and prints only bounded, derived context to stdout.
- Do not add a new skill for this slice. The existing role skills already cover
  execution, context routing, and review; the missing piece is cold-start
  delivery, not another pull-based instruction body.

Acceptance for this slice
- SessionStart emits task id, role, goal, scope contract, acceptance, policy,
  next action, verifier ids, handoff command names, tools, skills, and artifact
  refs when harness runtime context exists.
- Missing/malformed artifacts remain fail-open and do not trap the agent loop.
- Existing open-issues surfacing still runs after the context block.
- `PostToolUse` trajectory telemetry stays unchanged.
- The optional measurement tool profile exposes `session-start-context-hook`
  next to `post-tool-use-hook`, so the supported hook command is discoverable.

Agreement
- Claude's event-over-skill direction is correct for cold-start context because
  a new agent cannot be trusted to pull context before acting.
- Codex narrows the projection question to "reuse existing artifacts first" to
  avoid a new runtime ledger. A dedicated `context-event.json` can be added
  later only if repeated consumers need a single-file projection.
- Codex does not wire a tracked Codex hook config in this slice because the plan
  note warns against persisting use by event, and repo conventions for Codex
  hook config are not established here. The reviewable deliverable is the
  stdlib hook behavior plus optional tool registry entry.

## Codex

Implemented
- `scripts/hook_session_start.py` now prints a compact, role-aware harness
  context summary from existing runtime artifacts before open issues, including
  verifier ids and available handoff command names.
- The hook infers repo/task/role from `FOUNDATION_*`, `HARNESS_ROLE`, and
  `.harness-worktree.json`, matching other hook behavior.
- The hook remains stdlib-only, drains stdin without echoing it, and fails open
  with exit 0.
- `src/workflow_core/contract_harness/agent_tools.py` now exposes
  `session-start-context-hook` in the optional measurement profile for writer,
  reviewer, and integrator roles.
- `docs/reference/harness-observability-reference.md` documents the expanded
  SessionStart behavior.

Verification
- `pytest -q tests/test_hook_scripts.py tests/workflow_core/test_hook_events.py`
  -> passed, 24 tests.
- `uv run ruff check scripts/hook_session_start.py tests/test_hook_scripts.py src/workflow_core/contract_harness/agent_tools.py tests/workflow_core/test_contract_harness.py`
  -> passed.
- `uv run ruff format --check scripts/hook_session_start.py tests/test_hook_scripts.py src/workflow_core/contract_harness/agent_tools.py tests/workflow_core/test_contract_harness.py`
  -> passed.
- `make check-hooks` -> passed.
- With a temporary `python` -> `python3` shim in `PATH`, because this machine
  has `python3` but no `python` executable:
  - `pytest -q tests/workflow_core/test_contract_harness.py::test_script_tool_commands_use_absolute_paths_for_repo_local_scripts tests/workflow_core/test_contract_harness.py::test_prepare_capsule_exposes_existing_agent_tool_set tests/workflow_core/test_contract_harness.py::test_measurement_tool_ingests_observed_trajectory_into_task_metrics`
    -> passed, 3 tests.
  - `pytest -q tests/workflow_core/contract_harness/test_architecture_gate.py::test_architecture_gate_advisory_maps_to_oracle_requirement tests/workflow_core/contract_harness/test_architecture_gate_integration.py::test_verify_result_includes_architecture_gate`
    -> passed, 2 tests.
- `pytest -q tests/workflow_core/contract_harness/test_strict_capabilities.py`
  -> passed, 9 tests.
- `pytest -q tests/test_extension_surface_integrity.py tests/test_skill_route_check.py tests/workflow_core/contract_harness/test_architecture_skill_routing.py`
  -> passed, 8 tests.
- `pytest -q tests/test_foundation_integrity.py::test_required_contract_files_exist tests/test_foundation_integrity.py::test_tracked_hooks_enforce_agent_policy_and_checks tests/test_foundation_integrity.py::test_dev_environment_and_hygiene_checks_are_wired`
  -> passed, 3 tests.

Unshimmed environment note
- Direct verifier-backed tests using `python -c ...` fail on this machine
  without the temporary shim because `command -v python` is empty while
  `python3` is available. The shimmed runs prove the harness paths themselves.

### Claude opinion (review verdict)

I independently reviewed the implementation against the agreed Option C design
and the refactor.md policy, then re-ran verification myself on the current file
state (Codex made a live refinement adding `verifiers` and `handoff commands`
lines; I re-verified after that landed rather than trusting the report).

Design agreement
- Reuse-existing-artifacts (Q1): agreed. The hook reads contract.lock.json,
  capsule.json, resume-capsule.json, agent-tools.json, agent-skills.json, and
  the role session file (for handoff). No new runtime ledger; degrades
  gracefully when any artifact is absent.
- Compose-into-existing-hook (Q2): agreed. One SessionStart entry, harness
  context first then open issues. Honors the plan note "do not persist use hook
  by event" by not proliferating hooks.
- Operator-wired runtime config (Q3): agreed, consistent with repo posture. The
  repo commits no active SessionStart config for any runtime (the Claude
  template is archived; docs describe local wiring). The deliverable is the
  stdlib hook + discoverability via the `session-start-context-hook` measurement
  tool + the observability-reference doc. A committed always-on Codex hook is a
  deliberate non-goal here, not a gap.
- Packet scope (Q4): agreed. Emitted block carries goal, scope_contract
  (allowed/forbidden), acceptance, policy, next_action, verifiers, handoff
  commands, tools, skills, and a refs line — the proper task context, compact.

Code review (scripts/hook_session_start.py)
- Policy-compliant: only tool/skill/verifier/handoff NAMES are emitted, never
  bodies; scope_contract is carried; text clipped to 180 chars and lists bounded
  to 8 items; stdin drained but never echoed (asserted by test).
- Fail-open: main() wraps everything in try/except -> exit 0; `_read_json`
  returns None on error; no-op when no harness context exists. Matches the
  existing hook robustness contract (stdlib-only, plain python3).
- Robust resolution: repo/project/role from env OR `.harness-worktree.json`
  marker OR git, so it works on resume and reattach.

Independent verification (re-run by Claude, current state)
- `uv run pytest -q tests/test_hook_scripts.py` -> 15 passed (incl. new
  `- verifiers: unit` / `- handoff commands: verify, submit` assertions).
- `uv run pytest -q tests/test_hook_scripts.py tests/workflow_core/test_hook_events.py`
  -> 24 passed.
- `uv run pytest -q tests/workflow_core/test_contract_harness.py tests/workflow_core/contract_harness`
  -> 184 passed (no regression from the agent_tools.py tool-spec addition).
- `uv run ruff check` + `ruff format --check` on the 4 changed files -> passed.
- `make check-hooks` -> passed.

Verdict: AGREE. The agreed slice is implemented, policy-compliant, and verified.
No remaining plan disagreement. Residual (non-blocking): automatic SessionStart
firing is operator-wired by design; if committed auto-wiring is later wanted,
add a tracked hooks template as a follow-up plan.
