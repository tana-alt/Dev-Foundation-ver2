#!/usr/bin/env python3
"""SessionStart hook -- surface bounded harness context to the agent.

The hook's stdout lands in the session context. It prints a compact summary
from existing harness artifacts, then replays open measurement issues when
present. Non-blocking: silent when there is nothing to surface, always exits 0.

Env: FOUNDATION_PROJECT_ID, FOUNDATION_REPO_ROOT, HARNESS_RUNTIME_ROOT,
HARNESS_ROLE.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_MAX_SHOWN = 5
_MAX_LIST_ITEMS = 8
_MAX_TEXT_CHARS = 180


def main() -> int:
    try:
        sys.stdin.read()  # drain the hook payload; never echo or persist it
        root = _repo_root()
        project = _project_id(root)
        role = _role(root)
        for line in _harness_context_lines(root, project, role):
            print(line)
        for line in _issue_lines(root, project):
            print(line)
    except Exception as exc:
        print(f"hook_session_start: context skipped: {exc}", file=sys.stderr)
    return 0


def _harness_context_lines(root: Path, project: str, role: str) -> list[str]:
    runtime = _task_runtime_dir(root, project)
    context = _context_sources(root, runtime, project, role)
    if not context["available"]:
        return []

    lines = ["[harness assignment]"]
    _append_line(lines, "task_id", project)
    _append_line(lines, "role", role)
    _append_line(lines, "agent_id", _agent_id())
    _append_line(lines, "task yaml", _display_path(root, _task_yaml_path(root, project)))
    _append_line(lines, "packet dir", str(runtime))
    _append_line(lines, "packets", _list_text(_packet_names(runtime, role)))
    _append_line(
        lines, "review request architecture", _clip(context["review_request_architecture"])
    )
    _append_line(lines, "review request code", _clip(context["review_request_code"]))
    _append_line(lines, "goal", _clip(str(context["goal"])))
    _append_scope_lines(lines, context["scope"])
    _append_line(lines, "acceptance", _acceptance_text(context["acceptance"]))
    _append_line(lines, "policy", _policy_text(context["policy"]))
    _append_line(lines, "next action", _clip(str(context["next_action"])))
    _append_line(lines, "verifiers", _list_text(context["verifiers"]))
    _append_line(lines, "handoff commands", _list_text(context["handoff"]))
    _append_line(lines, "review output verdict", _review_verdict_path(runtime))
    _append_line(
        lines,
        "review output certificate",
        str(runtime / "reviews" / "certificates" / "<hash>.json"),
    )
    for label, command in _acp_command_lines(project, role):
        _append_line(lines, label, command)
    _append_line(lines, "issue escalation", _issue_command(project, role))
    _append_line(lines, "role tools", _list_text(context["tools"]))
    task_yaml = _display_path(root, _task_yaml_path(root, project))
    lines.append(
        "- refs: AGENTS.md; "
        f"{task_yaml}; "
        "runtime state/tasks/"
        f"{project}/{{contract.lock.json,capsule.json,resume-capsule.json}}"
    )
    return lines


def _context_sources(root: Path, runtime: Path, project: str, role: str) -> dict[str, Any]:
    contract = _read_json(runtime / "contract.lock.json")
    capsule = _read_json(runtime / "capsule.json")
    resume = _read_json(runtime / "resume-capsule.json")
    task = _read_task_yaml(_task_yaml_path(root, project))
    tools = _role_names(_read_json(runtime / "agent-tools.json"), role)
    if not tools:
        tools = _names(_dict_value(capsule, "agent_tools") or _dict_value(resume, "agent_tools"))
    architecture_review, code_review = _review_request(task)
    return {
        "available": contract is not None or capsule is not None or resume is not None,
        "review_request_architecture": architecture_review,
        "review_request_code": code_review,
        "goal": _first_text(
            _dict_value(resume, "task_goal"),
            _dict_value(contract, "goal"),
            _intent_summary(_dict_value(capsule, "intent")),
        ),
        "scope": _dict_value(contract, "scope_contract") or _dict_value(capsule, "scope_contract"),
        "acceptance": _dict_value(contract, "acceptance")
        or _dict_value(resume, "locked_acceptance"),
        "policy": _dict_value(contract, "policy") or _dict_value(resume, "policy"),
        "next_action": _first_text(
            _dict_value(resume, "next_expected_action"),
            _role_next_action(role),
        ),
        "verifiers": _verifier_ids(contract),
        "handoff": _handoff_names(runtime, role),
        "tools": tools,
    }


def _task_yaml_path(root: Path, project: str) -> Path:
    base = root / ".harness"
    legacy = base / "tasks" / project / "task.yaml"
    if legacy.is_file():
        return legacy
    matches = sorted(base.glob(f"*/tasks/{project}/task.yaml"))
    if len(matches) == 1:
        return matches[0]
    return legacy


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _packet_names(runtime: Path, role: str) -> list[str]:
    ordered = (
        "contract.lock.json",
        "capsule.json",
        "resume-capsule.json",
        "agent-tools.json",
        "verifier-plan.json",
    )
    names = [name for name in ordered if (runtime / name).is_file()]
    names.extend(path.name for path in _session_paths(runtime, role) if path.is_file())
    return names


def _review_request(task: dict[str, Any] | None) -> tuple[str, str]:
    request = _dict_value(task, "review_request")
    if not isinstance(request, dict):
        return "", ""
    return (
        _review_request_item(request.get("architecture_review")),
        _review_request_item(request.get("code_review")),
    )


def _review_request_item(value: Any) -> str:
    if isinstance(value, dict):
        return _first_text(value.get("ask"), value.get("prompt"), value.get("summary"))
    return str(value or "")


def _review_verdict_path(runtime: Path) -> str:
    reviewer_id = os.environ.get("FOUNDATION_REVIEWER_ID") or "<reviewer_id>"
    return str(runtime / "reviews" / f"{reviewer_id}.json")


def _agent_id() -> str:
    return os.environ.get("FOUNDATION_AGENT_ID") or "unset"


def _agent_id_ref() -> str:
    value = os.environ.get("FOUNDATION_AGENT_ID")
    return value if value else "AGENT_ID"


def _acp_command_lines(project: str, role: str) -> list[tuple[str, str]]:
    task = _quote(project)
    agent_id = _quote(_agent_id_ref())
    safe_role = _quote(role)
    role_env = f"FOUNDATION_AGENT_ID={agent_id} HARNESS_ROLE={safe_role}"
    return [
        ("ACP local peers", f"{role_env} ./harness comm-peers {task}"),
        (
            "ACP local inbox",
            f"{role_env} ./harness comm-inbox {task} --agent-id {agent_id}",
        ),
        (
            "ACP local send",
            (
                f"{role_env} ./harness comm-send {task} --to-agent TO_AGENT_ID "
                "--to-role TO_ROLE --kind KIND --subject SUBJECT --body BODY"
            ),
        ),
        ("ACP strict list", f"./harness --strict acp list {task} --agent-id {agent_id}"),
        (
            "ACP strict send",
            (
                f"./harness --strict acp send {task} --to-agent TO_AGENT_ID "
                "--to-role TO_ROLE --kind KIND --subject SUBJECT --body BODY"
            ),
        ),
        (
            "ACP strict request-action",
            "./harness --strict acp request-action MESSAGE_ID --body MESSAGE_BODY",
        ),
    ]


def _issue_command(project: str, role: str) -> str:
    if role != "writer":
        return ""
    return (
        f"HARNESS_ROLE={_quote(role)} ./harness issue-create {_quote(project)} "
        "--reason escalation --title ISSUE_TITLE --body ISSUE_BODY --execute"
    )


def _quote(value: str) -> str:
    return shlex.quote(value)


def _append_scope_lines(lines: list[str], scope: Any) -> None:
    if not isinstance(scope, dict):
        return
    _append_line(lines, "allowed paths", _list_text(scope.get("allowed_paths")))
    _append_line(lines, "forbidden paths", _list_text(scope.get("forbidden_paths")))


def _append_line(lines: list[str], label: str, value: str) -> None:
    if value:
        lines.append(f"- {label}: {value}")


def _issue_lines(root: Path, project: str) -> list[str]:
    path = root / "artifact" / project / "metrics" / "open-issues.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    issues = payload.get("issues") or []
    if not isinstance(issues, list) or not issues:
        return []

    generated_at = payload.get("generated_at", "unknown")
    lines = [
        f"[harness] {len(issues)} open issue(s) for project '{project}' "
        f"(measured {generated_at}; refresh with `make measure` then `make issues`):"
    ]
    for issue in issues[:_MAX_SHOWN]:
        if isinstance(issue, dict):
            lines.append(f"- [{issue.get('kind', '?')}] {_clip(str(issue.get('detail', '')))}")
    if len(issues) > _MAX_SHOWN:
        lines.append(f"- ... and {len(issues) - _MAX_SHOWN} more in {path.relative_to(root)}")
    return lines


def _repo_root() -> Path:
    if value := os.environ.get("FOUNDATION_REPO_ROOT"):
        return Path(value)
    marker_root = _nearest_marker_root(Path.cwd())
    if marker_root is not None:
        return _common_dir_parent(marker_root) or marker_root
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return Path(completed.stdout.strip())
    return Path(__file__).resolve().parents[1]


def _project_id(root: Path) -> str:
    for name in ("FOUNDATION_PROJECT_ID", "FOUNDATION_TASK_ID"):
        if value := os.environ.get(name):
            return value
    for candidate in (Path.cwd(), root):
        task_id = _marker_task_id(candidate)
        if task_id:
            return task_id
    return "default"


def _role(root: Path) -> str:
    for name in ("HARNESS_ROLE", "FOUNDATION_AGENT_ROLE"):
        if value := os.environ.get(name):
            return value
    for candidate in (Path.cwd(), root):
        role = _marker_role(candidate)
        if role:
            return role
    return "agent"


def _task_runtime_dir(root: Path, project: str) -> Path:
    if value := os.environ.get("HARNESS_RUNTIME_ROOT"):
        runtime = Path(value)
    else:
        runtime = _common_dir(root) / "harness-runtime"
    return runtime / "state" / "tasks" / project


def _common_dir(root: Path) -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        path = Path(completed.stdout.strip())
        return path if path.is_absolute() else root / path
    return root / ".git"


def _common_dir_parent(root: Path) -> Path | None:
    common = _common_dir(root)
    return common.resolve().parent if common.exists() else None


def _nearest_marker_root(start: Path) -> Path | None:
    for path in (start, *start.parents):
        if (path / ".harness-worktree.json").is_file():
            return path
    return None


def _marker_task_id(root: Path) -> str | None:
    value = _marker_value(root, "task_id")
    return str(value) if value else None


def _marker_role(root: Path) -> str | None:
    value = _marker_value(root, "kind")
    role = str(value) if value else ""
    return role if role in {"writer", "reviewer", "integrator"} else None


def _marker_value(root: Path, key: str) -> object | None:
    marker = root / ".harness-worktree.json"
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data.get(key)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_task_yaml(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import yaml

        data = yaml.safe_load(text)
    except Exception:
        data = _fallback_task_yaml(text)
    return data if isinstance(data, dict) else None


def _fallback_task_yaml(text: str) -> dict[str, Any]:
    review_request = _fallback_review_request(text)
    return {"review_request": review_request} if review_request else {}


def _fallback_review_request(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    in_review_request = False
    current: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0:
            in_review_request = stripped == "review_request:"
            current = None
            continue
        if not in_review_request:
            continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = _yaml_scalar(raw_value.strip())
        if indent == 2 and key in {"architecture_review", "code_review"}:
            current = key
            if value:
                result[current] = {"ask": value}
            else:
                result.setdefault(current, {})
            continue
        if indent >= 4 and current and key in {"ask", "prompt", "summary"}:
            section = result.setdefault(current, {})
            if isinstance(section, dict):
                section[key] = value
    return result


def _yaml_scalar(value: str) -> str:
    if value in {"", "|", ">"}:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _dict_value(data: dict[str, Any] | None, key: str) -> Any:
    return data.get(key) if isinstance(data, dict) else None


def _intent_summary(intent: Any) -> str:
    if not isinstance(intent, dict):
        return ""
    return str(intent.get("summary") or "")


def _role_names(data: dict[str, Any] | None, role: str) -> list[str]:
    if not isinstance(data, dict):
        return []
    return _names(data.get(role))


def _verifier_ids(contract: dict[str, Any] | None) -> list[str]:
    if not isinstance(contract, dict):
        return []
    plan = contract.get("verifier_plan")
    if not isinstance(plan, list):
        return []
    result: list[str] = []
    for item in plan:
        if isinstance(item, dict) and item.get("id"):
            result.append(str(item["id"]))
    return result


def _handoff_names(runtime: Path, role: str) -> list[str]:
    for path in _session_paths(runtime, role):
        data = _read_json(path)
        handoff = _dict_value(data, "handoff")
        if isinstance(handoff, dict):
            return [str(key) for key in handoff if str(key)]
    return []


def _session_paths(runtime: Path, role: str) -> list[Path]:
    if role in {"writer", "integrator"}:
        return [runtime / f"{role}-session.json"]
    if role == "reviewer":
        return sorted(runtime.glob("reviewer-session-*.json"))
    return []


def _names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        name = str(item.get("name") or "") if isinstance(item, dict) else str(item or "")
        if name:
            result.append(name)
    return result


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _acceptance_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    audit = value.get("audit")
    if isinstance(audit, dict) and audit.get("status"):
        parts.append(f"audit={audit['status']}")
    for key in ("mode", "source"):
        if value.get(key):
            parts.append(f"{key}={value[key]}")
    return ", ".join(parts)


def _policy_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("policy_id") or value.get("id") or "")


def _role_next_action(role: str) -> str:
    if role == "writer":
        return "implement verified candidate, then run harness verify and submit"
    if role == "reviewer":
        return "review submitted evidence and write a reviewer verdict"
    if role == "integrator":
        return "collect reviews, run gate, land, push, and handle PR checks as policy allows"
    return ""


def _list_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    items = [str(item) for item in value if str(item)]
    shown = items[:_MAX_LIST_ITEMS]
    suffix = f", +{len(items) - len(shown)} more" if len(items) > len(shown) else ""
    return ", ".join(shown) + suffix


def _clip(text: str) -> str:
    clean = " ".join(text.split())
    if len(clean) <= _MAX_TEXT_CHARS:
        return clean
    return clean[: _MAX_TEXT_CHARS - 3].rstrip() + "..."


if __name__ == "__main__":
    raise SystemExit(main())
