"""Render the final markdown report."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import AnalystOpinion, DebatePoint, EarningsContext, Verdict


LABEL_EMOJI = {"GOOD": "🟢", "MIXED": "🟡", "BAD": "🔴"}


def _format_number(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


def render_report(
    context: EarningsContext,
    opinions: list[AnalystOpinion],
    points: list[DebatePoint],
    debate_transcript: str,
    verdict: Verdict,
) -> str:
    eps_surprise = (
        f"{context.eps_surprise_pct:+.2f}%"
        if context.eps_surprise_pct is not None
        else "n/a"
    )
    actual = _format_number(context.eps_actual)
    consensus = _format_number(context.eps_consensus)

    lines = [
        f"# {context.ticker} {context.quarter} — Earnings Debate Report",
        "",
        f"_Generated {datetime.utcnow().isoformat(timespec='seconds')}Z_",
        "",
        f"## Verdict: {LABEL_EMOJI.get(verdict.label, '')} **{verdict.label}** "
        f"(confidence {verdict.confidence:.2f})",
        "",
        f"> {verdict.one_liner}",
        "",
        f"**EPS surprise assessment**: {verdict.eps_surprise_assessment}",
        "",
        f"**Rationale**: {verdict.rationale}",
        "",
        "---",
        "",
        "## Headline numbers",
        "",
        f"- EPS actual: **{actual}**",
        f"- EPS consensus: {consensus}",
        f"- EPS surprise: **{eps_surprise}**",
        "",
        "## Analyst one-liners (round 1)",
        "",
    ]
    for o in opinions:
        lines.append(f"- **{o.role.upper()}**: {o.headline}")
    lines += [
        "",
        "## Contested topics (extracted by chair)",
        "",
    ]
    for i, p in enumerate(points):
        lines += [
            f"### {i+1}. {p.topic}",
            f"- Bull view: {p.bull_view or '_n/a_'}",
            f"- Bear view: {p.bear_view or '_n/a_'}",
            "",
        ]
    lines += [
        "## Cross-examination (round 2)",
        "",
        debate_transcript,
        "",
        "## Detail: round-1 analyst notes",
        "",
    ]
    for o in opinions:
        lines += [
            f"### {o.role.upper()} analyst",
            f"_Headline_: {o.headline}",
            "",
            "**Key points**",
        ]
        lines += [f"- {kp}" for kp in o.key_points]
        lines += ["", "**Evidence cited**"]
        lines += [f"- {e}" for e in o.evidence]
        if o.concerns:
            lines += ["", "**Concerns**"]
            lines += [f"- {c}" for c in o.concerns]
        lines += [""]
    return "\n".join(lines)


def write_report(
    out_dir: Path,
    context: EarningsContext,
    body: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{context.ticker}_{context.quarter}_report.md"
    path.write_text(body, encoding="utf-8")
    return path
