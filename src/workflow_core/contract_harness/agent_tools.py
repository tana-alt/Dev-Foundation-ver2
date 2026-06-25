from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import common_dir
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.runtime_paths import task_dir

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def write_agent_tools(root: Path, task_id: str) -> dict[str, list[dict[str, Any]]]:
    tools = agent_tool_groups(root, task_id)
    write_json(task_dir(root, task_id) / "agent-tools.json", tools)
    return tools


def agent_tool_groups(root: Path, task_id: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "writer": role_agent_tools(root, task_id, "writer"),
        "reviewer": role_agent_tools(root, task_id, "reviewer"),
        "integrator": role_agent_tools(root, task_id, "integrator"),
    }


def optional_agent_tool_groups(
    root: Path,
    task_id: str,
    profile: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "writer": role_optional_tools(root, task_id, "writer", profile),
        "reviewer": role_optional_tools(root, task_id, "reviewer", profile),
        "integrator": role_optional_tools(root, task_id, "integrator", profile),
    }


def role_agent_tools(root: Path, task_id: str, role: str) -> list[dict[str, Any]]:
    if role == "writer":
        return _writer_harness_tools(root, task_id)
    if role == "reviewer":
        return _reviewer_harness_tools(root, task_id)
    if role == "integrator":
        return [*_integrator_tools(root, task_id), *_scope_checker_tools(root, include_lane=True)]
    raise ValueError(f"unknown role for agent tools: {role}")


def role_optional_tools(
    root: Path,
    task_id: str,
    role: str,
    profile: str,
) -> list[dict[str, Any]]:
    if profile == "coordination":
        return _coordination_tools(root, task_id, role)
    if profile != "measurement":
        raise ValueError(f"unknown optional tool profile: {profile}")
    if role == "writer":
        return _measurement_tools(root, task_id, role)
    if role == "reviewer":
        return _reviewer_measurement_tools(root, task_id)
    if role == "integrator":
        return _integrator_measurement_tools(root, task_id)
    raise ValueError(f"unknown role for optional agent tools: {role}")


_WRITER_TOOL_SPECS = (
    (
        "scope-map-forward",
        "before_edit",
        "{harness} scope-map {task_id} --forward",
        "Thin implementation discovery map; advisory only.",
    ),
    (
        "explain",
        "before_edit",
        "{harness} explain {task_id}",
        "Show the task capsule, path contract, verifier ids, and visible tools.",
    ),
    (
        "context-audit",
        "before_edit",
        "{harness} context-audit {task_id}",
        "Quantify role packet size and required tool visibility.",
    ),
    (
        "status",
        "coordination",
        "{harness} status {task_id}",
        "Read artifact-backed task status without changing workflow state.",
    ),
    (
        "passport",
        "coordination",
        "{harness} passport {task_id}",
        "Read the task proof passport without rerunning checks or changing workflow state.",
    ),
    (
        "verify",
        "before_submit",
        "{harness} verify {task_id}",
        "Write candidate diff and machine evidence for the current worktree.",
    ),
    (
        "submit",
        "handoff",
        "{harness} submit {task_id}",
        "Submit fresh verified evidence for reviewer and integrator processing.",
    ),
)

_STATUS_TOOL_SPECS = (
    (
        "status",
        "coordination",
        "{harness} status {task_id}",
        "Read artifact-backed task status without changing workflow state.",
    ),
    (
        "passport",
        "coordination",
        "{harness} passport {task_id}",
        "Read the task proof passport without rerunning checks or changing workflow state.",
    ),
)

_COMMON_COORDINATION_TOOL_SPECS = (
    (
        "comm-peers",
        "coordination",
        "{harness} comm-peers {task_id}",
        "List task-scoped peer agent ids, roles, and briefs for local ACP-style handoff.",
    ),
    (
        "comm-inbox",
        "coordination",
        '{harness} comm-inbox {task_id} --agent-id "$FOUNDATION_AGENT_ID"',
        "Read the current agent inbox from task-scoped runtime state.",
    ),
    (
        "comm-send",
        "coordination",
        (
            "{harness} comm-send {task_id} --to-agent <to_agent_id> --to-role <to_role> "
            '--kind <kind> --subject "<subject>" --body "<body>"'
        ),
        "Send a non-authoritative task-scoped ACP-style message to another agent.",
    ),
    (
        "acp-list",
        "coordination",
        '{harness} --strict acp list {task_id} --agent-id "$FOUNDATION_AGENT_ID"',
        "List the authenticated agent inbox through strict ACP.",
    ),
    (
        "acp-send",
        "coordination",
        (
            "{harness} --strict acp send {task_id} --to-agent <to_agent_id> "
            '--to-role <to_role> --kind <kind> --subject "<subject>" --body "<body>"'
        ),
        "Send a task-scoped ACP message through the strict daemon session.",
    ),
    (
        "acp-request-action",
        "coordination",
        '{harness} --strict acp request-action <message_id> --body "<message_body>"',
        "Ask ACP for a proposed action without executing it.",
    ),
)

