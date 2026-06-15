"""Run-scoped measurement store for the AB evaluation pipeline (Plan-N0002 R1).

Raw samples are first-class data: the ``metrics`` table is an aggregate cache
derived from ``samples`` via :meth:`RunStore.aggregate_run` and must never be
hand-written. ``checks`` and ``gate_results`` extend the R1 schema because R4
lands check results in the store and gate's ``retry_then_fail`` policy needs
durable retry counting; both follow R1's column style.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping

from workflow_core.contracts import StrictModel
from workflow_core.sqlite_store import SqliteStore
from workflow_core.stats import percentile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT,
    worktree TEXT,
    commit_sha TEXT,
    started_at TEXT,
    env_fingerprint TEXT,
    config_hash TEXT,
    tool_versions_json TEXT,
    metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    recorded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_samples_run_metric ON samples (run_id, metric);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    name TEXT,
    value REAL,
    unit TEXT,
    n_samples INTEGER,
    p50 REAL,
    p95 REAL,
    stddev REAL,
    metadata_json TEXT
);
CREATE TABLE IF NOT EXISTS verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    baseline_run_id TEXT,
    metric TEXT,
    statistic TEXT,
    delta_pct REAL,
    ci_low REAL,
    ci_high REAL,
    n_base INTEGER,
    n_cand INTEGER,
    threshold REAL,
    result TEXT,
    reason TEXT,
    policy_hash TEXT
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_s REAL,
    command TEXT,
    failures_json TEXT
);
CREATE TABLE IF NOT EXISTS gate_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_run_id TEXT NOT NULL,
    baseline_run_id TEXT,
    policy_hash TEXT NOT NULL,
    result TEXT NOT NULL,
    report_json TEXT,
    decided_at TEXT
);
"""


class RunRow(StrictModel):
    run_id: str
    task_id: str
    worktree: str
    commit_sha: str
    started_at: str
    env_fingerprint: str
    config_hash: str
    tool_versions: dict[str, str]
    metadata: dict[str, object]


class CheckRow(StrictModel):
    run_id: str
    name: str
    status: str
    duration_s: float
    command: str
    failures: list[str]


class VerdictRow(StrictModel):
    run_id: str
    baseline_run_id: str
    metric: str
    statistic: str
    delta_pct: float | None
    ci_low: float | None
    ci_high: float | None
    n_base: int
    n_cand: int
    threshold: float
    result: str
    reason: str
    policy_hash: str


class MetricAggregate(StrictModel):
    """One row of the aggregate cache; ``value`` is the median (p50)."""

    run_id: str
    name: str
    value: float
    unit: str
    n_samples: int
    p50: float
    p95: float
    stddev: float


