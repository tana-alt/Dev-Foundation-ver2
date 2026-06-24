from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import common_dir
from workflow_core.contract_harness.jsonio import read_json, write_json
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


def write_agent_skills(root: Path, task_id: str) -> dict[str, list[dict[str, Any]]]:
    skills = agent_skill_groups(root)
    write_json(task_dir(root, task_id) / "agent-skills.json", skills)
    return skills


def agent_skill_groups(root: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "writer": role_agent_skills(root, "writer"),
        "reviewer": role_agent_skills(root, "reviewer"),
        "integrator": role_agent_skills(root, "integrator"),
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


def role_agent_skills(root: Path, role: str) -> list[dict[str, Any]]:
    specs = {
        "writer": (
            ("tdd-scope", "acceptance_design", "Design focused acceptance checks first."),
            (
                "implementation-slice-verification",
                "implementation",
                "Keep the task runnable through small verified slices.",
            ),
            (
                "scope-routing-governance",
                "context_boundary",
                "Keep context bounded to the current task and named refs.",
            ),
        ),
        "reviewer": (
            (
                "security-check",
                "semantic_review",
                "Escalate auth, secret, external write, or irreversible risk.",
            ),
            (
                "implementation-slice-verification",
                "semantic_review",
                "Check whether the shipped slice matches the goal and evidence.",
            ),
            (
                "scope-routing-governance",
                "semantic_review",
                "Keep review context bounded to submitted evidence and named refs.",
            ),
        ),
        "integrator": (
            (
                "implementation-slice-verification",
                "merge_boundary",
                "Check branch, worktree, and changed-path boundaries.",
            ),
            (
                "scope-routing-governance",
                "merge_boundary",
                "Choose and report the narrowest verification before handoff.",
            ),
        ),
    }
    if role not in specs:
        raise ValueError(f"unknown role for agent skills: {role}")
    return [_skill(root, name, phase, purpose) for name, phase, purpose in specs[role]]


_WRITER_CORE_TOOL_SPECS = (
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
        "Quantify role packet size and required tool or skill visibility.",
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

_WRITER_COORDINATION_TOOL_SPECS = (
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
        "comm-peers",
        "coordination",
        "{harness} comm-peers {task_id}",
        "List task-scoped peer agent ids, roles, and briefs for local ACP-style handoff.",
    ),
    (
        "comm-send",
        "coordination",
        ("{harness} comm-send {task_id} --to <agent-id> --subject <subject> --body <message>"),
        "Send a non-authoritative task-scoped ACP-style message to another agent.",
    ),
    (
        "comm-inbox",
        "coordination",
        "{harness} comm-inbox {task_id}",
        "Read the current agent inbox from task-scoped runtime state.",
    ),
    (
        "spawn-writer",
        "coordination",
        "{harness} spawn {task_id} --role writer --agent codex",
        "Start or rebind a writer session without running verification.",
    ),
    (
        "report-rfc",
        "exception",
        "{harness} report {task_id} --type rfc",
        "Create durable RFC evidence for irreversible or policy-sensitive work.",
    ),
    (
        "report-metric",
        "exception",
        "{harness} report {task_id} --type metric",
        "Create durable metric evidence summary when quantitative results matter.",
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
        "Quantify role packet size and required tool or skill visibility.",
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
        "spawn",
        "coordination",
        "{harness} spawn {task_id} --role writer --agent codex",
        "Start or rebind a role session without running authority actions.",
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
)

_MEASUREMENT_TOOL_SPECS = (
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
    return _harness_tools_from_specs("writer", harness, task_id, _WRITER_CORE_TOOL_SPECS)


def _coordination_tools(root: Path, task_id: str, role: str) -> list[dict[str, Any]]:
    if role == "writer":
        harness = _harness_command(root)
        return _harness_tools_from_specs(
            "writer",
            harness,
            task_id,
            _WRITER_COORDINATION_TOOL_SPECS,
        )
    return []


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
            "Quantify role packet size and required tool or skill visibility.",
        ),
        _harness_tool(
            "reviewer",
            "status",
            "review",
            f"{harness} status {task_id}",
            "Read artifact-backed task status without changing workflow state.",
        ),
        _harness_tool(
            "reviewer",
            "passport",
            "review",
            f"{harness} passport {task_id}",
            "Read normalized proof, review, policy, and state evidence without rerunning checks.",
        ),
        _harness_tool(
            "reviewer",
            "review-verdict",
            "review",
            f"{harness} review {task_id} --write-verdict <reviewer> approve|block",
            "Write a harness-owned reviewer verdict with current evidence hashes.",
        ),
        _harness_tool(
            "reviewer",
            "certify",
            "review",
            f"{harness} certify {task_id} --reviewer-id <reviewer>",
            "Write a content-bound pass certificate for a fresh approve verdict.",
        ),
    ]


def _integrator_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    harness = _harness_command(root)
    return _harness_tools_from_specs("integrator", harness, task_id, _INTEGRATOR_TOOL_SPECS)


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
        "post-tool-use-hook",
        "nfr-metric",
        "bench-compare",
        "verdict",
        "quality-gate",
        "surface-issues",
    }
    return [tool for tool in _measurement_tools(root, task_id, "reviewer") if tool["name"] in names]


def _integrator_measurement_tools(root: Path, task_id: str) -> list[dict[str, Any]]:
    names = {"post-tool-use-hook", "measure-eval", "surface-issues"}
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


def _tool(name: str, phase: str, command: str, purpose: str) -> dict[str, Any]:
    return {
        "name": name,
        "phase": phase,
        "command": command,
        "purpose": purpose,
    }


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


def _skill(root: Path, name: str, phase: str, purpose: str) -> dict[str, Any]:
    path = _skill_path(root, name)
    return {
        "name": name,
        "phase": phase,
        "path": str(path) if path is not None else None,
        "purpose": purpose,
    }


def _skill_path(root: Path, name: str) -> Path | None:
    bases = _skill_search_bases(root)
    for base in bases:
        candidate = base / ".agents" / "skills" / name / "SKILL.md"
        if candidate.is_file():
            return candidate
    return None


def _skill_search_bases(root: Path) -> tuple[Path, ...]:
    if not _is_harness_worktree(root):
        return (root, _PACKAGE_ROOT)
    source = _marker_source_root(root)
    if source is None or source.resolve() == root.resolve():
        return (root,)
    return (root, source)


def _marker_source_root(root: Path) -> Path | None:
    marker = root / ".harness-worktree.json"
    if not marker.is_file():
        return None
    try:
        data = read_json(marker)
    except (OSError, ValueError):
        return None
    common = data.get("source_repo_common_dir")
    if not common:
        return None
    return Path(str(common)).resolve().parent


def _is_harness_worktree(root: Path) -> bool:
    return (root / ".harness-worktree.json").is_file()
