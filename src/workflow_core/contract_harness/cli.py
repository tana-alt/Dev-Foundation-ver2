from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from workflow_core.cli import R6ArgumentParser
from workflow_core.contract_harness import review
from workflow_core.contract_harness.affected import classify_affected_set
from workflow_core.contract_harness.agent_comm import ALLOWED_INTENTS, list_inbox, send_message
from workflow_core.contract_harness.agent_tools import (
    agent_skill_groups,
    agent_tool_groups,
    optional_agent_tool_groups,
    role_agent_tools,
    role_optional_tools,
)
from workflow_core.contract_harness.application.pr_service import check_local_pr, create_local_pr
from workflow_core.contract_harness.certification import write_pass_certificate
from workflow_core.contract_harness.compose import compose_candidates, push_composed_candidates
from workflow_core.contract_harness.config import ConfigError
from workflow_core.contract_harness.context_audit import audit_context
from workflow_core.contract_harness.contract import load_contract, prepare
from workflow_core.contract_harness.daemon.client import (
    DaemonClient,
    load_root_token,
    load_session_credentials,
)
from workflow_core.contract_harness.daemon.errors import DaemonUnavailableError
from workflow_core.contract_harness.gate import gate_task
from workflow_core.contract_harness.gitutil import GitError, repo_root
from workflow_core.contract_harness.integration import dispatch_task, integrate_task
from workflow_core.contract_harness.land import land_task
from workflow_core.contract_harness.manual_resolution import check_manual_resolution
from workflow_core.contract_harness.merge_oracle import run_single_candidate_oracle
from workflow_core.contract_harness.push import push_task
from workflow_core.contract_harness.report import write_report
from workflow_core.contract_harness.roles import RoleError, current_role, require_allowed
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.scope_map import (
    write_forward_scope_map,
    write_reverse_scope_map,
)
from workflow_core.contract_harness.spawn import spawn_session
from workflow_core.contract_harness.status import task_status
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
    if command == "daemon":
        return _daemon_command(root, args)
    if _strict_enabled(args):
        return _strict_dispatch(root, args)
    if command == "review":
        return _review(root, args)
    if command == "pr":
        return _pr(root, args)
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
        "context-audit": lambda: _context_audit(root, args.task_id),
        "launch-writer": lambda: _launch_writer(root, args),
        "spawn": lambda: _spawn(root, args),
        "comm-send": lambda: _json(_comm_send(root, args), 0),
        "comm-inbox": lambda: _json(_comm_inbox(root, args), 0),
        "status": lambda: _json(task_status(root, args.task_id), 0),
        "oracle": lambda: _json_pair(
            run_single_candidate_oracle(
                root,
                args.task_id,
                target_head_sha=args.target_head,
                attempt=int(args.attempt),
            )
        ),
        "certify": lambda: _json(
            write_pass_certificate(root, args.task_id, args.reviewer_id),
            0,
        ),
        "compose": lambda: _json_pair(compose_candidates(root, args.task_ids)),
        "compose-push": lambda: _json_pair(push_composed_candidates(root, args.task_ids)),
        "manual-resolution-check": lambda: _json_pair(check_manual_resolution(root, args.task_id)),
        "land": lambda: _json_pair(land_task(root, args.task_id)),
        "push": lambda: _json_pair(push_task(root, args.task_id)),
        "report": lambda: _json(write_report(root, args.task_id, args.type), 0),
    }
    return handlers.get(command, _deferred)()


def _strict_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "strict", False)) or os.environ.get("FOUNDATION_MODE") == "strict"


def _strict_dispatch(root: Path, args: argparse.Namespace) -> int:
    method, params = _strict_method(args)
    if method.startswith("session.") or method == "integrity.verify":
        params["root_token"] = str(
            getattr(args, "root_token", None) or load_root_token(root, allow_file=False) or ""
        )
    session_id, token = load_session_credentials(
        root,
        session_id=getattr(args, "session_id", None),
        capability_token=getattr(args, "capability_token", None),
    )
    return _daemon_request(
        root,
        method,
        params,
        session_id=session_id,
        capability_token=token,
        write_env=getattr(args, "write_env", None),
    )


