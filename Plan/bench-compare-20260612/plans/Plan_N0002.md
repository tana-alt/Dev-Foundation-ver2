---
plan_id: Plan_N0002
project_id: bench-compare-20260612
status: completed
log_ref: Plan/bench-compare-20260612/logs/Plan_N0002.log.md
---

# AB Evaluation Pipeline (abrun -> verdict -> check -> gate)

## Goal

Phase 1 core of the quantitative evaluation toolset: measure baseline vs
candidate refs under identical conditions, judge metric deltas with a
statistically grounded verdict, run functional checks, and gate merges on a
policy file -- with one shared exit-code convention so agents can branch on
"change is bad" (1) vs "measure more" (2) vs "measurement broken" (3).

## Source Spec

User-authored v2 revision spec at
`Plan/bench-compare-20260612/plans/Plan-N0002.md` (kept untracked: the
hyphenated name is outside the plan-record contract, and the file is the
user's working document). This record is the tracked summary; the full
requirement text (R1-R15) lives there.

## Scope

Phase 1 only: metrics store (runs/samples) + abrun + verdict + check + gate
(R1-R6, R12-R15). Phase 2-4 tools (bench/scaling/mutation/loadtest/sqlperf/
harness-eval, R7-R11) revise v1 specs that do not exist in this repo and are
out of scope. Existing tools (`nfr_metric.py`, `bench_compare.py`) are
retrofitted to the R6 exit-code convention.

## Deliverables

- `src/workflow_core/`: `runstore.py` (R1 schema + checks/gate_results),
  `verdict.py` (R2 MAD filter + seeded bootstrap CI), `abrun.py` (R3 ABAB
  interleaved worktree measurement), `checkrun.py` (R4), `quality_gate.py`
  (R5), `policy.py` (R12 anti-gaming), `envfp.py` (R13), `tracelog.py`
  (R14), `cli.py` + `hashing.py` (shared R6/json plumbing).
- `scripts/`: `abrun.py`, `verdict.py`, `check_runner.py`,
  `quality_gate.py`; R6 retrofit of `nfr_metric.py` and `bench_compare.py`.
- `.agents/policies/default.json`, `docs/reference/exit-codes-reference.md`,
  AB pipeline section in `docs/reference/harness-observability-reference.md`,
  registrations in `tests/test_foundation_integrity.py` and `AGENTS.md`.

## Acceptance (R15 Phase 1)

Via abrun -> verdict -> gate end to end on a scratch repo
(`tests/test_ab_pipeline_acceptance.py`): seeded regression -> exit 1,
perf-neutral refactor -> exit 0, noisy straddle -> exit 2 with
`suggested_additional_iterations`, policy outside the allowed dir -> exit 3.

Design decisions and verification evidence: see `log_ref`.
