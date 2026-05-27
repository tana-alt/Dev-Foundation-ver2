import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_DOCS = (
    "AGENTS.md",
    "docs/01-agent-operating-contract.md",
    "docs/02-output-verification-contract.md",
    "docs/03-repo-boundary-and-storage-contract.md",
)

REFERENCE_DOCS = (
    "docs/reference/agent-runtime-and-scope-reference.md",
    "docs/reference/git-worktree-and-branch-reference.md",
    "docs/reference/migration-and-acceptance-reference.md",
    "docs/reference/packet-evidence-and-rework-reference.md",
    "docs/reference/repo-boundary-and-storage-reference.md",
    "docs/reference/verification-ci-and-pr-reference.md",
)

TEMPLATES = (
    "templates/work-contract.yaml",
    "templates/evidence-record.yaml",
    "templates/verification-record.yaml",
    "templates/rework-record.yaml",
    "templates/project-storage-map.yaml",
    "templates/serena-project.yml",
    "templates/codex-config.toml.example",
)

ROOT_READMES = (
    "Plan/README.md",
    "artifact/README.md",
    "templates/README.md",
    "src/README.md",
)

DEV_DEFAULTS = (
    ".python-version",
    ".editorconfig",
    ".gitattributes",
    ".gitleaks.toml",
)

HOOKS = (
    "hooks/pre-commit",
    "hooks/pre-push",
)

RESTORE_SCRIPTS = (
    "scripts/setup-agent-environment.sh",
    "scripts/check-agent-worktree-policy.sh",
    "scripts/check-dev-environment.sh",
    "scripts/check-repo-hygiene.sh",
    "scripts/check-secrets.sh",
    "scripts/check-shell-static-analysis.sh",
)

DEPLOYMENT_CONFIGS = (
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "fly.toml",
    "netlify.toml",
    "render.yaml",
    "vercel.json",
)

DEPLOYMENT_WORKFLOW_KEYWORDS = (
    "deploy",
    "deployment",
    "publish",
    "release",
)

EXPECTED_TRACKED_TOP_LEVELS = {
    ".agents",
    ".editorconfig",
    ".gitattributes",
    ".gitleaks.toml",
    ".github",
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "Makefile",
    "Plan",
    "README.md",
    "app",
    "artifact",
    "docs",
    "hooks",
    "plugins",
    "pyproject.toml",
    "scripts",
    "src",
    "templates",
    "tests",
    "uv.lock",
}

FORBIDDEN_TRACKED_ROOTS = {
    ".serena",
    "archive",
    "agent_docs_rebuild_scope_ref",
    "Foundation-development",
    "packets",
    "project-orchestration",
    "runtime",
    "source-docs",
}

PLAN_ID_RE = re.compile(r"^Plan_N\d{4}$")

PROJECT_SCOPED_ROOT_DIRECT_FILES = {
    "Plan": {"README.md"},
    "artifact": {"README.md", ".gitkeep"},
    "src": {"README.md", ".gitkeep"},
}

ARTIFACT_PROJECT_DIRS = {"evidence", "verification", "output"}


def repo_path(relative_path: str) -> Path:
    return ROOT / relative_path


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def read_text(relative_path: str) -> str:
    return repo_path(relative_path).read_text(encoding="utf-8")


def make_target_dependencies(makefile: str, target: str) -> list[str]:
    match = re.search(rf"^{re.escape(target)}:([^\n]*)$", makefile, re.MULTILINE)
    assert match is not None, target
    return match.group(1).split()


def make_target_recipe(makefile: str, target: str) -> list[str]:
    lines = makefile.splitlines()

    for index, line in enumerate(lines):
        if not re.match(rf"^{re.escape(target)}:", line):
            continue

        recipe: list[str] = []
        for following_line in lines[index + 1 :]:
            if following_line.startswith("\t"):
                recipe.append(following_line.strip())
                continue
            if following_line.strip() == "":
                continue
            break

        return recipe

    raise AssertionError(target)


