# Evaluation Exit Codes Reference

Open this only when wiring quantitative evaluation tools into gates or when
branching on their exit codes.

## Convention

Every quantitative evaluation CLI in `scripts/` separates "the change is bad"
from "the measurement is unusable":

- `0` pass: the quality condition holds.
- `1` quality fail: a real, statistically supported signal -- regression past
  threshold, failed gate condition, or missed budget.
- `2` inconclusive: the data cannot decide at the configured confidence.
  Collect more samples and re-run; never treat as pass or fail.
- `3` tool error: bad configuration, insufficient samples, or measurement
  failure. Says nothing about change quality.

Argparse usage errors are remapped from the argparse default (2) to 3 via
`workflow_core.cli.R6ArgumentParser`, so exit 2 always means statistical
inconclusiveness, never a CLI mistake.

## Agent Branching Rules

- exit 1 -> fix the code (or change the policy explicitly with human
  approval); re-measuring and hoping for a different verdict is gaming.
- exit 2 -> re-measure. `verdict compare` prints
  `suggested_additional_iterations` and a `repro` command line; collect that
  many more iterations and evaluate again. The gate counts repeats against
  the policy's `max_retries`.
- exit 3 -> escalate the measurement problem: fix the config, record samples,
  or repair the environment. Rerunning unchanged will not help.

## Compliant Tools

- `scripts/abrun.py`: 0 measured, 3 tool error.
- `scripts/verdict.py`: 0 pass, 1 regression, 2 inconclusive, 3 error.
- `scripts/check_runner.py`: 0 pass, 1 check failed, 3 tool error.
- `scripts/quality_gate.py`: 0 pass, 1 fail, 2 inconclusive, 3 error.
- `scripts/nfr_metric.py` (`evaluate`): 0 within budget, 1 missed budget,
  3 no samples recorded.
- `scripts/bench_compare.py` (`run`/`compare`): 0 ok, 1 regression or unmet
  `--min-improvement-pct`, 3 missing samples or failed measured command.
