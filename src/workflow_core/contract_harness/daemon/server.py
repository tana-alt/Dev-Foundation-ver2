from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.adapters.filesystem_evidence_store import (
    FilesystemEvidenceStore,
)
from workflow_core.contract_harness.adapters.local_secret_store import LocalSecretStore
from workflow_core.contract_harness.adapters.sqlite_state_store import SQLiteStateStore
from workflow_core.contract_harness.agent_comm import list_inbox, send_message
from workflow_core.contract_harness.application.capability_service import (
    CapabilityError,
    CapabilityService,
    ForbiddenError,
    UnauthorizedError,
    session_actor,
)
from workflow_core.contract_harness.application.outbox import OutboxService
from workflow_core.contract_harness.application.recovery import reconcile_task
from workflow_core.contract_harness.application.runtime_lock import RuntimeLock
from workflow_core.contract_harness.application.services import evidence_root, state_db_path
from workflow_core.contract_harness.config import ConfigError
from workflow_core.contract_harness.contract import prepare
from workflow_core.contract_harness.daemon.client import (
    DaemonClient,
    daemon_auth_dir,
    daemon_socket_path,
)
from workflow_core.contract_harness.daemon.client import load_root_token as client_load_root_token
from workflow_core.contract_harness.daemon.protocol import (
    DaemonRequest,
    DaemonResponse,
    error_response,
    ok_response,
)
from workflow_core.contract_harness.domain.capabilities import METHOD_CAPABILITIES, Capability
from workflow_core.contract_harness.domain.errors import IntegrityError
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.gate import gate_task
from workflow_core.contract_harness.gitutil import GitError, repo_root
from workflow_core.contract_harness.jsonio import read_json, write_json_atomic
from workflow_core.contract_harness.post_review_gate import run_post_review_gate
from workflow_core.contract_harness.review import collect as collect_reviews
from workflow_core.contract_harness.review import run_mode as run_review_mode
from workflow_core.contract_harness.review import run_profile
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.status import task_status
from workflow_core.contract_harness.submission import submit_task
from workflow_core.contract_harness.verify import verify_task

READ_ONLY_METHODS = {
    "daemon.ping",
    "daemon.status",
    "task.context",
    "task.status",
    "integrity.verify",
    "acp.list",
}


class InvalidStateError(RuntimeError):
    pass


