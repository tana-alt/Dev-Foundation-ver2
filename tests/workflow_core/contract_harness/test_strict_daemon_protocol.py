from __future__ import annotations

import json
import socket
from pathlib import Path

from workflow_core.contract_harness.daemon.protocol import DaemonRequest, DaemonResponse

from .conftest import git, start_daemon, strict_env, strict_json


def test_strict_protocol_models_round_trip() -> None:
    request = DaemonRequest(request_id="req_1", method="daemon.ping")
    response = DaemonResponse(request_id=request.request_id, ok=True, result={"status": "running"})

    assert request.model_dump(mode="json")["method"] == "daemon.ping"
    assert response.model_dump(mode="json")["result"]["status"] == "running"


def test_strict_protocol_returns_json_error_for_unknown_method(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        response = _raw_request(harness_repo, {"request_id": "req_unknown", "method": "no.such"})
        assert response["ok"] is False
        assert response["error"]["code"] == "usage_error"
    finally:
        daemon.stop()


def test_strict_malformed_json_does_not_crash_daemon(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        socket_path = _socket_path(harness_repo)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            sock.sendall(b"{not-json}\n")
            raw = sock.recv(4096)
        response = json.loads(raw.decode("utf-8"))
        assert response["ok"] is False
        assert response["error"]["code"] == "usage_error"
        ping = strict_json(harness_repo, "daemon", "ping")
        assert ping["ok"] is True
    finally:
        daemon.stop()


def _raw_request(repo: Path, data: dict[str, object]) -> dict[str, object]:
    socket_path = _socket_path(repo)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        sock.sendall(json.dumps(data).encode("utf-8") + b"\n")
        raw = sock.recv(4096)
    response = json.loads(raw.decode("utf-8"))
    assert isinstance(response, dict)
    return response


def _socket_path(repo: Path) -> Path:
    env = strict_env(repo)
    if "HARNESS_RUNTIME_ROOT" in env:
        return Path(env["HARNESS_RUNTIME_ROOT"]) / "daemon" / "foundation.sock"
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "daemon" / "foundation.sock"
