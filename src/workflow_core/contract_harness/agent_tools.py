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


def role_optional_tools(root: Path, task_id: str, role: str, profile: str) -> list[dict[str, Any]]:
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
        "Map likely implementation scope.",
    ),
    (
        "explain",
        "before_edit",
        "{harness} explain {task_id}",
        "Print task contract summary.",
    ),
    (
        "context-audit",
        "before_edit",
        "{harness} context-audit {task_id}",
        "Check role context visibility.",
    ),
    (
        "status",
        "coordination",
        "{harness} status {task_id}",
        "Read current workflow phase.",
    ),
    (
        "passport",
        "coordination",
        "{harness} passport {task_id}",
        "Read proof summary.",
    ),
    (
        "verify",
        "before_submit",
        "{harness} verify {task_id}",
        "Write candidate proof.",
    ),
    (
        "submit",
        "handoff",
        "{harness} submit {task_id}",
        "Hand off verified candidate.",
    ),
)

_STATUS_TOOL_SPECS = (
    (
        "status",
        "coordination",
        "{harness} status {task_id}",
        "Read current workflow phase.",
    ),
    (
        "passport",
        "coordination",
        "{harness} passport {task_id}",
        "Read proof summary.",
    ),
)

_COMMON_COORDINATION_TOOL_SPECS = (
    (
        "comm-peers",
        "coordination",
        "{harness} comm-peers {task_id}",
        "List local peer agents.",
    ),
    (
        "comm-inbox",
        "coordination",
        '{harness} comm-inbox {task_id} --agent-id "$FOUNDATION_AGENT_ID"',
        "Read local agent inbox.",
    ),
    (
        "comm-send",
        "coordination",
        "{harness} comm-send {task_id} --to-agent <to_agent_id> --to-role <to_role> "
        '--kind <kind> --subject "<subject>" --body "<body>"',
        "Send local coordination message.",
    ),
    (
        "acp-list",
        "coordination",
        '{harness} --strict acp list {task_id} --agent-id "$FOUNDATION_AGENT_ID"',
        "Read strict ACP inbox.",
    ),
    (
        "acp-send",
        "coordination",
        "{harness} --strict acp send {task_id} --to-agent <to_agent_id> "
        '--to-role <to_role> --kind <kind> --subject "<subject>" --body "<body>"',
        "Send strict ACP message.",
    ),
    (
        "acp-request-action",
        "coordination",
        '{harness} --strict acp request-action <message_id> --body "<message_body>"',
        "Request proposed action only.",
    ),
)

_WRITER_ESCALATION_TOOL_SPECS = (
    (
        "issue-create",
        "escalation",
        '{harness} issue-create {task_id} --reason escalation --title "<title>" '
        '--body "<body>" --execute',
        "Escalate unresolved policy issue.",
    ),
)

_INTEGRATOR_TOOL_SPECS = (
    (
        "review-collect",
        "merge_preflight",
        "{harness} review {task_id} --collect",
        "Collect reviewer verdicts.",
    ),
    (
        "scope-map-reverse",
        "merge_preflight",
        "{harness} scope-map {task_id} --reverse",
        "Map candidate impact.",
    ),
    (
        "affected",
        "merge_preflight",
        "{harness} affected {task_id}",
        "Classify target drift.",
    ),
    (
        "context-audit",
        "merge_preflight",
        "{harness} context-audit {task_id}",
        "Check role context visibility.",
    ),
    (
        "dispatch",
        "integration",
        "{harness} dispatch {task_id}",
        "Run reviewer/gate dispatch.",
    ),
    (
        "integrate",
        "integration",
        "{harness} integrate {task_id}",
        "Write integration result.",
    ),
    (
        "gate",
        "completion",
        "{harness} gate {task_id}",
        "Run final gate.",
    ),
    (
        "post-review-gate",
        "completion",
        "{harness} post-review-gate {task_id}",
        "Run post-review gate.",
    ),
    (
        "pr-create",
        "external_write",
        "{harness} pr create {task_id}",
        "Create draft PR.",
    ),
    (
        "pr-checks",
        "external_read",
        "{harness} pr checks {task_id}",
        "Verify PR evidence.",
    ),
    (
        "land",
        "merge",
        "{harness} land {task_id}",
        "Land to local main.",
    ),
    (
        "compose",
        "merge",
        "{harness} compose {task_id} <other-task-id>",
        "Compose candidate set.",
    ),
    (
        "compose-push",
        "external_write",
        "{harness} compose-push {task_id} <other-task-id>",
        "Push composed set.",
    ),
    (
        "oracle",
        "merge",
        "{harness} oracle {task_id} --target-head <sha>",
        "Test candidate on target.",
    ),
    (
        "push",
        "external_write",
        "{harness} push {task_id}",
        "Push under policy.",
    ),
)