def pytest_ini_options() -> dict[str, Any]:
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    tool = cast(dict[str, Any], pyproject["tool"])
    pytest_config = cast(dict[str, Any], tool["pytest"])
    return cast(dict[str, Any], pytest_config["ini_options"])


def line_count(relative_path: str) -> int:
    return len(read_text(relative_path).splitlines())


def test_active_agent_context_stays_under_budget() -> None:
    total_lines = sum(line_count(path) for path in ACTIVE_DOCS)
    assert total_lines <= 200


def test_agents_routes_to_active_docs_and_references() -> None:
    agents = read_text("AGENTS.md")

    for relative_path in (*ACTIVE_DOCS[1:], *REFERENCE_DOCS):
        assert f"`{relative_path}`" in agents

    assert "Root Boundary" not in agents


def test_agents_routes_project_scoped_work_to_reference_docs() -> None:
    agents = read_text("AGENTS.md")

    assert "project-scoped Plan/artifact/src placement" in agents
    assert "`docs/reference/repo-boundary-and-storage-reference.md`" in agents
    assert "project-scoped worktree setup" in agents
    assert "`docs/reference/git-worktree-and-branch-reference.md`" in agents
    assert "`project-worktree-scope`" not in agents
    assert "`project-storage-placement`" not in agents


def test_reference_set_matches_routed_reference_docs() -> None:
    actual = sorted(path.name for path in repo_path("docs/reference").glob("*.md"))
    expected = sorted(Path(path).name for path in REFERENCE_DOCS)
    assert actual == expected


def test_required_contract_files_exist() -> None:
    required = (
        *ACTIVE_DOCS,
        *REFERENCE_DOCS,
        *TEMPLATES,
        *ROOT_READMES,
        *DEV_DEFAULTS,
        *HOOKS,
        *RESTORE_SCRIPTS,
    )

    for relative_path in required:
        assert repo_path(relative_path).is_file(), relative_path


def test_docs_root_stays_contract_only() -> None:
    direct_docs = sorted(
        path
        for path in tracked_files()
        if path.startswith("docs/") and Path(path).parent == Path("docs") and path.endswith(".md")
    )

    assert direct_docs == sorted(ACTIVE_DOCS[1:])


def test_project_storage_routes_are_documented() -> None:
    reference = read_text("docs/reference/repo-boundary-and-storage-reference.md")

    for relative_path in ROOT_READMES:
        assert f"`{relative_path}`" in reference

    for required_text in (
        "Plan/<project_id>/index.yaml",
        "Plan/<project_id>/plans/Plan_N0001.md",
        "Plan/<project_id>/logs/Plan_N0001.log.md",
        "artifact/<project_id>/manifest.yaml",
        "src/<project_id>/",
        "`project_id`",
    ):
        assert required_text in reference


def test_project_plan_artifact_and_source_rules_are_project_scoped() -> None:
    plan_readme = read_text("Plan/README.md")
    artifact_readme = read_text("artifact/README.md")
    templates_readme = read_text("templates/README.md")
    src_readme = read_text("src/README.md")
    git_reference = read_text("docs/reference/git-worktree-and-branch-reference.md")

    for required_text in (
        "Plan/<project_id>/",
        "Plan_N0001.md",
        "Plan_N0001.log.md",
        "`plan_id`",
        "`index.yaml`",
    ):
        assert required_text in plan_readme

    assert "artifact/<project_id>/" in artifact_readme
    assert "manifest.yaml" in artifact_readme
    assert "<project_id>" in templates_readme
    assert "src/<project_id>/" in src_readme
    assert "project_id" in git_reference
    assert "do not share a\nworktree across project IDs" in git_reference


def test_project_scoped_roots_do_not_accept_loose_files() -> None:
    tracked = tracked_files()

    for root, allowed_direct_files in PROJECT_SCOPED_ROOT_DIRECT_FILES.items():
        for path in tracked:
            if not path.startswith(f"{root}/"):
                continue

            relative = Path(path).relative_to(root)
            parts = relative.parts
            assert parts, path

            if len(parts) == 1:
                assert parts[0] in allowed_direct_files, path
                continue

            project_id = parts[0]
            assert project_id not in {"active", "completed", "logs", "plans", "output"}, path
            assert project_id not in allowed_direct_files, path
            assert project_id.strip(), path


