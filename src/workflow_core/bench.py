"""Benchmark comparison store -- speed-ups become measured verdicts.

``NfrStore`` answers "does latency meet the budget?"; ``BenchStore`` answers
"did the change make the system faster?". Samples are namespaced by
``(benchmark, label)`` so a pre-change distribution (label ``baseline``) can
be compared against a post-change one (label ``candidate``) on one statistic.
Lower is better by contract: samples are non-negative costs (latency ms,
bytes, ...), validated at record time. The comparison applies a noise band --
relative changes smaller than ``min_change_pct`` count as ``unchanged``
instead of fabricating a win. Unlike ``nfr.db``, the store is durable across
sessions, so a baseline recorded before an optimization stays comparable;
retention still caps samples per benchmark/label. CLI binding:
``scripts/bench_compare.py`` (run / record / summary / compare / purge).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from workflow_core.contracts import StrictModel
from workflow_core.sqlite_store import SqliteStore
from workflow_core.stats import Statistic, describe

Verdict = Literal["improved", "regressed", "unchanged"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bench_samples (
    benchmark TEXT,
    label TEXT,
    value REAL,
    unit TEXT,
    run_id TEXT,
    ts TEXT
);
CREATE INDEX IF NOT EXISTS bench_samples_key ON bench_samples (benchmark, label);
"""


class BenchSummary(StrictModel):
    benchmark: str
    label: str
    unit: str
    count: int
    p50: float
    p95: float
    max: float
    mean: float


class BenchComparison(StrictModel):
    """Candidate distribution vs baseline on one statistic, noise-banded.

    ``delta`` is candidate minus baseline (negative means faster);
    ``improvement_pct`` is positive when the candidate improved.
    """

    benchmark: str
    statistic: Statistic
    baseline: BenchSummary
    candidate: BenchSummary
    baseline_value: float
    candidate_value: float
    delta: float
    improvement_pct: float
    min_change_pct: float
    verdict: Verdict


def _verdict(improvement_pct: float, min_change_pct: float) -> Verdict:
    if improvement_pct > 0 and improvement_pct >= min_change_pct:
        return "improved"
    if improvement_pct < 0 and -improvement_pct >= min_change_pct:
        return "regressed"
    return "unchanged"


class BenchStore(SqliteStore):
    def __init__(self, path: Path | str) -> None:
        super().__init__(path, schema=_SCHEMA)

    def record(
        self,
        benchmark: str,
        value: float,
        *,
        label: str,
        ts: str,
        unit: str = "ms",
        run_id: str = "",
    ) -> None:
        if not benchmark.strip():
            raise ValueError("benchmark must be non-empty")
        if not label.strip():
            raise ValueError("label must be non-empty")
        if not math.isfinite(value):
            raise ValueError(f"value must be finite, got {value!r}")
        if value < 0:
            raise ValueError(f"value must be non-negative (lower is better), got {value!r}")
        self._conn.execute(
            "INSERT INTO bench_samples VALUES (?,?,?,?,?,?)",
            (benchmark, label, float(value), unit, run_id, ts),
        )
        self._conn.commit()

    def benchmarks(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT benchmark FROM bench_samples ORDER BY benchmark")
        return [str(row[0]) for row in rows.fetchall()]

    def labels(self, benchmark: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT label FROM bench_samples WHERE benchmark = ? ORDER BY label",
            (benchmark,),
        )
        return [str(row[0]) for row in rows.fetchall()]

    def summarize(self, benchmark: str, label: str) -> BenchSummary | None:
        rows = self._conn.execute(
            "SELECT value, unit FROM bench_samples WHERE benchmark = ? AND label = ? "
            "ORDER BY value",
            (benchmark, label),
        ).fetchall()
        if not rows:
            return None
        values = [float(row[0]) for row in rows]
        dist = describe(values)
        return BenchSummary(
            benchmark=benchmark,
            label=label,
            unit=str(rows[0][1]),
            count=len(values),
            p50=dist.p50,
            p95=dist.p95,
            max=dist.max,
            mean=dist.mean,
        )

    def compare(
        self,
        benchmark: str,
        *,
        baseline: str = "baseline",
        candidate: str = "candidate",
        statistic: Statistic = "p50",
        min_change_pct: float = 3.0,
    ) -> BenchComparison | None:
        """Compare candidate against baseline; ``None`` until both sides have samples.

        Raises ``ValueError`` when the labels were recorded in different units
        or ``min_change_pct`` is negative.
        """
        if min_change_pct < 0:
            raise ValueError(f"min_change_pct must be non-negative, got {min_change_pct!r}")
        base = self.summarize(benchmark, baseline)
        cand = self.summarize(benchmark, candidate)
        if base is None or cand is None:
            return None
        if base.unit != cand.unit:
            raise ValueError(f"unit mismatch: baseline '{base.unit}' vs candidate '{cand.unit}'")
        baseline_value = float(getattr(base, statistic))
        candidate_value = float(getattr(cand, statistic))
        if baseline_value > 0:
            improvement_pct = round((baseline_value - candidate_value) / baseline_value * 100, 4)
            verdict = _verdict(improvement_pct, min_change_pct)
        else:
            # Degenerate zero baseline: a percentage is meaningless, so pin it
            # to 0.0 and judge on the raw values alone.
            improvement_pct = 0.0
            verdict = "unchanged" if candidate_value == 0 else "regressed"
        return BenchComparison(
            benchmark=benchmark,
            statistic=statistic,
            baseline=base,
            candidate=cand,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            delta=round(candidate_value - baseline_value, 4),
            improvement_pct=improvement_pct,
            min_change_pct=min_change_pct,
            verdict=verdict,
        )

    def enforce_retention(self, *, max_samples_per_label: int) -> int:
        """Drop the oldest samples of each benchmark/label beyond the budget."""
        purged = 0
        for benchmark in self.benchmarks():
            for label in self.labels(benchmark):
                count = self._conn.execute(
                    "SELECT COUNT(*) FROM bench_samples WHERE benchmark = ? AND label = ?",
                    (benchmark, label),
                ).fetchone()[0]
                excess = int(count) - max_samples_per_label
                if excess <= 0:
                    continue
                self._conn.execute(
                    "DELETE FROM bench_samples WHERE rowid IN ("
                    "SELECT rowid FROM bench_samples WHERE benchmark = ? AND label = ? "
                    "ORDER BY ts ASC, rowid ASC LIMIT ?)",
                    (benchmark, label, excess),
                )
                purged += excess
        self._conn.commit()
        return purged

    def purge(self, benchmark: str, label: str | None = None) -> int:
        """Delete a label's samples, or every sample of the benchmark."""
        if label is None:
            cursor = self._conn.execute(
                "DELETE FROM bench_samples WHERE benchmark = ?", (benchmark,)
            )
        else:
            cursor = self._conn.execute(
                "DELETE FROM bench_samples WHERE benchmark = ? AND label = ?", (benchmark, label)
            )
        self._conn.commit()
        return cursor.rowcount