_MEASUREMENT_TOOL_SPECS = (
    (
        "session-start-context-hook",
        "context",
        "scripts/hook_session_start.py",
        "{env} python3 {{script}}",
        "Print bounded session context.",
    ),
    (
        "post-tool-use-hook",
        "observe",
        "scripts/hook_post_tool_use.py",
        "{env} python3 {{script}}",
        "Record task trajectory event.",
    ),
    (
        "nfr-metric",
        "measure",
        "scripts/nfr_metric.py",
        "{env} python3 {{script}} summary",
        "Summarize NFR samples.",
    ),
    (
        "bench-compare",
        "measure",
        "scripts/bench_compare.py",
        "{env} python3 {{script}} summary",
        "Compare benchmark samples.",
    ),
    (
        "abrun",
        "measure",
        "scripts/abrun.py",
        "{env} python3 {{script}} run --config <config.json>",
        "Run AB measurement.",
    ),
    (
        "check-runner",
        "measure",
        "scripts/check_runner.py",
        "{env} python3 {{script}} run --run-id <run-id> --worktree <path>",
        "Record check evidence.",
    ),
    (
        "verdict",
        "measure",
        "scripts/verdict.py",
        "{env} python3 {{script}} compare --baseline-run <id> --candidate-run <id>",
        "Compare run samples.",
    ),
    (
        "quality-gate",
        "measure",
        "scripts/quality_gate.py",
        "{env} python3 {{script}} evaluate --policy <policy.json>",
        "Evaluate quality policy.",
    ),
    (
        "measure-eval",
        "observe",
        "scripts/measure_eval.py",
        "{env} python3 {{script}}",
        "Summarize trajectory metrics.",
    ),
    (
        "surface-issues",
        "observe",
        "scripts/surface_issues.py",
        "{env} python3 {{script}}",
        "Surface recurring issues.",
    ),
)


def _writer_harness_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    specs = (*_WRITER_TOOL_SPECS[:3], *_WRITER_TOOL_SPECS[5:])
    return _harness_tools_from_specs("writer", harness, task_id, specs)


def _reviewer_harness_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    return [
        _harness_tool(
            "reviewer",
            "scope-map-reverse",
            "review",
            f"{harness} scope-map {task_id} --reverse",
            "Map candidate impact.",
        ),
        _harness_tool(
            "reviewer",
            "context-audit",
            "review",
            f"{harness} context-audit {task_id}",
            "Check role context visibility.",
        ),
        _harness_tool(
            "reviewer",
            "review-verdict",
            "review",
            f"{harness} review {task_id} --write-verdict <reviewer> approve|block",
            "Write reviewer verdict.",
        ),
        _harness_tool(
            "reviewer",
            "certify",
            "review",
            f"{harness} certify {task_id} --reviewer-id <reviewer>",
            "Certify fresh approve.",
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
                "Start writer session.",
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
    return [tool for tool in _measurement_tools(root, task_id, "integrator") if tool["name"] in names]


def _scope_checker_tools(root: Path, *, include_lane: bool) -> list[dict[str, Any]]:
    tools = [
        _script_tool(
            root,
            "context-scope-check",
            "scope_check",
            "scripts/check-context-scope.py",
            "python3 {script}",
            "Validate context scope.",
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
                "Validate lane map.",
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


def _tool(name: str, phase: str, command: str, purpose: str) -> dict[str, Any]:
    return {
        "name": name,
        "phase": phase,
        "command": command,
        "purpose": purpose,
        "skill": _tool_skill(name),
    }


def _tool_skill(name: str) -> str:
    if name.startswith("comm-") or name.startswith("acp-"):
        return "harness-acp-communication"
    if name in {
        "affected",
        "context-scope-check",
        "lane-map-check",
        "scope-map-forward",
        "scope-map-reverse",
    }:
        return "scope-routing-governance"
    return "architecture-check"


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
