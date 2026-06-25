---
plan_id: Plan_N0010
project_id: Harness-refactor
plan_ref: Plan/Harness-refactor/plans/Plan_N0010.md
---

# Plan_N0010 log

## 2026-06-24

- Created draft plan from user correction:
  - hook is for ACP, review request, task_id, and packet path delivery
  - skill manifest is not needed in harness packets
  - `report-rfc` and `report-metric` are obsolete because escalation goes
    through GitHub issues
  - integrator `compose`, `compose-push`, and `oracle` should not be hidden
    merely as "advanced"; they support normal integration diagnostics and
    recovery around land/push/PR flow
- No implementation changes were made in this plan step.

## 2026-06-24 compact checkpoint addition

- Added investigation plan for preserving subtle design judgments around
  context compaction.
- Current repo inspection found no existing `PreCompact` or `PostCompact`
  script and no proven context-usage ratio path. Existing normalized
  trajectory events can carry token counts, but current hook translation does
  not populate them for tool-call events.
- Added feasibility gate: exact 80% triggering is only implementable if the
  runtime exposes context usage ratio/token capacity in hook payloads or
  another reliable event stream. Otherwise use runtime-fired `PreCompact` or a
  manual `checkpoint` command as fallback.
- Chose runtime packet storage for agent-specific compact checkpoints:
  `<packet dir>/agent-docs/<agent_id>/compact-checkpoint.md`. This avoids
  turning individual agent memory into tracked repo docs.

## 2026-06-24 compact hook feasibility probe

- Used the current local Codex manual and local `codex exec` probes to verify
  compact hook feasibility before treating the feature as plan-ready.
- Manual facts:
  - `PreCompact` and `PostCompact` are documented hook events.
  - `SessionStart` supports `startup`, `resume`, `clear`, and `compact`
    matchers.
  - `model_auto_compact_token_limit` and `model_context_window` are documented
    config keys, but a hook payload field for reliable context usage ratio or
    max-context capacity was not found.
- Probe facts:
  - `SessionStart` stdout can be model-visible context.
  - A low `model_auto_compact_token_limit` caused auto compaction and fired
    `PreCompact`, `PostCompact`, and then `SessionStart`.
  - `SessionStart` stdout on resume can be model-visible context.
  - `PreCompact` and `PostCompact` stdout is not model-visible context.
  - `SessionStart` stdout for both `compact` and `resume` can be
    model-visible context after compaction.
  - Compact hook payload keys observed in the safe probe were `cwd`,
    `hook_event_name`, `model`, `session_id`, `transcript_path`, `trigger`,
    and `turn_id`; no usage ratio, current token count, or max context value
    was present.
- Resulting design decision:
  - Do not claim hook-side exact 80% detection.
  - Do not rely on `PostCompact` stdout for context restoration.
  - Use `SessionStart` `startup|resume|compact` to inject a bounded
    agent-specific checkpoint summary.
  - Use `PreCompact`/`PostCompact` only for compaction event metadata and
    checkpoint presence/size checks.
  - Add a guarded `issue-create` command to the role manifest instead of
    keeping `report-rfc` or `report-metric`.

## 2026-06-24 implementation

- Implemented the hook/manifest cleanup slice and deferred compact-checkpoint
  automation.
- Changed the default role manifest:
  - removed writer `spawn-writer`, `report-rfc`, and `report-metric`
  - added local comm and strict ACP command exposure for
    writer/reviewer/integrator, plus writer-owned `issue-create`
  - added integrator `pr-create` and `pr-checks`
  - kept integrator `land`, `push`, `compose`, `compose-push`, and `oracle`
    visible
- Removed generated skill manifest use from harness packet generation and
  diagnostics:
  - `prepare` no longer writes `agent-skills.json`
  - stale `agent-skills.json` is removed from task runtime on prepare
  - `context-audit`, `gate` packet exposure, `explain`, and SessionStart no
    longer read or print generated skill manifest data
- Added `issue-create` as a writer-owned escalation CLI command. It returns
  `protected_external_write` dry-run output by default and creates the GitHub
  issue only with `HARNESS_ROLE=writer --execute`.
- Updated SessionStart output to surface task id, role, agent id, task yaml,
  runtime packet directory, packet names, review request asks, review output
  paths, ACP/local communication commands, role tools, and next action.
- Verification:
  - fail-before focused tests failed on the old behavior
  - focused tests passed after implementation
  - `pytest -q tests/test_hook_scripts.py` passed
  - `PATH=/tmp/codex-python-shim:$PATH pytest -q tests/workflow_core/test_contract_harness.py`
    passed
  - `pytest -q tests/workflow_core/contract_harness/test_strict_capabilities.py`
    was blocked by sandboxed Unix socket bind permission for the daemon
  - `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` passed
  - `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check ...` passed

## 2026-06-24 subagent review rework

- Subagent review found four actionable issues:
  - `issue-create --execute` could write to GitHub with only `HARNESS_ROLE`
    set.
  - SessionStart review request parsing depended on PyYAML despite plain
    `python3` hook operation.
  - Hook-printed command examples did not shell-quote task and agent values.
  - SessionStart did not print the issue escalation command directly.
- Reworked the implementation:
  - `issue-create --execute` was temporarily blocked after review.
  - SessionStart has a narrow stdlib fallback parser for
    `review_request.architecture_review.ask` and
    `review_request.code_review.ask`.
  - SessionStart command examples shell-quote concrete task, role, and agent
    values and avoid angle-bracket placeholders.
  - SessionStart prints the direct `issue-create` escalation command.
  - Integrator fallback next action now mentions land, push, and PR checks.
- Rework verification:
  - `pytest -q tests/test_hook_scripts.py` passed.
  - `PATH=/tmp/codex-python-shim:$PATH pytest -q tests/workflow_core/test_contract_harness.py`
    passed.
  - `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` passed for the touched
    files.

## 2026-06-24 writer-owned issue escalation correction

- User clarified that GitHub issue creation is intentionally the escalation
  external write, and the authority belongs to the writer role.
- Corrected the implementation:
  - `issue-create` is visible and executable only for writer role.
  - `HARNESS_ROLE=writer ./harness issue-create ... --execute` runs
    `gh issue create`.
  - reviewer/integrator manifests no longer expose `issue-create`.
  - SessionStart prints the direct issue escalation command only for writer.
  - un-escalated unfinished work is treated as implementation defect, not an
    issue to file.
