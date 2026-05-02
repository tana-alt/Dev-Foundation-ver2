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

RESTORE_SCRIPTS = (
    "scripts/setup-agent-environment.sh",
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


def repo_path(relative_path: str) -> Path:
    return ROOT / relative_path


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


def test_reference_set_is_exactly_four_files() -> None:
    actual = sorted(path.name for path in repo_path("docs/reference").glob("*.md"))
    expected = sorted(Path(path).name for path in REFERENCE_DOCS)
    assert actual == expected


def test_required_contract_files_exist() -> None:
    required = (*ACTIVE_DOCS, *REFERENCE_DOCS, *TEMPLATES, *RESTORE_SCRIPTS)

    for relative_path in required:
        assert repo_path(relative_path).is_file(), relative_path


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


def test_agent_environment_restore_uses_templates_not_runtime_state() -> None:
    readme = read_text("README.md")
    setup_script = read_text("scripts/setup-agent-environment.sh")
    codex_template = read_text("templates/codex-config.toml.example")

    assert "scripts/setup-agent-environment.sh" in readme
    assert "templates/serena-project.yml" in setup_script
    assert "templates/codex-config.toml.example" in setup_script
    assert ".serena/project.yml" in setup_script
    assert "web_dashboard_open_on_launch" in setup_script
    assert "@upstash/context7-mcp" in codex_template
    assert "auth.json" not in codex_template


def test_skill_roots_are_explicit() -> None:
    skill_root = repo_path(".agents/skills")
    live_skills = sorted(path for path in skill_root.iterdir() if path.is_dir())

    assert live_skills

    for skill_path in live_skills:
        assert (skill_path / "SKILL.md").is_file(), skill_path


def test_cd_readiness_is_guarded_until_deployment_exists() -> None:
    workflow = read_text(".github/workflows/ci.yml")
    verification_reference = read_text("docs/reference/verification-ci-and-pr-reference.md")

    for relative_path in DEPLOYMENT_CONFIGS:
        assert not repo_path(relative_path).exists(), relative_path

    assert "make check-required" in workflow
    assert "make check-cd" in verification_reference
    assert "not_applicable" in verification_reference
