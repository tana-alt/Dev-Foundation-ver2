# Quant Stack Decision

## Source Refs

- `artifact/Gpt-pro-review`
- `pyproject.toml`
- `Makefile`
- `docs/01-agent-operating-contract.md`
- `docs/02-output-verification-contract.md`
- `docs/03-repo-boundary-and-storage-contract.md`

## Decision

Adopt a crypto-first, contract-first layered hybrid stack.

The default development surface stays small: `uv`, `ruff`, `mypy`, `pytest`,
`hypothesis`, secret scanning, hygiene checks, and repo-local hooks. Quant
packages are split into dependency groups so parallel worktrees can install only
the surface they own.

## Initial Stack

- Runtime/config: Pydantic, Pydantic Settings, Typer, Rich.
- Data: Polars, DuckDB, PyArrow, NumPy, pandas, Pandera.
- Crypto data: CCXT plus HTTP/WebSocket/orjson support.
- Research: SciPy, scikit-learn, statsmodels, CVXPY, Optuna, MLflow.
- Fast screening and baseline checks: Numba in dedicated groups.
- Event-driven validation/live parity: NautilusTrader in a dedicated group.
- HFT/L2-L3 validation: HftBacktest in a dedicated group.
- Hummingbot: external runtime only; this repo tracks an API-boundary group.
- Monitoring: structured logs first, with Prometheus/OpenTelemetry as optional
  local dependencies.
- Notebooks and profiling are separate groups.

## Explicit Non-Core Choices

- Freqtrade is not a core dependency.
- Jesse is not a core dependency.
- Hummingbot full runtime is not a project dependency.
- CCXT is not a live execution source of truth.
- vectorbt is not included until a license review explicitly approves it.
- Raw market data, exchange state, book text, indexes, logs, MLflow runs,
  Optuna databases, DuckDB files, and secrets remain outside tracked repo truth.

## Python Policy

The base repo remains `>=3.12,<3.15` to preserve foundation checks. Quant
dependency groups are constrained to `>=3.12,<3.14` because the scientific,
trading, and profiling ecosystem lags newer Python releases more often than the
foundation tools do.

## Verification

Default gate:

```sh
uv sync --frozen --group dev
make check-foundation
```

Quant group smoke checks:

```sh
make check-quant-runtime
make check-quant-data
make check-quant-research
make check-quant-nautilus
make check-quant-hft
make check-quant-hummingbot-api
```

Dedicated engine groups are installed only when their lane owns that work:

```sh
make sync-nautilus
make sync-hft
make sync-hummingbot-api
```