def test_plan_project_records_keep_plan_id_log_and_index_in_sync() -> None:
    tracked = set(tracked_files())
    plan_files = [
        path
        for path in tracked
        if path.startswith("Plan/") and "/plans/" in path and path.endswith(".md")
    ]
    log_files = [
        path
        for path in tracked
        if path.startswith("Plan/") and "/logs/" in path and path.endswith(".log.md")
    ]

    for path in plan_files:
        parts = Path(path).parts
        assert len(parts) == 4, path
        _, project_id, plans_dir, filename = parts
        assert plans_dir == "plans", path
        plan_id = filename.removesuffix(".md")
        assert PLAN_ID_RE.match(plan_id), path
        assert f"Plan/{project_id}/index.yaml" in tracked, path
        assert f"Plan/{project_id}/logs/{plan_id}.log.md" in tracked, path

    for path in log_files:
        parts = Path(path).parts
        assert len(parts) == 4, path
        _, project_id, logs_dir, filename = parts
        assert logs_dir == "logs", path
        plan_id = filename.removesuffix(".log.md")
        assert PLAN_ID_RE.match(plan_id), path
        assert f"Plan/{project_id}/index.yaml" in tracked, path
        assert f"Plan/{project_id}/plans/{plan_id}.md" in tracked, path


def test_artifact_project_records_have_manifest_and_allowed_sections() -> None:
    tracked = set(tracked_files())

    for path in tracked:
        if not path.startswith("artifact/") or path in {"artifact/README.md", "artifact/.gitkeep"}:
            continue

        parts = Path(path).parts
        assert len(parts) >= 3, path
        _, project_id, section = parts[:3]
        assert f"artifact/{project_id}/manifest.yaml" in tracked, path
        if len(parts) == 3:
            assert section == "manifest.yaml", path
        else:
            assert section in ARTIFACT_PROJECT_DIRS, path


def test_source_project_records_are_project_scoped() -> None:
    for path in tracked_files():
        if not path.startswith("src/") or path in {"src/README.md", "src/.gitkeep"}:
            continue

        parts = Path(path).parts
        assert len(parts) >= 3, path
        assert parts[1].strip(), path
        assert parts[1] not in {"shared", "common", "logs", "notes", "artifacts"}, path


def test_project_storage_template_uses_external_placeholder() -> None:
    storage_template = read_text("templates/project-storage-map.yaml")

    assert "projects/example_project" not in storage_template
    assert "obsidian-vault/Apps/example_project" not in storage_template
    assert "example_project" not in storage_template
    assert "<project-id>" in storage_template
    assert "<external-project-root>" in storage_template
    assert "<external-overlay-root>" in storage_template
    assert "Do not create a default projects/ root inside this repository" in storage_template


def test_removed_runtime_surfaces_are_not_current_roots() -> None:
    inactive_roots = (
        ".claude",
        "packets",
        "project-orchestration",
        "runtime",
        "source-docs",
    )

    for relative_path in inactive_roots:
        assert not repo_path(relative_path).exists(), relative_path

    assert repo_path(".agents/plugins/marketplace.json").is_file()

    gitignore = read_text(".gitignore")
    assert "archive/" in gitignore
    assert ".serena/" in gitignore


def test_tracked_top_level_roots_stay_explicit() -> None:
    top_level_roots = {path.split("/", 1)[0] for path in tracked_files()}

    assert top_level_roots <= EXPECTED_TRACKED_TOP_LEVELS
    assert not top_level_roots & FORBIDDEN_TRACKED_ROOTS


def test_agent_environment_restore_uses_templates_not_runtime_state() -> None:
    readme = read_text("README.md")
    setup_script = read_text("scripts/setup-agent-environment.sh")
    codex_template = read_text("templates/codex-config.toml.example")

    assert "scripts/setup-agent-environment.sh" in readme
    assert "make doctor" in readme
    assert "make check-foundation" in readme
    assert "templates/serena-project.yml" in setup_script
    assert "templates/codex-config.toml.example" in setup_script
    assert ".serena/project.yml" in setup_script
    assert "core.hooksPath" in setup_script
    assert "foundation.canonicalRoot" in setup_script
    assert "web_dashboard_open_on_launch" in setup_script
    assert "@upstash/context7-mcp@2.2.5" in setup_script
    assert "@upstash/context7-mcp@2.2.5" in codex_template
    assert "auth.json" not in codex_template


