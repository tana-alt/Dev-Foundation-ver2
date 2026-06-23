from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.daemon.errors import DaemonUnavailableError
from workflow_core.contract_harness.daemon.protocol import DaemonRequest, DaemonResponse
from workflow_core.contract_harness.gitutil import repo_root
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.runtime_paths import runtime_root


def daemon_dir(repo: Path) -> Path:
    return runtime_root(repo) / "daemon"


def daemon_socket_path(repo: Path) -> Path:
    return daemon_dir(repo) / "foundation.sock"


def daemon_auth_dir(repo: Path) -> Path:
    return daemon_dir(repo) / "auth"


def root_token_path(repo: Path) -> Path:
    return daemon_auth_dir(repo) / "root.token"


class DaemonClient:
    def __init__(self, socket_path: Path, timeout_s: float = 30.0) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s

    @classmethod
    def for_repo(cls, repo: Path, timeout_s: float = 30.0) -> DaemonClient:
        return cls(daemon_socket_path(repo), timeout_s=timeout_s)

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        capability_token: str | None = None,
    ) -> DaemonResponse:
        request = DaemonRequest(
            request_id=f"req_{uuid4().hex}",
            method=method,
            params=params or {},
            session_id=session_id,
            capability_token=capability_token,
        )
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout_s)
                sock.connect(str(self.socket_path))
                sock.sendall(
                    json.dumps(request.model_dump(mode="json"), sort_keys=True).encode("utf-8")
                    + b"\n"
                )
                response_line = _readline(sock)
        except OSError as exc:
            raise DaemonUnavailableError("foundationd is not running for this repository") from exc
        data = json.loads(response_line.decode("utf-8"))
        return DaemonResponse.model_validate(data)


def repo_client(start: Path | None = None) -> tuple[Path, DaemonClient]:
    root = repo_root(start or Path.cwd())
    return root, DaemonClient.for_repo(root)


def load_session_credentials(
    repo: Path,
    *,
    session_id: str | None = None,
    capability_token: str | None = None,
) -> tuple[str | None, str | None]:
    sid = session_id or os.environ.get("FOUNDATION_SESSION_ID")
    token = capability_token or os.environ.get("FOUNDATION_CAPABILITY_TOKEN")
    if sid and token:
        return sid, token
    for name in _session_file_candidates():
        path = daemon_auth_dir(repo) / "sessions" / f"{name}.json"
        if not path.is_file():
            continue
        data = read_json(path)
        return str(data.get("session_id") or ""), str(data.get("capability_token") or "")
    return sid, token


def load_root_token(repo: Path, *, allow_file: bool = True) -> str | None:
    token = os.environ.get("FOUNDATION_ROOT_TOKEN")
    if token:
        return token
    if not allow_file:
        return None
    path = root_token_path(repo)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return None


def _session_file_candidates() -> list[str]:
    values = [
        os.environ.get("FOUNDATION_SESSION_REF"),
        os.environ.get("FOUNDATION_AGENT_ID"),
        os.environ.get("HARNESS_ROLE"),
    ]
    return [value for value in values if value]


def _readline(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    line, _sep, _rest = raw.partition(b"\n")
    if not line:
        raise DaemonUnavailableError("daemon returned an empty response")
    return line
