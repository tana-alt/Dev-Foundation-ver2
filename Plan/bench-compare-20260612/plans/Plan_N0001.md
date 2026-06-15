---
plan_id: Plan_N0001
project_id: bench-compare-20260612
status: completed
log_ref: Plan/bench-compare-20260612/logs/Plan_N0001.log.md
---

# Benchmark Comparison Tool (BenchStore + bench_compare CLI)

## Goal

Give agents a quality-measurement surface for performance work: capture a
pre-change latency distribution as a baseline, re-capture after the change,
and turn "it got faster" into a measured, gate-compatible verdict. This fills
the gap next to `NfrStore` (budget verdicts) which has no baseline/comparison
concept.

## Source Refs

- `src/workflow_core/nfr.py` (closest analog: sample store + statistics)
- `src/workflow_core/sqlite_store.py` (store lifecycle base)
- `src/workflow_core/contracts.py` (StrictModel)
- `scripts/nfr_metric.py` (CLI shape, env resolution, exit-code vocabulary)
- `docs/reference/harness-observability-reference.md`
- `tests/workflow_core/test_nfr.py` (test style)

## Design Decisions (thought trail)

1. New `BenchStore`/`bench.db`, not an extension of `NfrStore` or
   `MetricsStore`: `nfr.db` is documented as temporary (purge after verdict);
   baselines must survive across optimization sessions, and `eval.db` is
   trajectory-eval-only. Different lifecycle => different store.
2. Samples namespaced by `(benchmark, label)`; comparison is between two
   labels (default `baseline` vs `candidate`). Labels are free-form so
   multi-variant comparisons (e.g. `v1`, `v2`) work without schema change.
3. Noise band: relative changes smaller than `min_change_pct` (default 3.0)
   are `unchanged`, not improvements -- prevents timer jitter from being
   reported as a win. Band boundary is inclusive (`pct >= band` improves).
4. `improvement_pct = (baseline - candidate) / baseline * 100` (positive =
   faster); lower-is-better is the contract, so values are validated
   non-negative at record time. Zero baseline is degenerate: pct pinned to
   0.0, verdict `unchanged` iff candidate is also 0 else `regressed`.
5. Default statistic `p50` (median is robust for improvement measurement);
   NFR budgets keep `p95` as their default (tail guarantees). Statistic
   vocabulary shared via new `workflow_core/stats.py` so the two stores
   cannot drift on percentile semantics (`_percentile` moved out of `nfr.py`,
   nearest-rank kept bit-identical).
6. Unit mismatch between the two labels raises `ValueError` instead of
   producing a meaningless ratio.
7. CLI `run` buffers all wall-clock samples and records nothing unless every
   iteration exits 0 -- partial data from a broken command must not skew a
   comparison. Warmup iterations are measured but discarded.
8. Exit codes mirror `nfr_metric.py evaluate`: 0 ok, 1 regression (or
   `--min-improvement-pct` unmet), 2 missing samples (cold start
   distinguishable for CI callers).
9. Stdlib only (sqlite3, subprocess, time.perf_counter): dependency changes
   are human-gated; no numpy/statistics needed for nearest-rank percentiles.
10. Retention mirrors NfrStore: per `(benchmark, label)` cap via
    `FOUNDATION_BENCH_MAX_SAMPLES` (default 1000), applied on record.

## Coding Notes

- ruff: line 100, C901 max complexity 10; tests/test_code_quality.py bounds
  function length 60 lines / nesting 4 => CLI split into per-command handlers.
- mypy strict checks tests/ and follows imports into src/ => full annotations
  in src; `describe()` returns a NamedTuple instead of dict-unpacking into
  pydantic models.
- Hygiene check forbids tracked `*.db` => bench.db stays under `artifact/`.
- `workflow_core/__init__.py` lazy-export hub intentionally NOT extended:
  `NfrStore` is also imported directly (`from workflow_core.nfr import ...`),
  bench follows the same convention.
- `tests/test_foundation_integrity.py::HARNESS_SCRIPTS` is existence-only;
  new script added there.

## Allowed Write Targets

- `src/workflow_core/{stats.py,bench.py,nfr.py}`
- `scripts/bench_compare.py`
- `tests/workflow_core/{test_stats.py,test_bench.py,test_nfr.py}`
- `tests/test_foundation_integrity.py` (HARNESS_SCRIPTS entry)
- `Makefile` (bench-summary target)
- `docs/reference/harness-observability-reference.md`, `AGENTS.md` (routing line)
- `Plan/bench-compare-20260612/`, `artifact/bench-compare-20260612/`

## Work Plan

1. `workflow_core/stats.py`: shared `Statistic`, `percentile`, `describe`.
2. `workflow_core/bench.py`: `BenchSummary`, `BenchComparison`, `BenchStore`.
3. Refactor `nfr.py` onto `stats.py` (behavior-identical).
4. `scripts/bench_compare.py`: run / record / summary / compare / purge.
5. Tests: `test_stats.py`, `test_bench.py`; update `test_nfr.py` imports;
   register script in `test_foundation_integrity.py`.
6. Makefile `bench-summary`, reference doc section, AGENTS.md routing line.
7. Verify: ruff format/lint, pytest, mypy, end-to-end CLI demo with evidence
   in the plan log.

## Human Gates

- None expected: local code/doc/test work only, no dependency or CI changes.

## Residual Blockers

- None.