_WRITER_ESCALATION_TOOL_SPECS = (
    (
        "issue-create",
        "escalation",
        (
            '{harness} issue-create {task_id} --reason escalation --title "<title>" '
            '--body "<body>" --execute'
        ),
        (
            "Create a GitHub issue for escalation only; un-escalated unfinished work "
            "is a defect, not an issue."
        ),
    ),
)

_INTEGRATOR_TOOL_SPECS = (
    (
        "review-collect",
        "merge_preflight",
        "{harness} review {task_id} --collect",
        "Collect fresh, stale, approving, and blocking reviewer verdicts.",
    ),
    (
        "scope-map-reverse",
        "merge_preflight",
        "{harness} scope-map {task_id} --reverse",
        "Diff impact map for merge-boundary diagnosis; advisory only.",
    ),
    (
        "affected",
        "merge_preflight",
        "{harness} affected {task_id}",
        "Classify FAST, PARTIAL, or REBASE against the integration target.",
    ),
    (
        "context-audit",
        "merge_preflight",
        "{harness} context-audit {task_id}",
        "Quantify role packet size and required tool visibility.",
    ),
    (
        "dispatch",
        "integration",
        "{harness} dispatch {task_id}",
        "Run missing reviewers and integration gate from the integrator boundary.",
    ),
    (
        "integrate",
        "integration",
        "{harness} integrate {task_id}",
        "Run integration checks and write rework or integrated result evidence.",
    ),
    (
        "gate",
        "completion",
        "{harness} gate {task_id}",
        "Run final machine gate and reviewer freshness checks.",
    ),
    (
        "post-review-gate",
        "completion",
        "{harness} post-review-gate {task_id}",
        "Run the deterministic post-review mechanical gate before PR creation.",
    ),
    (
        "land",
        "merge",
        "{harness} land {task_id}",
        "Merge the candidate under push lock and affected-set policy.",
    ),
    (
        "compose",
        "merge",
        "{harness} compose {task_id} <other-task-id>",
        "Compose a deterministic pending candidate set and localize red candidates.",
    ),
    (
        "compose-push",
        "external_write",
        "{harness} compose-push {task_id} <other-task-id>",
        "Push a green composed candidate set with exact-CAS, lock, and rescue evidence.",
    ),
    (
        "oracle",
        "merge",
        "{harness} oracle {task_id} --target-head <sha>",
        "Reapply the submitted candidate on a target head and run machine validation.",
    ),
    (
        "push",
        "external_write",
        "{harness} push {task_id}",
        "Push through policy checks and rescue ref handling.",
    ),
    (
        "pr-create",
        "external_write",
        "{harness} pr create {task_id}",
        "Create the task PR from landed or prepared integration evidence.",
    ),
    (
        "pr-checks",
        "external_read",
        "{harness} pr checks {task_id}",
        "Read PR check status for the task PR evidence.",
    ),
)

_MEASUREMENT_TOOL_SPECS = (
    (
        "session-start-context-hook",
        "context",
        "scripts/hook_session_start.py",
        "{env} python3 {{script}}",
        "SessionStart hook command that prints bounded task context and open issues.",
    ),
    (
        "post-tool-use-hook",
        "observe",
        "scripts/hook_post_tool_use.py",
        "{env} python3 {{script}}",
        "PostToolUse hook command that records task-scoped trajectory JSONL from stdin.",
    ),
    (
        "nfr-metric",
        "measure",
        "scripts/nfr_metric.py",
        "{env} python3 {{script}} summary",
        "Record and evaluate latency or other NFR samples in nfr.db.",
    ),
    (
        "bench-compare",
        "measure",
        "scripts/bench_compare.py",
        "{env} python3 {{script}} summary",
        "Record, summarize, and compare benchmark distributions in bench.db.",
    ),
    (
        "abrun",
        "measure",
        "scripts/abrun.py",
        "{env} python3 {{script}} run --config <config.json>",
        "Run AB baseline/candidate measurements into runs.db.",
    ),
    (
        "check-runner",
        "measure",
        "scripts/check_runner.py",
        "{env} python3 {{script}} run --run-id <run-id> --worktree <path>",
        "Run functional checks and record check evidence in runs.db.",
    ),
    (
        "verdict",
        "measure",
        "scripts/verdict.py",
        "{env} python3 {{script}} compare --baseline-run <id> --candidate-run <id>",
        "Statistically compare baseline and candidate samples from runs.db.",
    ),
    (
        "quality-gate",
        "measure",
        "scripts/quality_gate.py",
        "{env} python3 {{script}} evaluate --policy <policy.json>",
        "Aggregate functional and statistical policy conditions.",
    ),
    (
        "measure-eval",
        "observe",
        "scripts/measure_eval.py",
        "{env} python3 {{script}}",
        "Ingest trajectory JSONL into eval.db and summarize tool/skill signals.",
    ),
    (
        "surface-issues",
        "observe",
        "scripts/surface_issues.py",
        "{env} python3 {{script}}",
        "Surface recurring issues from eval.db for later sessions.",
    ),
)


