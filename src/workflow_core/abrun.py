"""AB execution orchestrator (Plan-N0002 R3).

Owns the responsibilities v1 assigned to nobody: prepare baseline/candidate
worktrees, sync dependencies, take the environment fingerprint, drive the
measurement in an ABAB interleave (so thermal drift lands on both groups
instead of biasing one), and record runs + raw samples in the run store.

Guard rails:
- worktree paths must resolve outside the measured repo (repo rule: no
  worktrees inside tracked paths) — the spec's ``.ab/`` example is
  deliberately not followed;
- abrun stamps an ``.abrun-worktree`` marker at creation and ``clean``
  removes only marker-bearing worktrees, so it can never delete a worktree
  it does not own (worktree deletion is otherwise human-gated);
- reuse of an existing worktree requires marker + HEAD == resolved ref.
"""

from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import ValidationError

from workflow_core.contracts import StrictModel
from workflow_core.envfp import collect_fingerprint, fingerprint_hash
from workflow_core.hashing import canonical_hash
from workflow_core.runstore import RunStore
from workflow_core.tracelog import TraceWriter

_MARKER = ".abrun-worktree"
TOOL_VERSION = "0.1.0"


class AbrunError(RuntimeError):
    """Tool error (exit 3): setup, configuration, or measurement failure."""


class SideSpec(StrictModel):
    ref: str
    worktree: str


class HealthcheckSpec(StrictModel):
    method: str = "GET"
    path: str = "/health"
    timeout_sec: float = 30.0


class ServerSpec(StrictModel):
    start: str
    healthcheck: HealthcheckSpec = HealthcheckSpec()


class MeasureSpec(StrictModel):
    tool: Literal["command"] = "command"
    command: list[str]
    metric: str
    unit: str = "ms"
    value_from: Literal["wallclock", "stdout"] = "wallclock"


class AbConfig(StrictModel):
    baseline: SideSpec
    candidate: SideSpec
    measure: MeasureSpec
    setup: list[str] = []
    iterations: int = 20
    warmup: int = 3
    schedule: Literal["interleaved", "sequential"] = "interleaved"
    cooldown_sec: float = 0.0
    task_id: str = ""
    server: ServerSpec | None = None


class AbResult(StrictModel):
    baseline_run_id: str
    candidate_run_id: str
    baseline_cached: bool
    candidate_cached: bool
    metric: str


