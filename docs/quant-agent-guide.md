# Quant Agent Guide

Open this file when work touches the quant stack, dependency groups, or
directory routing. It is a map, not an implementation spec.

## Stack

- Decision: `docs/stack_decision.md`
- License gates: `docs/license_review.md`
- Source review artifact: `artifact/Gpt-pro-review`
- Runtime: Pydantic, Pydantic Settings, Typer, Rich.
- Data: Polars, DuckDB, PyArrow, NumPy, pandas, Pandera.
- Crypto data: CCXT for ingestion and exchange metadata only.
- Research: SciPy, scikit-learn, statsmodels, CVXPY, Optuna, MLflow.
- Engines: small deterministic baseline first; NautilusTrader for event-driven
  validation and live parity; HftBacktest only for L2/L3 or HFT lanes.
- Hummingbot: external runtime boundary only.
- vectorbt: optional only after license review.

## Directory Routing

- `src/qlab/core/`: config, shared types, time, errors.
- `src/qlab/data/`: IO, schemas, manifests, catalogs, synthetic fixtures.
- `src/qlab/data/crypto/`: symbols, fees, funding, CCXT importers, metadata.
- `src/qlab/research/`: factors, features, splits, walk-forward analysis.
- `src/qlab/screening/`: fast screening and optional adapters.
- `src/qlab/baseline/`: deterministic bar-level correctness engine.
- `src/qlab/execution/`: strategy contracts, order intents, risk limits.
- `src/qlab/execution/nautilus/`: Nautilus catalog, strategy, parity adapters.
- `src/qlab/execution/hummingbot/`: config/API boundary, no runtime state.
- `src/qlab/hft/`: HftBacktest and L2/L3 simulation adapters.
- `src/qlab/monitoring/`: events, freshness, reconciliation, alerts.
- `src/qlab/profit/`: ledger, costs, attribution, capital allocation.
- `src/qlab/experiments/`: experiment tracking and sweeps.
- `configs/`: templates and safe defaults only.
- `tests/<lane>/`: lane-local tests matching `src/qlab/<lane>/`.
- `artifact/`: sanitized reports and benchmarks only.

## Dependency Groups

- Default: `make sync`
- Data: `make sync-data`
- Crypto ingestion: `make sync-crypto`
- Research: `make sync-research`
- Screening: `make sync-screening`
- Baseline: `make sync-baseline`
- Nautilus: `make sync-nautilus`
- HFT: `make sync-hft`
- Hummingbot API boundary: `make sync-hummingbot-api`
- Monitoring: `make sync-monitoring`
- Notebooks: `make sync-notebooks`
- Profiling: `make sync-performance`
- Reporting: `make sync-reporting`
- Full local OSS environment: `uv sync --frozen --all-groups`

## Storage Rules

- Track code, contracts, templates, tests, docs, and sanitized artifacts.
- Do not track raw market data, raw book text, extracted book text, embedding
  indexes, exchange account state, logs, caches, secrets, `.env` files,
  `mlruns/`, `optuna.db`, DuckDB runtime files, or live order payloads.
- Root `/data/` and `/runtime/` are local ignored state. Package and test
  directories named `data` remain trackable.

## Verification

- Default gate: `make check-foundation`
- Quant runtime smoke: `make check-quant-runtime`
- Data smoke: `make check-quant-data`
- Research smoke: `make check-quant-research`
- Engine smoke: `make check-quant-nautilus` and `make check-quant-hft`
- Hummingbot boundary smoke: `make check-quant-hummingbot-api`
