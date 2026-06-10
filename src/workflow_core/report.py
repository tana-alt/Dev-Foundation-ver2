"""Result-report-only contract for inter-agent exchange.

Agents hand each other bounded results, never raw context. ResultReport is the
only shape that crosses an agent boundary: a status, a bounded summary, the
changed paths, and what was verified. The summary budget keeps a subagent from
dumping its transcript back into the caller's context. ``build_result_report``
clips an over-long summary so coercing subagent output never crashes.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from workflow_core.contracts import StrictModel

MAX_SUMMARY_CHARS = 1000

ReportStatus = Literal["completed", "blocked", "failed"]


class ResultReport(StrictModel):
    status: ReportStatus
    summary: str
    changed_paths: list[str] = []
    verification: str = ""
    next_action: str = ""

    @model_validator(mode="after")
    def summary_is_bounded(self) -> Self:
        if not self.summary.strip():
            raise ValueError("summary must be non-empty")
        if len(self.summary) > MAX_SUMMARY_CHARS:
            raise ValueError(
                f"summary exceeds {MAX_SUMMARY_CHARS} chars; report results, not raw context"
            )
        return self


def build_result_report(
    status: ReportStatus,
    summary: str,
    *,
    changed_paths: list[str] | None = None,
    verification: str = "",
    next_action: str = "",
) -> ResultReport:
    clipped = summary.strip()
    if len(clipped) > MAX_SUMMARY_CHARS:
        clipped = clipped[: MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    return ResultReport(
        status=status,
        summary=clipped,
        changed_paths=changed_paths or [],
        verification=verification,
        next_action=next_action,
    )
