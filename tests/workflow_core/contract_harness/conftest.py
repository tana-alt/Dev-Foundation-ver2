from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "harness"
FOUNDATIOND = ROOT / "foundationd"
TASK_ID = "T-0001"


def git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=check,
    )


def run_harness(
    repo: Path,
    *args: str,
    role: str = "writer",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HARNESS), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "HARNESS_ROLE": role},
    )


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    capability_token: str
    role: str
    agent_id: str


@dataclass
class DaemonProcess:
    repo: Path
    process: subprocess.Popen[str]
    env: dict[str, str]

    def stop(self) -> None:
        if self.process.poll() is None:
            subprocess.run(
                [str(HARNESS), "daemon", "stop"],
                cwd=self.repo,
                capture_output=True,
                text=True,
                timeout=20,
                env=self.env,
                check=False,
            )
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=20)


def strict_env(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    socket_path = common / "harness-runtime" / "daemon" / "foundation.sock"
    if len(str(socket_path)) > 96:
        digest = sha256(str(repo).encode("utf-8")).hexdigest()[:16]
        short_tmp = Path(os.environ.get("RUNNER_TEMP", "/tmp"))
        env["HARNESS_RUNTIME_ROOT"] = str(short_tmp / f"harness-strict-{digest}")
    return env


def start_daemon(repo: Path, *, dev_open_session_create: bool = False) -> DaemonProcess:
    env = strict_env(repo)
    args = [
        str(FOUNDATIOND),
        "run",
        "--foreground",
        "--repo",
        str(repo),
    ]
    if dev_open_session_create:
        args.append("--dev-open-session-create")
    process = subprocess.Popen(
        args,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    daemon = DaemonProcess(repo=repo, process=process, env=env)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise AssertionError(f"daemon exited early\nstdout={stdout}\nstderr={stderr}")
        ping = subprocess.run(
            [str(HARNESS), "daemon", "ping"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        if ping.returncode == 0:
            return daemon
        time.sleep(0.1)
    daemon.stop()
    raise AssertionError("daemon did not become ready")


def strict_cli(
    repo: Path,
    *args: str,
    session: SessionInfo | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = strict_env(repo)
    if env:
        for key, value in env.items():
            if value == "":
                merged.pop(key, None)
            else:
                merged[key] = value
    if session is not None:
        merged["FOUNDATION_SESSION_ID"] = session.session_id
        merged["FOUNDATION_CAPABILITY_TOKEN"] = session.capability_token
        merged["HARNESS_ROLE"] = session.role
        merged["FOUNDATION_AGENT_ID"] = session.agent_id
    return subprocess.run(
        [str(HARNESS), "--strict", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=180,
        env=merged,
    )


def strict_json(
    repo: Path,
    *args: str,
    session: SessionInfo | None = None,
) -> dict[str, Any]:
    completed = strict_cli(repo, *args, session=session)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    data = json.loads(completed.stdout)
    assert isinstance(data, dict)
    return data


def create_session(
    repo: Path,
    role: str,
    *,
    agent_id: str,
    task_id: str = TASK_ID,
) -> SessionInfo:
    root_token = root_token_for(repo)
    completed = strict_cli(
        repo,
        "session",
        "create",
        "--role",
        role,
        "--task",
        task_id,
        "--agent",
        agent_id,
        "--root-token",
        root_token,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    response = json.loads(completed.stdout)
    assert response["ok"] is True
    result = response["result"]
    return SessionInfo(
        session_id=str(result["session_id"]),
        capability_token=str(result["capability_token"]),
        role=role,
        agent_id=agent_id,
    )


def root_token_for(repo: Path) -> str:
    env = strict_env(repo)
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    runtime = Path(env.get("HARNESS_RUNTIME_ROOT", str(common / "harness-runtime")))
    return (runtime / "daemon" / "auth" / "root.token").read_text(encoding="utf-8").strip()


def runtime_task_dir(repo: Path, task_id: str = TASK_ID) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / task_id


def load_runtime_json(repo: Path, name: str, task_id: str = TASK_ID) -> dict[str, Any]:
    data = json.loads((runtime_task_dir(repo, task_id) / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.fixture
def harness_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    base = repo / ".harness"
    (base / "tasks" / TASK_ID).mkdir(parents=True)
    (base / "rfc-decisions").mkdir()
    (base / "bottleneck.yaml").write_text("version: 1\n", encoding="utf-8")
    (base / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/**\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    (base / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: unit\n"
        "    command: python -c 'raise SystemExit(0)'\n"
        "    applies_to: ['**/*']\n"
        "    always: true\n",
        encoding="utf-8",
    )
    (base / "review.yaml").write_text(
        "default:\n"
        "  quorum: 2\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "  background_auto_run: false\n",
        encoding="utf-8",
    )
    (base / "policy.yaml").write_text(
        "version: 1\n"
        "goal:\n"
        "  summary: local harness test\n"
        "constraints:\n"
        "  integration_target:\n"
        "    remote: origin\n"
        "    branch: main\n"
        "  external_writes:\n"
        "    default_mode: dry_run\n"
        "    allowed_roles:\n"
        "      - integrator\n"
        "    remotes:\n"
        "      origin:\n"
        "        branches:\n"
        "          main:\n"
        "            mode: dry_run\n"
        "bottlenecks:\n"
        "  integration:\n"
        "    lock_timeout_s: 900\n",
        encoding="utf-8",
    )
    (base / "tasks" / TASK_ID / "task.yaml").write_text(
        f"id: {TASK_ID}\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: test task\n"
        "acceptance:\n"
        "  mode: generated\n"
        "allowed_outputs:\n"
        "  - source_diff\n",
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "Makefile").write_text("check-required:\n\t@true\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo
