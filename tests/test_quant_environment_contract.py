import tomllib
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]

QUANT_GROUPS = {
    "data",
    "crypto-data",
    "research",
    "screening",
    "baseline",
    "nautilus",
    "hft",
    "hummingbot-api",
    "monitoring",
    "notebooks",
    "performance",
    "reporting",
}


def read_pyproject() -> dict[str, Any]:
    raw_data: object = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert isinstance(raw_data, dict)
    return cast(dict[str, Any], raw_data)


def requirement_name(requirement: str) -> str:
    name = requirement.split(";", 1)[0].split("[", 1)[0]
    for operator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if operator in name:
            name = name.split(operator, 1)[0]
    return name.strip().lower().replace("_", "-")


def dependency_names(raw_dependencies: object) -> set[str]:
    assert isinstance(raw_dependencies, list)
    names: set[str] = set()
    for item in raw_dependencies:
        if isinstance(item, str):
            names.add(requirement_name(item))
    return names


def included_groups(raw_dependencies: object) -> set[str]:
    assert isinstance(raw_dependencies, list)
    groups: set[str] = set()
    for item in raw_dependencies:
        if isinstance(item, dict):
            raw_group = item.get("include-group")
            assert isinstance(raw_group, str)
            groups.add(raw_group)
    return groups


def test_quant_dependency_groups_are_layered_and_optional() -> None:
    pyproject = read_pyproject()
    groups = cast(dict[str, object], pyproject["dependency-groups"])

    assert QUANT_GROUPS <= set(groups)
    assert {"pydantic", "pydantic-settings", "rich", "typer"} <= dependency_names(
        pyproject["project"]["dependencies"]
    )
    assert {"hypothesis", "mypy", "pytest", "pytest-cov", "ruff"} <= dependency_names(groups["dev"])

    assert {"duckdb", "numpy", "pandas", "pandera", "polars", "pyarrow"} <= dependency_names(
        groups["data"]
    )
    assert included_groups(groups["crypto-data"]) == {"data"}
    assert {"ccxt", "orjson", "aiohttp", "websockets"} <= dependency_names(groups["crypto-data"])
    assert included_groups(groups["research"]) == {"crypto-data"}
    assert {"cvxpy", "mlflow", "optuna", "scikit-learn", "scipy", "statsmodels"} <= (
        dependency_names(groups["research"])
    )
    assert included_groups(groups["baseline"]) == {"crypto-data"}
    assert included_groups(groups["screening"]) == {"research"}
    assert "numba" in dependency_names(groups["baseline"])
    assert "numba" in dependency_names(groups["screening"])


def test_heavy_or_license_gated_engines_are_not_default_dependencies() -> None:
    pyproject = read_pyproject()
    groups = cast(dict[str, object], pyproject["dependency-groups"])

    default_dependency_names = dependency_names(
        pyproject["project"]["dependencies"]
    ) | dependency_names(groups["dev"])
    assert "nautilus-trader" not in default_dependency_names
    assert "hftbacktest" not in default_dependency_names
    assert "vectorbt" not in default_dependency_names
    assert "freqtrade" not in default_dependency_names
    assert "jesse" not in default_dependency_names

    assert "nautilus-trader" in dependency_names(groups["nautilus"])
    assert "hftbacktest" in dependency_names(groups["hft"])
    assert "httpx" in dependency_names(groups["hummingbot-api"])
    assert "vectorbt" not in {name for group in groups.values() for name in dependency_names(group)}


def test_quant_groups_pin_to_python_312_and_313() -> None:
    pyproject = read_pyproject()
    tool_uv = cast(dict[str, Any], pyproject["tool"]["uv"])
    group_metadata = cast(dict[str, object], tool_uv["dependency-groups"])

    for group_name in QUANT_GROUPS:
        metadata = cast(dict[str, str], group_metadata[group_name])
        assert metadata["requires-python"] == ">=3.12,<3.14"


def test_runtime_data_and_experiment_state_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for ignored_path in (
        "/data/",
        "/runtime/",
        "mlruns/",
        "optuna.db",
        "*.duckdb",
        "*.duckdb.wal",
        ".env",
        ".env.*",
        "secrets/",
    ):
        assert ignored_path in gitignore
