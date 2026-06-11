"""Eval metrics store with a retention policy.

Accumulates run results in sqlite (stdlib, no new dependency). Two tiers:

- ``run_metrics`` -- the structured signals that are *kept*: success, tool /
  skill usage, unexpected actions. This is the durable measurement record.
- ``tool_usage`` -- per-run call/failure tallies per tool and skill, also kept;
  ``tool_stats`` aggregates them into usage and failure rates for issue
  surfacing.
- ``raw_runs`` -- the raw trajectory JSONL, which is *purgeable*. Once the raw
  tier exceeds a threshold, the oldest raw rows are deleted while the structured
  metrics survive. So the store grows bounded: raw data ages out, distilled
  signals remain for trend analysis.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from workflow_core.evaluation import EvalReport, EvalScore, ToolStat, ToolUsage, aggregate
from workflow_core.sqlite_store import SqliteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_metrics (
    run_id TEXT PRIMARY KEY,
    succeeded INTEGER,
    event_count INTEGER,
    tool_calls INTEGER,
    tool_call_rate REAL,
    skill_uses INTEGER,
    skill_usage_rate REAL,
    unexpected_actions TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS tool_usage (
    run_id TEXT,
    name TEXT,
    kind TEXT,
    calls INTEGER,
    failures INTEGER,
    PRIMARY KEY (run_id, kind, name)
);
CREATE TABLE IF NOT EXISTS raw_runs (
    run_id TEXT PRIMARY KEY,
    trajectory_jsonl TEXT,
    created_at TEXT
);
"""


class MetricsStore(SqliteStore):
    def __init__(self, path: Path | str) -> None:
        super().__init__(path, schema=_SCHEMA)

    def record_run(self, score: EvalScore, *, raw_trajectory: str, created_at: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO run_metrics VALUES (?,?,?,?,?,?,?,?,?)",
            (
                score.run_id,
                int(score.succeeded),
                score.event_count,
                score.tool_calls,
                score.tool_call_rate,
                score.skill_uses,
                score.skill_usage_rate,
                json.dumps(score.unexpected_actions),
                created_at,
            ),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO raw_runs VALUES (?,?,?)",
            (score.run_id, raw_trajectory, created_at),
        )
        self._conn.commit()

    def record_tool_usage(self, run_id: str, usages: Sequence[ToolUsage]) -> None:
        """Replace the run's per-tool tallies (idempotent re-measurement)."""
        self._conn.execute("DELETE FROM tool_usage WHERE run_id = ?", (run_id,))
        self._conn.executemany(
            "INSERT INTO tool_usage VALUES (?,?,?,?,?)",
            [(run_id, u.name, u.kind, u.calls, u.failures) for u in usages],
        )
        self._conn.commit()

    def tool_stats(self) -> list[ToolStat]:
        """Cross-run usage and failure rates per tool/skill.

        ``usage_rate`` is the share of all recorded calls; ``failure_rate`` is
        failures over the tool's own calls.
        """
        total = self._conn.execute("SELECT COALESCE(SUM(calls), 0) FROM tool_usage").fetchone()[0]
        rows = self._conn.execute(
            "SELECT name, kind, SUM(calls), SUM(failures), COUNT(DISTINCT run_id) "
            "FROM tool_usage GROUP BY kind, name ORDER BY SUM(calls) DESC, name"
        ).fetchall()
        return [
            ToolStat(
                name=str(row[0]),
                kind="skill" if str(row[1]) == "skill" else "tool",
                calls=int(row[2]),
                failures=int(row[3]),
                runs_used=int(row[4]),
                usage_rate=round(int(row[2]) / total, 4) if total else 0.0,
                failure_rate=round(int(row[3]) / int(row[2]), 4) if row[2] else 0.0,
            )
            for row in rows
        ]

    def raw_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM raw_runs").fetchone()[0])

    def metrics_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM run_metrics").fetchone()[0])

    def enforce_retention(self, *, max_raw_runs: int) -> int:
        """Purge oldest raw trajectories beyond the budget; keep structured metrics.

        Ordered by ``created_at`` (not rowid) so re-ingesting an old run via
        INSERT OR REPLACE cannot promote it past newer raws.
        """
        count = self.raw_count()
        if count <= max_raw_runs:
            return 0
        purge = count - max_raw_runs
        self._conn.execute(
            "DELETE FROM raw_runs WHERE rowid IN "
            "(SELECT rowid FROM raw_runs ORDER BY created_at ASC, rowid ASC LIMIT ?)",
            (purge,),
        )
        self._conn.commit()
        return purge

    def metrics(self) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT run_id, succeeded, tool_calls, skill_uses, unexpected_actions "
            "FROM run_metrics ORDER BY rowid"
        ).fetchall()
        return [
            {
                "run_id": str(row[0]),
                "succeeded": bool(row[1]),
                "tool_calls": int(row[2]),
                "skill_uses": int(row[3]),
                "unexpected_actions": list(json.loads(row[4])),
            }
            for row in rows
        ]

    def aggregate_stored(self) -> EvalReport:
        return aggregate(self._scores())

    def _scores(self) -> list[EvalScore]:
        rows = self._conn.execute(
            "SELECT run_id, succeeded, event_count, tool_calls, tool_call_rate, "
            "skill_uses, skill_usage_rate, unexpected_actions FROM run_metrics ORDER BY rowid"
        ).fetchall()
        return [
            EvalScore(
                run_id=str(row[0]),
                succeeded=bool(row[1]),
                event_count=int(row[2]),
                tool_calls=int(row[3]),
                tool_call_rate=float(row[4]),
                skill_uses=int(row[5]),
                skill_usage_rate=float(row[6]),
                unexpected_actions=list(json.loads(row[7])),
            )
            for row in rows
        ]