def _daemon_command(root: Path, args: argparse.Namespace) -> int:
    action = str(args.daemon_action)
    if action == "run":
        from workflow_core.contract_harness.daemon.server import main as daemon_main

        argv = ["run", "--repo", str(getattr(args, "repo", None) or root)]
        if getattr(args, "foreground", False):
            argv.append("--foreground")
        if getattr(args, "dev_open_session_create", False):
            argv.append("--dev-open-session-create")
        return daemon_main(argv)
    method = {
        "ping": "daemon.ping",
        "status": "daemon.status",
        "stop": "daemon.shutdown",
    }.get(action)
    if method is None:
        return _deferred()
    params: dict[str, Any] = {}
    if method == "daemon.shutdown":
        params["root_token"] = load_root_token(root, allow_file=True) or ""
    return _daemon_request(root, method, params)


def _daemon_request(
    root: Path,
    method: str,
    params: dict[str, Any],
    *,
    session_id: str | None = None,
    capability_token: str | None = None,
    write_env: str | None = None,
) -> int:
    try:
        response = DaemonClient.for_repo(root).request(
            method,
            params,
            session_id=session_id,
            capability_token=capability_token,
        )
    except DaemonUnavailableError as exc:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "request_id": "local",
                    "ok": False,
                    "result": None,
                    "error": {
                        "code": exc.code,
                        "message": str(exc),
                        "details": {},
                    },
                },
                sort_keys=True,
            )
        )
        return 1
    payload = response.model_dump(mode="json")
    print(json.dumps(payload, sort_keys=True))
    if response.ok and write_env:
        _write_session_env(Path(write_env), response.result or {})
    if not response.ok:
        return 1
    result = response.result or {}
    exit_code = result.get("exit_code")
    return int(exit_code) if isinstance(exit_code, int) else 0


def _write_session_env(path: Path, result: dict[str, Any]) -> None:
    session_id = str(result.get("session_id") or "")
    token = str(result.get("capability_token") or "")
    if not session_id or not token:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"FOUNDATION_SESSION_ID={session_id}\nFOUNDATION_CAPABILITY_TOKEN={token}\n",
        encoding="utf-8",
    )
    path.chmod(0o600)


def _strict_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    command = str(args.command)
    task_methods = {
        "prepare": "task.prepare",
        "context": "task.context",
        "status": "task.status",
        "verify": "candidate.verify",
        "submit": "candidate.submit",
        "gate": "gate.run",
        "land": "merge.local",
        "push": "push.remote",
        "complete": "task.complete",
    }
    if command in task_methods:
        return task_methods[command], {"task_id": args.task_id}
    complex_handlers = {
        "review": _strict_review_method,
        "pr": _strict_pr_method,
        "merge": _strict_merge_method,
        "session": _strict_session_method,
        "outbox": _strict_outbox_method,
        "integrity": _strict_integrity_method,
        "acp": _strict_acp_method,
    }
    handler = complex_handlers.get(command)
    if handler is not None:
        return handler(args)
    raise ValueError(f"strict command is not supported: {command}")


def _strict_review_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.collect:
        return "review.collect", {"task_id": args.task_id}
    return "review.run", {"task_id": args.task_id, "reviewer_id": args.run}


def _strict_pr_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    return f"pr.{args.pr_action}", {"task_id": args.task_id}


def _strict_merge_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    return "merge.local", {"task_id": args.task_id, "target": args.target}


def _strict_outbox_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    return f"outbox.{args.outbox_action}", {}


def _strict_integrity_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    return "integrity.verify", {"root_token": args.root_token or ""}


def _strict_session_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    action = str(args.session_action)
    if action == "create":
        return "session.create", {
            "role": args.role,
            "task_id": args.task,
            "agent_id": args.agent,
            "root_token": args.root_token or "",
        }
    if action == "revoke":
        return "session.revoke", {
            "session_id": args.session_to_revoke,
            "root_token": args.root_token or "",
        }
    return "session.list", {"root_token": args.root_token or ""}


