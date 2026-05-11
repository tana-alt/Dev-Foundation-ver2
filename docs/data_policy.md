# Data Policy

This repo tracks reproducible code, contracts, tests, templates, docs, and
sanitized artifacts. It does not store operational data.

## Tracked

- `src/`: data loaders, schema definitions, manifest code, synthetic generators.
- `configs/`: safe templates and defaults only.
- `tests/`: small synthetic fixtures and golden outputs that can be reviewed in
  plain text or rebuilt deterministically.
- `artifact/`: sanitized reports, benchmark summaries, and verification
  outputs with no account, credential, vendor, or raw source payloads.
- `docs/`: policies, stack decisions, implementation plans, and review notes.

## Local Or External Only

- Root `/data/`: raw market data, vendor exports, CCXT downloads, Tardis data,
  Nautilus catalogs, DEX state, and cache files.
- Root `/runtime/`: logs, order/fill/position snapshots, reconciliation output,
  broker or exchange state, and live/paper ledgers.
- `mlruns/`, `optuna.db`, `*.duckdb`, `*.duckdb.wal`, notebook checkpoints,
  local indexes, and profiler dumps.
- `.env`, `.env.*`, secrets, credentials, cookies, API keys, wallet addresses,
  private account identifiers, and auth material.

## Market Data

Raw exchange or vendor data is never repo truth. Track manifests and schema
contracts instead of raw payloads. A manifest may include source name, dataset
kind, symbol, venue, time range, row count, checksum, schema version, and local
or external storage reference. Do not include secret-bearing URLs or account
specific request bodies.

Synthetic fixtures must be tiny, deterministic, and clearly marked as synthetic.
Use them for schema, golden, and correctness tests before any live or vendor
dataset is involved.

## Search And Knowledge Data

The search layer is separate from this quant environment. If quant code consumes
search results later, consume stable source references or claims, not raw book
text, extracted book text, embedding indexes, or local vector database files.

## Artifact Rules

Artifacts must be safe to review in PRs. They may include sanitized summaries,
synthetic benchmark reports, schema validation output, and golden test
summaries. They must not include raw market data, raw knowledge-source text,
live order payloads, account IDs, API keys, wallet addresses, or exchange
private endpoint responses.

## Verification

When changing data policy, schema, or storage behavior, run:

```sh
uv run pytest tests/test_quant_environment_contract.py tests/test_quant_directory_structure.py -q
make check-foundation
```
