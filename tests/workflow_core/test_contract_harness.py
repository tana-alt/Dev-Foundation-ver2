from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from workflow_core.contract_harness.agent_tools import (
    role_agent_skills,
    role_agent_tools,
    role_optional_tools,
)
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.lock import LockBlocked, _lock_path, local_lock
from workflow_core.contract_harness.verify import recompute_machine_evidence
from workflow_core.evaluation import EvalScore
from workflow_core.metrics_store import MetricsStore

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness"
TASK_ID = "T-0001"


def run_harness(
    repo: Path,
    *args: str,
    role: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(extra_env or {})}
    if role:
        env["HARNESS_ROLE"] = role
    return subprocess.run(
        [str(HARNESS), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return result.stdout.strip()


def init_repo(
    tmp_path: Path,
    *,
    verifier_command: str = "python -c 'raise SystemExit(0)'",
    make_exit: int = 0,
    reject_unexpected: bool = False,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    write_harness_config(repo, verifier_command, reject_unexpected)
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "Makefile").write_text(
        "check-required:\n"
        f"\t@python -c 'raise SystemExit({make_exit})'\n"
        "custom-gate:\n"
        f"\t@mkdir -p artifact/{TASK_ID}/tier\n"
        f"\t@printf custom > artifact/{TASK_ID}/tier/called.txt\n"
        f"\t@python -c 'raise SystemExit({make_exit})'\n"
    )
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    return repo


def enable_policy_and_remote(tmp_path: Path, repo: Path) -> Path:
    git(repo, "branch", "-M", "main")
    (repo / ".harness" / "policy.yaml").write_text(policy_yaml(), encoding="utf-8")
    git(repo, "add", ".harness/policy.yaml")
    git(repo, "commit", "-m", "enable integration policy")
    remote = tmp_path / f"{repo.name}-remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote


def policy_yaml() -> str:
    return (
        "version: 1\n"
        "goal:\n"
        "  summary: safe serialized integration for contract harness tasks\n"
        "constraints:\n"
        "  runtime_state:\n"
        "    must_use_git_common_dir: true\n"
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
        "            require_rescue_ref: true\n"
        "            require_push_lock: true\n"
        "            require_local_sync_after_remote_update: true\n"
        "bottlenecks:\n"
        "  integration:\n"
        "    max_active_integrators_per_branch: 1\n"
        "    lock_timeout_s: 900\n"
    )


def write_harness_config(repo: Path, verifier_command: str, reject_unexpected: bool) -> None:
    base = repo / ".harness"
    (base / "tasks" / TASK_ID).mkdir(parents=True)
    (base / "rfc-decisions").mkdir()
    (base / "bottleneck.yaml").write_text("version: 1\n", encoding="utf-8")
    (base / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/**\n"
        "      - tests/**\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    (base / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: unit\n"
        f"    command: {json.dumps(verifier_command)}\n"
        "    applies_to: ['**/*']\n"
        "    always: true\n",
        encoding="utf-8",
    )
    (base / "review.yaml").write_text(review_yaml(reject_unexpected), encoding="utf-8")
    (base / "tasks" / TASK_ID / "task.yaml").write_text(task_yaml("generated"), encoding="utf-8")


def enable_semantic_reviewer(repo: Path) -> None:
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['verify_result']['status'] == 'pass'\n"
        "assert 'candidate\\n' in packet['candidate_diff']\n"
        "assert packet['test_interpretation']['overall_status'] == 'pass'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['semantic_ai'],\n"
        "  'reason': 'diff and tests reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable semantic reviewer")


def review_yaml(reject_unexpected: bool = False) -> str:
    return (
        "default:\n"
        "  quorum: 2\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "  background_auto_run: true\n"
        "  blocking_labels:\n"
        "    - scope_risk\n"
        "    - missing_repro\n"
        "    - acceptance_gap\n"
        "    - machine_failed\n"
        "    - protected_contract_edit\n"
        "metrics:\n"
        f"  reject_unexpected_actions: {'true' if reject_unexpected else 'false'}\n"
    )


def semantic_review_yaml(
    command: list[str],
    mutation_command: list[str] | None = None,
) -> str:
    command_yaml = "\n".join(f"      - {json.dumps(part)}" for part in command)
    mutation_yaml = ""
    if mutation_command is not None:
        mutation_command_yaml = "\n".join(f"    - {json.dumps(part)}" for part in mutation_command)
        mutation_yaml = f"mutation:\n  command:\n{mutation_command_yaml}\n  timeout_s: 30\n"
    return (
        "default:\n"
        "  quorum: 3\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - semantic-ai\n"
        "  background_auto_run: true\n"
        "  blocking_labels:\n"
        "    - semantic_gap\n"
        "profiles:\n"
        "  semantic-ai:\n"
        "    kind: command\n"
        "    command:\n"
        f"{command_yaml}\n"
        f"{mutation_yaml}"
        "metrics:\n"
        "  reject_unexpected_actions: false\n"
    )


def task_yaml(mode: str, task_id: str = TASK_ID) -> str:
    return (
        f"id: {task_id}\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: test task\n"
        "acceptance:\n"
        f"  mode: {mode}\n"
        "allowed_outputs:\n"
        "  - source_diff\n"
    )


def runtime_task_dir(repo: Path, task_id: str = TASK_ID) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / task_id


def runtime_root(repo: Path) -> Path:
    return runtime_task_dir(repo).parents[2]


def load_runtime_json(repo: Path, name: str, task_id: str = TASK_ID) -> dict[str, Any]:
    data = json.loads((runtime_task_dir(repo, task_id) / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def tool_names(tools: list[dict[str, Any]]) -> set[str]:
    return {str(tool.get("name")) for tool in tools}


def skill_names(skills: list[dict[str, Any]]) -> set[str]:
    return {str(skill.get("name")) for skill in skills}


def test_harness_worktree_skill_paths_do_not_fallback_to_package_root(tmp_path: Path) -> None:
    worktree = tmp_path / "writer"
    skill = worktree / ".agents" / "skills" / "tdd-scope" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: tdd-scope\ndescription: local writer skill\n---\n",
        encoding="utf-8",
    )
    (worktree / ".harness-worktree.json").write_text("{}", encoding="utf-8")

    skills = role_agent_skills(worktree, "writer")
    by_name = {str(item["name"]): item for item in skills}

    assert by_name["tdd-scope"]["path"] == str(skill)
    assert by_name["implementation-slice-verification"]["path"] is None
    assert by_name["scope-routing-governance"]["path"] is None


def test_harness_worktree_skill_paths_can_use_marker_source_repo_root(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source_skill = source / ".agents" / "skills" / "implementation-slice-verification" / "SKILL.md"
    source_skill.parent.mkdir(parents=True)
    source_skill.write_text(
        "---\nname: implementation-slice-verification\ndescription: source skill\n---\n",
        encoding="utf-8",
    )
    worktree = tmp_path / "writer"
    worktree.mkdir(parents=True)
    (worktree / ".harness-worktree.json").write_text(
        json.dumps({"source_repo_common_dir": str(source / ".git")}),
        encoding="utf-8",
    )

    skills = role_agent_skills(worktree, "writer")
    by_name = {str(item["name"]): item for item in skills}

    assert by_name["implementation-slice-verification"]["path"] == str(source_skill)
    assert by_name["tdd-scope"]["path"] is None


def test_harness_worktree_tool_commands_use_current_harness_not_stale_local(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "writer"
    worktree.mkdir(parents=True)
    (worktree / ".harness-worktree.json").write_text("{}", encoding="utf-8")
    stale_local_harness = worktree / "harness"
    stale_local_harness.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    stale_local_harness.chmod(0o755)

    tools = role_agent_tools(worktree, TASK_ID, "writer")

    assert all(str(tool["command"]).startswith("HARNESS_ROLE=writer ") for tool in tools)
    assert all(str(HARNESS) in str(tool["command"]) for tool in tools)
    assert all(str(stale_local_harness) not in str(tool["command"]) for tool in tools)


def test_script_tool_commands_use_absolute_paths_for_repo_local_scripts(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / "scripts" / "hook_post_tool_use.py"
    script.parent.mkdir()
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    tools = role_optional_tools(repo, TASK_ID, "writer", "measurement")
    hook_tool = tool_by_name(tools, "post-tool-use-hook")

    assert str(script) in hook_tool["command"]
    assert " python3 scripts/hook_post_tool_use.py" not in hook_tool["command"]


def test_active_review_config_wires_semantic_ai_to_repo_root_wrapper() -> None:
    review = yaml.safe_load((ROOT / ".harness" / "review.yaml").read_text(encoding="utf-8"))

    assert "semantic-ai" in review["default"]["reviewers"]
    profile = review["profiles"]["semantic-ai"]
    assert profile["kind"] == "command"
    assert profile["command"] == [
        "python3",
        "{repo_root}/.harness/semantic_ai_reviewer.py",
        "{review_packet}",
        "{review_output}",
    ]
    assert (ROOT / ".harness" / "semantic_ai_reviewer.py").is_file()


def tool_by_name(tools: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for tool in tools:
        if tool.get("name") == name:
            return tool
    raise AssertionError(f"missing tool: {name}")


def run_tool_command(
    command: str,
    cwd: Path,
    *,
    role: str = "writer",
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=90,
        shell=True,
        env={**os.environ, "HARNESS_ROLE": role},
    )


def test_role_boundaries_reject_disallowed_commands(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "gate", TASK_ID).returncode != 0
    assert "role writer cannot run gate" in run_harness(repo, "gate", TASK_ID).stdout
    assert run_harness(repo, "dispatch", TASK_ID).returncode != 0
    assert run_harness(repo, "integrate", TASK_ID).returncode != 0
    writer_review = run_harness(
        repo,
        "review",
        TASK_ID,
        "--write-verdict",
        "reader-scope",
        "approve",
    )
    assert writer_review.returncode != 0
    assert "role writer cannot run review:write-verdict" in writer_review.stdout
    assert run_harness(repo, "verify", TASK_ID, role="reviewer").returncode != 0
    assert run_harness(repo, "verify", TASK_ID, role="integrator").returncode != 0

    assert run_harness(repo, "scope-map", TASK_ID, "--forward").returncode == 0
    assert run_harness(repo, "scope-map", TASK_ID, "--forward", role="reviewer").returncode == 0
    assert run_harness(repo, "scope-map", TASK_ID, "--reverse", role="integrator").returncode == 0
    assert run_harness(repo, "tools", TASK_ID, "--role", "writer").returncode == 0
    assert (
        run_harness(repo, "tools", TASK_ID, "--role", "reviewer", role="reviewer").returncode == 0
    )


def test_active_harness_surface_has_no_phantom_rfc_and_tools_match_roles(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)

    help_result = run_harness(repo, "--help")
    assert help_result.returncode == 0
    assert "rfc" not in help_result.stdout

    phantom = run_harness(repo, "rfc", TASK_ID, "approve", "RFC-1", "--reason", "ok")
    assert phantom.returncode != 0
    assert "deferred_in_mvp" not in phantom.stdout
    assert run_harness(repo, "report", TASK_ID, "--type", "rfc").returncode == 0

    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    groups = load_runtime_json(repo, "agent-tools.json")
    reviewer_tools = tool_names(groups["reviewer"])
    integrator_tools = tool_names(groups["integrator"])
    assert "review-collect" not in reviewer_tools
    assert "review-collect" in integrator_tools
    assert all(str(tool["command"]).startswith("HARNESS_ROLE=writer ") for tool in groups["writer"])
    assert all(
        str(tool["command"]).startswith("HARNESS_ROLE=reviewer ") for tool in groups["reviewer"]
    )
    assert all(
        str(tool["command"]).startswith("HARNESS_ROLE=integrator ")
        for tool in groups["integrator"]
        if tool["name"]
        in {
            "review-collect",
            "scope-map-reverse",
            "affected",
            "dispatch",
            "integrate",
            "gate",
            "land",
            "push",
        }
    )

    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    collect_tool = tool_by_name(groups["integrator"], "review-collect")
    collect_smoke = run_tool_command(collect_tool["command"], repo / ".harness")
    assert collect_smoke.returncode == 0, collect_smoke.stdout + collect_smoke.stderr


def test_prepare_capsule_exposes_existing_agent_tool_set(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    prepared = run_harness(repo, "prepare", TASK_ID)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    capsule = load_runtime_json(repo, "capsule.json")
    names = tool_names(capsule["agent_tools"])
    skills = skill_names(capsule["agent_skills"])

    assert names == {
        "scope-map-forward",
        "explain",
        "context-audit",
        "status",
        "spawn-writer",
        "verify",
        "submit",
        "report-rfc",
        "report-metric",
    }
    assert {
        "nfr-metric",
        "bench-compare",
        "abrun",
        "check-runner",
        "verdict",
        "quality-gate",
        "measure-eval",
        "surface-issues",
        "context-scope-check",
    }.isdisjoint(names)
    assert {
        "tdd-scope",
        "implementation-slice-verification",
        "scope-routing-governance",
    }.issubset(skills)
    assert all(not str(tool["command"]).startswith("./harness") for tool in capsule["agent_tools"])
    assert all("nfr_metric.py" not in tool["command"] for tool in capsule["agent_tools"])
    scope_tool = tool_by_name(capsule["agent_tools"], "scope-map-forward")
    smoke = run_tool_command(scope_tool["command"], repo / ".harness")
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    groups = load_runtime_json(repo, "agent-tools.json")
    assert "scope-map-reverse" in tool_names(groups["reviewer"])
    assert "review-collect" not in tool_names(groups["reviewer"])
    assert "affected" in tool_names(groups["integrator"])
    assert "review-collect" in tool_names(groups["integrator"])
    skill_groups = load_runtime_json(repo, "agent-skills.json")
    assert "release-check" in skill_names(skill_groups["reviewer"])
    assert "merge-integrity-governance" in skill_names(skill_groups["integrator"])

    optional = run_harness(repo, "tools", TASK_ID, "--role", "writer", "--profile", "measurement")
    assert optional.returncode == 0, optional.stdout + optional.stderr
    optional_tools = json.loads(optional.stdout)["tools"]
    optional_names = tool_names(optional_tools)
    assert {
        "nfr-metric",
        "bench-compare",
        "abrun",
        "check-runner",
        "verdict",
        "quality-gate",
        "measure-eval",
        "surface-issues",
        "post-tool-use-hook",
    }.issubset(optional_names)


def test_measurement_tool_ingests_observed_trajectory_into_task_metrics(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    optional = run_harness(repo, "tools", TASK_ID, "--role", "writer", "--profile", "measurement")
    optional_tools = json.loads(optional.stdout)["tools"]
    hook_tool = tool_by_name(optional_tools, "post-tool-use-hook")
    measure_tool = tool_by_name(optional_tools, "measure-eval")
    assert f"FOUNDATION_REPO_ROOT={repo}" in hook_tool["command"]
    assert f"FOUNDATION_PROJECT_ID={TASK_ID}" in hook_tool["command"]
    assert "HARNESS_ROLE=writer" in hook_tool["command"]
    assert f"FOUNDATION_REPO_ROOT={repo}" in measure_tool["command"]

    for payload in (
        {
            "session_id": "agent-run",
            "tool_name": "Bash",
            "tool_input": {"command": "harness verify"},
            "tool_response": {"exit_code": 0},
        },
        {
            "session_id": "agent-run",
            "tool_name": "Skill",
            "tool_input": {"name": "tdd-scope"},
            "tool_response": {"exit_code": 0},
        },
    ):
        recorded = run_tool_command(
            hook_tool["command"],
            repo / ".harness",
            input_text=json.dumps(payload),
        )
        assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    trajectory_file = repo / "artifact" / TASK_ID / "trajectory" / "agent-run.jsonl"
    events = [
        json.loads(line)
        for line in trajectory_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [event["role"] for event in events] == ["writer", "writer"]

    measured = run_tool_command(measure_tool["command"], repo / ".harness")

    assert measured.returncode == 0, measured.stdout + measured.stderr
    measurement = json.loads(measured.stdout)
    assert measurement["runs_measured"] == 1
    assert measurement["report"]["mean_tool_call_rate"] == 1.0
    assert measurement["report"]["mean_skill_usage_rate"] == 0.5
    assert (repo / "artifact" / TASK_ID / "metrics" / "eval.db").is_file()
    with MetricsStore(repo / "artifact" / TASK_ID / "metrics" / "eval.db") as store:
        assert store.metrics_count() == 1
        stats = {(stat.kind, stat.name): stat for stat in store.tool_stats()}
    assert stats[("tool", "Bash")].calls == 1
    assert stats[("skill", "tdd-scope")].calls == 1

    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo, "review", TASK_ID, "--run", "reader-correctness", role="reviewer"
        ).returncode
        == 0
    )
    assert (
        run_harness(repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer").returncode
        == 0
    )
    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode == 0, gate.stdout + gate.stderr
    metrics = json.loads(gate.stdout)["metrics"]
    assert metrics["usage_observed"] is True
    assert metrics["tool_calls"] == 2
    assert metrics["skill_uses"] == 1
    assert metrics["skill_usage_rate"] == 0.5


def test_explain_lists_agent_tools(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0

    explained = run_harness(repo, "explain", TASK_ID)
    assert explained.returncode == 0, explained.stdout + explained.stderr
    assert "writer tools:" in explained.stdout
    assert "writer skills:" in explained.stdout
    assert "scope-map-forward" in explained.stdout
    assert "report-rfc" in explained.stdout
    assert "nfr-metric" not in explained.stdout
    assert "tdd-scope" in explained.stdout


def test_launch_writer_prepares_worktree_and_returns_interactive_command(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)

    launched = run_harness(repo, "launch-writer", TASK_ID)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    session = json.loads(launched.stdout)
    writer_path = Path(session["worktree"]["path"])
    assert session["status"] == "ready"
    assert session["role"] == "writer"
    assert writer_path.is_dir()
    assert session["cwd"] == str(writer_path)
    assert session["env"]["HARNESS_ROLE"] == "writer"
    assert session["env"]["FOUNDATION_REPO_ROOT"] == str(repo)
    assert session["env"]["FOUNDATION_PROJECT_ID"] == TASK_ID
    assert session["env"]["FOUNDATION_TASK_ID"] == TASK_ID
    assert "codex --yolo" in session["command"]
    assert str(writer_path) in session["command"]
    assert str(HARNESS) in session["handoff"]["verify"]
    assert str(HARNESS) in session["handoff"]["submit"]
    assert str(HARNESS) in session["handoff"]["submit_and_wait"]
    assert "./harness" not in session["handoff"]["verify"]
    assert "scope-map-forward" in {
        tool["name"] for tool in session["initial_context"]["agent_tools"]
    }
    assert "context-audit" in {tool["name"] for tool in session["initial_context"]["agent_tools"]}
    assert "tdd-scope" in {skill["name"] for skill in session["initial_context"]["agent_skills"]}
    assert load_runtime_json(repo, "writer-session.json")["command"] == session["command"]
    assert session["context_audit"]["roles"]["writer"]["status"] in {"pass", "fail"}


def test_spawn_writer_assigns_role_without_running_verify(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--agent-command",
        "codex --yolo",
        "--comm",
    )

    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    session = json.loads(spawned.stdout)
    writer_path = Path(session["worktree"]["path"])
    assert session["status"] == "ready"
    assert session["role"] == "writer"
    assert session["agent"] == "codex"
    assert session["env"]["HARNESS_ROLE"] == "writer"
    assert session["env"]["FOUNDATION_AGENT_ID"] == session["agent_id"]
    assert writer_path.is_dir()
    assert not (runtime_task_dir(repo) / "verify-result.json").exists()
    assert not (runtime_task_dir(repo) / "transcripts").exists()
    assert (runtime_task_dir(repo) / "comm" / "sessions" / f"{session['agent_id']}.json").is_file()
    assert (runtime_task_dir(repo) / "comm" / "rebind" / f"{session['agent_id']}.json").is_file()


def test_spawn_writes_rebind_packet_without_transcript(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "writer",
        "--agent",
        "codex",
        "--comm",
    )

    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    session = json.loads(spawned.stdout)
    rebind = load_runtime_json(
        repo,
        f"comm/rebind/{session['agent_id']}.json",
    )
    assert rebind["role"] == "writer"
    assert rebind["transcript_included"] is False
    assert "transcript_path" not in rebind
    assert "body_markdown" not in rebind


def test_rebind_packet_excludes_transcript(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    spawned = run_harness(repo, "spawn", TASK_ID, "--role", "writer", "--agent", "codex")

    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    session = json.loads(spawned.stdout)
    rebind = load_runtime_json(repo, f"comm/rebind/{session['agent_id']}.json")
    assert "transcripts" not in json.dumps(rebind, sort_keys=True)
    assert not (runtime_task_dir(repo) / "comm" / "transcripts").exists()


def test_launch_writer_is_spawn_writer_wrapper(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    launched = run_harness(repo, "launch-writer", TASK_ID)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    session = json.loads(launched.stdout)
    assert session["role"] == "writer"
    assert session["agent"] == "codex"
    assert session["agent_id"] == f"writer.codex.{TASK_ID}"
    assert load_runtime_json(repo, "writer-session.json")["agent_id"] == session["agent_id"]


def test_spawn_does_not_import_gate_land_push(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    spawned = run_harness(repo, "spawn", TASK_ID, "--role", "writer", "--agent", "codex")

    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    session = json.loads(spawned.stdout)
    tool_set = tool_names(session["initial_context"]["agent_tools"])
    assert not {"gate", "land", "push", "oracle", "compose", "compose-push"} & tool_set


def test_spawn_reviewer_requires_reviewer_id(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "reviewer",
        "--agent",
        "codex",
        role="reviewer",
    )

    assert spawned.returncode != 0
    assert "reviewer-id is required" in spawned.stdout


def test_spawn_integrator_sets_integrator_role(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)

    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "integrator",
        "--agent",
        "codex",
        "--agent-command",
        "codex --yolo",
        role="integrator",
    )

    assert spawned.returncode == 0, spawned.stdout + spawned.stderr
    session = json.loads(spawned.stdout)
    assert session["role"] == "integrator"
    assert session["env"]["HARNESS_ROLE"] == "integrator"
    assert session["worktree"]["kind"] == "integrator"
    assert Path(session["cwd"]).is_dir()


def test_spawn_target_role_validation_blocks_writer_spawning_integrator(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)

    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "integrator",
        "--agent",
        "codex",
    )

    assert spawned.returncode != 0
    assert "role writer cannot spawn integrator" in spawned.stdout


def test_task_yaml_acceptance_mode_must_be_generated(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    task_file = repo / ".harness" / "tasks" / TASK_ID / "task.yaml"
    task_file.write_text(task_yaml("manual"), encoding="utf-8")

    from workflow_core.contract_harness.config import ConfigError, load_task

    with pytest.raises(ConfigError, match="acceptance.mode must be generated"):
        load_task(repo, TASK_ID)


def test_status_query_returns_partial_when_artifacts_are_missing(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    status = run_harness(repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["schema_version"] == 1
    assert result["task_id"] == TASK_ID
    assert result["phase"] == "submitted"
    assert result["authority"] == {
        "complete": False,
        "source": "missing gate-result.json",
    }
    assert "verify-result.json" in result["artifacts"]["present"]
    assert "submission.json" in result["artifacts"]["present"]
    assert "gate-result.json" in result["artifacts"]["missing"]
    assert "land-result.json" in result["artifacts"]["missing"]
    assert "push-result.json" in result["artifacts"]["missing"]
    assert result["written_by"] == "harness"
    assert not (runtime_task_dir(repo) / "status-result.json").exists()


def test_status_reports_rework_when_integration_result_requires_rework(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    runtime = runtime_task_dir(repo)
    (runtime / "integration-result.json").write_text(
        json.dumps(
            {
                "task_id": TASK_ID,
                "role": "integrator",
                "status": "rework_required",
                "reason": "stale_submission",
                "review": {},
                "completion": {"status": "not_run"},
                "metrics": {},
                "head_unchanged": True,
            }
        ),
        encoding="utf-8",
    )

    status = run_harness(repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    result = json.loads(status.stdout)
    assert result["phase"] == "rework_required"
    assert result["authority"] == {
        "complete": False,
        "source": "missing gate-result.json",
    }


def test_status_reports_config_health_for_missing_task_paths(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/missing_feature.py\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "verifiers.yaml").write_text(
        "default:\n"
        "  - id: missing-test\n"
        '    command: "uv run pytest -q tests/missing_feature_test.py"\n'
        "    applies_to:\n"
        "      - tests/missing_feature_test.py\n"
        "    always: true\n",
        encoding="utf-8",
    )

    status = run_harness(repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    health = json.loads(status.stdout)["health"]
    assert health["status"] == "warn"
    missing = health["missing_paths"]
    assert {
        "source": "owners.yaml allowed_paths",
        "path": "src/missing_feature.py",
    } in missing
    assert {
        "source": "verifier missing-test applies_to",
        "path": "tests/missing_feature_test.py",
    } in missing
    assert {
        "source": "verifier missing-test command",
        "path": "tests/missing_feature_test.py",
    } in missing


def test_status_reports_review_config_health_warnings(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "review.yaml").write_text(
        "default:\n"
        "  quorum: 4\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - broken-reviewer\n"
        "  background_auto_run: false\n",
        encoding="utf-8",
    )

    status = run_harness(repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    health = json.loads(status.stdout)["health"]
    assert health["status"] == "warn"
    assert {
        "source": "review.quorum",
        "reason": "quorum 4 exceeds reviewer count 3",
    } in health["warnings"]
    assert {
        "source": "review.background_auto_run",
        "reason": "manual reviewer runs required",
    } in health["warnings"]
    assert {
        "source": "reviewer broken-reviewer",
        "reason": "unknown reviewer profile",
    } in health["warnings"]


def test_status_reports_missing_command_reviewer_executable(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "review.yaml").write_text(
        "default:\n"
        "  quorum: 3\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - semantic-ai\n"
        "  background_auto_run: true\n"
        "profiles:\n"
        "  semantic-ai:\n"
        "    kind: command\n"
        "    command:\n"
        "      - definitely-missing-reviewer-command\n"
        "      - .harness/semantic_reviewer.py\n",
        encoding="utf-8",
    )

    status = run_harness(repo, "status", TASK_ID)

    assert status.returncode == 0, status.stdout + status.stderr
    warnings = json.loads(status.stdout)["health"]["warnings"]
    assert {
        "source": "reviewer semantic-ai command",
        "reason": "executable not found: definitely-missing-reviewer-command",
    } in warnings


def test_verifier_plan_preserves_configured_timeout_s() -> None:
    from workflow_core.contract_harness.config import verifier_plan

    plan = verifier_plan(
        {
            "default": [
                {
                    "id": "slow-check",
                    "command": "python -c 'raise SystemExit(0)'",
                    "timeout_s": 12,
                }
            ]
        },
        "demo",
    )

    assert plan[0]["timeout_s"] == 12


def test_status_response_is_allowed_when_artifact_backed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    from workflow_core.contract_harness.agent_comm import build_status_response

    message = build_status_response(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
    )

    assert message["kind"] == "status_response"
    assert "completion authority: missing gate-result.json" in message["body_markdown"]
    assert any(ref["type"] == "verify_result" for ref in message["basis_refs"])
    assert any(ref["type"] == "submission" for ref in message["basis_refs"])
    inbox = runtime_task_dir(repo) / "comm" / "inbox" / "writer.claude.1"
    assert (inbox / f"{message['message_sha256']}.json").is_file()


def test_switchboard_auto_attaches_basis_refs_for_status_query(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0

    from workflow_core.contract_harness.agent_comm import send_message

    message = send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="status_query",
        subject="where are we",
        body_markdown="今どうなっている？",
    )

    assert any(ref["type"] == "candidate_diff" for ref in message["basis_refs"])
    assert any(ref["type"] == "verify_result" for ref in message["basis_refs"])


def test_status_response_cannot_mark_completion_without_harness_result(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0

    from workflow_core.contract_harness.agent_comm import build_status_response

    message = build_status_response(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
    )

    status_refs = [ref for ref in message["basis_refs"] if ref["type"] == "harness_status"]
    assert status_refs[0]["value"]["authority"]["complete"] is False
    assert "completion authority: missing gate-result.json" in message["body_markdown"]


def test_basis_ref_auto_attach_failure_does_not_block_message_send(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness import agent_comm

    def fail_basis_refs(_root: Path, _task_id: str, _kind: str) -> list[dict[str, Any]]:
        raise RuntimeError("simulated comm store read failure")

    monkeypatch.setattr(agent_comm, "_auto_basis_refs", fail_basis_refs)
    message = agent_comm.send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="status_query",
        subject="where are we",
        body_markdown="今どうなっている？",
    )

    assert message["warnings"] == [
        "basis_refs_auto_attach_failed: simulated comm store read failure"
    ]
    assert (runtime_task_dir(repo) / "comm" / "inbox" / "writer.claude.1").is_dir()


def test_artifact_ref_requires_hash(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.agent_comm import send_message

    with pytest.raises(ValueError, match="artifact_ref requires sha256"):
        send_message(
            repo,
            TASK_ID,
            from_agent_id="writer.codex.1",
            from_role="writer",
            to_agent_id="writer.claude.1",
            to_role="writer",
            kind="artifact_summary",
            subject="artifact",
            body_markdown="see artifact",
            artifact_refs=[{"type": "verify_result", "path": "verify-result.json"}],
        )


def test_message_body_done_language_is_not_authority(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.agent_comm import send_message

    message = send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="action_request",
        subject="please continue",
        body_markdown="done / complete と書いても authority ではない",
    )

    assert message["kind"] == "action_request"
    assert "authority" not in message
    assert not (runtime_task_dir(repo) / "push-result.json").exists()


def test_action_request_does_not_bypass_role_permissions(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.agent_comm import send_message

    message = send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="action_request",
        subject="please gate",
        body_markdown="HARNESS_ROLE=writer でも gate してほしい",
    )
    gated = run_harness(repo, "gate", TASK_ID, role="writer")

    assert message["kind"] == "action_request"
    assert gated.returncode != 0
    assert "role writer cannot run gate" in gated.stdout
    assert not (runtime_task_dir(repo) / "gate-result.json").exists()


def test_routing_handle_has_no_status(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.agent_comm import send_message

    message = send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="clarification",
        subject="question",
        body_markdown="方針確認です",
    )

    thread = load_runtime_json(
        repo,
        f"comm/threads/{message['correlation_handle'].replace(':', '-')}.json",
    )
    assert thread["correlation_handle"] == message["correlation_handle"]
    assert "status" not in thread
    assert "authority" not in thread


def test_comm_store_under_git_common_dir_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.agent_comm import send_message

    message = send_message(
        repo,
        TASK_ID,
        from_agent_id="writer.codex.1",
        from_role="writer",
        to_agent_id="writer.claude.1",
        to_role="writer",
        kind="clarification",
        subject="question",
        body_markdown="状態確認です",
    )
    inbox = runtime_task_dir(repo) / "comm" / "inbox" / "writer.claude.1"

    assert (inbox / f"{message['message_sha256']}.json").is_file()
    assert str(inbox).startswith(str(runtime_root(repo)))
    assert not (repo / ".harness" / "state" / "comm").exists()


def test_agent_comm_unavailable_does_not_block_harness_verify_submit(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    verified = run_harness(repo, "verify", TASK_ID, extra_env={"HARNESS_AGENT_COMM_DISABLE": "1"})
    submitted = run_harness(repo, "submit", TASK_ID, extra_env={"HARNESS_AGENT_COMM_DISABLE": "1"})

    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    assert load_runtime_json(repo, "submission.json")["status"] == "submitted"


def test_mcp_readonly_facade_exposes_resources_without_write_tools(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0

    from workflow_core.contract_harness import mcp_readonly

    resources = mcp_readonly.list_resources(repo, TASK_ID)
    verify_resource = next(item for item in resources if item["name"] == "verify-result.json")
    assert verify_resource["present"] is True
    assert verify_resource["readonly"] is True
    read = mcp_readonly.read_resource(repo, TASK_ID, "verify-result.json")
    assert '"status": "pass"' in read["content"]
    assert mcp_readonly.exposed_tools() == ()
    assert not {"verify", "submit", "gate", "land", "push"} & set(mcp_readonly.exposed_tools())


def test_pass_id_is_content_addressed_not_bearer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import (
        validate_pass_certificate,
        write_pass_certificate,
    )
    from workflow_core.contract_harness.hashing import hash_json

    certificate = write_pass_certificate(repo, TASK_ID, "reader-correctness")

    assert certificate["pass_subject_sha256"] == hash_json(certificate["subject"])
    assert validate_pass_certificate(repo, TASK_ID, certificate) is True
    assert (
        runtime_task_dir(repo)
        / "reviews"
        / "certificates"
        / f"{certificate['pass_subject_sha256']}.json"
    ).is_file()


def test_certify_cli_is_reviewer_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    blocked = run_harness(
        repo,
        "certify",
        TASK_ID,
        "--reviewer-id",
        "reader-correctness",
        role="writer",
    )
    certified = run_harness(
        repo,
        "certify",
        TASK_ID,
        "--reviewer-id",
        "reader-correctness",
        role="reviewer",
    )

    assert blocked.returncode != 0
    assert "role writer cannot run certify" in blocked.stdout
    assert certified.returncode == 0, certified.stdout + certified.stderr
    assert json.loads(certified.stdout)["pass_subject_sha256"].startswith("sha256:")


def test_pass_id_rejects_different_candidate_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import (
        validate_pass_certificate,
        write_pass_certificate,
    )

    certificate = write_pass_certificate(repo, TASK_ID, "reader-correctness")
    certificate["subject"] = {
        **certificate["subject"],
        "candidate_diff_sha256": "sha256:" + "0" * 64,
    }

    assert validate_pass_certificate(repo, TASK_ID, certificate) is False


def test_pass_id_rejects_different_task_with_same_token(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    other_task = "T-0002"
    (repo / ".harness" / "tasks" / other_task).mkdir()
    (repo / ".harness" / "tasks" / other_task / "task.yaml").write_text(
        task_yaml("generated", task_id=other_task),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/tasks/T-0002/task.yaml")
    git(repo, "commit", "-m", "add second task")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "verify", other_task).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import (
        validate_pass_certificate,
        write_pass_certificate,
    )

    certificate = write_pass_certificate(repo, TASK_ID, "reader-correctness")

    assert validate_pass_certificate(repo, other_task, certificate) is False


def test_pass_certificate_excludes_transcript_and_thread(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import write_pass_certificate

    certificate = write_pass_certificate(repo, TASK_ID, "reader-correctness")

    serialized = json.dumps(certificate, sort_keys=True)
    assert "transcript" not in serialized
    assert "thread" not in serialized
    assert "correlation_handle" not in serialized


def test_certified_test_content_hash_is_pinned(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import write_pass_certificate

    certified_tests = [
        {
            "id": "behavior_x_pytest",
            "kind": "pytest",
            "content_sha256": "sha256:" + "a" * 64,
            "runner": "pytest",
            "covers": ["behavior-x"],
        }
    ]
    certificate = write_pass_certificate(
        repo,
        TASK_ID,
        "reader-correctness",
        certified_tests=certified_tests,
    )
    assert certificate["subject"]["certified_tests"] == certified_tests
    with pytest.raises(ValueError, match="content_sha256"):
        write_pass_certificate(
            repo,
            TASK_ID,
            "reader-correctness",
            certified_tests=[{"id": "missing-hash", "kind": "pytest", "runner": "pytest"}],
        )


def test_trivial_certified_test_fails_mutation_adequacy(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import write_pass_certificate

    with pytest.raises(ValueError, match="trivial certified test"):
        write_pass_certificate(
            repo,
            TASK_ID,
            "reader-correctness",
            certified_tests=[
                {
                    "id": "empty_test",
                    "kind": "pytest",
                    "content_sha256": (
                        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    ),
                    "runner": "pytest",
                    "covers": [],
                }
            ],
        )


def test_certified_test_mutation_failure_invalidates_certify_claim(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    mutation_script = repo / ".harness" / "mutation_survivor.py"
    mutation_script.write_text(
        "import json, pathlib, sys\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'status': 'review_required',\n"
        "  'survivor_count': 1,\n"
        "  'survivors': [{'path': 'src/app.txt', 'reason': 'survived'}]\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        review_yaml()
        + "mutation:\n"
        + "  command:\n"
        + "    - python\n"
        + "    - .harness/mutation_survivor.py\n"
        + "  timeout_s: 30\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/mutation_survivor.py")
    git(repo, "commit", "-m", "enable mutation survivor")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import write_pass_certificate

    with pytest.raises(ValueError, match="mutation adequacy failed"):
        write_pass_certificate(
            repo,
            TASK_ID,
            "reader-correctness",
            certified_tests=[
                {
                    "id": "behavior_x_pytest",
                    "kind": "pytest",
                    "content_sha256": "sha256:" + "b" * 64,
                    "runner": "pytest",
                    "covers": ["behavior-x"],
                }
            ],
        )


def test_certified_tests_do_not_replace_required_verifiers_until_policy_allows(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )

    from workflow_core.contract_harness.certification import write_pass_certificate

    write_pass_certificate(
        repo,
        TASK_ID,
        "reader-correctness",
        certified_tests=[
            {
                "id": "behavior_x_pytest",
                "kind": "pytest",
                "content_sha256": "sha256:" + "c" * 64,
                "runner": "pytest",
                "covers": ["behavior-x"],
            }
        ],
    )

    verifiers = load_runtime_json(repo, "verifier-plan.json")["verifiers"]
    assert [verifier["id"] for verifier in verifiers] == ["unit"]


def test_reviewer_frozen_test_cannot_be_weakened_by_writer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    from workflow_core.contract_harness.frozen_tests import (
        certified_test_freeze_violations,
        freeze_certified_test_paths,
    )

    result = freeze_certified_test_paths(
        repo,
        "harness-review",
        [
            {
                "id": "reviewer_behavior",
                "kind": "pytest",
                "path": "tests/reviewer/test_behavior.py",
                "content_sha256": "sha256:" + "d" * 64,
                "runner": "pytest",
                "covers": ["behavior-x"],
            }
        ],
    )

    assert Path(result["frozen_file"]).is_file()
    assert certified_test_freeze_violations(
        repo,
        "harness-review",
        ["tests/reviewer/test_behavior.py"],
    ) == ["tests/reviewer/test_behavior.py"]
    assert certified_test_freeze_violations(repo, "harness-review", ["src/app.py"]) == []


def test_reviewer_can_write_harness_certificate_but_not_candidate_tree(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )
    before = (repo / "src" / "app.txt").read_text(encoding="utf-8")

    from workflow_core.contract_harness.certification import write_pass_certificate

    certificate = write_pass_certificate(repo, TASK_ID, "reader-correctness")

    assert certificate["written_by"] == "harness"
    assert (repo / "src" / "app.txt").read_text(encoding="utf-8") == before


def test_launch_writer_resumes_existing_dirty_sealed_writer_worktree(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    (writer_path / "src" / "notes.txt").write_text("untracked writer note\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0

    launched = run_harness(repo, "launch-writer", TASK_ID)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    session = json.loads(launched.stdout)
    assert session["status"] == "ready"
    assert session["worktree"]["path"] == str(writer_path)
    assert session["worktree"]["state"] == "sealed_for_review"
    assert session["worktree"]["dirty"] is True
    assert session["cwd"] == str(writer_path)
    assert str(HARNESS) in session["handoff"]["verify"]
    assert (writer_path / "src" / "app.txt").read_text(encoding="utf-8") == "candidate\n"
    assert (writer_path / "src" / "notes.txt").read_text(encoding="utf-8") == (
        "untracked writer note\n"
    )


def test_context_audit_from_writer_worktree_flags_missing_required_skill_paths(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])

    audited = run_harness(writer_path, "context-audit", TASK_ID)

    assert audited.returncode != 0
    audit = json.loads(audited.stdout)
    assert audit["status"] == "fail"
    writer_audit = audit["roles"]["writer"]
    assert writer_audit["status"] == "fail"
    assert "skill_path:implementation-slice-verification" in writer_audit["missing_required"]
    assert "skill_path:tdd-scope" in writer_audit["missing_required"]
    assert "scope-map-forward" in writer_audit["tools"]
    assert "budget" not in json.dumps(audit)


def test_context_audit_quantifies_role_context_without_budget_escape(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0

    audited = run_harness(repo, "context-audit", TASK_ID)

    assert audited.returncode == 0, audited.stdout + audited.stderr
    audit = json.loads(audited.stdout)
    assert audit["status"] == "pass"
    assert audit["pressure_estimator"] == "utf8_json_bytes_and_chars_div_4"
    assert "budget" not in json.dumps(audit)
    assert set(audit["roles"]) == {"writer", "reviewer", "integrator"}
    for _role, packet in audit["roles"].items():
        assert packet["status"] == "pass"
        assert packet["bytes"] > 0
        assert packet["estimated_tokens"] > 0
        assert packet["missing_required"] == []
        assert packet["tool_count"] > 0
        assert packet["skill_count"] > 0
    assert "scope-map-forward" in audit["roles"]["writer"]["tools"]
    assert "scope-map-reverse" in audit["roles"]["reviewer"]["tools"]
    assert "dispatch" in audit["roles"]["integrator"]["tools"]
    assert load_runtime_json(repo, "context-audit.json")["status"] == "pass"


def test_scope_map_forward_and_reverse_are_thin_scope_evidence(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0

    forward = run_harness(repo, "scope-map", TASK_ID, "--forward")
    assert forward.returncode == 0, forward.stdout + forward.stderr
    forward_map = load_runtime_json(repo, "scope-map-forward.json")
    assert forward_map["direction"] == "forward"
    assert "src/**" in forward_map["path_hints"]
    assert forward_map["hard_constraint"] is False
    assert forward_map["limitations"]

    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    reverse_map = load_runtime_json(repo, "scope-map-reverse.json")
    assert reverse_map["direction"] == "reverse"
    assert reverse_map["observed_scope"]["source"] == "candidate.diff"
    assert reverse_map["observed_scope"]["changed_paths"] == ["src/app.txt"]
    assert reverse_map["hard_constraint"] is False
    assert reverse_map["likely_affected"]["verifiers"] == ["unit"]


def test_scope_map_reverse_reaches_semantic_reviewer_and_stales_only_semantic(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "reverse = packet['scope_map']['reverse']\n"
        "assert reverse['observed_scope']['changed_paths'] == ['src/app.txt']\n"
        "assert reverse['hard_constraint'] is False\n"
        "policy = packet['reviewer_policy']['scope_map']\n"
        "assert 'diff is the observed implementation scope' in policy\n"
        "assert 'scope-map-reverse' in {tool['name'] for tool in packet['agent_tools']}\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['scope_map_reviewed'],\n"
        "  'reason': 'reverse scope map reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable scope map reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    reverse_path = runtime_task_dir(repo) / "scope-map-reverse.json"
    reverse = json.loads(reverse_path.read_text(encoding="utf-8"))
    reverse["likely_affected"]["review_topics"].append("manual stale probe")
    reverse_path.write_text(json.dumps(reverse, sort_keys=True) + "\n", encoding="utf-8")

    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    summary = json.loads(collected.stdout)
    assert summary["fresh_approves"] == 2
    assert summary["stale"] == ["semantic-ai"]


def test_scope_map_evidence_mismatch_blocks_gate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    reverse_path = runtime_task_dir(repo) / "scope-map-reverse.json"
    reverse = json.loads(reverse_path.read_text(encoding="utf-8"))
    reverse["observed_scope"]["changed_paths"].append("src/not-real.txt")
    reverse_path.write_text(json.dumps(reverse, sort_keys=True) + "\n", encoding="utf-8")

    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "evidence_hash_mismatch"


def test_submit_requires_passed_verify_and_writes_submission_evidence(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    missing = run_harness(repo, "submit", TASK_ID)
    assert missing.returncode != 0
    assert "verify-result" in missing.stdout

    failing_repo = init_repo(
        tmp_path / "failing", verifier_command="python -c 'raise SystemExit(1)'"
    )
    (failing_repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(failing_repo, "verify", TASK_ID).returncode != 0
    failed = run_harness(failing_repo, "submit", TASK_ID)
    assert failed.returncode != 0
    assert "verify-result status must be pass" in failed.stdout

    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    submitted = run_harness(repo, "submit", TASK_ID)
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    submission = load_runtime_json(repo, "submission.json")
    verify_result = load_runtime_json(repo, "verify-result.json")
    assert submission["status"] == "submitted"
    assert submission["candidate_diff_sha256"] == verify_result["candidate_diff_sha256"]
    assert submission["machine_evidence_sha256"] == verify_result["machine_evidence_sha256"]
    assert submission["written_by"] == "harness"


def test_dispatch_rejects_stale_submission_and_integrate_runs_reviewers(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    (repo / "src" / "app.txt").write_text("new candidate\n", encoding="utf-8")
    stale = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert stale.returncode != 0
    assert json.loads(stale.stdout)["reason"] == "stale_submission"

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    before_head = git(repo, "rev-parse", "HEAD")
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    result = json.loads(dispatched.stdout)
    assert result["status"] == "integrated"
    assert result["reason"] == "ok"
    assert result["review"]["fresh_approves"] == 2
    assert (runtime_task_dir(repo) / "reviews" / "reader-correctness.json").is_file()
    assert (runtime_task_dir(repo) / "reviews" / "reader-scope.json").is_file()
    assert git(repo, "rev-parse", "HEAD") == before_head


def test_dispatch_writes_review_runner_diagnosis_when_reviewer_subprocess_fails(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "review.yaml").write_text(
        "default:\n"
        "  quorum: 3\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - broken-reviewer\n"
        "  background_auto_run: true\n"
        "  blocking_labels:\n"
        "    - semantic_gap\n"
        "metrics:\n"
        "  reject_unexpected_actions: false\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml")
    git(repo, "commit", "-m", "add broken reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")

    assert dispatched.returncode != 0
    result = json.loads(dispatched.stdout)
    assert result["status"] == "rework_required"
    assert result["reason"] == "reviewer_failed:broken-reviewer"
    run_result = load_runtime_json(repo, "review-runs/broken-reviewer.json")
    assert run_result["reviewer_id"] == "broken-reviewer"
    assert run_result["status"] == "fail"
    assert run_result["exit_code"] == 1
    assert "unknown reviewer: broken-reviewer" in (
        run_result["stdout_tail"] + run_result["stderr_tail"]
    )
    assert load_runtime_json(repo, "integration-result.json")["reason"] == (
        "reviewer_failed:broken-reviewer"
    )


def test_gate_writes_review_runner_diagnosis_when_auto_reviewer_fails(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "review.yaml").write_text(
        "default:\n"
        "  quorum: 3\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - broken-reviewer\n"
        "  background_auto_run: true\n"
        "  blocking_labels:\n"
        "    - semantic_gap\n"
        "metrics:\n"
        "  reject_unexpected_actions: false\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml")
    git(repo, "commit", "-m", "add broken reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0

    gated = run_harness(repo, "gate", TASK_ID, role="integrator")

    assert gated.returncode != 0
    result = json.loads(gated.stdout)
    assert result["reason"] == "reviewer_failed:broken-reviewer"
    run_result = load_runtime_json(repo, "review-runs/broken-reviewer.json")
    assert run_result["mode"] == "in_process"
    assert run_result["status"] == "fail"
    assert "unknown reviewer: broken-reviewer" in run_result["stderr_tail"]
    assert load_runtime_json(repo, "gate-result.json")["reason"] == (
        "reviewer_failed:broken-reviewer"
    )


def test_submit_wait_dispatches_in_integrator_boundary(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    waited = run_harness(writer_path, "submit", TASK_ID, "--wait")
    assert waited.returncode == 0, waited.stdout + waited.stderr
    result = json.loads(waited.stdout)
    assert result["status"] == "integrated"
    assert load_runtime_json(repo, "integration-result.json")["role"] == "integrator"
    integration = result["integration_workspace"]
    assert integration["path"] == str(runtime_root(repo) / "worktrees" / TASK_ID / "integrator")
    assert integration["path"] != str(writer_path)
    handoff = load_runtime_json(repo, "integrator-handoff.json")
    assert handoff["from_workspace"] == str(writer_path)
    assert handoff["integration_workspace"]["kind"] == "integrator"


def test_submit_wait_records_dispatch_subprocess_diagnosis(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)
    fake_harness = repo / "fake-harness"
    fake_harness.write_text(
        "#!/usr/bin/env sh\n"
        "printf 'not json output\\n'\n"
        "printf 'dispatch exploded\\n' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    fake_harness.chmod(0o755)

    from workflow_core.contract_harness.submission import wait_for_dispatch

    result, code = wait_for_dispatch(repo, TASK_ID, harness_bin=fake_harness)

    assert code == 7
    assert result["ok"] is False
    assert result["reason"] == "dispatch exploded"
    dispatch_result = load_runtime_json(repo, "dispatch-result.json")
    assert dispatch_result["status"] == "fail"
    assert dispatch_result["exit_code"] == 7
    assert dispatch_result["stdout_tail"] == "not json output\n"
    assert dispatch_result["stderr_tail"] == "dispatch exploded\n"


def test_submit_wait_uses_canonical_harness_config_when_worktrees_lack_harness_dir(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test User")
    git(repo, "branch", "-M", "main")
    (repo / "src").mkdir()
    (repo / "src" / "app.txt").write_text("base\n", encoding="utf-8")
    (repo / "Makefile").write_text("check-required:\n\t@true\n", encoding="utf-8")
    git(repo, "add", "src/app.txt", "Makefile")
    git(repo, "commit", "-m", "base without harness config")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-u", "origin", "main")
    write_harness_config(repo, "python -c 'raise SystemExit(0)'", reject_unexpected=False)
    (repo / ".harness" / "policy.yaml").write_text(policy_yaml(), encoding="utf-8")
    semantic = repo / ".harness" / "semantic_reviewer.py"
    semantic.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert pathlib.Path.cwd() == pathlib.Path(packet['review_workspace']['path'])\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['canonical_config_wrapper'],\n"
        "  'reason': 'control-plane reviewer wrapper ran from integration worktree'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", "{repo_root}/.harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )

    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    assert not (writer_path / ".harness" / "review.yaml").exists()
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0

    waited = run_harness(writer_path, "submit", TASK_ID, "--wait")

    assert waited.returncode == 0, waited.stdout + waited.stderr
    result = json.loads(waited.stdout)
    assert result["status"] == "integrated"
    integration_path = Path(result["integration_workspace"]["path"])
    assert not (integration_path / ".harness" / "review.yaml").exists()
    semantic_result = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic_result["labels"] == ["canonical_config_wrapper"]
    assert load_runtime_json(repo, "integration-result.json")["status"] == "integrated"


def test_e2e_integrator_dispatch_land_then_push_blocks_under_dry_run(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    integrator = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--integrator", role="integrator").stdout
    )
    integrator_path = Path(integrator["path"])

    dispatched = run_harness(integrator_path, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    status = git(integrator_path, "status", "--porcelain=v1")
    assert status == ""

    landed = run_harness(repo, "land", TASK_ID, role="integrator")
    assert landed.returncode == 0, landed.stdout + landed.stderr
    land_result = json.loads(landed.stdout)
    assert land_result["status"] == "landed"
    assert land_result["worktree_path"] == str(integrator_path)

    pushed = run_harness(repo, "push", TASK_ID, role="integrator")

    assert pushed.returncode != 0
    push_result = json.loads(pushed.stdout)
    assert push_result["status"] == "blocked"
    assert push_result["reason"] == "protected_external_write"
    assert push_result["landed_commit"] == land_result["landed_commit"]
    assert push_result["lock_acquire"]["status"] == "not_attempted"
    assert load_runtime_json(repo, "push-result.json")["reason"] == "protected_external_write"


def test_land_default_gate_reruns_task_verifiers_not_broad_make(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, make_exit=1)
    enable_policy_and_remote(tmp_path, repo)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    landed = run_harness(repo, "land", TASK_ID, role="integrator")

    assert landed.returncode == 0, landed.stdout + landed.stderr
    land_result = json.loads(landed.stdout)
    assert land_result["status"] == "landed"
    land_gate = land_result["land_gate"]
    assert land_gate["status"] == "pass"
    assert land_gate["command"] == "harness verifiers: unit"
    assert len(land_gate["verifiers"]) == 1
    assert land_gate["verifiers"][0]["id"] == "unit"
    assert land_gate["verifiers"][0]["status"] == "pass"
    assert land_gate["verifiers"][0]["exit_code"] == 0


def test_land_explicit_gate_tier_blocks_and_records_gate_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, make_exit=1)
    enable_policy_and_remote(tmp_path, repo)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    landed = run_harness(
        repo,
        "land",
        TASK_ID,
        role="integrator",
        extra_env={"FOUNDATION_GATE_TIER": "check-required"},
    )

    assert landed.returncode != 0
    land_result = json.loads(landed.stdout)
    assert land_result["status"] == "rework_required"
    assert land_result["reason"] == "machine_gate_failed"
    land_gate = land_result["land_gate"]
    assert land_gate["status"] == "fail"
    assert land_gate["command"] == "make check-required"
    assert land_gate["exit_code"] != 0

    retry = run_harness(repo, "land", TASK_ID, role="integrator")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    retry_result = json.loads(retry.stdout)
    assert retry_result["status"] == "landed"
    assert retry_result["land_gate"]["status"] == "pass"


def test_land_commits_on_agent_branch_when_hooks_reject_detached_head(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    hooks = repo / "hooks"
    hooks.mkdir()
    pre_commit = hooks / "pre-commit"
    pre_commit.write_text(
        "#!/bin/sh\n"
        "branch=$(git branch --show-current)\n"
        '[ -n "$branch" ] || { echo detached >&2; exit 2; }\n'
        'case "$branch" in\n'
        "  agent/*/*/*) exit 0 ;;\n"
        "  *) echo bad-branch >&2; exit 2 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    pre_commit.chmod(0o755)
    git(repo, "add", "hooks/pre-commit")
    git(repo, "commit", "-m", "add detached guard hook")
    enable_policy_and_remote(tmp_path, repo)
    git(repo, "config", "core.hooksPath", "hooks")
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    landed = run_harness(repo, "land", TASK_ID, role="integrator")

    assert landed.returncode == 0, landed.stdout + landed.stderr
    result = json.loads(landed.stdout)
    assert result["status"] == "landed"
    worktree_path = Path(result["worktree_path"])
    assert git(worktree_path, "branch", "--show-current") == f"agent/{TASK_ID}/integrator/land"


def test_parallel_land_same_branch_blocks_one_task_without_mixing_evidence(
    tmp_path: Path,
) -> None:
    task_a = "T-parallel-a"
    task_b = "T-parallel-b"
    repo = init_repo(
        tmp_path,
        verifier_command='python -c "import time; time.sleep(2); raise SystemExit(0)"',
    )
    (repo / ".harness" / "tasks" / task_a).mkdir(parents=True)
    (repo / ".harness" / "tasks" / task_a / "task.yaml").write_text(
        task_yaml("generated", task_a),
        encoding="utf-8",
    )
    (repo / ".harness" / "tasks" / task_b).mkdir(parents=True)
    (repo / ".harness" / "tasks" / task_b / "task.yaml").write_text(
        task_yaml("generated", task_b),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/tasks")
    git(repo, "commit", "-m", "add parallel tasks")
    enable_policy_and_remote(tmp_path, repo)
    for task_id, path, content in (
        (task_a, "src/parallel-a.txt", "candidate a\n"),
        (task_b, "src/parallel-b.txt", "candidate b\n"),
    ):
        assert run_harness(repo, "prepare", task_id).returncode == 0
        writer = json.loads(
            run_harness(repo, "worktree", task_id, "--writer", role="integrator").stdout
        )
        writer_path = Path(writer["path"])
        (writer_path / path).write_text(content, encoding="utf-8")
        assert run_harness(writer_path, "verify", task_id).returncode == 0
        assert run_harness(writer_path, "submit", task_id).returncode == 0
        dispatched = run_harness(repo, "dispatch", task_id, role="integrator")
        assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    first = subprocess.Popen(
        [str(HARNESS), "land", task_a],
        cwd=repo,
        env={**os.environ, "HARNESS_ROLE": "integrator"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    lock_dir = runtime_root(repo) / "locks"
    deadline = time.monotonic() + 10
    while (
        not list(lock_dir.glob("land-*.lock"))
        and first.poll() is None
        and time.monotonic() < deadline
    ):
        time.sleep(0.05)
    assert list(lock_dir.glob("land-*.lock"))

    blocked = run_harness(repo, "land", task_b, role="integrator")
    first_stdout, first_stderr = first.communicate(timeout=30)

    assert first.returncode == 0, first_stdout + first_stderr
    first_result = json.loads(first_stdout)
    assert first_result["status"] == "landed"
    assert first_result["task_id"] == task_a
    assert first_result["land_gate"]["status"] == "pass"
    assert blocked.returncode != 0
    blocked_result = json.loads(blocked.stdout)
    assert blocked_result["task_id"] == task_b
    assert blocked_result["status"] == "blocked"
    assert blocked_result["reason"] == "blocked_by_lock"
    assert blocked_result["lock"]["read_status"] == "readable"
    assert blocked_result["lock"]["task_id"] == task_a
    assert (
        blocked_result["candidate_diff_sha256"]
        == load_runtime_json(repo, "verify-result.json", task_b)["candidate_diff_sha256"]
    )
    assert load_runtime_json(repo, "land-result.json", task_a)["status"] == "landed"
    assert load_runtime_json(repo, "land-result.json", task_b)["status"] == "blocked"

    retry = run_harness(repo, "land", task_b, role="integrator")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    retry_result = json.loads(retry.stdout)
    assert retry_result["task_id"] == task_b
    assert retry_result["status"] == "landed"
    assert retry_result["land_gate"]["status"] == "pass"


def test_land_blocked_by_corrupt_local_lock_reports_lock_diagnostics(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    assert run_harness(repo, "dispatch", TASK_ID, role="integrator").returncode == 0
    lock_dir = runtime_root(repo) / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = next(lock_dir.glob("land-*.lock"), None)
    assert lock_path is None
    corrupt = _lock_path(repo, "land", "main")
    corrupt.write_text("not json", encoding="utf-8")

    landed = run_harness(repo, "land", TASK_ID, role="integrator")

    assert landed.returncode != 0
    result = json.loads(landed.stdout)
    assert result["status"] == "blocked"
    assert result["reason"] == "blocked_by_lock"
    assert result["lock"]["read_status"] == "invalid_json"
    assert result["lock"]["path"] == str(corrupt)


def test_parallel_submit_wait_keeps_reviewer_and_integrator_evidence_per_task(
    tmp_path: Path,
) -> None:
    task_a = "T-submit-a"
    task_b = "T-submit-b"
    repo = init_repo(
        tmp_path,
        verifier_command='python -c "import time; time.sleep(0.2); raise SystemExit(0)"',
    )
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys, time\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "task_id = packet['task_id']\n"
        "assert task_id in packet['candidate_diff']\n"
        "assert packet['verify_result']['task_id'] == task_id\n"
        "time.sleep(0.4)\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['semantic_' + task_id],\n"
        "  'reason': 'reviewed ' + task_id\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", "{repo_root}/.harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    for task_id in (task_a, task_b):
        task_dir_path = repo / ".harness" / "tasks" / task_id
        task_dir_path.mkdir(parents=True)
        (task_dir_path / "task.yaml").write_text(
            task_yaml("generated", task_id),
            encoding="utf-8",
        )
    git(repo, "add", ".harness")
    git(repo, "commit", "-m", "add parallel submit tasks")
    enable_policy_and_remote(tmp_path, repo)
    writers: dict[str, Path] = {}
    for task_id in (task_a, task_b):
        assert run_harness(repo, "prepare", task_id).returncode == 0
        writer = json.loads(
            run_harness(repo, "worktree", task_id, "--writer", role="integrator").stdout
        )
        writer_path = Path(writer["path"])
        writers[task_id] = writer_path
        (writer_path / "src" / f"{task_id}.txt").write_text(
            f"candidate {task_id}\n",
            encoding="utf-8",
        )
        assert run_harness(writer_path, "verify", task_id).returncode == 0

    processes = {
        task_id: subprocess.Popen(
            [str(HARNESS), "submit", task_id, "--wait"],
            cwd=writer_path,
            env={**os.environ, "HARNESS_ROLE": "writer"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for task_id, writer_path in writers.items()
    }

    results: dict[str, dict[str, Any]] = {}
    for task_id, process in processes.items():
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stdout + stderr
        result = json.loads(stdout)
        results[task_id] = result
        assert result["task_id"] == task_id
        assert result["status"] == "integrated"
        assert result["review"]["review_pass"] is True
        assert result["review"]["stale"] == []
        assert result["review"]["fresh_semantic_approves"] == 1

    for task_id, result in results.items():
        verify = load_runtime_json(repo, "verify-result.json", task_id)
        semantic = load_runtime_json(repo, "reviews/semantic-ai.json", task_id)
        packet = load_runtime_json(repo, "reviews/semantic-ai.review-packet.json", task_id)
        integration = load_runtime_json(repo, "integration-result.json", task_id)
        collected = run_harness(repo, "review", task_id, "--collect", role="integrator")
        summary = json.loads(collected.stdout)

        assert semantic["labels"] == [f"semantic_{task_id}"]
        assert semantic["evidence_seen"]["candidate_diff_sha256"] == verify["candidate_diff_sha256"]
        assert packet["task_id"] == task_id
        assert task_id in packet["candidate_diff"]
        assert integration["task_id"] == task_id
        assert integration["candidate_diff_sha256"] == result["candidate_diff_sha256"]
        assert summary["review_pass"] is True
        assert summary["stale"] == []


def test_local_land_lock_is_scoped_to_target_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    with (
        local_lock(
            repo,
            "land",
            task_id="T-main",
            target_branch="main",
            base_sha="base-main",
            timeout_s=900,
        ) as main_lock,
        local_lock(
            repo,
            "land",
            task_id="T-release",
            target_branch="release/v1",
            base_sha="base-release",
            timeout_s=900,
        ) as release_lock,
    ):
        assert main_lock != release_lock
        assert main_lock.is_file()
        assert release_lock.is_file()


def test_local_land_lock_still_blocks_same_target_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    with (
        local_lock(
            repo,
            "land",
            task_id="T-first",
            target_branch="main",
            base_sha="base-main",
            timeout_s=900,
        ),
        pytest.raises(LockBlocked),
        local_lock(
            repo,
            "land",
            task_id="T-second",
            target_branch="main",
            base_sha="base-main",
            timeout_s=900,
        ),
    ):
        pass


def test_integrator_failure_writes_rework_packet(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, make_exit=1)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(
        repo,
        "dispatch",
        TASK_ID,
        role="integrator",
        extra_env={"FOUNDATION_GATE_TIER": "check-required"},
    )
    assert dispatched.returncode != 0
    result = load_runtime_json(repo, "integration-result.json")
    assert result["status"] == "rework_required"
    assert result["reason"] == "machine_gate_failed"


def test_integrator_default_completion_gate_reruns_task_verifiers_not_broad_make(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path, make_exit=1)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")

    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    result = json.loads(dispatched.stdout)
    assert result["status"] == "integrated"
    assert result["reason"] == "ok"
    completion = result["completion"]
    assert completion["status"] == "pass"
    assert completion["command"] == "harness verifiers: unit"
    assert len(completion["verifiers"]) == 1
    assert completion["verifiers"][0]["id"] == "unit"
    assert completion["verifiers"][0]["status"] == "pass"
    assert completion["verifiers"][0]["exit_code"] == 0
    evidence = json.loads(Path(completion["evidence_path"]).read_text(encoding="utf-8"))
    assert evidence["command"] == "harness verifiers: unit"


def test_semantic_ai_reviewer_receives_diff_and_test_interpretation(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    enable_semantic_reviewer(repo)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = json.loads((runtime_task_dir(repo) / "reviews" / "semantic-ai.json").read_text())
    assert semantic["verdict"] == "approve"
    assert semantic["reason"] == "diff and tests reviewed"
    packet = load_runtime_json(repo, "reviews/semantic-ai.review-packet.json")
    assert "candidate\n" in packet["candidate_diff"]
    assert (
        packet["candidate_diff_sha256"]
        == load_runtime_json(repo, "verify-result.json")["candidate_diff_sha256"]
    )
    assert packet["requires_artifact_read"] is False
    assert packet["omitted_required_evidence"] == []
    assert "context_manifest" not in packet
    assert "budget" not in json.dumps(packet)
    assert packet["test_interpretation"]["required_verifiers_passed"] is True


def test_large_diff_is_not_inlined_in_semantic_reviewer_packet(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import hashlib, json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['candidate_diff'] == ''\n"
        "assert packet['requires_artifact_read'] is True\n"
        "assert packet['omitted_required_evidence'] == ['candidate_diff']\n"
        "diff_path = pathlib.Path(packet['candidate_diff_path'])\n"
        "digest = 'sha256:' + hashlib.sha256(diff_path.read_bytes()).hexdigest()\n"
        "assert digest == packet['candidate_diff_sha256']\n"
        "assert 'budget' not in json.dumps(packet)\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['artifact_diff_reviewed'],\n"
        "  'reason': 'large diff read from candidate artifact'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable large diff reviewer")
    (repo / "src" / "large.txt").write_text("candidate\n" * 12000, encoding="utf-8")

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["artifact_diff_reviewed"]


def test_e2e_semantic_reviewer_receives_writer_handoff_diff_index_tools_and_skills(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    enable_policy_and_remote(tmp_path, repo)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "writer = packet['writer_handoff']\n"
        "assert writer['verification']['status'] == 'pass'\n"
        "assert 'verify' in {tool['name'] for tool in writer['agent_tools']}\n"
        "assert 'tdd-scope' in {skill['name'] for skill in writer['agent_skills']}\n"
        "assert packet['candidate_diff_index']['changed_files'] == ['src/app.txt']\n"
        "assert packet['candidate_diff_path'].endswith('candidate.diff')\n"
        "assert 'scope-map-reverse' in {tool['name'] for tool in packet['agent_tools']}\n"
        "assert 'release-check' in {skill['name'] for skill in packet['agent_skills']}\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['ideal_packet_reviewed'],\n"
        "  'reason': 'writer handoff, diff index, tools and skills reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable ideal semantic reviewer")
    git(repo, "push", "origin", "main")
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    integrator = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--integrator", role="integrator").stdout
    )
    dispatched = run_harness(Path(integrator["path"]), "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["ideal_packet_reviewed"]


def test_semantic_reviewer_runs_in_sealed_writer_worktree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "cwd = pathlib.Path.cwd().resolve()\n"
        "workspace = pathlib.Path(packet['review_workspace']['path']).resolve()\n"
        "assert cwd == workspace\n"
        "assert packet['review_workspace']['state'] == 'sealed_for_review'\n"
        "assert pathlib.Path('src/app.txt').read_text() == 'candidate\\n'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['sealed_workspace'],\n"
        "  'reason': 'reviewed sealed writer worktree'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable sealed workspace reviewer")
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    submission = load_runtime_json(repo, "submission.json")
    writer_skill_paths = [
        skill.get("path")
        for skill in submission["writer_handoff"]["agent_skills"]
        if skill.get("path") is not None
    ]
    assert all(str(path).startswith(str(writer_path)) for path in writer_skill_paths)
    assert submission["candidate_workspace"]["path"] == str(writer_path)
    assert submission["candidate_workspace"]["state"] == "sealed_for_review"
    marker = json.loads((writer_path / ".harness-worktree.json").read_text(encoding="utf-8"))
    assert marker["state"] == "sealed_for_review"
    assert (repo / "src" / "app.txt").read_text(encoding="utf-8") == "base\n"

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["sealed_workspace"]
    packet = load_runtime_json(repo, "reviews/semantic-ai.review-packet.json")
    assert packet["review_workspace"]["path"] == str(writer_path)


def test_semantic_reviewer_command_can_use_repo_root_placeholder_from_writer_worktree(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "root_only_semantic.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "cwd = pathlib.Path.cwd().resolve()\n"
        "assert not (cwd / '.harness' / 'root_only_semantic.py').exists()\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['review_workspace']['path'] == str(cwd)\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['repo_root_wrapper'],\n"
        "  'reason': 'repo root reviewer wrapper ran from sealed worktree'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", "{repo_root}/.harness/root_only_semantic.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml")
    git(repo, "commit", "-m", "enable root wrapper semantic reviewer")
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    assert not (writer_path / ".harness" / "root_only_semantic.py").exists()
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")

    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["repo_root_wrapper"]


def test_semantic_reviewer_mutating_sealed_worktree_blocks_without_crashing(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "pathlib.Path('src/app.txt').write_text('reviewer mutation\\n')\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['attempted_approve'],\n"
        "  'reason': 'mutated candidate'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable mutating reviewer")
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0
    assert run_harness(writer_path, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")

    assert dispatched.returncode != 0
    result = json.loads(dispatched.stdout)
    assert result["reason"] == "review_blocked"
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["verdict"] == "block"
    assert semantic["labels"] == ["semantic_gap"]
    assert semantic["reason"] == "reviewer mutated candidate workspace"


def test_mutation_handoff_survivors_reach_semantic_reviewer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    mutation_script = repo / ".harness" / "mutation_probe.py"
    mutation_script.write_text(
        "import json, pathlib, sys\n"
        "candidate = pathlib.Path(sys.argv[1]).read_text()\n"
        "assert 'candidate\\n' in candidate\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'survivors': [{\n"
        "    'path': 'src/app.txt',\n"
        "    'line': 1,\n"
        "    'mutator': 'replace-candidate-text',\n"
        "    'reason': 'tests did not assert the new behavior'\n"
        "  }]\n"
        "}))\n",
        encoding="utf-8",
    )
    reviewer_script = repo / ".harness" / "semantic_reviewer.py"
    reviewer_script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "mutation = packet['test_interpretation']['mutation']\n"
        "assert mutation['status'] == 'review_required'\n"
        "assert mutation['survivor_count'] == 1\n"
        "assert packet['mutation_result']['survivors'][0]['path'] == 'src/app.txt'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'block',\n"
        "  'labels': ['mutation_survivor'],\n"
        "  'reason': 'surviving mutant shows missing assertion for src/app.txt'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(
            command=["python", ".harness/semantic_reviewer.py"],
            mutation_command=["python", ".harness/mutation_probe.py"],
        ),
        encoding="utf-8",
    )
    git(
        repo,
        "add",
        ".harness/review.yaml",
        ".harness/mutation_probe.py",
        ".harness/semantic_reviewer.py",
    )
    git(repo, "commit", "-m", "enable mutation handoff")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    submitted = run_harness(repo, "submit", TASK_ID)
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    mutation = load_runtime_json(repo, "mutation-result.json")
    assert mutation["status"] == "review_required"
    assert mutation["survivor_count"] == 1
    assert load_runtime_json(repo, "submission.json")["mutation_result_sha256"]

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode != 0
    result = json.loads(dispatched.stdout)
    assert result["reason"] == "review_blocked"
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["mutation_survivor"]
    packet = load_runtime_json(repo, "reviews/semantic-ai.review-packet.json")
    assert packet["test_interpretation"]["mutation"]["survivor_count"] == 1


def test_mutation_error_output_is_bounded_and_redacted(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    mutation_script = repo / ".harness" / "mutation_fail.py"
    mutation_script.write_text(
        "import sys\n"
        "print('token=SECRET_VALUE ' + 'x' * 10000)\n"
        "print('password: SECRET_VALUE ' + 'y' * 10000, file=sys.stderr)\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    reviewer_script = repo / ".harness" / "semantic_reviewer.py"
    reviewer_script.write_text(
        "import json, pathlib, sys\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({'verdict': 'approve'}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(
            command=["python", ".harness/semantic_reviewer.py"],
            mutation_command=["python", ".harness/mutation_fail.py"],
        ),
        encoding="utf-8",
    )
    git(
        repo,
        "add",
        ".harness/review.yaml",
        ".harness/mutation_fail.py",
        ".harness/semantic_reviewer.py",
    )
    git(repo, "commit", "-m", "enable failing mutation")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    submitted = run_harness(repo, "submit", TASK_ID)
    assert submitted.returncode != 0
    result = load_runtime_json(repo, "mutation-result.json")

    assert result["reason"] == "mutation_command_failed"
    assert len(result["stdout"]) <= 4200
    assert len(result["stderr"]) <= 4200
    assert "SECRET_VALUE" not in result["stdout"]
    assert "SECRET_VALUE" not in result["stderr"]
    assert "[REDACTED]" in result["stdout"]
    assert "[REDACTED]" in result["stderr"]


def test_quality_review_flags_do_not_block_submit_and_reach_semantic_reviewer(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['quality_result']['status'] == 'review_required'\n"
        "assert packet['test_interpretation']['quality']['status'] == 'review_required'\n"
        "assert 'threshold gaming' in packet['reviewer_policy']['quality']\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['quality_reviewed'],\n"
        "  'reason': 'quality flags reviewed against policy anchor'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable quality reviewer")
    long_body = "\n".join("    value += 1" for _ in range(65))
    (repo / "src" / "quality.py").write_text(
        f"def readable_but_long() -> int:\n    value = 0\n{long_body}\n    return value\n",
        encoding="utf-8",
    )

    verify = run_harness(repo, "verify", TASK_ID)
    assert verify.returncode == 0, verify.stdout + verify.stderr
    quality = load_runtime_json(repo, "quality-result.json")
    assert quality["status"] == "review_required"
    assert quality["hard_failures"] == []
    submitted = run_harness(repo, "submit", TASK_ID)
    assert submitted.returncode == 0, submitted.stdout + submitted.stderr
    submission = load_runtime_json(repo, "submission.json")
    assert submission["quality_result_sha256"]

    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["quality_reviewed"]


def test_quality_hard_fail_blocks_submit_before_semantic_reviewer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    marker = repo / "semantic-called.txt"
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('called')\n"
        'pathlib.Path(sys.argv[2]).write_text(\'{"verdict":"approve"}\')\n',
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable semantic reviewer")
    (repo / "src" / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    verify = run_harness(repo, "verify", TASK_ID)
    assert verify.returncode != 0
    quality = load_runtime_json(repo, "quality-result.json")
    assert quality["status"] == "fail"
    assert quality["hard_failures"]
    submitted = run_harness(repo, "submit", TASK_ID)
    assert submitted.returncode != 0
    assert "verify-result status must be pass" in submitted.stdout

    reviewed = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["machine_failed"]
    assert not marker.exists()


def test_semantic_reviewer_timeout_writes_command_diagnosis(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "slow_semantic_reviewer.py"
    script.write_text(
        "import time\ntime.sleep(2)\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/slow_semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/slow_semantic_reviewer.py")
    git(repo, "commit", "-m", "enable slow semantic reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0

    reviewed = run_harness(
        repo,
        "review",
        TASK_ID,
        "--run",
        "semantic-ai",
        role="reviewer",
        extra_env={"FOUNDATION_REVIEW_TIMEOUT_S": "1"},
    )

    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["verdict"] == "block"
    assert semantic["labels"] == ["reviewer_infra_failed"]
    assert (
        semantic["reason"] == "semantic reviewer infrastructure failed; reviewer agent not active"
    )
    command_result = load_runtime_json(repo, "review-runs/semantic-ai-command.json")
    assert command_result["status"] == "timeout"
    assert command_result["timed_out"] is True
    assert command_result["exit_code"] == 124
    assert command_result["agent_activity"]["status"] == "not_active"
    assert command_result["agent_activity"]["reviewer_id"] == "semantic-ai"
    assert command_result["next_action"] == "resume_reviewer_agent"
    assert "spawn" in command_result["resume_command"]
    assert "semantic-ai" in command_result["resume_command"]


def test_semantic_reviewer_command_failure_prompts_rerun_when_agent_session_exists(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "failing_semantic_reviewer.py"
    script.write_text(
        "raise SystemExit(17)\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/failing_semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/failing_semantic_reviewer.py")
    git(repo, "commit", "-m", "enable failing semantic reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    spawned = run_harness(
        repo,
        "spawn",
        TASK_ID,
        "--role",
        "reviewer",
        "--reviewer-id",
        "semantic-ai",
        "--agent",
        "codex",
        role="integrator",
    )
    assert spawned.returncode == 0, spawned.stdout + spawned.stderr

    reviewed = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")

    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["verdict"] == "block"
    assert semantic["labels"] == ["reviewer_infra_failed"]
    command_result = load_runtime_json(repo, "review-runs/semantic-ai-command.json")
    assert command_result["status"] == "fail"
    assert command_result["exit_code"] == 17
    assert command_result["agent_activity"]["status"] == "active"
    assert command_result["next_action"] == "rerun_semantic_review"
    assert command_result["rerun_command"].endswith(" review T-0001 --run semantic-ai")


def test_tool_candidates_and_reviewer_policy_anchor_reach_semantic_reviewer(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/**\n"
        "      - tests/**\n"
        "      - scripts/**\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "candidate = packet['tool_candidates']['candidates'][0]\n"
        "assert candidate['path'] == 'scripts/tool_probe.py'\n"
        "assert candidate['kind'] == 'script'\n"
        "assert 'reusable beyond the current task' in packet['reviewer_policy']['tool_reuse']\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['tool_generalized'],\n"
        "  'reason': 'tool candidate reviewed against reuse policy'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(
        repo,
        "add",
        ".harness/owners.yaml",
        ".harness/review.yaml",
        ".harness/semantic_reviewer.py",
    )
    git(repo, "commit", "-m", "allow script tool candidates")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool_probe.py").write_text(
        "import argparse, json\n"
        "\n"
        "def main() -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--input', default='')\n"
        "    args = parser.parse_args()\n"
        "    print(json.dumps({'input': args.input}))\n"
        "    return 0\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    tool_candidates = load_runtime_json(repo, "tool-candidates.json")
    assert tool_candidates["status"] in {"pass", "review_required"}
    assert tool_candidates["candidates"][0]["path"] == "scripts/tool_probe.py"
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["tool_generalized"]


def test_configured_semantic_reviewer_is_required_even_when_quorum_is_lower(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['verify_result']['status'] == 'pass'\n"
        "assert 'candidate\\n' in packet['candidate_diff']\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['semantic_required'],\n"
        "  'reason': 'semantic reviewer consumed diff and tests'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        "default:\n"
        "  quorum: 2\n"
        "  reviewers:\n"
        "    - reader-correctness\n"
        "    - reader-scope\n"
        "    - semantic-ai\n"
        "  background_auto_run: false\n"
        "  blocking_labels:\n"
        "    - semantic_gap\n"
        "profiles:\n"
        "  semantic-ai:\n"
        "    kind: command\n"
        "    command:\n"
        '      - "python"\n'
        '      - ".harness/semantic_reviewer.py"\n'
        "metrics:\n"
        "  reject_unexpected_actions: false\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable semantic reviewer with low quorum")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo, "review", TASK_ID, "--run", "reader-correctness", role="reviewer"
        ).returncode
        == 0
    )
    assert (
        run_harness(repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer").returncode
        == 0
    )

    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    summary = json.loads(collected.stdout)
    assert summary["fresh_approves"] == 2
    assert summary["semantic_review_required"] is True
    assert summary["review_pass"] is False

    reviewed = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    recovered = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    recovered_summary = json.loads(recovered.stdout)
    assert recovered_summary["fresh_semantic_approves"] == 1
    assert recovered_summary["review_pass"] is True


def test_review_required_tool_candidate_needs_semantic_reviewer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/**\n"
        "      - tests/**\n"
        "      - scripts/**\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/owners.yaml")
    git(repo, "commit", "-m", "allow script candidates without semantic reviewer")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool_probe.py").write_text(
        "import argparse\n"
        "\n"
        "def main() -> int:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--input', default='')\n"
        "    parser.parse_args()\n"
        "    return 0\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode != 0
    assert json.loads(dispatched.stdout)["reason"] == "semantic_review_required"


def test_broken_tool_candidate_probe_hard_fails_verify(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / ".harness" / "owners.yaml").write_text(
        "scopes:\n"
        "  demo:\n"
        "    allowed_paths:\n"
        "      - src/**\n"
        "      - tests/**\n"
        "      - scripts/**\n"
        "    forbidden_paths:\n"
        "      - forbidden/**\n",
        encoding="utf-8",
    )
    git(repo, "add", ".harness/owners.yaml")
    git(repo, "commit", "-m", "allow script candidates")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "bad_tool.py").write_text(
        "def main() -> int:\n"
        "    raise RuntimeError('boom')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )

    verify = run_harness(repo, "verify", TASK_ID)
    assert verify.returncode != 0
    tool_candidates = load_runtime_json(repo, "tool-candidates.json")
    assert tool_candidates["status"] == "fail"
    probe_failures = [
        item
        for item in tool_candidates["hard_failures"]
        if item["path"] == "scripts/bad_tool.py" and item["kind"] == "script_help_probe"
    ]
    assert probe_failures
    assert "Traceback (most recent call last):" in probe_failures[0]["message"]


def test_metric_evidence_reaches_semantic_reviewer(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['metric_evidence']['eval']['tool_call_rate'] == 0.5\n"
        "assert packet['test_interpretation']['metrics']['status'] == 'present'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['metrics_reviewed'],\n"
        "  'reason': 'metric evidence reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable metric reviewer")
    metrics_dir = repo / "artifact" / TASK_ID / "metrics"
    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r1",
                succeeded=True,
                event_count=4,
                tool_calls=2,
                tool_call_rate=0.5,
                skill_uses=1,
                skill_usage_rate=0.5,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:00:00Z",
        )
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["metrics_reviewed"]


def test_worktree_semantic_review_uses_canonical_metric_evidence(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "assert packet['metric_evidence']['eval']['tool_call_rate'] == 0.5\n"
        "assert packet['test_interpretation']['metrics']['status'] == 'present'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['canonical_metrics_reviewed'],\n"
        "  'reason': 'canonical metric evidence reviewed from worktree'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", "{repo_root}/.harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable canonical metric reviewer")
    enable_policy_and_remote(tmp_path, repo)
    metrics_dir = repo / "artifact" / TASK_ID / "metrics"
    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r1",
                succeeded=True,
                event_count=4,
                tool_calls=2,
                tool_call_rate=0.5,
                skill_uses=1,
                skill_usage_rate=0.5,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:00:00Z",
        )
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0
    writer = json.loads(
        run_harness(repo, "worktree", TASK_ID, "--writer", role="integrator").stdout
    )
    writer_path = Path(writer["path"])
    assert not (writer_path / "artifact" / TASK_ID / "metrics" / "eval.db").exists()
    (writer_path / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(writer_path, "verify", TASK_ID).returncode == 0

    waited = run_harness(writer_path, "submit", TASK_ID, "--wait")

    assert waited.returncode == 0, waited.stdout + waited.stderr
    result = json.loads(waited.stdout)
    assert result["status"] == "integrated"
    assert result["metrics"]["usage_observed"] is True
    assert result["metrics"]["tool_call_rate"] == 0.5
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["canonical_metrics_reviewed"]
    integration = load_runtime_json(repo, "integration-result.json")
    assert integration["metrics"]["usage_observed"] is True
    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    assert collected.returncode == 0, collected.stdout + collected.stderr
    summary = json.loads(collected.stdout)
    assert summary["review_pass"] is True
    assert summary["stale"] == []


def test_missing_quality_evidence_blocks_gate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    (runtime_task_dir(repo) / "quality-result.json").unlink()

    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "evidence_hash_mismatch"


def test_quality_evidence_stales_only_semantic_reviewer_and_recovers_minimally(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    enable_semantic_reviewer(repo)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr

    quality_path = runtime_task_dir(repo) / "quality-result.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    quality["review_flags"] = [{"kind": "manual_refresh", "path": "src/app.txt"}]
    quality["status"] = "review_required"
    quality_path.write_text(json.dumps(quality, sort_keys=True) + "\n", encoding="utf-8")

    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    summary = json.loads(collected.stdout)
    assert summary["fresh_approves"] == 2
    assert summary["stale"] == ["semantic-ai"]

    rerun = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    recovered = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    assert json.loads(recovered.stdout)["fresh_approves"] == 3


def test_metric_evidence_stales_only_semantic_reviewer_and_recovers_minimally(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "runs = packet['metric_evidence']['eval']['runs']\n"
        "assert packet['test_interpretation']['metrics']['status'] == 'present'\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['metrics_runs_' + str(runs)],\n"
        "  'reason': 'metric evidence reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable metric stale reviewer")
    metrics_dir = repo / "artifact" / TASK_ID / "metrics"
    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r1",
                succeeded=True,
                event_count=4,
                tool_calls=2,
                tool_call_rate=0.5,
                skill_uses=1,
                skill_usage_rate=0.5,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:00:00Z",
        )
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    assert load_runtime_json(repo, "reviews/semantic-ai.json")["labels"] == ["metrics_runs_1"]

    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r2",
                succeeded=True,
                event_count=6,
                tool_calls=4,
                tool_call_rate=0.67,
                skill_uses=2,
                skill_usage_rate=0.33,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:01:00Z",
        )
    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    summary = json.loads(collected.stdout)
    assert summary["fresh_approves"] == 2
    assert summary["stale"] == ["semantic-ai"]
    assert summary["review_pass"] is False

    rerun = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert load_runtime_json(repo, "reviews/semantic-ai.json")["labels"] == ["metrics_runs_2"]
    recovered = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    recovered_summary = json.loads(recovered.stdout)
    assert recovered_summary["fresh_approves"] == 3
    assert recovered_summary["review_pass"] is True


def test_metric_evidence_change_after_submit_requires_resubmit_before_dispatch(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "packet = json.loads(pathlib.Path(sys.argv[1]).read_text())\n"
        "runs = packet['metric_evidence']['eval']['runs']\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['submission_metrics_runs_' + str(runs)],\n"
        "  'reason': 'submission metric evidence reviewed'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable metric submit reviewer")
    metrics_dir = repo / "artifact" / TASK_ID / "metrics"
    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r1",
                succeeded=True,
                event_count=4,
                tool_calls=2,
                tool_call_rate=0.5,
                skill_uses=1,
                skill_usage_rate=0.5,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:00:00Z",
        )
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    first_submission = load_runtime_json(repo, "submission.json")

    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r2",
                succeeded=True,
                event_count=6,
                tool_calls=4,
                tool_call_rate=0.67,
                skill_uses=2,
                skill_usage_rate=0.33,
                unexpected_actions=[],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:01:00Z",
        )
    stale = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert stale.returncode != 0
    assert json.loads(stale.stdout)["reason"] == "stale_submission"
    assert load_runtime_json(repo, "integration-result.json")["reason"] == "stale_submission"

    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    second_submission = load_runtime_json(repo, "submission.json")
    assert second_submission["metric_evidence_sha256"] != first_submission["metric_evidence_sha256"]
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode == 0, dispatched.stdout + dispatched.stderr
    result = json.loads(dispatched.stdout)
    assert result["status"] == "integrated"
    semantic = load_runtime_json(repo, "reviews/semantic-ai.json")
    assert semantic["labels"] == ["submission_metrics_runs_2"]
    assert load_runtime_json(repo, "integration-result.json")["reason"] == "ok"


def test_semantic_ai_reviewer_not_invoked_until_machine_verification_passes(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path, verifier_command="python -c 'raise SystemExit(1)'")
    marker = repo / "semantic-called.txt"
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text('called')\n"
        'pathlib.Path(sys.argv[2]).write_text(\'{"verdict":"approve"}\')\n',
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable semantic reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode != 0

    result = run_harness(repo, "review", TASK_ID, "--run", "semantic-ai", role="reviewer")
    assert result.returncode == 0, result.stdout + result.stderr
    verdict = json.loads((runtime_task_dir(repo) / "reviews" / "semantic-ai.json").read_text())
    assert verdict["verdict"] == "block"
    assert verdict["reason"] == "machine verification failed before semantic review"
    assert not marker.exists()


def test_prepare_generated_acceptance_and_proposals_do_not_affect_semantics(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    first = run_harness(repo, "prepare", TASK_ID)
    assert first.returncode == 0, first.stdout + first.stderr
    before = load_runtime_json(repo, "contract.lock.json")["contract_semantic_sha256"]

    proposal = repo / ".harness" / "proposals" / "rfcs" / "x.json"
    proposal.parent.mkdir(parents=True)
    proposal.write_text('{"proposal": true}\n', encoding="utf-8")
    second = run_harness(repo, "prepare", TASK_ID)
    assert second.returncode == 0
    after = load_runtime_json(repo, "contract.lock.json")["contract_semantic_sha256"]
    assert after == before

    (repo / ".harness" / "tasks" / TASK_ID / "task.yaml").write_text(
        task_yaml("manual"),
        encoding="utf-8",
    )
    rejected = run_harness(repo, "prepare", TASK_ID)
    assert rejected.returncode != 0
    assert "acceptance.mode must be generated" in rejected.stdout


def test_verify_writes_candidate_and_machine_evidence_without_mutating_index(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "staged.txt").write_text("staged\n", encoding="utf-8")
    git(repo, "add", "src/staged.txt")
    before_index = git(repo, "diff", "--cached", "--name-only")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")

    result = run_harness(repo, "verify", TASK_ID)
    assert result.returncode == 0, result.stdout + result.stderr
    assert git(repo, "diff", "--cached", "--name-only") == before_index

    task_dir = runtime_task_dir(repo)
    assert (task_dir / "candidate.diff").is_file()
    verify_result = load_runtime_json(repo, "verify-result.json")
    assert verify_result["candidate_diff_sha256"] == file_hash(task_dir / "candidate.diff")
    assert verify_result["machine_evidence_sha256"] == recompute_machine_evidence(verify_result)


def test_verify_rejects_forbidden_and_contract_input_edits(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    run_harness(repo, "prepare", TASK_ID)
    (repo / ".harness" / "owners.yaml").write_text("scopes: {}\n", encoding="utf-8")
    result = run_harness(repo, "verify", TASK_ID)
    assert result.returncode != 0
    verify_result = load_runtime_json(repo, "verify-result.json")
    assert verify_result["scope"]["violation_count"] >= 1
    assert verify_result["contract"]["semantic_reproducible"] is False


def test_review_quorum_stale_malformed_and_gate_success(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo, "review", TASK_ID, "--run", "reader-correctness", role="reviewer"
        ).returncode
        == 0
    )
    assert (
        run_harness(repo, "review", TASK_ID, "--run", "reader-scope", role="reviewer").returncode
        == 0
    )
    verdict = json.loads((runtime_task_dir(repo) / "reviews" / "reader-scope.json").read_text())
    assert verdict["written_by"] == "harness"
    assert verdict["evidence_seen"]["candidate_diff_sha256"]

    (runtime_task_dir(repo) / "reviews" / "bad.json").write_text("{not json", encoding="utf-8")
    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    assert json.loads(collected.stdout)["review_pass"] is True

    before_head = git(repo, "rev-parse", "HEAD")
    gate = run_harness(
        repo,
        "gate",
        TASK_ID,
        role="integrator",
        extra_env={"FOUNDATION_GATE_TIER": "custom-gate"},
    )
    assert gate.returncode == 0, gate.stdout + gate.stderr
    gate_result = json.loads(gate.stdout)
    assert gate_result["mergeable"] is True
    assert gate_result["metrics"]["usage_observed"] is False
    assert gate_result["metrics"]["tool_call_rate"] == 0.0
    assert gate_result["metrics"]["skill_usage_rate"] == 0.0
    exposure = gate_result["metrics"]["packet_exposure"]
    assert exposure["status"] == "present"
    assert exposure["roles"]["writer"]["tool_count"] >= 6
    assert exposure["roles"]["writer"]["skill_count"] >= 3
    assert exposure["roles"]["reviewer"]["tool_count"] >= 2
    assert exposure["roles"]["integrator"]["tool_count"] >= 8
    assert (repo / "artifact" / TASK_ID / "tier" / "called.txt").read_text() == "custom"
    assert git(repo, "rev-parse", "HEAD") == before_head
    assert (repo / "artifact" / TASK_ID / "evidence").is_dir()

    (repo / "src" / "app.txt").write_text("new candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    stale = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    assert json.loads(stale.stdout)["fresh_approves"] == 0


def test_review_collect_ignores_structurally_valid_manual_verdicts(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    verify_result = load_runtime_json(repo, "verify-result.json")
    reviews = runtime_task_dir(repo) / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    for reviewer_id in ("reader-correctness", "reader-scope"):
        (reviews / f"{reviewer_id}.json").write_text(
            json.dumps(
                {
                    "task_id": TASK_ID,
                    "reviewer_id": reviewer_id,
                    "verdict": "approve",
                    "labels": [],
                    "reason": "manual verdict must not satisfy quorum",
                    "evidence_seen": {
                        "candidate_diff_sha256": verify_result["candidate_diff_sha256"],
                        "machine_evidence_sha256": verify_result["machine_evidence_sha256"],
                    },
                    "written_by": "manual",
                    "written_at": "2026-06-15T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    collected = run_harness(repo, "review", TASK_ID, "--collect", role="integrator")
    assert collected.returncode == 0, collected.stdout + collected.stderr
    summary = json.loads(collected.stdout)
    assert summary["fresh_approves"] == 0
    assert summary["review_pass"] is False


def test_gate_fails_if_auto_reviewer_changes_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    script = repo / ".harness" / "semantic_reviewer.py"
    script.write_text(
        "import json, pathlib, subprocess, sys\n"
        "pathlib.Path('src/reviewer-head.txt').write_text('mutated\\n')\n"
        "subprocess.run(['git', 'add', 'src/reviewer-head.txt'], check=True)\n"
        "subprocess.run(['git', 'commit', '-m', 'semantic reviewer mutated head'], check=True)\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps({\n"
        "  'verdict': 'approve',\n"
        "  'labels': ['semantic_ai'],\n"
        "  'reason': 'mutated head'\n"
        "}))\n",
        encoding="utf-8",
    )
    (repo / ".harness" / "review.yaml").write_text(
        semantic_review_yaml(command=["python", ".harness/semantic_reviewer.py"]),
        encoding="utf-8",
    )
    git(repo, "add", ".harness/review.yaml", ".harness/semantic_reviewer.py")
    git(repo, "commit", "-m", "enable mutating semantic reviewer")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0

    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "reviewer_head_changed"


def test_approve_cannot_override_failing_machine_gate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, verifier_command="python -c 'raise SystemExit(1)'")
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode != 0
    for reviewer in ("reader-correctness", "reader-scope"):
        assert (
            run_harness(
                repo,
                "review",
                TASK_ID,
                "--write-verdict",
                reviewer,
                "approve",
                role="reviewer",
            ).returncode
            == 0
        )
    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "machine_gate_failed"


def test_fresh_block_veto_rejects_gate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-correctness",
            "approve",
            role="reviewer",
        ).returncode
        == 0
    )
    assert (
        run_harness(
            repo,
            "review",
            TASK_ID,
            "--write-verdict",
            "reader-scope",
            "block",
            "--label",
            "scope_risk",
            role="reviewer",
        ).returncode
        == 0
    )

    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    assert gate.returncode != 0
    assert json.loads(gate.stdout)["reason"] == "review_blocked"


def test_metrics_unexpected_actions_policy_rejects_gate(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, reject_unexpected=True)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    metrics_dir = repo / "artifact" / TASK_ID / "metrics"
    with MetricsStore(metrics_dir / "eval.db") as store:
        store.record_run(
            EvalScore(
                run_id="r1",
                succeeded=True,
                event_count=4,
                tool_calls=2,
                tool_call_rate=0.5,
                skill_uses=1,
                skill_usage_rate=0.5,
                unexpected_actions=["unexpected tool: WebFetch"],
            ),
            raw_trajectory="{}",
            created_at="2026-06-15T00:00:00Z",
        )
    gate = run_harness(repo, "gate", TASK_ID, role="integrator")
    data = json.loads(gate.stdout)
    assert gate.returncode != 0
    assert data["reason"] == "unexpected_actions"
    assert data["metrics"]["tool_call_rate"] == 0.5
    assert data["metrics"]["skill_usage_rate"] == 0.5


def test_provider_neutral_import_surface() -> None:
    forbidden = ("openai", "anthropic", "mcp")
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "workflow_core" / "contract_harness").glob("*.py")
    )
    assert not any(token in text.lower() for token in forbidden)
