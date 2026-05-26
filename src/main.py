"""CLI entry point.

Usage:
    python -m src.main --ticker NVDA --quarter 2025Q3 --filing-url <url>

All configuration (API keys, model names) comes from environment variables
loaded from .env (twelve-factor: config).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

from .llm import get_provider
from .orchestrator import Orchestrator
from .preprocessor import fetch_consensus, fetch_filing_html, segment_filing
from .report import render_report, write_report


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


@click.command()
@click.option("--ticker", required=True, help="e.g. NVDA")
@click.option("--quarter", required=True, help='e.g. "2025Q3"')
@click.option("--filing-url", required=True, help="URL to SEC 10-Q HTML")
@click.option("--out", "out_dir", default="outputs", show_default=True)
def cli(ticker: str, quarter: str, filing_url: str, out_dir: str) -> None:
    load_dotenv()
    setup_logging()
    log = structlog.get_logger()

    log.info("run.start", ticker=ticker, quarter=quarter)

    # 1. Preprocess: fetch + segment + consensus
    html = fetch_filing_html(filing_url)
    sections = segment_filing(html)
    context = fetch_consensus(ticker, quarter)

    # 2. Orchestrate the debate
    llm = get_provider()
    orch = Orchestrator(llm)

    opinions = orch.round_one(context, sections)
    points = orch.extract_debate_points(opinions)
    debate = orch.round_two(context, points)
    verdict = orch.judge(context, opinions, debate)

    # 3. Render & write report
    body = render_report(context, opinions, points, debate, verdict)
    path = write_report(Path(out_dir), context, body)

    log.info("run.done", report=str(path), verdict=verdict.label)
    click.echo(f"\n✔ Verdict: {verdict.label} (confidence {verdict.confidence:.2f})")
    click.echo(f"→ {path}")


if __name__ == "__main__":
    cli()