def test_lightweight_dev_defaults_are_declared() -> None:
    python_version = read_text(".python-version").strip()
    pyproject = read_text("pyproject.toml")
    editorconfig = read_text(".editorconfig")
    gitattributes = read_text(".gitattributes")
    gitleaks_config = read_text(".gitleaks.toml")
    workflow = read_text(".github/workflows/ci.yml")

    assert python_version == "3.12"
    assert 'requires-python = ">=3.12,<3.15"' in pyproject
    assert 'python_version = "3.12"' in pyproject
    assert "root = true" in editorconfig
    assert "end_of_line = lf" in editorconfig
    assert "insert_final_newline = true" in editorconfig
    assert "* text=auto eol=lf" in gitattributes
    assert "useDefault = true" in gitleaks_config
    assert "sanitized Figma example file keys" in gitleaks_config
    assert 'python-version-file: ".python-version"' in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    assert 'version: "0.11.4"' in workflow
    assert 'GITLEAKS_VERSION: "8.30.1"' in workflow
    assert "sha256sum -c" in workflow
    assert "uv sync --frozen --group dev" in workflow
    assert "make check-foundation" in workflow


def test_tracked_hooks_enforce_agent_policy_and_checks() -> None:
    pre_commit = read_text("hooks/pre-commit")
    pre_push = read_text("hooks/pre-push")
    worktree_policy = read_text("scripts/check-agent-worktree-policy.sh")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")

    for relative_path in (*HOOKS, "scripts/check-agent-worktree-policy.sh"):
        assert repo_path(relative_path).stat().st_mode & 0o111, relative_path

    assert "scripts/check-agent-worktree-policy.sh" in pre_commit
    assert "scripts/check-agent-worktree-policy.sh" in pre_push
    assert "check-push" in pre_push
    assert 'make "$CHECK_TARGET"' in pre_push

    for required_text in (
        "agent/<work_id>/<lane>/<slug>",
        "FOUNDATION_PROJECT_ID",
        "FOUNDATION_REQUIRE_AGENT_WORKTREE",
        "foundation.requireAgentWorktree",
        "foundation.canonicalRoot",
        "main",
        "canonical repo root",
        "replace 'none'",
    ):
        assert required_text in worktree_policy

    assert "core.hooksPath=hooks" in verification_reference