class _Side(NamedTuple):
    label: str
    run_id: str
    worktree: Path
    port: int | None = None


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def load_config(path: Path) -> tuple[AbConfig, str]:
    """Load and validate an abrun config; returns (config, config_hash)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AbrunError(f"cannot load config {path}: {exc}") from exc
    try:
        config = AbConfig.model_validate(data)
    except ValidationError as exc:
        raise AbrunError(f"invalid config {path}: {exc}") from exc
    if config.iterations < 1 or config.warmup < 0:
        raise AbrunError("iterations must be >= 1 and warmup >= 0")
    return config, canonical_hash(data)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AbrunError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def resolve_ref(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", f"{ref}^{{commit}}")


def ensure_worktree(repo: Path, side: SideSpec, sha: str) -> Path:
    path = Path(side.worktree).resolve()
    if path.is_relative_to(repo.resolve()):
        raise AbrunError(
            f"worktree {path} is inside {repo}; worktrees must live outside tracked repo paths"
        )
    marker = path / _MARKER
    if path.exists():
        if not marker.exists():
            raise AbrunError(f"{path} exists but is not an abrun worktree; refusing to reuse")
        head = _git(path, "rev-parse", "HEAD")
        if head != sha:
            raise AbrunError(
                f"{path} is at {head[:12]}, expected {sha[:12]}; run 'abrun clean' first"
            )
        return path
    _git(repo, "worktree", "add", "--detach", str(path), sha)
    marker.write_text(sha + "\n", encoding="utf-8")
    return path


def run_setup(config: AbConfig, worktree: Path) -> None:
    for command in config.setup:
        proc = subprocess.run(shlex.split(command), cwd=worktree, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
            raise AbrunError(f"setup command {command!r} failed in {worktree}:\n{tail}")


def _measure_once(measure: MeasureSpec, worktree: Path, iteration: int, port: int | None) -> float:
    env = {**os.environ, "ABRUN_ITERATION": str(iteration)}
    command = list(measure.command)
    if port is not None:
        env["ABRUN_PORT"] = str(port)
        command = [token.replace("{port}", str(port)) for token in command]
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=worktree, capture_output=True, text=True, env=env)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise AbrunError(f"measure command exited {proc.returncode} in {worktree}:\n{tail}")
    if measure.value_from == "wallclock":
        return round(elapsed_ms, 4)
    lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise AbrunError("measure command printed nothing; value_from=stdout needs a number")
    try:
        return float(lines[-1])
    except ValueError as exc:
        raise AbrunError(f"cannot parse sample from stdout line {lines[-1]!r}") from exc


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _Server:
    """One measured-side server: start -> healthcheck -> stop (R3 step 5)."""

    def __init__(self, spec: ServerSpec, worktree: Path) -> None:
        self._spec = spec
        self.port = _free_port()
        command = [t.replace("{port}", str(self.port)) for t in shlex.split(spec.start)]
        try:
            self._proc: subprocess.Popen[bytes] = subprocess.Popen(
                command, cwd=worktree, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError as exc:
            raise AbrunError(f"cannot start server {spec.start!r}: {exc}") from exc

    def wait_healthy(self) -> None:
        check = self._spec.healthcheck
        deadline = time.monotonic() + check.timeout_sec
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{check.path}", method=check.method
        )
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise AbrunError(f"server exited with {self._proc.returncode} before healthy")
            try:
                with urllib.request.urlopen(request, timeout=2):
                    return
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        self.stop()
        raise AbrunError(f"server not healthy within {check.timeout_sec}s")

    def stop(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def _start_servers(spec: ServerSpec, sides: list[_Side]) -> tuple[list[_Server], list[_Side]]:
    servers: list[_Server] = []
    bound: list[_Side] = []
    try:
        for side in sides:
            server = _Server(spec, side.worktree)
            servers.append(server)
            server.wait_healthy()
            bound.append(side._replace(port=server.port))
    except AbrunError:
        for server in servers:
            server.stop()
        raise
    return servers, bound


def _take_sample(
    store: RunStore, config: AbConfig, side: _Side, iteration: int, trace: TraceWriter | None
) -> None:
    value = _measure_once(config.measure, side.worktree, iteration, side.port)
    if iteration >= config.warmup:
        store.record_sample(
            side.run_id,
            config.measure.metric,
            iteration - config.warmup,
            value,
            unit=config.measure.unit,
            recorded_at=_now_ts(),
        )
        if trace is not None:
            trace.emit(
                "metric_recorded",
                {"metric": config.measure.metric, "value": value, "side": side.label},
                {"run_id": side.run_id},
            )
    if config.cooldown_sec > 0:
        time.sleep(config.cooldown_sec)


def _run_schedule(
    store: RunStore, config: AbConfig, sides: list[_Side], trace: TraceWriter | None
) -> None:
    rounds = config.warmup + config.iterations
    if config.schedule == "interleaved":
        for iteration in range(rounds):
            for side in sides:
                _take_sample(store, config, side, iteration, trace)
        return
    for side in sides:
        for iteration in range(rounds):
            _take_sample(store, config, side, iteration, trace)


def _measure_sides(
    store: RunStore, config: AbConfig, sides: list[_Side], trace: TraceWriter | None
) -> None:
    servers: list[_Server] = []
    try:
        if config.server is not None:
            servers, sides = _start_servers(config.server, sides)
        _run_schedule(store, config, sides, trace)
    finally:
        for server in servers:
            server.stop()


def orchestrate(
    repo: Path,
    store: RunStore,
    config: AbConfig,
    config_hash: str,
    *,
    no_cache: bool = False,
    trace: TraceWriter | None = None,
) -> AbResult:
    """Prepare both sides, measure the uncached ones, aggregate, return run ids."""
    run_ids: dict[str, str] = {}
    cached: dict[str, bool] = {}
    to_measure: list[_Side] = []
    for label, spec in (("baseline", config.baseline), ("candidate", config.candidate)):
        sha = resolve_ref(repo, spec.ref)
        worktree = ensure_worktree(repo, spec, sha)
        fingerprint = fingerprint_hash(collect_fingerprint(worktree))
        hit = None if no_cache else store.find_cached_run(sha, config_hash, fingerprint)
        if hit is not None:
            run_ids[label], cached[label] = hit, True
            continue
        run_setup(config, worktree)
        run_id = f"{label}_{uuid.uuid4().hex[:8]}"
        store.create_run(
            run_id,
            started_at=_now_ts(),
            task_id=config.task_id,
            worktree=str(worktree),
            commit_sha=sha,
            env_fingerprint=fingerprint,
            config_hash=config_hash,
            tool_versions={"abrun": TOOL_VERSION},
        )
        run_ids[label], cached[label] = run_id, False
        to_measure.append(_Side(label, run_id, worktree))
    if to_measure:
        _measure_sides(store, config, to_measure, trace)
    for run_id in run_ids.values():
        store.aggregate_run(run_id)
    return AbResult(
        baseline_run_id=run_ids["baseline"],
        candidate_run_id=run_ids["candidate"],
        baseline_cached=cached["baseline"],
        candidate_cached=cached["candidate"],
        metric=config.measure.metric,
    )


def clean(repo: Path, config: AbConfig) -> list[str]:
    """Remove abrun-owned (marker-bearing) worktrees for both sides."""
    removed: list[str] = []
    for spec in (config.baseline, config.candidate):
        path = Path(spec.worktree).resolve()
        if not path.exists():
            continue
        if not (path / _MARKER).exists():
            raise AbrunError(f"{path} has no {_MARKER} marker; refusing to remove")
        _git(repo, "worktree", "remove", "--force", str(path))
        removed.append(str(path))
    _git(repo, "worktree", "prune")
    return removed
