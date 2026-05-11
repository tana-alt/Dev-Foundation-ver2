# Quant Implementation Plan

Use one PR and one isolated worktree per lane. Do not merge from an agent;
merge is a human-only action.

## Current State

- PR 1: quant OSS environment, dependency groups, directory skeleton, and agent
  routing.
- Search layer: already handled outside this plan.

## Next PRs

1. Core contracts
   - Paths: `src/qlab/core/`, `tests/unit/`
   - Scope: config, shared value types, time utilities, errors.
   - Gate: `make sync`, `uv run pytest tests/unit -q`, `make check-foundation`.

2. Crypto data schema
   - Paths: `src/qlab/data/`, `src/qlab/data/crypto/`, `tests/schema/`,
     `tests/crypto/`, `configs/data/`, `configs/crypto/`
   - Scope: symbol normalization, OHLCV/trade/funding/fee schemas, manifest
     contracts, exchange metadata templates.
   - Gate: `make sync-crypto`, `uv run pytest tests/schema tests/crypto -q`,
     `make check-foundation`.

3. Synthetic fixtures
   - Paths: `tests/data/`, `tests/golden/`, `artifact/sanitized_reports/`
   - Scope: tiny deterministic OHLCV, funding, fee, and L2 examples; no raw
     vendor or account data.
   - Gate: `make sync-crypto`, `uv run pytest tests/data tests/golden -q`,
     `make check-foundation`.

4. Baseline deterministic engine
   - Paths: `src/qlab/baseline/`, `tests/baseline/`, `tests/golden/`
   - Scope: bar-level orders, fills, maker/taker fees, funding accrual,
     cash/position/equity, no-lookahead checks.
   - Gate: `make sync-baseline`, `uv run pytest tests/baseline tests/golden -q`,
     `make check-foundation`.

## Parallel Work Rule

Lanes may run in parallel only when `allowed_write_targets` do not overlap. If a
lane needs to touch shared docs, contracts, or fixtures, call out the conflict
and serialize that part of the work.

