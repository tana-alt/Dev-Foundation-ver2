from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from workflow_core.cli import R6ArgumentParser
from workflow_core.contract_harness import review
from workflow_core.contract_harness.affected import classify_affected_set
from workflow_core.contract_harness.agent_tools import (
    agent_skill_groups,
    agent_tool_groups,
    role_agent_tools,
)
from workflow_core.contract_harness.config import ConfigError
from workflow_core.contract_harness.contract import load_contract, prepare
from workflow_core.contract_harness.gate import gate_task
from workflow_core.contract_harness.gitutil import GitError, repo_root
from workflow_core.contract_harness.integration import dispatch_task, integrate_task
from workflow_core.contract_harness.land import land_task
from workflow_core.contract_harness.push import push_task
from workflow_core.contract_harness.report import write_report
from workflow_core.contract_harness.roles import RoleError, require_allowed
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.scope_map import (
    write_forward_scope_map,
    write_reverse_scope_map,
)
from workflow_core.contract_harness.submission import submit_task
from workflow_core.contract_harness.verify import verify_task
from workflow_core.contract_harness.worktree import create_worktree


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except (ConfigError, GitError, RoleError, OSError, ValueError, KeyError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, sort_keys=True))
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    root = repo_root(Path.cwd())
    command = str(args.command)
    if command == "review":
        return _review(root, args)
    require_allowed(command)
    handlers: dict[str, Callable[[], int]] = {
        "prepare": lambda: _json(prepare(root, args.task_id), 0),
        "explain": lambda: _explain(root, args.task_id),
        "verify": lambda: _json_pair(verify_task(root, args.task_id)),
        "gate": lambda: _json_pair(gate_task(root, args.task_id)),
        "submit": lambda: _json_pair(
            submit_task(
                root,
                args.task_id,
                wait=bool(args.wait),
                harness_bin=_harness_bin(),
            )
        ),
        "dispatch": lambda: _json_pair(
            dispatch_task(root, args.task_id, harness_bin=_harness_bin())
        ),
        "integrate": lambda: _json_pair(
            integrate_task(root, args.task_id, harness_bin=_harness_bin())
        ),
        "worktree": lambda: _json(_worktree(root, args), 0),
        "affected": lambda: _json(classify_affected_set(root, args.task_id), 0),
        "scope-map": lambda: _json(_scope_map(root, args), 0),
        "tools": lambda: _json(_tools(root, args), 0),
        "land": lambda: _json_pair(land_task(root, args.task_id)),
        "push": lambda: _json_pair(push_task(root, args.task_id)),
        "report": lambda: _json(write_report(root, args.task_id, args.type), 0),
    }
    return handlers.get(command, _deferred)()


def _review(root: Path, args: argparse.Namespace) -> int:
    action = _review_action(args)
    require_allowed("review", action=action)
    if action == "run":
        return _json(review.run_profile(root, args.task_id, args.run), 0)
    if action == "write-verdict":
        labels = args.label or []
        data = review.write_verdict(
            root,
            args.task_id,
            args.reviewer_id,
            args.verdict,
            labels=labels,
            reason=args.reason or "",
        )
        return _json(data, 0)
    return _json(review.collect(root, args.task_id), 0)


def _review_action(args: argparse.Namespace) -> str:
    if args.collect:
        return "collect"
    if args.run:
        return "run"
    return "write-verdict"


def _explain(root: Path, task_id: str) -> int:
    contract = load_contract(root, task_id)
    runtime = task_dir(root, task_id)
    scope = contract["scope_contract"]
    tools = agent_tool_groups(root, task_id)
    skills = agent_skill_groups(root)
    print(f"task: {task_id}")
    print(f"allowed paths: {', '.join(scope['allowed_paths'])}")
    print(f"forbidden paths: {', '.join(scope['forbidden_paths'])}")
    print(f"verifiers: {', '.join(item['id'] for item in contract['verifier_plan'])}")
    for role, items in tools.items():
        print(f"{role} tools: {', '.join(item['name'] for item in items)}")
    for role, items in skills.items():
        print(f"{role} skills: {', '.join(item['name'] for item in items)}")
    print(f"runtime: {runtime}")
    return 0


def _scope_map(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    if args.forward:
        return write_forward_scope_map(root, args.task_id)
    return write_reverse_scope_map(root, args.task_id)


def _tools(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    role = str(args.role)
    if role == "all":
        return {"task_id": args.task_id, "tools": agent_tool_groups(root, args.task_id)}
    return {
        "task_id": args.task_id,
        "role": role,
        "tools": role_agent_tools(root, args.task_id, role),
    }


def _worktree(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    if args.writer:
        return create_worktree(root, args.task_id, kind="writer")
    if args.integrator:
        return create_worktree(root, args.task_id, kind="integrator")
    return create_worktree(root, args.task_id, kind="reviewer", reviewer_id=args.reviewer)


def _json(data: dict[str, Any], code: int) -> int:
    print(json.dumps(data, sort_keys=True))
    return code


def _json_pair(pair: tuple[dict[str, Any], int]) -> int:
    data, code = pair
    return _json(data, code)


def _deferred() -> int:
    print(json.dumps({"ok": False, "reason": "deferred_in_mvp"}, sort_keys=True))
    return 1


def _harness_bin() -> Path:
    current = Path(sys.argv[0]).resolve()
    if current.exists():
        return current
    return Path(__file__).resolve().parents[3] / "harness"


def _parser() -> argparse.ArgumentParser:
    parser = R6ArgumentParser(prog="./harness")
    sub = parser.add_subparsers(dest="command", required=True)
    _task_command(sub, "prepare")
    _task_command(sub, "explain")
    _task_command(sub, "verify")
    _task_command(sub, "gate")
    _submit_command(sub)
    _task_command(sub, "dispatch")
    _task_command(sub, "integrate")
    _task_command(sub, "affected")
    _scope_map_command(sub)
    _tools_command(sub)
    _report_command(sub)
    _review_command(sub)
    _worktree_command(sub)
    _task_command(sub, "land")
    _task_command(sub, "push")
    _rfc_command(sub)
    return parser


def _submit_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("submit")
    parser.add_argument("task_id")
    parser.add_argument("--wait", action="store_true")


def _task_command(sub: argparse._SubParsersAction[Any], name: str) -> None:
    parser = sub.add_parser(name)
    parser.add_argument("task_id")


def _worktree_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("worktree")
    parser.add_argument("task_id")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--writer", action="store_true")
    group.add_argument("--integrator", action="store_true")
    group.add_argument("--reviewer")


def _scope_map_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("scope-map")
    parser.add_argument("task_id")
    direction = parser.add_mutually_exclusive_group(required=True)
    direction.add_argument("--forward", action="store_true")
    direction.add_argument("--reverse", action="store_true")


def _tools_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("tools")
    parser.add_argument("task_id")
    parser.add_argument(
        "--role", choices=["writer", "reviewer", "integrator", "all"], default="all"
    )


def _report_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("report")
    parser.add_argument("task_id")
    parser.add_argument("--type", choices=["incident", "rfc", "metric"], required=True)


def _review_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("review")
    parser.add_argument("task_id")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run")
    group.add_argument("--collect", action="store_true")
    group.add_argument("--write-verdict", dest="reviewer_id")
    parser.add_argument("verdict", nargs="?", choices=["approve", "block"])
    parser.add_argument("--label", action="append")
    parser.add_argument("--reason")


def _rfc_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("rfc")
    parser.add_argument("task_id")
    parser.add_argument("decision", choices=["approve", "reject"])
    parser.add_argument("rfc_id")
    parser.add_argument("--reason", required=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
