from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.hashing import file_hash
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


def task_yaml(mode: str) -> str:
    return (
        f"id: {TASK_ID}\n"
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


def runtime_task_dir(repo: Path) -> Path:
    common = Path(git(repo, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "tasks" / TASK_ID


def runtime_root(repo: Path) -> Path:
    return runtime_task_dir(repo).parents[2]


def load_runtime_json(repo: Path, name: str) -> dict[str, Any]:
    data = json.loads((runtime_task_dir(repo) / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def tool_names(tools: list[dict[str, Any]]) -> set[str]:
    return {str(tool.get("name")) for tool in tools}


def skill_names(skills: list[dict[str, Any]]) -> set[str]:
    return {str(skill.get("name")) for skill in skills}


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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
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


def test_prepare_capsule_exposes_existing_agent_tool_set(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    prepared = run_harness(repo, "prepare", TASK_ID)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    capsule = load_runtime_json(repo, "capsule.json")
    names = tool_names(capsule["agent_tools"])
    skills = skill_names(capsule["agent_skills"])

    assert {
        "scope-map-forward",
        "verify",
        "submit",
        "report-rfc",
        "nfr-metric",
        "bench-compare",
        "abrun",
        "check-runner",
        "verdict",
        "quality-gate",
        "measure-eval",
        "surface-issues",
    }.issubset(names)
    assert {
        "tdd-scope",
        "implementation-slice-verification",
        "scope-routing-governance",
    }.issubset(skills)
    assert all(not str(tool["command"]).startswith("./harness") for tool in capsule["agent_tools"])
    assert any("nfr_metric.py" in tool["command"] for tool in capsule["agent_tools"])
    scope_tool = tool_by_name(capsule["agent_tools"], "scope-map-forward")
    smoke = run_tool_command(scope_tool["command"], repo / ".harness")
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    groups = load_runtime_json(repo, "agent-tools.json")
    assert "scope-map-reverse" in tool_names(groups["reviewer"])
    assert "affected" in tool_names(groups["integrator"])
    skill_groups = load_runtime_json(repo, "agent-skills.json")
    assert "release-check" in skill_names(skill_groups["reviewer"])
    assert "merge-integrity-governance" in skill_names(skill_groups["integrator"])


def test_explain_lists_agent_tools(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    assert run_harness(repo, "prepare", TASK_ID).returncode == 0

    explained = run_harness(repo, "explain", TASK_ID)
    assert explained.returncode == 0, explained.stdout + explained.stderr
    assert "writer tools:" in explained.stdout
    assert "writer skills:" in explained.stdout
    assert "scope-map-forward" in explained.stdout
    assert "nfr-metric" in explained.stdout
    assert "tdd-scope" in explained.stdout


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


def test_e2e_integrator_dispatch_then_land_keeps_integrator_worktree_reusable(
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


def test_integrator_failure_writes_rework_packet(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, make_exit=1)
    (repo / "src" / "app.txt").write_text("candidate\n", encoding="utf-8")
    assert run_harness(repo, "verify", TASK_ID).returncode == 0
    assert run_harness(repo, "submit", TASK_ID).returncode == 0
    dispatched = run_harness(repo, "dispatch", TASK_ID, role="integrator")
    assert dispatched.returncode != 0
    result = load_runtime_json(repo, "integration-result.json")
    assert result["status"] == "rework_required"
    assert result["reason"] == "machine_gate_failed"


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
    assert packet["test_interpretation"]["required_verifiers_passed"] is True


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
    assert any(item["kind"] == "script_help_probe" for item in tool_candidates["hard_failures"])


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
    assert gate_result["metrics"]["tool_call_rate"] == 0.0
    assert gate_result["metrics"]["skill_usage_rate"] == 0.0
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
