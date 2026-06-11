"""NFR sample store -- non-functional requirements become measured verdicts.

The agent records latency (or any numeric NFR) samples into a small sqlite
store while it works, then evaluates the distribution against a budget, so
"p95 latency under 200ms" is a measurement instead of a claim. The store is
temporary by design: samples age out per metric by count, and a metric can be
purged outright once its verdict is recorded in durable evidence or a plan log.
CLI binding: ``scripts/nfr_metric.py`` (record / summary / evaluate / purge).
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Literal

from workflow_core.contracts import StrictModel

Statistic = Literal["p50", "p95", "max", "mean"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nfr_samples (
    metric TEXT,
    value REAL,
    unit TEXT,
    run_id TEXT,
    ts TEXT
);
CREATE INDEX IF NOT EXISTS nfr_samples_metric ON nfr_samples (metric);
"""


class NfrSummary(StrictModel):
    metric: str
    unit: str
    count: int
    p50: float
    p95: float
    max: float
    mean: float


class NfrVerdict(StrictModel):
    """One evaluated budget: observed statistic vs threshold."""

    metric: str
    statistic: Statistic
    threshold: float
    observed: float
    passed: bool
    count: int


def _percentile(ordered: list[float], q: float) -> float:
    """Nearest-rank percentile over pre-sorted values."""
    rank = max(math.ceil(q * len(ordered)), 1)
    return ordered[rank - 1]


class NfrStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(
        self, metric: str, value: float, *, ts: str, unit: str = "ms", run_id: str = ""
    ) -> None:
        if not metric.strip():
            raise ValueError("metric must be non-empty")
        self._conn.execute(
            "INSERT INTO nfr_samples VALUES (?,?,?,?,?)", (metric, float(value), unit, run_id, ts)
        )
        self._conn.commit()

    def metrics(self) -> list[str]:
        rows = self._conn.execute("SELECT DISTINCT metric FROM nfr_samples ORDER BY metric")
        return [str(row[0]) for row in rows.fetchall()]

    def summarize(self, metric: str) -> NfrSummary | None:
        rows = self._conn.execute(
            "SELECT value, unit FROM nfr_samples WHERE metric = ? ORDER BY value", (metric,)
        ).fetchall()
        if not rows:
            return None
        values = [float(row[0]) for row in rows]
        return NfrSummary(
            metric=metric,
            unit=str(rows[0][1]),
            count=len(values),
            p50=_percentile(values, 0.50),
            p95=_percentile(values, 0.95),
            max=values[-1],
            mean=round(sum(values) / len(values), 4),
        )

    def evaluate(
        self, metric: str, *, threshold: float, statistic: Statistic = "p95"
    ) -> NfrVerdict | None:
        """Budget check: the statistic must stay at or under the threshold."""
        summary = self.summarize(metric)
        if summary is None:
            return None
        observed = float(getattr(summary, statistic))
        return NfrVerdict(
            metric=metric,
            statistic=statistic,
            threshold=threshold,
            observed=observed,
            passed=observed <= threshold,
            count=summary.count,
        )

    def enforce_retention(self, *, max_samples_per_metric: int) -> int:
        """Drop the oldest samples of each metric beyond the budget."""
        purged = 0
        for metric in self.metrics():
            count = self._conn.execute(
                "SELECT COUNT(*) FROM nfr_samples WHERE metric = ?", (metric,)
            ).fetchone()[0]
            excess = int(count) - max_samples_per_metric
            if excess <= 0:
                continue
            self._conn.execute(
                "DELETE FROM nfr_samples WHERE rowid IN ("
                "SELECT rowid FROM nfr_samples WHERE metric = ? "
                "ORDER BY ts ASC, rowid ASC LIMIT ?)",
                (metric, excess),
            )
            purged += excess
        self._conn.commit()
        return purged

    def purge_metric(self, metric: str) -> int:
        """Delete every sample of the metric (after its verdict is recorded)."""
        cursor = self._conn.execute("DELETE FROM nfr_samples WHERE metric = ?", (metric,))
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