def init_git_repo(path: Path, branch: str, canonical_root: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", branch],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "foundation.canonicalRoot", str(canonical_root)],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def run_worktree_policy(
    repo: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env is not None:
        env.update(extra_env)

    return subprocess.run(
        ["sh", str(repo_path("scripts/check-agent-worktree-policy.sh"))],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def run_pre_push_hook(repo: Path, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(repo_path("hooks/pre-push")), "origin", "git@example.invalid:repo.git"],
        cwd=repo,
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
    )


def test_worktree_policy_behavior(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical"

    init_git_repo(canonical_root, "main", canonical_root)
    main_result = run_worktree_policy(canonical_root)
    assert main_result.returncode == 2
    assert "direct writes on main are blocked" in main_result.stderr

    feature_repo = tmp_path / "feature"
    init_git_repo(feature_repo, "feature/test", canonical_root)
    feature_result = run_worktree_policy(feature_repo)
    assert feature_result.returncode == 2
    assert "use agent/<work_id>/<lane>/<slug>" in feature_result.stderr

    malformed_agent_repo = tmp_path / "malformed-agent"
    init_git_repo(malformed_agent_repo, "agent/work-only", canonical_root)
    malformed_result = run_worktree_policy(malformed_agent_repo)
    assert malformed_result.returncode == 2
    assert "use agent/<work_id>/<lane>/<slug>" in malformed_result.stderr

    unset_agent_repo = tmp_path / "unset-agent"
    init_git_repo(unset_agent_repo, "agent/none/none/none", canonical_root)
    unset_agent_result = run_worktree_policy(unset_agent_repo)
    assert unset_agent_result.returncode == 2
    assert "replace 'none'" in unset_agent_result.stderr

    canonical_agent_repo = tmp_path / "canonical-agent"
    init_git_repo(canonical_agent_repo, "agent/work/lane/slug", canonical_agent_repo)
    canonical_agent_result = run_worktree_policy(canonical_agent_repo)
    assert canonical_agent_result.returncode == 0
    assert "agent worktree policy: passed" in canonical_agent_result.stdout

    parallel_canonical_result = run_worktree_policy(
        canonical_agent_repo,
        {"FOUNDATION_REQUIRE_AGENT_WORKTREE": "1"},
    )
    assert parallel_canonical_result.returncode == 2
    assert "requires an external worktree" in parallel_canonical_result.stderr

    configured_parallel_repo = tmp_path / "configured-parallel"
    init_git_repo(configured_parallel_repo, "agent/work/lane/slug", configured_parallel_repo)
    subprocess.run(
        ["git", "config", "foundation.requireAgentWorktree", "true"],
        cwd=configured_parallel_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    configured_parallel_result = run_worktree_policy(configured_parallel_repo)
    assert configured_parallel_result.returncode == 2
    assert "requires an external worktree" in configured_parallel_result.stderr

    external_agent_repo = tmp_path / "external-agent"
    init_git_repo(external_agent_repo, "agent/foundation-work/lane/slug", canonical_root)
    external_result = run_worktree_policy(external_agent_repo)
    assert external_result.returncode == 0
    assert "agent worktree policy: passed" in external_result.stdout

    mismatched_project_repo = tmp_path / "other-project-worktree"
    init_git_repo(mismatched_project_repo, "agent/other-work/lane/slug", canonical_root)
    mismatched_result = run_worktree_policy(
        mismatched_project_repo,
        {"FOUNDATION_PROJECT_ID": "foundation"},
    )
    assert mismatched_result.returncode == 2
    assert "must include FOUNDATION_PROJECT_ID" in mismatched_result.stderr

    matched_project_repo = tmp_path / "foundation-project-worktree"
    init_git_repo(matched_project_repo, "agent/foundation-work/lane/slug", canonical_root)
    matched_result = run_worktree_policy(
        matched_project_repo,
        {"FOUNDATION_PROJECT_ID": "foundation"},
    )
    assert matched_result.returncode == 0
    assert "agent worktree policy: passed" in matched_result.stdout


def test_pre_push_blocks_protected_remote_destination_refs(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical"
    init_git_repo(canonical_root, "main", canonical_root)

    external_agent_repo = tmp_path / "external-agent"
    init_git_repo(external_agent_repo, "agent/work/lane/slug", canonical_root)

    for remote_ref in ("refs/heads/main", "refs/heads/master"):
        result = run_pre_push_hook(
            external_agent_repo,
            f"refs/heads/agent/work/lane/slug local-sha {remote_ref} remote-sha\n",
        )

        assert result.returncode == 2
        assert f"direct push to {remote_ref} is blocked" in result.stderr


def init_hygiene_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def git_add(repo: Path, *paths: str) -> None:
    subprocess.run(
        ["git", "add", *paths],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def run_hygiene_check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(repo_path("scripts/check-repo-hygiene.sh"))],
        cwd=repo,
        env={**os.environ, "FOUNDATION_REPO_ROOT": str(repo)},
        check=False,
        capture_output=True,
        text=True,
    )


def test_repo_hygiene_behavior(tmp_path: Path) -> None:
    clean_repo = tmp_path / "clean"
    init_hygiene_repo(clean_repo)
    clean_result = run_hygiene_check(clean_repo)
    assert clean_result.returncode == 0
    assert "repo hygiene: passed" in clean_result.stdout

    ignored_repo = tmp_path / "ignored"
    init_hygiene_repo(ignored_repo)
    (ignored_repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (ignored_repo / "ignored.txt").write_text("tracked but ignored\n", encoding="utf-8")
    git_add(ignored_repo, ".gitignore")
    subprocess.run(
        ["git", "add", "-f", "ignored.txt"],
        cwd=ignored_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    ignored_result = run_hygiene_check(ignored_repo)
    assert ignored_result.returncode == 1
    assert "tracked ignored files:" in ignored_result.stderr
    assert "ignored.txt" in ignored_result.stderr

    forbidden_repo = tmp_path / "forbidden"
    init_hygiene_repo(forbidden_repo)
    forbidden_file = forbidden_repo / "runtime" / "state.txt"
    forbidden_file.parent.mkdir()
    forbidden_file.write_text("local state\n", encoding="utf-8")
    git_add(forbidden_repo, "runtime/state.txt")
    forbidden_result = run_hygiene_check(forbidden_repo)
    assert forbidden_result.returncode == 1
    assert "tracked forbidden local or past-source refs:" in forbidden_result.stderr
    assert "runtime/state.txt" in forbidden_result.stderr

    nested_repo = tmp_path / "nested"
    init_hygiene_repo(nested_repo)
    (nested_repo / "nested" / ".git").mkdir(parents=True)
    nested_result = run_hygiene_check(nested_repo)
    assert nested_result.returncode == 1
    assert "unignored nested git dirs:" in nested_result.stderr
    assert "nested/.git" in nested_result.stderr

    sensitive_name_repo = tmp_path / "sensitive-name"
    init_hygiene_repo(sensitive_name_repo)
    (sensitive_name_repo / "auth.json").write_text("{}\n", encoding="utf-8")
    git_add(sensitive_name_repo, "auth.json")
    sensitive_name_result = run_hygiene_check(sensitive_name_repo)
    assert sensitive_name_result.returncode == 1
    assert "tracked sensitive-name refs:" in sensitive_name_result.stderr
    assert "auth.json" in sensitive_name_result.stderr

    sensitive_space_repo = tmp_path / "sensitive-space-name"
    init_hygiene_repo(sensitive_space_repo)
    sensitive_space_file = sensitive_space_repo / "secret dir" / "auth.json"
    sensitive_space_file.parent.mkdir()
    sensitive_space_file.write_text("{}\n", encoding="utf-8")
    git_add(sensitive_space_repo, "secret dir/auth.json")
    sensitive_space_result = run_hygiene_check(sensitive_space_repo)
    assert sensitive_space_result.returncode == 1
    assert "secret dir/auth.json" in sensitive_space_result.stderr


def test_secret_scan_covers_worktree_and_cached_content_without_head(tmp_path: Path) -> None:
    repo = tmp_path / "secret-scan"
    init_hygiene_repo(repo)
    (repo / ".gitleaks.toml").write_text('title = "test"\n', encoding="utf-8")
    (repo / "tracked.txt").write_text("cached marker\n", encoding="utf-8")
    git_add(repo, ".gitleaks.toml", "tracked.txt")
    (repo / "tracked.txt").write_text("worktree-only marker\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gitleaks = fake_bin / "gitleaks"
    fake_gitleaks.write_text(
        """#!/usr/bin/env sh
set -eu
cat >> "$GITLEAKS_CAPTURE"
""",
        encoding="utf-8",
    )
    fake_gitleaks.chmod(0o755)
    capture = tmp_path / "gitleaks-stdin.txt"

    result = subprocess.run(
        ["sh", str(repo_path("scripts/check-secrets.sh"))],
        cwd=repo,
        env={
            **os.environ,
            "FOUNDATION_REPO_ROOT": str(repo),
            "GITLEAKS_CAPTURE": str(capture),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    scanned = capture.read_text(encoding="utf-8")
    assert "worktree-only marker" in scanned
    assert "cached marker" in scanned
    assert "secret scan: skipped git history scan (no commits yet)" in result.stdout


def test_dev_environment_and_hygiene_checks_are_wired() -> None:
    makefile = read_text("Makefile")
    dev_check = read_text("scripts/check-dev-environment.sh")
    hygiene_check = read_text("scripts/check-repo-hygiene.sh")
    secret_check = read_text("scripts/check-secrets.sh")
    shell_check = read_text("scripts/check-shell-static-analysis.sh")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")
    workflow = read_text(".github/workflows/ci.yml")

    for relative_path in (
        "scripts/check-dev-environment.sh",
        "scripts/check-repo-hygiene.sh",
        "scripts/check-secrets.sh",
        "scripts/check-shell-static-analysis.sh",
    ):
        assert repo_path(relative_path).stat().st_mode & 0o111, relative_path

    assert "doctor:" in makefile
    assert "format-check:" in makefile
    assert "check-toolchain:" in makefile
    assert "test-fast:" in makefile
    assert "check-fast:" in makefile
    assert "check-push:" in makefile
    assert "check-ci:" in makefile
    assert "check-hygiene:" in makefile
    assert "check-shell:" in makefile
    assert "check-secrets:" in makefile
    assert make_target_dependencies(makefile, "check-required") == [
        "format-check",
        "lint",
        "typecheck",
        "check-hooks",
        "check-shell",
        "check-hygiene",
        "check-secrets",
        "test",
    ]
    assert "check-shell check-hygiene check-secrets test" in makefile
    assert "core.hooksPath" in dev_check
    assert "foundation.canonicalRoot" in dev_check
    assert "command -v shellcheck" in dev_check
    assert "command -v gitleaks" in dev_check
    assert "git --version" in dev_check
    assert "uv --version" in dev_check
    assert "shellcheck --version" in dev_check
    assert "gitleaks version" in dev_check
    assert "tracked ignored files" in hygiene_check
    assert "tracked forbidden local or past-source refs" in hygiene_check
    assert "tracked sensitive-name refs" in hygiene_check
    assert "credentials|secrets" in hygiene_check
    assert "auth\\.json" in hygiene_check
    assert "gitlinks without .gitmodules" in hygiene_check
    assert "shellcheck -s sh" in shell_check
    assert "FOUNDATION_REPO_ROOT" in secret_check
    assert 'git -C "$ROOT" grep -I -n -e . -- .' in secret_check
    assert 'git -C "$ROOT" grep --cached -I -n -e . -- .' in secret_check
    assert 'gitleaks --config "$ROOT/.gitleaks.toml" --redact --no-banner' in secret_check
    assert 'gitleaks git --config "$ROOT/.gitleaks.toml" --redact' in secret_check
    assert "Install OSS check tools" in workflow
    assert "runs-on: ubuntu-24.04" in workflow
    assert "apt-get install -y shellcheck" in workflow
    assert 'GITLEAKS_VERSION: "8.30.1"' in workflow
    assert "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" in workflow
    assert "gitleaks_${GITLEAKS_VERSION}_checksums.txt" in workflow
    assert "sha256sum -c" in workflow
    assert "make doctor" in verification_reference
    assert "make check-hygiene" in verification_reference
    assert "make check-shell" in verification_reference
    assert "make check-secrets" in verification_reference


def test_pytest_collection_is_aggregate_foundation_gate() -> None:
    makefile = read_text("Makefile")
    workflow = read_text(".github/workflows/ci.yml")
    testpaths = cast(list[str], pytest_ini_options()["testpaths"])

    assert testpaths == ["tests"]
    assert make_target_recipe(makefile, "test") == ["$(UV) run pytest"]
    expected_test_fast = (
        "$(UV) run pytest -q tests/test_contract_models.py "
        "tests/test_extension_surface_integrity.py"
    )
    assert make_target_recipe(makefile, "test-fast") == [expected_test_fast]
    assert "test" in make_target_dependencies(makefile, "check-required")
    assert "check-required" in make_target_dependencies(makefile, "check-ci")
    assert "check-ci" in make_target_dependencies(makefile, "check-foundation")
    assert re.search(r"^\s*run:\s*make check-foundation\s*$", workflow, re.MULTILINE)


def test_verification_reference_documents_pytest_aggregate_gate() -> None:
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")

    for required_text in (
        "`make test`: aggregate gate",
        "`tests/test_*.py`",
        "`make check-contracts`, `make check-doc-consistency`, and `make check-cd`",
        "targeted shortcuts",
        "`make check-foundation`",
        "`make check-required`",
        "`make test-fast`",
        "`make check-fast`",
        "`make check-push`",
        "`make check-ci`",
        "Fast And Full Gate Mapping",
        "not automatic test classification",
        "local edit loop",
        "PR handoff or high-risk change",
        "curated fast pytest smoke set",
    ):
        assert required_text in verification_reference


def test_skill_roots_are_explicit() -> None:
    skill_root = repo_path(".agents/skills")
    live_skills = sorted(path for path in skill_root.iterdir() if path.is_dir())

    assert live_skills

    for skill_path in live_skills:
        assert (skill_path / "SKILL.md").is_file(), skill_path


def test_cd_readiness_is_guarded_until_deployment_exists() -> None:
    workflow = read_text(".github/workflows/ci.yml")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")
    workflow_files = [
        *repo_path(".github/workflows").glob("*.yml"),
        *repo_path(".github/workflows").glob("*.yaml"),
    ]

    for relative_path in DEPLOYMENT_CONFIGS:
        assert not repo_path(relative_path).exists(), relative_path

    deploy_workflows = [
        path
        for path in workflow_files
        if any(keyword in path.stem.lower() for keyword in DEPLOYMENT_WORKFLOW_KEYWORDS)
    ]
    assert deploy_workflows == []

    deployment_workflow_content = {
        path: [
            line
            for line in path.read_text(encoding="utf-8").lower().splitlines()
            if "gitleaks/releases/download" not in line
        ]
        for path in workflow_files
    }
    workflows_with_deploy_steps = [
        path
        for path, lines in deployment_workflow_content.items()
        if any(keyword in line for line in lines for keyword in DEPLOYMENT_WORKFLOW_KEYWORDS)
    ]
    assert workflows_with_deploy_steps == []

    assert "make check-foundation" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "timeout-minutes: 10" in workflow
    assert "make check-foundation" in verification_reference
    assert "not_applicable" in verification_reference


def test_doc_consistency_uses_canonical_result_states() -> None:
    output_contract = read_text("docs/02-output-verification-contract.md")
    packet_reference = read_text("docs/reference/packet-evidence-and-rework-reference.md")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")
    verification_template = read_text("templates/verification-record.yaml")

    for text in (
        output_contract,
        packet_reference,
        verification_reference,
        verification_template,
    ):
        assert "not_applicable" in text

    assert "not applicable" not in output_contract


def test_doc_consistency_routes_canonical_output_and_human_gates() -> None:
    operating_contract = read_text("docs/01-agent-operating-contract.md")
    output_contract = read_text("docs/02-output-verification-contract.md")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")
    normalized_output = " ".join(output_contract.split())
    normalized_verification = " ".join(verification_reference.split())

    assert "`docs/02-output-verification-contract.md`" in operating_contract
    assert "canonical human-gate list" in operating_contract

    for phrase in (
        "external write outside the owned review branch or PR",
        "branch/worktree deletion",
        "irreversible/protected action",
    ):
        assert phrase in normalized_output
        assert phrase in normalized_verification

    assert "create or update PRs" in normalized_output
    assert "Direct pushes to `main` or `master` are prohibited" in normalized_verification


def test_work_contract_git_scope_matches_parallel_policy() -> None:
    work_contract = read_text("templates/work-contract.yaml")
    packet_reference = read_text("docs/reference/packet-evidence-and-rework-reference.md")
    git_reference = read_text("docs/reference/git-worktree-and-branch-reference.md")

    for field in (
        "git_scope:",
        "mode: parallel",
        "base_ref:",
        "merge_target:",
        "branch_target:",
        "worktree_target:",
        "conflict_policy: no_overlap",
    ):
        assert field in work_contract

    assert "work contract boundaries" in packet_reference
    assert "../worktrees/<repo>/<work_id>-<lane>" in git_reference
    assert "explicitly_scoped" in git_reference
