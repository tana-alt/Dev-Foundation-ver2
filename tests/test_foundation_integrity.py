import os
import subprocess
from pathlib import Path

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
    "configs",
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


def line_count(relative_path: str) -> int:
    return len(read_text(relative_path).splitlines())


def test_active_agent_context_stays_under_budget() -> None:
    total_lines = sum(line_count(path) for path in ACTIVE_DOCS)
    assert total_lines <= 300


def test_agents_routes_to_active_docs_and_references() -> None:
    agents = read_text("AGENTS.md")

    for relative_path in (*ACTIVE_DOCS[1:], *REFERENCE_DOCS):
        assert f"`{relative_path}`" in agents

    assert "Root Boundary" not in agents


def test_reference_set_matches_routed_reference_docs() -> None:
    actual = sorted(path.name for path in repo_path("docs/reference").glob("*.md"))
    expected = sorted(Path(path).name for path in REFERENCE_DOCS)
    assert actual == expected


def test_required_contract_files_exist() -> None:
    required = (*ACTIVE_DOCS, *REFERENCE_DOCS, *TEMPLATES, *DEV_DEFAULTS, *HOOKS, *RESTORE_SCRIPTS)

    for relative_path in required:
        assert repo_path(relative_path).is_file(), relative_path


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
    assert "@upstash/context7-mcp" in codex_template
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
    assert "make check-foundation" in pre_push

    for required_text in (
        "agent/<work_id>/<lane>/<slug>",
        "foundation.canonicalRoot",
        "main",
        "canonical repo root",
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


def run_worktree_policy(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(repo_path("scripts/check-agent-worktree-policy.sh"))],
        cwd=repo,
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

    canonical_agent_repo = tmp_path / "canonical-agent"
    init_git_repo(canonical_agent_repo, "agent/work/lane/slug", canonical_agent_repo)
    canonical_agent_result = run_worktree_policy(canonical_agent_repo)
    assert canonical_agent_result.returncode == 2
    assert "canonical repo root" in canonical_agent_result.stderr

    external_agent_repo = tmp_path / "external-agent"
    init_git_repo(external_agent_repo, "agent/work/lane/slug", canonical_root)
    external_result = run_worktree_policy(external_agent_repo)
    assert external_result.returncode == 0
    assert "agent worktree policy: passed" in external_result.stdout


def test_pre_push_blocks_protected_remote_destination_refs(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical"
    init_git_repo(canonical_root, "main", canonical_root)

    external_agent_repo = tmp_path / "external-agent"
    init_git_repo(external_agent_repo, "agent/work/lane/slug", canonical_root)

    for remote_ref in ("refs/heads/main", "refs/heads/master"):
        result = run_pre_push_hook(
            external_agent_repo,
            "refs/heads/agent/work/lane/slug local-sha "
            f"{remote_ref} remote-sha\n",
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
    assert "check-toolchain:" in makefile
    assert "check-hygiene:" in makefile
    assert "check-shell:" in makefile
    assert "check-secrets:" in makefile
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
