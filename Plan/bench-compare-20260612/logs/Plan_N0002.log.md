---
plan_id: Plan_N0002
project_id: bench-compare-20260612
plan_ref: Plan/bench-compare-20260612/plans/Plan_N0002.md
source_spec: Plan/bench-compare-20260612/plans/Plan-N0002.md  # user-authored, untracked
---

# Execution Log — Plan-N0002 (quantitative eval toolset v2, Phase 1)

## 2026-06-12 — Scope and design decisions (thought trail)

### Scope

Plan-N0002.md is a v1→v2 diff; v1 is not in the repo. The diff is
self-contained for the Phase 1 core it names as the new top priority:
`metrics store(samples) + abrun + verdict + check + gate` (R1–R6, R12–R15).
This plan executes Phase 1 to the R15 acceptance criteria, plus the R6
retrofit of the existing tools (`nfr_metric.py`, `bench_compare.py`) per the
goal's 「既存ツールも利用可能な形で整備」. Phase 2–4 tools (bench/scaling/
mutation/loadtest/sqlperf/harness-eval; R7–R11) revise v1 specs that do not
exist yet and stay out of scope.

### Design decisions

1. **Spec→repo layout mapping.** The repo-boundary contract enumerates the
   allowed top-level roots and forbids new ones, so the spec's deliverable
   paths map as: `tools/abrun|check|gate` → `scripts/abrun.py`,
   `scripts/check_runner.py`, `scripts/quality_gate.py` (+ `scripts/verdict.py`);
   `policies/` → `.agents/policies/` (existing agent-config root);
   `docs/exit_codes.md` → `docs/reference/exit-codes-reference.md` (repo keeps
   numbered contracts at docs/ root, kebab-case references under reference/).
2. **New `RunStore` (runs.db), not an extension of existing stores.** R1's
   runs/samples/metrics/verdicts schema is run-scoped and provenance-bearing
   (env_fingerprint, config_hash, tool_versions); `eval.db` is trajectory-eval,
   `nfr.db` is temporary, `bench.db` is the lightweight label-store. Two
   extension tables beyond R1 — `checks` and `gate_results` — because R4 says
   check results land in the store and gate's `retry_then_fail` needs durable
   retry counting; both follow R1's column style.
3. **Logic in `src/workflow_core/`, CLIs thin.** mypy strict checks tests/
   (and follows imports into src/) but not scripts/, and the repo's CLI tests
   run via subprocess. So all algorithmic code (verdict statistics, store,
   policy, fingerprint, orchestration) lives in typed workflow_core modules
   with library-level tests; scripts are argparse wrappers. Module names avoid
   collisions with existing `gate.py`/`trajectory.py`: `runstore.py`,
   `verdict.py`, `policy.py`, `envfp.py`, `tracelog.py`, `abrun.py`,
   `checkrun.py`, `quality_gate.py`.
4. **Bootstrap verdict is stdlib + seeded.** percentile bootstrap
   (resamples=10000, `random.Random(seed)`, default seed recorded in output)
   over Δ% of the chosen statistic; nearest-rank percentiles reused from
   `workflow_core.stats` (`median` accepted as alias of `p50`). MAD outlier
   filter uses the 1.4826 normal-consistency constant; `mad == 0` keeps only
   exact-median values, which is deterministic and surfaces via the 10%
   exclusion guard. Per-side exclusion rate > 10% → `inconclusive`.
5. **R6 semantics fixed as:** missing/insufficient samples are `error` (exit
   3), matching R2's explicit `n < 7 → error(insufficient_samples)` — exit 2
   is reserved for statistical inconclusiveness. argparse usage errors default
   to exit 2, which would collide with `inconclusive`, so a shared
   `workflow_core.cli.build_parser()` remaps parser errors to exit 3; all six
   CLIs (4 new + 2 retrofitted) use it.
6. **Retrofit of existing tools:** `nfr_metric.py evaluate` no-samples 2→3;
   `bench_compare.py` compare missing-side 2→3, bad-args 2→3, failed measured
   command 1→3 (tool error, not a quality verdict); docstrings/reference doc
   updated. Verdict-bearing codes (0/1) unchanged.
7. **mode vocabulary (v1 absent, assumption logged):** `non_regression` and
   `lower_is_better` both judge Δ% = (T_cand−T_base)/T_base·100 against
   `threshold_pct` (CI low > t → regression; CI high < t → pass; else
   inconclusive). `higher_is_better` negates Δ% first. `equal_required`
   compares the statistic exactly (pass/regression, no bootstrap).
   Zero baseline statistic → `error(zero_baseline)` (Δ% undefined).
