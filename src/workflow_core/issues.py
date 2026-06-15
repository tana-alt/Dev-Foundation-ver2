"""Issue surfacing -- distilled eval signals become recurring problems.

Pure derivation: given the stored aggregate report and per-tool stats, emit
Issue records when rates cross thresholds. ``scripts/surface_issues.py``
persists them under ``artifact/<project>/metrics/`` and
``scripts/hook_session_start.py`` replays them into the agent's context each
session, so a degrading tool or skill keeps resurfacing until the numbers
recover.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from workflow_core.contracts import StrictModel
from workflow_core.evaluation import EvalReport, ToolStat

IssueKind = Literal["low_success_rate", "high_failure_rate", "unexpected_actions"]


class IssueThresholds(StrictModel):
    """When a stored signal becomes a surfaced problem."""

    min_calls: int = 5
    max_failure_rate: float = 0.3
    min_success_rate: float = 0.8


class Issue(StrictModel):
    kind: IssueKind
    subject: str
    value: float
    detail: str


def derive_issues(
    report: EvalReport,
    stats: Sequence[ToolStat],
    thresholds: IssueThresholds,
) -> list[Issue]:
    issues: list[Issue] = []
    if report.runs and report.success_rate < thresholds.min_success_rate:
        issues.append(
            Issue(
                kind="low_success_rate",
                subject="runs",
                value=report.success_rate,
                detail=(
                    f"success rate {report.success_rate:.2f} over {report.runs} run(s) "
                    f"is below {thresholds.min_success_rate:.2f}"
                ),
            )
        )
    if report.runs_with_unexpected:
        issues.append(
            Issue(
                kind="unexpected_actions",
                subject="runs",
                value=float(report.runs_with_unexpected),
                detail=f"{report.runs_with_unexpected} run(s) acted outside the expected envelope",
            )
        )
    for stat in stats:
        if stat.calls >= thresholds.min_calls and stat.failure_rate > thresholds.max_failure_rate:
            issues.append(
                Issue(
                    kind="high_failure_rate",
                    subject=f"{stat.kind}:{stat.name}",
                    value=stat.failure_rate,
                    detail=(
                        f"{stat.kind} {stat.name}: failure rate {stat.failure_rate:.2f} "
                        f"over {stat.calls} call(s) exceeds {thresholds.max_failure_rate:.2f}"
                    ),
                )
            )
    return issues


def render_issues_markdown(issues: Sequence[Issue], *, project: str, generated_at: str) -> str:
    lines = [
        "# Open Harness Issues",
        "",
        f"Project: {project}",
        f"Generated: {generated_at} (refresh with `make issues`)",
        "",
    ]
    if not issues:
        lines.append("No open issues.")
    else:
        lines.extend(f"- [{issue.kind}] {issue.subject}: {issue.detail}" for issue in issues)
    return "\n".join(lines) + "\n"