def _writer_harness_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    return _harness_tools_from_specs(
        "writer",
        harness,
        task_id,
        (
            *_WRITER_TOOL_SPECS[:3],
            *_WRITER_TOOL_SPECS[5:],
        ),
    )


def _reviewer_harness_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    return [
        _harness_tool(
            "reviewer",
            "scope-map-reverse",
            "review",
            f"{harness} scope-map {task_id} --reverse",
            "Diff impact map for semantic review; advisory only.",
        ),
        _harness_tool(
            "reviewer",
            "context-audit",
            "review",
            f"{harness} context-audit {task_id}",
            "Quantify role packet size and required tool visibility.",
        ),
        _harness_tool(
            "reviewer",
            "review-verdict",
            "review",
            f"{harness} review {task_id} --write-verdict <reviewer> approve|block",
            "harness-ai-review",
        ),
        _harness_tool(
            "reviewer",
            "certify",
            "review",
            f"{harness} certify {task_id} --reviewer-id <reviewer>",
            "harness-ai-review",
        ),
    ]


def _integrator_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    return _harness_tools_from_specs("integrator", harness, task_id, _INTEGRATOR_TOOL_SPECS)


def _coordination_tools(root: Path, task_id: str, role: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    specs: tuple[tuple[str, str, str, str], ...] = (
        *_STATUS_TOOL_SPECS,
        *_COMMON_COORDINATION_TOOL_SPECS,
    )
    if role == "writer":
        specs = (*specs, *_WRITER_ESCALATION_TOOL_SPECS)
    elif role == "integrator":
        specs = (
            *specs,
            (
                "spawn",
                "coordination",
                "{harness} spawn {task_id} --role writer --agent codex",
                "Start or rebind a role session without running authority actions.",
            ),
        )
    elif role != "reviewer":
        raise ValueError(f"unknown role for optional agent tools: {role}")
    return _harness_tools_from_specs(role, harness, task_id, specs)


def _measurement_tools(root: Path, task_id: str, role: str) -> list[dict[str, Any]]:
    return [
        tool
        for spec in _measurement_tool_specs(root, task_id, role)
        if (tool := _script_tool(root, *spec)) is not None
    ]


def _measurement_tool_specs(
    root: Path,
    task_id: str,
    role: str,
) -> tuple[tuple[str, str, str, str, str], ...]:
    env = _measurement_env(root, task_id, role)
    return tuple(
        (name, phase, rel_path, command_template.format(env=env), purpose)
        for name, phase, rel_path, command_template, purpose in _MEASUREMENT_TOOL_SPECS
    )


def _measurement_env(root: Path, task_id: str, role: str) -> str:
    repo = common_dir(root).resolve().parent
    return (
        f"FOUNDATION_REPO_ROOT={shlex.quote(str(repo))} "
        f"FOUNDATION_PROJECT_ID={shlex.quote(task_id)} "
        f"HARNESS_ROLE={shlex.quote(role)}"
    )


def _reviewer_measurement_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    names = {
        "session-start-context-hook",
        "post-tool-use-hook",
        "nfr-metric",
        "bench-compare",
        "verdict",
        "quality-gate",
        "surface-issues",
    }
    return [tool for tool in _measurement_tools(root, task_id, "reviewer") if tool["name"] in names]


def _integrator_measurement_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    names = {
        "session-start-context-hook",
        "post-tool-use-hook",
        "measure-eval",
        "surface-issues",
    }
    return [
        tool for tool in _measurement_tools(root, task_id, "integrator") if tool["name"] in names
    ]


def _scope_checker_tools(root: Path, *, include_lane: bool) -> list[dict[str, Any]]:
    tools = [
        _script_tool(
            root,
            "context-scope-check",
            "scope_check",
            "scripts/check-context-scope.py",
            "python3 {script}",
            "Validate context-scope manifests and evidence records when present.",
        )
    ]
    if include_lane:
        tools.append(
            _script_tool(
                root,
                "lane-map-check",
                "parallel_merge_check",
                "scripts/check-lane-map.py",
                "python3 {script}",
                "Validate parallel lane-map templates and project lane records.",
            )
        )
    return [tool for tool in tools if tool is not None]


def _script_tool(
    root: Path,
    name: str,
    phase: str,
    rel_path: str,
    command_template: str,
    purpose: str,
) -> dict[str, Any] | None:
    path = _script_path(root, rel_path)
    if path is None:
        return None
    return _tool(name, phase, command_template.format(script=shlex.quote(str(path))), purpose)


def _script_path(root: Path, rel_path: str) -> Path | None:
    for base in (root, _PACKAGE_ROOT):
        candidate = base / rel_path
        if candidate.is_file():
            return candidate
    return None


def _harness_command(root: Path) -> str:
    bases = (_PACKAGE_ROOT,) if _is_harness_worktree(root) else (root, _PACKAGE_ROOT)
    for base in bases:
        candidate = base / "harness"
        if candidate.is_file():
            return shlex.quote(str(candidate))
    return "python -m workflow_core.contract_harness.cli"


_TOOL_SKILLS = {
    "abrun": "harness-tool-abrun",
    "acp-list": "harness-tool-acp-list",
    "acp-request-action": "harness-tool-acp-request-action",
    "acp-send": "harness-tool-acp-send",
    "affected": "harness-tool-affected",
    "bench-compare": "harness-tool-bench-compare",
    "certify": "harness-tool-certify",
    "check-runner": "harness-tool-check-runner",
    "comm-inbox": "harness-tool-comm-inbox",
    "comm-peers": "harness-tool-comm-peers",
    "comm-send": "harness-tool-comm-send",
    "compose": "harness-tool-compose",
    "compose-push": "harness-tool-compose-push",
    "context-audit": "harness-tool-context-audit",
    "context-scope-check": "harness-tool-context-scope-check",
    "dispatch": "harness-tool-dispatch",
    "explain": "harness-tool-explain",
    "gate": "harness-tool-gate",
    "integrate": "harness-tool-integrate",
    "issue-create": "harness-tool-issue-create",
    "land": "harness-tool-land",
    "lane-map-check": "harness-tool-lane-map-check",
    "measure-eval": "harness-tool-measure-eval",
    "nfr-metric": "harness-tool-nfr-metric",
    "oracle": "harness-tool-oracle",
    "passport": "harness-tool-passport",
    "post-tool-use-hook": "harness-tool-post-tool-use-hook",
    "post-review-gate": "harness-tool-post-review-gate",
    "pr-checks": "harness-tool-pr-checks",
    "pr-create": "harness-tool-pr-create",
    "push": "harness-tool-push",
    "quality-gate": "harness-tool-quality-gate",
    "review-collect": "harness-tool-review-collect",
    "review-verdict": "harness-tool-review-verdict",
    "scope-map-forward": "harness-tool-scope-map-forward",
    "scope-map-reverse": "harness-tool-scope-map-reverse",
    "session-start-context-hook": "harness-tool-session-start-context-hook",
    "spawn": "harness-tool-spawn",
    "status": "harness-tool-status",
    "submit": "harness-tool-submit",
    "surface-issues": "harness-tool-surface-issues",
    "verdict": "harness-tool-verdict",
    "verify": "harness-tool-verify",
}


def _tool(name: str, phase: str, command: str, purpose: str) -> dict[str, Any]:
    return {
        "name": name,
        "phase": phase,
        "command": command,
        "purpose": "",
        "skill": _tool_skill(name),
    }


def _tool_skill(name: str) -> str:
    try:
        return _TOOL_SKILLS[name]
    except KeyError as exc:
        raise ValueError(f"missing tool-specific skill for tool: {name}") from exc


def _harness_tool(
    role: str,
    name: str,
    phase: str,
    command: str,
    purpose: str,
) -> dict[str, Any]:
    return _tool(name, phase, f"HARNESS_ROLE={role} {command}", purpose)


def _harness_tools_from_specs(
    role: str,
    harness: str,
    task_id: str,
    specs: tuple[tuple[str, str, str, str], ...],
) -> list[dict[str, Any]]:
    return [
        _harness_tool(
            role,
            name,
            phase,
            command_template.format(harness=harness, task_id=task_id),
            purpose,
        )
        for name, phase, command_template, purpose in specs
    ]


def _is_harness_worktree(root: Path) -> bool:
    return (root / ".harness-worktree.json").is_file()