class DaemonServer:
    def __init__(
        self,
        repo_root: Path,
        *,
        foreground: bool = False,
        dev_open_session_create: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.foreground = foreground
        self.dev_open_session_create = dev_open_session_create
        self.runtime_root = runtime_root(repo_root)
        self.daemon_dir = self.runtime_root / "daemon"
        self.socket_path = daemon_socket_path(repo_root)
        self.pid_path = self.daemon_dir / "foundation.pid"
        self.metadata_path = self.daemon_dir / "daemon.json"
        self.lock = RuntimeLock(self.daemon_dir / "daemon.lock")
        self._shutdown_requested = False
        self.root_token = ""
        self.evidence = FilesystemEvidenceStore(evidence_root(repo_root))
        self.store = SQLiteStateStore(state_db_path(repo_root), evidence_store=self.evidence)
        self.capabilities = CapabilityService(self.store)
        self.outbox = OutboxService(repo_root, self.store)
        self.degraded_reason: str | None = None

    def serve_forever(self) -> int:
        self._prepare_runtime()
        if not self.lock.acquire():
            _print_json_error("conflict", "foundationd already running for this repository")
            return 1
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self._initialize_authority()
            if self.socket_path.exists():
                self.socket_path.unlink()
            sock.bind(str(self.socket_path))
            sock.listen(16)
            self.socket_path.chmod(0o600)
            self._write_metadata()
            while not self._shutdown_requested:
                conn, _addr = sock.accept()
                with conn:
                    try:
                        self._handle_connection(conn)
                    except (BrokenPipeError, ConnectionResetError):
                        continue
        except KeyboardInterrupt:
            return 0
        finally:
            sock.close()
            self._cleanup()
        return 0

    def shutdown(self) -> None:
        self._shutdown_requested = True

    def _prepare_runtime(self) -> None:
        for path in [
            self.runtime_root,
            self.runtime_root / "state",
            self.runtime_root / "objects",
            evidence_root(self.repo_root),
            self.daemon_dir,
            daemon_auth_dir(self.repo_root),
            daemon_auth_dir(self.repo_root) / "sessions",
        ]:
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)

    def _initialize_authority(self) -> None:
        self.root_token = LocalSecretStore(daemon_auth_dir(self.repo_root)).get_or_create_token(
            "root.token",
            prefix="froot",
        )
        try:
            self.store.verify_integrity()
        except IntegrityError as exc:
            self.degraded_reason = str(exc)

    def _write_metadata(self) -> None:
        write_json_atomic(
            self.metadata_path,
            {
                "schema_version": 1,
                "pid": os.getpid(),
                "repo_root": str(self.repo_root),
                "runtime_root": str(self.runtime_root),
                "socket_path": str(self.socket_path),
                "mode": "degraded" if self.degraded_reason else "local-strict",
                "degraded_reason": self.degraded_reason,
            },
        )
        self.pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self.pid_path.chmod(0o600)

    def _cleanup(self) -> None:
        for path in (self.socket_path, self.pid_path):
            with suppress(FileNotFoundError):
                path.unlink()
        self.lock.release()

    def _handle_connection(self, conn: socket.socket) -> None:
        raw = _read_line(conn)
        response = self._response_for_raw(raw)
        payload = json.dumps(response.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        conn.sendall(payload + b"\n")

    def _response_for_raw(self, raw: bytes) -> DaemonResponse:
        try:
            data = json.loads(raw.decode("utf-8"))
            request = DaemonRequest.model_validate(data)
        except Exception as exc:
            return error_response(
                "unknown",
                code="usage_error",
                message="malformed daemon request",
                details={"error": str(exc)},
            )
        try:
            return self._dispatch(request)
        except CapabilityError as exc:
            return error_response(request.request_id, code=exc.code, message=str(exc))
        except InvalidStateError as exc:
            return error_response(request.request_id, code="invalid_state", message=str(exc))
        except IntegrityError as exc:
            return error_response(request.request_id, code="integrity_error", message=str(exc))
        except (ConfigError, GitError, OSError, ValueError, KeyError, RuntimeError) as exc:
            return error_response(request.request_id, code="internal_error", message=str(exc))

    def _dispatch(self, request: DaemonRequest) -> DaemonResponse:
        method = request.method
        if method == "daemon.ping":
            return ok_response(request.request_id, {"status": "running", "mode": self.mode})
        if method == "daemon.status":
            return ok_response(request.request_id, self._daemon_status())
        if method == "daemon.shutdown":
            self._authorize_admin_or_root(request)
            self.shutdown()
            return ok_response(request.request_id, {"status": "stopping"})
        if self.degraded_reason and method not in READ_ONLY_METHODS:
            return error_response(
                request.request_id,
                code="integrity_error",
                message="StateStore integrity check failed; daemon is in degraded read-only mode",
                details={"reason": self.degraded_reason},
            )
        if method == "session.create":
            return ok_response(request.request_id, self._create_session(request))
        if method == "session.revoke":
            self._authorize_admin_or_root(request)
            return ok_response(request.request_id, self._revoke_session(request.params))
        if method == "session.list":
            self._authorize_admin_or_root(request)
            return ok_response(request.request_id, {"sessions": self.capabilities.list_sessions()})
        if method == "integrity.verify" and self._root_token_matches(request):
            return ok_response(request.request_id, self._integrity_result())
        required = METHOD_CAPABILITIES.get(method)
        if required is None:
            return error_response(request.request_id, code="usage_error", message="unknown method")
        session = self.capabilities.authorize(
            session_id=request.session_id,
            token=request.capability_token,
            required=required,
        )
        self._authorize_task_scope(session, request.params)
        with _session_environment(str(session.role), session_actor(session), session.agent_id):
            return ok_response(
                request.request_id,
                self._dispatch_authorized(method, request.params),
            )

    @property
    def mode(self) -> str:
        return "degraded" if self.degraded_reason else "local-strict"

    def _daemon_status(self) -> dict[str, Any]:
        return {
            "status": "running",
            "mode": self.mode,
            "daemon": {
                "running": True,
                "pid": os.getpid(),
                "socket_path": str(self.socket_path),
                "runtime_root": str(self.runtime_root),
            },
            "degraded_reason": self.degraded_reason,
        }

    def _create_session(self, request: DaemonRequest) -> dict[str, Any]:
        params = request.params
        if not self.dev_open_session_create:
            try:
                self._authorize_admin_or_root(request)
            except UnauthorizedError:
                raise
        session, token = self.capabilities.create_session(
            role=str(params["role"]),
            agent_id=str(params["agent_id"]),
            task_id=str(params["task_id"]) if params.get("task_id") is not None else None,
            expires_at=str(params["expires_at"]) if params.get("expires_at") is not None else None,
        )
        result = {
            "session_id": session.session_id,
            "capability_token": token,
            "role": session.role,
            "agent_id": session.agent_id,
            "task_id": session.task_id,
            "capabilities": [cap.value for cap in session.capabilities],
        }
        self._write_session_files(result)
        return result

    def _authorize_admin_or_root(self, request: DaemonRequest) -> None:
        if self._root_token_matches(request):
            return
        if request.session_id and request.capability_token:
            self.capabilities.authorize(
                session_id=request.session_id,
                token=request.capability_token,
                required=Capability.ADMIN,
            )
            return
        raise UnauthorizedError("root token or admin session is required")

    def _root_token_matches(self, request: DaemonRequest) -> bool:
        root_token = request.params.get("root_token")
        return isinstance(root_token, str) and bool(root_token) and root_token == self.root_token

    def _authorize_task_scope(self, session: Any, params: dict[str, Any]) -> None:
        task_id = params.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return
        if session.task_id is None or Capability.ADMIN in session.capabilities:
            return
        if session.task_id != task_id:
            raise ForbiddenError("session is not scoped to this task")

    def _write_session_files(self, result: dict[str, Any]) -> None:
        sessions_dir = daemon_auth_dir(self.repo_root) / "sessions"
        for name in (
            str(result["session_id"]),
            str(result["role"]),
            str(result["agent_id"]),
        ):
            path = sessions_dir / f"{_safe_component(name)}.json"
            write_json_atomic(path, result)
            path.chmod(0o600)

    def _revoke_session(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = str(params["session_id"])
        revoked = self.capabilities.revoke_session(session_id)
        return {"session_id": session_id, "revoked": revoked}

    def _dispatch_authorized(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "task.prepare": self._handle_task_prepare,
            "task.context": self._handle_task_context,
            "task.status": self._handle_task_status,
            "candidate.verify": self._handle_candidate_verify,
            "candidate.submit": self._handle_candidate_submit,
            "review.run": self._handle_review_run,
            "review.run_mode": self._handle_review_run_mode,
            "review.collect": self._handle_review_collect,
            "gate.run": self._handle_gate_run,
            "gate.post_review": self._handle_gate_post_review,
            "pr.create": self._handle_pr_create,
            "pr.checks": self._handle_pr_checks,
            "merge.local": self._handle_merge_local,
            "task.complete": self._handle_task_complete,
            "push.remote": self._handle_push_remote,
            "outbox.resume": self._handle_outbox_resume,
            "outbox.status": self._handle_outbox_status,
            "reconcile.task": self._handle_reconcile_task,
            "integrity.verify": self._handle_integrity_verify,
            "acp.send": self._handle_acp_send,
            "acp.list": self._handle_acp_list,
            "acp.request_action": self._handle_acp_request_action,
        }
        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"unknown method: {method}")
        return handler(params)

    def _handle_task_prepare(self, params: dict[str, Any]) -> dict[str, Any]:
        return prepare(self.repo_root, str(params["task_id"]))

    def _handle_task_context(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._task_context(str(params["task_id"]))

    def _handle_task_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._task_status(str(params["task_id"]))

    def _handle_candidate_verify(self, params: dict[str, Any]) -> dict[str, Any]:
        return _with_exit_code(verify_task(self.repo_root, str(params["task_id"])))

    def _handle_candidate_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_phase(str(params["task_id"]), {WorkflowPhase.VERIFIED})
        return _with_exit_code(submit_task(self.repo_root, str(params["task_id"])))

    def _handle_review_run(self, params: dict[str, Any]) -> dict[str, Any]:
        return run_profile(
            self.repo_root,
            str(params["task_id"]),
            str(params["reviewer_id"]),
        )

    def _handle_review_run_mode(self, params: dict[str, Any]) -> dict[str, Any]:
        return run_review_mode(
            self.repo_root,
            str(params["task_id"]),
            str(params["mode"]),
        )

    def _handle_review_collect(self, params: dict[str, Any]) -> dict[str, Any]:
        return collect_reviews(self.repo_root, str(params["task_id"]))

    def _handle_gate_run(self, params: dict[str, Any]) -> dict[str, Any]:
        return _with_exit_code(gate_task(self.repo_root, str(params["task_id"])))

    def _handle_gate_post_review(self, params: dict[str, Any]) -> dict[str, Any]:
        return _with_exit_code(run_post_review_gate(self.repo_root, str(params["task_id"])))

    def _handle_pr_create(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_effect("create_pr", str(params["task_id"]), params)

    def _handle_pr_checks(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_effect("pr_checks", str(params["task_id"]), params)

    def _handle_merge_local(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_effect("merge_local", str(params["task_id"]), params)

    def _handle_task_complete(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_effect("complete_task", str(params["task_id"]), params)

    def _handle_push_remote(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_effect("push_remote", str(params["task_id"]), params)

    def _handle_outbox_resume(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self.outbox.resume()

    def _handle_outbox_status(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self.outbox.status()

    def _handle_reconcile_task(self, params: dict[str, Any]) -> dict[str, Any]:
        return reconcile_task(self.repo_root, str(params["task_id"]))

    def _handle_integrity_verify(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self._integrity_result()

    def _handle_acp_send(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._acp_send(params)

    def _handle_acp_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return list_inbox(
            self.repo_root,
            str(params["task_id"]),
            agent_id=str(params["agent_id"]),
        )

    def _handle_acp_request_action(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._acp_request_action(params)

    def _task_context(self, task_id: str) -> dict[str, Any]:
        runtime = task_dir(self.repo_root, task_id)
        result: dict[str, Any] = {"task_id": task_id}
        for key, name in (("contract", "contract.lock.json"), ("capsule", "capsule.json")):
            path = runtime / name
            payload = read_json(path) if path.is_file() else None
            result[key] = _context_payload(payload) if key == "capsule" else payload
        contract = result.get("contract")
        result["scope_contract"] = None
        if isinstance(contract, dict):
            result["scope_contract"] = contract.get("scope_contract")
        return result

    def _task_status(self, task_id: str) -> dict[str, Any]:
        status = task_status(self.repo_root, task_id)
        status["mode"] = self.mode
        status["daemon"] = self._daemon_status()["daemon"]
        if status.get("state_store", {}).get("current_phase") == WorkflowPhase.COMPLETE.value:
            status["completion"] = {"complete": True}
        return status

    def _require_phase(self, task_id: str, allowed: set[WorkflowPhase]) -> None:
        current = self.store.current_phase(task_id)
        if current not in allowed:
            raise InvalidStateError(f"current phase is {current}")

    def _request_effect(
        self,
        effect_type: str,
        task_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_id = _candidate_id(self.repo_root, task_id)
        idempotency_key = _idempotency_key(effect_type, task_id, candidate_id, params)
        existing = self.store.get_effect_by_idempotency_key(idempotency_key)
        requested_event_sha256 = (
            str(existing.get("requested_event_sha256")) if existing is not None else None
        )
        if existing is None:
            event = self.store.append_event(
                task_id=task_id,
                candidate_id=candidate_id,
                event_type=f"{effect_type.upper()}_REQUESTED",
                from_phase=self.store.current_phase(task_id),
                to_phase=self.store.current_phase(task_id) or WorkflowPhase.UNKNOWN,
                payload={"idempotency_key": idempotency_key, "params": params},
                actor=os.environ.get("HARNESS_ACTOR") or "daemon",
            )
            requested_event_sha256 = event.event_sha256
        return self.outbox.request_effect(
            effect_type=effect_type,
            task_id=task_id,
            candidate_id=candidate_id,
            idempotency_key=idempotency_key,
            payload=params,
            requested_event_sha256=requested_event_sha256,
        )

    def _integrity_result(self) -> dict[str, Any]:
        if self.degraded_reason:
            return {
                "status": "fail",
                "reason": self.degraded_reason,
                "mode": self.mode,
            }
        return self.store.verify_integrity()

    def _acp_send(self, params: dict[str, Any]) -> dict[str, Any]:
        return send_message(
            self.repo_root,
            str(params["task_id"]),
            from_agent_id=str(os.environ.get("FOUNDATION_AGENT_ID") or "strict-cli"),
            from_role=str(os.environ.get("HARNESS_ROLE") or "writer"),
            to_agent_id=str(params["to_agent_id"]),
            to_role=str(params["to_role"]),
            kind=str(params["kind"]),
            subject=str(params.get("subject") or ""),
            body_markdown=str(params.get("body") or ""),
        )

    def _acp_request_action(self, params: dict[str, Any]) -> dict[str, Any]:
        body = str(params.get("body") or "")
        proposed = "candidate.verify" if "verify" in body.lower() else "task.status"
        return {
            "proposed_action": proposed,
            "executed": False,
            "message_id": params.get("message_id"),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foundationd")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repo", default=".")
    run.add_argument("--foreground", action="store_true")
    run.add_argument("--dev-open-session-create", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--repo", default=".")
    stop = sub.add_parser("stop")
    stop.add_argument("--repo", default=".")
    ping = sub.add_parser("ping")
    ping.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    if args.command == "run":
        root = repo_root(Path(str(args.repo)))
        return DaemonServer(
            root,
            foreground=bool(args.foreground),
            dev_open_session_create=bool(args.dev_open_session_create),
        ).serve_forever()
    if args.command in {"status", "stop", "ping"}:
        root = repo_root(Path(str(args.repo)))
        method = {
            "status": "daemon.status",
            "stop": "daemon.shutdown",
            "ping": "daemon.ping",
        }[str(args.command)]
        params: dict[str, Any] = {}
        if method == "daemon.shutdown":
            params["root_token"] = client_load_root_token(root) or ""
        response = DaemonClient.for_repo(root).request(method, params)
        print(json.dumps(response.model_dump(mode="json"), sort_keys=True))
        return 0 if response.ok else 1
    return 1


def _read_line(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    line, _sep, _rest = raw.partition(b"\n")
    return line


def _print_json_error(code: str, message: str) -> None:
    print(
        json.dumps({"ok": False, "error": {"code": code, "message": message}}, sort_keys=True),
        file=sys.stderr,
    )


def _with_exit_code(pair: tuple[dict[str, Any], int]) -> dict[str, Any]:
    result, code = pair
    return {**result, "exit_code": code}


def _context_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    sanitized = dict(payload)
    sanitized.pop("agent_skills", None)
    return sanitized


def _candidate_id(root: Path, task_id: str) -> str | None:
    runtime = task_dir(root, task_id)
    for name in ("submission.json", "verify-result.json", "land-result.json"):
        path = runtime / name
        if path.is_file():
            data = read_json(path)
            value = data.get("candidate_id")
            if isinstance(value, str) and value:
                return value
    return None


def _idempotency_key(
    effect_type: str,
    task_id: str,
    candidate_id: str | None,
    params: dict[str, Any],
) -> str:
    candidate = candidate_id or "none"
    if effect_type == "merge_local":
        return f"{effect_type}:{task_id}:{candidate}:{params.get('target', 'main')}"
    if effect_type == "complete_task":
        return f"{effect_type}:{task_id}:{candidate}:{_landed_commit(params)}"
    if effect_type == "push_remote":
        return f"{effect_type}:{task_id}:{candidate}"
    return f"{effect_type}:{task_id}:{candidate}"


def _landed_commit(params: dict[str, Any]) -> str:
    value = params.get("landed_commit")
    return str(value) if isinstance(value, str) and value else "latest"


@contextmanager
def _session_environment(role: str, actor: str, agent_id: str) -> Iterator[None]:
    previous_role = os.environ.get("HARNESS_ROLE")
    previous_actor = os.environ.get("HARNESS_ACTOR")
    previous_agent = os.environ.get("FOUNDATION_AGENT_ID")
    os.environ["HARNESS_ROLE"] = role
    os.environ["HARNESS_ACTOR"] = actor
    os.environ["FOUNDATION_AGENT_ID"] = agent_id
    try:
        yield
    finally:
        if previous_role is None:
            os.environ.pop("HARNESS_ROLE", None)
        else:
            os.environ["HARNESS_ROLE"] = previous_role
        if previous_actor is None:
            os.environ.pop("HARNESS_ACTOR", None)
        else:
            os.environ["HARNESS_ACTOR"] = previous_actor
        if previous_agent is None:
            os.environ.pop("FOUNDATION_AGENT_ID", None)
        else:
            os.environ["FOUNDATION_AGENT_ID"] = previous_agent


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "session"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