8. **suggested_additional_iterations** (R2 step 7): with CI width w and the
   distance d = 2·|threshold − Δ%_point| needed for the CI to clear the
   threshold, w ∝ 1/√n gives n_total = n·(w/d)²; suggestion =
   max(ceil(n_total) − n, 1), capped at 200 to avoid absurd advice when
   d ≈ 0.
9. **abrun worktrees.** The worktree reference forbids worktrees inside
   tracked repo paths, so abrun validates every configured worktree path
   resolves outside the target repo (tool error otherwise) — the spec's
   `.ab/base` example is repo-internal and intentionally not followed.
   abrun stamps a `.abrun-worktree` marker at creation; `abrun clean` only
   removes marker-bearing worktrees (structural guard so the human-gated
   "worktree deletion" never touches worktrees abrun does not own). Reuse
   requires marker + HEAD == resolved ref, else error.
10. **Measure adapters.** Phase 1 ships `tool: "command"` with
    `value_from: "wallclock"` (perf_counter ms) or `"stdout"` (command prints
    the sample; deterministic path used by tests and CI). `ABRUN_ITERATION`
    and `ABRUN_PORT` are exported to the measured command. The ABAB
    interleave runs warmup+iterations rounds, alternating baseline/candidate
    inside each round, so thermal drift lands on both groups (R3). Phase 2
    `bench` plugs in as a new adapter without schema change.
11. **Cache key** `(commit_sha, config_hash, env_fingerprint)` per R1: abrun
    reuses the newest matching run unless `--no-cache`; config_hash is the
    sha256 of the canonical (sorted, compact) config JSON, recorded on runs.
12. **Anti-gaming (R12).** Thresholds exist only in policy files; gate/verdict
    take no threshold CLI flag. Policy files must resolve inside
    `FOUNDATION_POLICY_DIR` (default `<root>/.agents/policies`) or gate exits
    3 — in hardened deployments the env var points at a read-only mount.
    `policy_hash` (canonical sha256) is recorded with every verdict/gate row.
13. **Gate conditions are generic.** `tool: "check"` reads the checks table;
    every other condition (verdict/mutation/sqlperf/…) is evaluated as a
    statistical verdict over that metric's samples — future tools only need
    to write samples, gate does not enumerate tools. `on_inconclusive`:
    `fail` → exit 1, `pass_with_warning` → exit 0 + warning,
    `retry_then_fail` → exit 2 while prior inconclusive gate evaluations for
    (candidate_run_id, policy_hash) < max_retries, then 1 (counted via
    gate_results — gate stays stateless per call, state lives in the store).
14. **env_fingerprint (R13)** is best-effort: every field present, unknowns
    explicit `"unknown"` (macOS has no cgroups), canonical-JSON sha256.
    Baseline/candidate mismatch → warning in verdict output, judgement
    continues (per spec).
15. **trace-collector (R14): writer only.** `tracelog.TraceWriter` appends
    R14 envelopes (seq resumes from existing line count); `trace ingest` is
    not in the v2 deliverable list and is deferred. abrun/gate emit
    `metric_recorded`/`verdict`/`gate_result` events when
    `FOUNDATION_TRACE_PATH` is set.
16. **No new Makefile targets.** abrun/check/gate are per-task tools with
    required arguments, unlike the argument-less `nfr-summary`/`bench-summary`
    print targets; they are documented in the reference doc instead.

### Coding notes

- Quality bounds: functions ≤60 lines, nesting ≤4, C901 ≤10 — verdict and
  abrun orchestration are split into single-purpose helpers up front.
- New scripts must be registered in `HARNESS_SCRIPTS`
  (tests/test_foundation_integrity.py); check whether reference-doc lists are
  exhaustiveness-checked before adding the new reference doc.
- Hygiene: only `Plan_N[0-9]{4}.log.md` is a valid log name — this file is
  `Plan_N0002.log.md` even though the user-authored plan is `Plan-N0002.md`.
- Tests: library-level under tests/workflow_core (tmp_path db, typed, mypy
  strict); CLI/acceptance via subprocess with
  FOUNDATION_REPO_ROOT/FOUNDATION_PROJECT_ID/FOUNDATION_POLICY_DIR overrides,
  timeout=30. Scratch git repos under tmp_path need explicit user.name/email.
