"""Eval metrics store with a retention policy.

Accumulates run results in sqlite (stdlib, no new dependency). Two tiers:

- ``run_metrics`` -- the structured signals that are *kept*: success, tool /
  skill usage, unexpected actions. This is the durable measurement record.
- ``raw_runs`` -- the raw trajectory JSONL, which is *purgeable*. Once the raw
  tier exceeds a threshold, the oldest raw rows are deleted while the structured
  metrics survive. So the store grows bounded: raw data ages out, distilled
  signals remain for trend analysis.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from workflow_core.evaluation import EvalReport, EvalScore, aggregate

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
CREATE TABLE IF NOT EXISTS raw_runs (
    run_id TEXT PRIMARY KEY,
    trajectory_jsonl TEXT,
    created_at TEXT
);
"""


class MetricsStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

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

    def raw_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM raw_runs").fetchone()[0])

    def metrics_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM run_metrics").fetchone()[0])

    def enforce_retention(self, *, max_raw_runs: int) -> int:
        """Purge oldest raw trajectories beyond the budget; keep structured metrics."""
        count = self.raw_count()
        if count <= max_raw_runs:
            return 0
        purge = count - max_raw_runs
        self._conn.execute(
            "DELETE FROM raw_runs WHERE rowid IN "
            "(SELECT rowid FROM raw_runs ORDER BY rowid ASC LIMIT ?)",
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

    def close(self) -> None:
        self._conn.close()