class RunStore(SqliteStore):
    """Durable store for AB runs, raw samples, and derived judgements."""

    def __init__(self, path: object) -> None:
        super().__init__(str(path), schema=_SCHEMA)

    # -- runs ---------------------------------------------------------------

    def create_run(
        self,
        run_id: str,
        *,
        started_at: str,
        task_id: str = "",
        worktree: str = "",
        commit_sha: str = "",
        env_fingerprint: str = "",
        config_hash: str = "",
        tool_versions: Mapping[str, str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        if not run_id.strip():
            raise ValueError("run_id must be non-empty")
        self._conn.execute(
            "INSERT INTO runs (run_id, task_id, worktree, commit_sha, started_at,"
            " env_fingerprint, config_hash, tool_versions_json, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                task_id,
                worktree,
                commit_sha,
                started_at,
                env_fingerprint,
                config_hash,
                json.dumps(dict(tool_versions or {}), sort_keys=True),
                json.dumps(dict(metadata or {}), sort_keys=True),
            ),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> RunRow | None:
        row = self._conn.execute(
            "SELECT run_id, task_id, worktree, commit_sha, started_at, env_fingerprint,"
            " config_hash, tool_versions_json, metadata_json FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return RunRow(
            run_id=row[0],
            task_id=row[1],
            worktree=row[2],
            commit_sha=row[3],
            started_at=row[4],
            env_fingerprint=row[5],
            config_hash=row[6],
            tool_versions=json.loads(row[7] or "{}"),
            metadata=json.loads(row[8] or "{}"),
        )

    def find_cached_run(
        self, commit_sha: str, config_hash: str, env_fingerprint: str
    ) -> str | None:
        """Newest run matching the R1 cache key, or None."""
        if not (commit_sha and config_hash and env_fingerprint):
            return None
        row = self._conn.execute(
            "SELECT run_id FROM runs WHERE commit_sha = ? AND config_hash = ?"
            " AND env_fingerprint = ? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (commit_sha, config_hash, env_fingerprint),
        ).fetchone()
        return None if row is None else str(row[0])

    # -- samples and the derived aggregate cache -----------------------------

    def record_sample(
        self,
        run_id: str,
        metric: str,
        iteration: int,
        value: float,
        *,
        unit: str = "",
        recorded_at: str = "",
    ) -> None:
        if not metric.strip():
            raise ValueError("metric must be non-empty")
        self._conn.execute(
            "INSERT INTO samples (run_id, metric, iteration, value, unit, recorded_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, metric, iteration, float(value), unit, recorded_at),
        )
        self._conn.commit()

    def sample_values(self, run_id: str, metric: str) -> list[float]:
        rows = self._conn.execute(
            "SELECT value FROM samples WHERE run_id = ? AND metric = ?"
            " ORDER BY iteration ASC, id ASC",
            (run_id, metric),
        ).fetchall()
        return [float(r[0]) for r in rows]

    def metric_names(self, run_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT metric FROM samples WHERE run_id = ? ORDER BY metric",
            (run_id,),
        ).fetchall()
        return [str(r[0]) for r in rows]

    def aggregate_run(self, run_id: str) -> list[MetricAggregate]:
        """Regenerate the ``metrics`` cache for a run from its raw samples."""
        aggregates = []
        for name in self.metric_names(run_id):
            values = sorted(self.sample_values(run_id, name))
            unit_row = self._conn.execute(
                "SELECT unit FROM samples WHERE run_id = ? AND metric = ? LIMIT 1",
                (run_id, name),
            ).fetchone()
            aggregates.append(
                MetricAggregate(
                    run_id=run_id,
                    name=name,
                    value=percentile(values, 0.50),
                    unit=str(unit_row[0]) if unit_row else "",
                    n_samples=len(values),
                    p50=percentile(values, 0.50),
                    p95=percentile(values, 0.95),
                    stddev=statistics.stdev(values) if len(values) > 1 else 0.0,
                )
            )
        self._conn.execute("DELETE FROM metrics WHERE run_id = ?", (run_id,))
        self._conn.executemany(
            "INSERT INTO metrics (run_id, name, value, unit, n_samples, p50, p95, stddev,"
            " metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}')",
            [
                (a.run_id, a.name, a.value, a.unit, a.n_samples, a.p50, a.p95, a.stddev)
                for a in aggregates
            ],
        )
        self._conn.commit()
        return aggregates

    # -- verdicts -------------------------------------------------------------

    def record_verdict(
        self,
        *,
        run_id: str,
        baseline_run_id: str,
        metric: str,
        statistic: str,
        delta_pct: float | None,
        ci_low: float | None,
        ci_high: float | None,
        n_base: int,
        n_cand: int,
        threshold: float,
        result: str,
        reason: str,
        policy_hash: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO verdicts (run_id, baseline_run_id, metric, statistic, delta_pct,"
            " ci_low, ci_high, n_base, n_cand, threshold, result, reason, policy_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                baseline_run_id,
                metric,
                statistic,
                delta_pct,
                ci_low,
                ci_high,
                n_base,
                n_cand,
                threshold,
                result,
                reason,
                policy_hash,
            ),
        )
        self._conn.commit()

    def verdicts_for_run(self, run_id: str) -> list[VerdictRow]:
        rows = self._conn.execute(
            "SELECT run_id, baseline_run_id, metric, statistic, delta_pct, ci_low, ci_high,"
            " n_base, n_cand, threshold, result, reason, policy_hash"
            " FROM verdicts WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [
            VerdictRow(
                run_id=r[0],
                baseline_run_id=r[1],
                metric=r[2],
                statistic=r[3],
                delta_pct=r[4],
                ci_low=r[5],
                ci_high=r[6],
                n_base=int(r[7]),
                n_cand=int(r[8]),
                threshold=float(r[9]),
                result=r[10],
                reason=r[11],
                policy_hash=r[12],
            )
            for r in rows
        ]

    # -- checks ---------------------------------------------------------------

    def record_check(
        self,
        run_id: str,
        name: str,
        *,
        status: str,
        duration_s: float,
        command: str,
        failures: list[str] | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO checks (run_id, name, status, duration_s, command, failures_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, name, status, duration_s, command, json.dumps(failures or [])),
        )
        self._conn.commit()

    def checks_for_run(self, run_id: str) -> list[CheckRow]:
        rows = self._conn.execute(
            "SELECT run_id, name, status, duration_s, command, failures_json"
            " FROM checks WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [
            CheckRow(
                run_id=r[0],
                name=r[1],
                status=r[2],
                duration_s=float(r[3]),
                command=r[4],
                failures=json.loads(r[5] or "[]"),
            )
            for r in rows
        ]

    # -- gate results ----------------------------------------------------------

    def record_gate_result(
        self,
        *,
        candidate_run_id: str,
        baseline_run_id: str,
        policy_hash: str,
        result: str,
        report_json: str,
        decided_at: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO gate_results (candidate_run_id, baseline_run_id, policy_hash,"
            " result, report_json, decided_at) VALUES (?, ?, ?, ?, ?, ?)",
            (candidate_run_id, baseline_run_id, policy_hash, result, report_json, decided_at),
        )
        self._conn.commit()

    def inconclusive_gate_count(self, candidate_run_id: str, policy_hash: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM gate_results WHERE candidate_run_id = ?"
            " AND policy_hash = ? AND result = 'inconclusive'",
            (candidate_run_id, policy_hash),
        ).fetchone()
        return int(row[0])