- Acceptance suite (R15): seeded-regression → exit 1, neutral → exit 0,
  inconclusive → exit 2 + suggested_additional_iterations, driven through
  abrun → verdict → gate with a deterministic stdout-metric command (values
  committed in the scratch repo, indexed by ABRUN_ITERATION).
- Bootstrap determinism: fixed default seed (20260612); tests pin expected
  verdicts, not CI endpoints, to stay robust against resample-count tweaks.

## 2026-06-12 — Execution log

Implementation order (library first, CLIs thin, acceptance last):

1. Shared plumbing: `hashing.py` (canonical JSON sha256), `cli.py`
   (R6 exit constants + `R6ArgumentParser` remapping argparse usage errors
   2 -> 3 so exit 2 stays purely statistical).
2. `runstore.py`: R1 schema plus `checks`/`gate_results` extension tables;
   `metrics` treated as a derived cache (`aggregate_run` deletes and
   re-inserts; value = p50). Cache lookup newest-first by
   `(commit_sha, config_hash, env_fingerprint)`, all parts required.
3. `verdict.py`: MAD filter (5 sigma x 1.4826; mad==0 keeps exact-median
   values only), >10% per-side exclusion -> inconclusive; seeded percentile
   bootstrap of delta%; `higher_is_better` negates the interval;
   `equal_required` is exact statistic equality, no bootstrap. Self-caught:
   `compare` drifted past the 60-line bound -> extracted
   `_base_fields`/`_decide`/`_finish` helpers.
4. `policy.py` / `envfp.py` / `tracelog.py`: R12 dir containment + policy
   hash, R13 best-effort fingerprint, R14 append-only writer (seq resumes
   from line count).
5. `checkrun.py` + `quality_gate.py`: generic conditions (check table vs
   statistical verdict per metric); `retry_then_fail` counts prior
   inconclusive `gate_results` rows so the gate stays stateless per call.
6. `abrun.py`: ABAB interleaving, worktree guards (outside-repo +
   `.abrun-worktree` marker for reuse/clean), measure adapters
   (wallclock | stdout), optional server lifecycle with healthcheck poll.
7. CLIs (`scripts/abrun.py`, `verdict.py`, `check_runner.py`,
   `quality_gate.py`), `.agents/policies/default.json`.
8. Legacy retrofit (delegated to a sonnet subagent): `nfr_metric.py`
   evaluate no-samples 2 -> 3; `bench_compare.py` missing-samples 2 -> 3,
   measured-command failure 1 -> 3, plus `R6ArgumentParser`; subagent also
   wrote `tests/test_metric_cli_exit_codes.py` (9 CLI tests).
9. Docs/registration: `docs/reference/exit-codes-reference.md` (new), AB
   pipeline section + stale exit-code prose fixes in
   `docs/reference/harness-observability-reference.md`, AGENTS.md routing
   bullets, `HARNESS_SCRIPTS` + `ACTIVE_REFERENCE_DOCS` registration.

Contract collision resolved during closeout: the integrity suite only
tracks plan files named `Plan_N\d{4}.md`, so the user-authored
`Plan-N0002.md` (hyphen) stays untracked as the source spec and the tracked
record `plans/Plan_N0002.md` summarizes it; `plan_ref`s repointed.

### Verification evidence (2026-06-12)

- `uv run mypy` (strict, tests/): Success, no issues in 54 source files.
- `make check-required`: 388 passed (ruff, mypy, pytest), 71s.
- `make check-foundation`: 388 passed + hygiene/secrets/worktree-policy/
  cd_readiness checks green.
- R15 acceptance (`tests/test_ab_pipeline_acceptance.py`, scratch repo,
  abrun -> check_runner -> quality_gate, resamples=1500):
  - seeded regression (+12%) -> gate exit 1, conditions
    {overall: pass, demo.value: regression};
  - perf-neutral refactor -> gate exit 0;
  - noisy straddle -> gate exit 2 and `verdict compare` exit 2 with integer
    `suggested_additional_iterations` + `repro` line;
  - policy outside `FOUNDATION_POLICY_DIR` -> exit 3.
- Library coverage: 62 workflow_core tests (runstore 14, verdict 18,
  policy 7, envfp 3, tracelog 3, checkrun 5, quality_gate 10 incl.
  retry_then_fail sequence inconclusive/inconclusive/fail) + abrun 13.

Status: completed (index.yaml updated).
