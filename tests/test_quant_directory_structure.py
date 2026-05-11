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