def _strict_acp_method(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    action = str(args.acp_action)
    if action == "request-action":
        return "acp.request_action", {"message_id": args.message_id, "body": args.body or ""}
    if action == "list":
        return "acp.list", {"task_id": args.task_id, "agent_id": args.agent_id}
    return "acp.send", {
        "task_id": args.task_id,
        "to_agent_id": args.to_agent,
        "to_role": args.to_role,
        "kind": args.kind,
        "subject": args.subject,
        "body": args.body,
    }


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


def _pr(root: Path, args: argparse.Namespace) -> int:
    action = str(args.pr_action)
    require_allowed("pr", action=action)
    if action == "create":
        return _json_pair(create_local_pr(root, args.task_id))
    return _json_pair(check_local_pr(root, args.task_id))


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
    profile = str(args.profile)
    if role == "all":
        tools = (
            agent_tool_groups(root, args.task_id)
            if profile == "default"
            else optional_agent_tool_groups(root, args.task_id, profile)
        )
        return {"task_id": args.task_id, "profile": profile, "tools": tools}
    tools = (
        role_agent_tools(root, args.task_id, role)
        if profile == "default"
        else role_optional_tools(root, args.task_id, role, profile)
    )
    return {
        "task_id": args.task_id,
        "role": role,
        "profile": profile,
        "tools": tools,
    }


def _launch_writer(root: Path, args: argparse.Namespace) -> int:
    session = spawn_session(
        root,
        args.task_id,
        target_role="writer",
        agent="codex",
        agent_command=args.agent_command,
    )
    if args.shell:
        print(session["command"])
        return 0
    return _json(session, 0)


def _spawn(root: Path, args: argparse.Namespace) -> int:
    return _json(
        spawn_session(
            root,
            args.task_id,
            target_role=args.role,
            agent=args.agent,
            agent_command=args.agent_command,
            reviewer_id=args.reviewer_id,
            profile=args.profile,
            comm=bool(args.comm),
        ),
        0,
    )


def _comm_send(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    from_agent = str(args.from_agent or os.environ.get("FOUNDATION_AGENT_ID") or "")
    if not from_agent:
        raise ValueError("from-agent is required when FOUNDATION_AGENT_ID is unset")
    return send_message(
        root,
        args.task_id,
        from_agent_id=from_agent,
        from_role=current_role(),
        to_agent_id=args.to_agent,
        to_role=args.to_role,
        kind=args.kind,
        subject=args.subject,
        body_markdown=_body_text(args),
        auto_basis_refs=not bool(args.no_auto_basis_refs),
    )


def _comm_inbox(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    agent_id = str(args.agent_id or os.environ.get("FOUNDATION_AGENT_ID") or "")
    if not agent_id:
        raise ValueError("agent-id is required when FOUNDATION_AGENT_ID is unset")
    return list_inbox(root, args.task_id, agent_id=agent_id)


def _body_text(args: argparse.Namespace) -> str:
    if args.body_file:
        if args.body_file == "-":
            return sys.stdin.read()
        return Path(str(args.body_file)).read_text(encoding="utf-8")
    return str(args.body)


def _context_audit(root: Path, task_id: str) -> int:
    result = audit_context(root, task_id)
    return _json(result, 0 if result.get("status") == "pass" else 1)


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
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--session-id")
    parser.add_argument("--capability-token")
    sub = parser.add_subparsers(dest="command", required=True)
    _daemon_parser(sub)
    _task_command(sub, "prepare")
    _task_command(sub, "context")
    _task_command(sub, "explain")
    _task_command(sub, "verify")
    _task_command(sub, "gate")
    _submit_command(sub)
    _task_command(sub, "dispatch")
    _task_command(sub, "integrate")
    _task_command(sub, "affected")
    _scope_map_command(sub)
    _tools_command(sub)
    _task_command(sub, "context-audit")
    _launch_writer_command(sub)
    _spawn_command(sub)
    _comm_send_command(sub)
    _comm_inbox_command(sub)
    _task_command(sub, "status")
    _oracle_command(sub)
    _pr_command(sub)
    _certify_command(sub)
    _compose_command(sub)
    _compose_push_command(sub)
    _task_command(sub, "manual-resolution-check")
    _report_command(sub)
    _review_command(sub)
    _worktree_command(sub)
    _task_command(sub, "land")
    _task_command(sub, "push")
    _merge_command(sub)
    _task_command(sub, "complete")
    _session_command(sub)
    _outbox_command(sub)
    _acp_command(sub)
    _integrity_command(sub)
    return parser


def _daemon_parser(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("daemon")
    daemon_sub = parser.add_subparsers(dest="daemon_action", required=True)
    run = daemon_sub.add_parser("run")
    run.add_argument("--foreground", action="store_true")
    run.add_argument("--repo")
    run.add_argument("--dev-open-session-create", action="store_true")
    daemon_sub.add_parser("start")
    daemon_sub.add_parser("ping")
    daemon_sub.add_parser("status")
    daemon_sub.add_parser("stop")


def _submit_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("submit")
    parser.add_argument("task_id")
    parser.add_argument("--wait", action="store_true")


def _task_command(sub: argparse._SubParsersAction[Any], name: str) -> None:
    parser = sub.add_parser(name)
    parser.add_argument("task_id")


def _merge_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("merge")
    merge_sub = parser.add_subparsers(dest="merge_action", required=True)
    local = merge_sub.add_parser("local")
    local.add_argument("task_id")
    local.add_argument("--target", default="main")


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
    parser.add_argument("--profile", choices=["default", "measurement"], default="default")


def _launch_writer_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("launch-writer")
    parser.add_argument("task_id")
    parser.add_argument("--agent-command", default="codex --yolo")
    parser.add_argument("--shell", action="store_true")


def _spawn_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("spawn")
    parser.add_argument("task_id")
    parser.add_argument("--role", choices=["writer", "reviewer", "integrator"], required=True)
    parser.add_argument("--agent", choices=["codex", "claude", "custom"], required=True)
    parser.add_argument("--agent-command", default="codex --yolo")
    parser.add_argument("--reviewer-id")
    parser.add_argument("--profile", choices=["default", "measurement"], default="default")
    parser.add_argument("--comm", action="store_true")


def _comm_send_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("comm-send")
    parser.add_argument("task_id")
    parser.add_argument("--from-agent")
    parser.add_argument("--to-agent", required=True)
    parser.add_argument("--to-role", choices=["writer", "reviewer", "integrator"], required=True)
    parser.add_argument("--kind", choices=sorted(ALLOWED_INTENTS), required=True)
    parser.add_argument("--subject", required=True)
    body = parser.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file")
    parser.add_argument("--no-auto-basis-refs", action="store_true")


def _comm_inbox_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("comm-inbox")
    parser.add_argument("task_id")
    parser.add_argument("--agent-id")


def _oracle_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("oracle")
    parser.add_argument("task_id")
    parser.add_argument("--target-head", required=True)
    parser.add_argument("--attempt", type=int, default=1)


def _pr_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("pr")
    pr_sub = parser.add_subparsers(dest="pr_action", required=True)
    create = pr_sub.add_parser("create")
    create.add_argument("task_id")
    checks = pr_sub.add_parser("checks")
    checks.add_argument("task_id")


def _certify_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("certify")
    parser.add_argument("task_id")
    parser.add_argument("--reviewer-id", required=True)


def _compose_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("compose")
    parser.add_argument("task_ids", nargs="+")


def _compose_push_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("compose-push")
    parser.add_argument("task_ids", nargs="+")


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


def _session_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("session")
    session_sub = parser.add_subparsers(dest="session_action", required=True)
    create = session_sub.add_parser("create")
    create.add_argument(
        "--role",
        choices=["writer", "reviewer", "integrator", "admin"],
        required=True,
    )
    create.add_argument("--task")
    create.add_argument("--agent", required=True)
    create.add_argument("--root-token")
    create.add_argument("--write-env")
    revoke = session_sub.add_parser("revoke")
    revoke.add_argument("session_to_revoke")
    revoke.add_argument("--root-token")
    list_parser = session_sub.add_parser("list")
    list_parser.add_argument("--root-token")


def _outbox_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("outbox")
    outbox_sub = parser.add_subparsers(dest="outbox_action", required=True)
    outbox_sub.add_parser("resume")
    outbox_sub.add_parser("status")


def _acp_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("acp")
    acp_sub = parser.add_subparsers(dest="acp_action", required=True)
    send = acp_sub.add_parser("send")
    send.add_argument("task_id")
    send.add_argument("--to-agent", required=True)
    send.add_argument("--to-role", choices=["writer", "reviewer", "integrator"], required=True)
    send.add_argument("--kind", choices=sorted(ALLOWED_INTENTS), required=True)
    send.add_argument("--subject", required=True)
    send.add_argument("--body", required=True)
    list_parser = acp_sub.add_parser("list")
    list_parser.add_argument("task_id")
    list_parser.add_argument("--agent-id", required=True)
    request_action = acp_sub.add_parser("request-action")
    request_action.add_argument("message_id")
    request_action.add_argument("--body")


def _integrity_command(sub: argparse._SubParsersAction[Any]) -> None:
    parser = sub.add_parser("integrity")
    integrity_sub = parser.add_subparsers(dest="integrity_action", required=True)
    verify = integrity_sub.add_parser("verify")
    verify.add_argument("--root-token")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
