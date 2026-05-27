import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STATIC_REQUIRED_PATHS = (
    ".editorconfig",
    ".gitattributes",
    ".github/workflows/ci.yml",
    ".gitleaks.toml",
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "Makefile",
    "Plan/README.md",
    "README.md",
    "artifact/README.md",
    "docs/01-agent-operating-contract.md",
    "docs/02-output-verification-contract.md",
    "docs/03-repo-boundary-and-storage-contract.md",
    "docs/reference/agent-runtime-and-scope-reference.md",
    "docs/reference/git-worktree-and-branch-reference.md",
    "docs/reference/migration-and-acceptance-reference.md",
    "docs/reference/packet-evidence-and-rework-reference.md",
    "docs/reference/repo-boundary-and-storage-reference.md",
    "docs/reference/verification-ci-and-pr-reference.md",
    "hooks/pre-commit",
    "hooks/pre-push",
    "pyproject.toml",
    "scripts/check-agent-worktree-policy.sh",
    "scripts/check-dev-environment.sh",
    "scripts/check-repo-hygiene.sh",
    "scripts/check-secrets.sh",
    "scripts/check-shell-static-analysis.sh",
    "scripts/setup-agent-environment.sh",
    "src/README.md",
    "templates/README.md",
    "templates/codex-config.toml.example",
    "templates/evidence-record.yaml",
    "templates/project-storage-map.yaml",
    "templates/rework-record.yaml",
    "templates/serena-project.yml",
    "templates/verification-record.yaml",
    "templates/work-contract.yaml",
    "tests/test_clean_checkout_reproducibility.py",
    "tests/test_contract_models.py",
    "tests/test_extension_surface_integrity.py",
    "tests/test_foundation_integrity.py",
    "uv.lock",
)


def git_ls_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def dynamic_required_paths() -> list[str]:
    paths: list[str] = []

    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yaml"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    )
    paths.extend(pytest_test_paths())
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "plugins").glob("*/.codex-plugin/plugin.json"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "plugins").glob("*/.mcp.json"))
    )
    paths.extend(
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "plugins").glob("*/skills/*/SKILL.md"))
    )
    paths.extend(manifest_referenced_plugin_asset_paths())

    paths.append(".agents/plugins/marketplace.json")
    paths.append(".agents/skills/SKILL_INDEX.md")
    return paths


def pytest_test_paths() -> list[str]:
    return [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.is_file()
    ]


def manifest_referenced_plugin_asset_paths() -> list[str]:
    paths: list[str] = []

    for manifest_path in sorted((ROOT / "plugins").glob("*/.codex-plugin/plugin.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugin_dir = manifest_path.parents[1]
        interface = manifest.get("interface", {})
        if not isinstance(interface, dict):
            continue

        for key in ("composerIcon", "logo"):
            raw_path = interface.get(key)
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue

            relative = raw_path[2:] if raw_path.startswith("./") else raw_path
            asset_path = plugin_dir / relative
            if asset_path.is_file():
                paths.append(asset_path.relative_to(ROOT).as_posix())

    return paths


def test_required_foundation_files_are_tracked_for_clean_checkout() -> None:
    tracked = git_ls_files()
    required = sorted({*STATIC_REQUIRED_PATHS, *dynamic_required_paths()})

    missing = [path for path in required if path not in tracked]

    assert not missing, "required clean-checkout files are not tracked:\n" + "\n".join(missing)


def test_pytest_test_files_are_clean_checkout_required_paths() -> None:
    test_files = set(pytest_test_paths())
    required = set(dynamic_required_paths())

    assert test_files
    assert test_files <= required
