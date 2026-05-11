from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = (
    "src/qlab/core",
    "src/qlab/data/crypto",
    "src/qlab/research",
    "src/qlab/screening",
    "src/qlab/baseline",
    "src/qlab/execution/nautilus",
    "src/qlab/execution/hummingbot",
    "src/qlab/hft",
    "src/qlab/monitoring",
    "src/qlab/profit",
    "src/qlab/experiments",
    "configs/data",
    "configs/crypto",
    "configs/baseline",
    "configs/nautilus",
    "configs/hummingbot",
    "configs/monitoring",
    "configs/live/templates",
    "tests/unit",
    "tests/schema",
    "tests/data",
    "tests/crypto",
    "tests/screening",
    "tests/baseline",
    "tests/golden",
    "tests/nautilus",
    "tests/hummingbot",
    "tests/hft",
    "tests/parity",
    "tests/monitoring",
    "tests/profit",
    "artifact/sanitized_reports",
    "artifact/sanitized_benchmarks",
)


def test_quant_directory_structure_exists() -> None:
    missing = [path for path in REQUIRED_DIRS if not (ROOT / path).is_dir()]

    assert not missing, "missing quant directory skeleton:\n" + "\n".join(missing)


def test_quant_package_is_typed_and_importable() -> None:
    assert (ROOT / "src/qlab/__init__.py").is_file()
    assert (ROOT / "src/qlab/py.typed").is_file()


def test_artifact_policy_documents_sanitized_outputs_only() -> None:
    policy = (ROOT / "artifact/README.md").read_text(encoding="utf-8")

    assert "sanitized reports" in policy
    assert "raw market data" in policy
    assert "secrets" in policy


def test_quant_agent_guide_routes_stack_and_storage_boundaries() -> None:
    guide = (ROOT / "docs/quant-agent-guide.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "`docs/quant-agent-guide.md`" in agents
    assert "src/qlab/data/crypto/" in guide
    assert "uv sync --frozen --all-groups" in guide
    assert "docs/quant-implementation-plan.md" in guide
    assert "docs/data_policy.md" in guide
    assert "vectorbt: optional only after license review" in guide


def test_quant_implementation_plan_and_data_policy_are_agent_readable() -> None:
    plan = (ROOT / "docs/quant-implementation-plan.md").read_text(encoding="utf-8")
    policy = (ROOT / "docs/data_policy.md").read_text(encoding="utf-8")

    assert "Search layer: already handled outside this plan" in plan
    assert "one isolated worktree per lane" in plan
    assert "Core contracts" in plan
    assert "Crypto data schema" in plan
    assert "Synthetic fixtures" in plan
    assert "Raw exchange or vendor data is never repo truth" in policy
    assert "The search layer is separate from this quant environment" in policy
    assert "Root `/data/`" in policy
    assert "Root `/runtime/`" in policy
