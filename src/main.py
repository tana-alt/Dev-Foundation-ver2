"""CLI utilities for the API-first earnings review workflow.

The deliverable workflow lives behind the FastAPI app. This CLI is intentionally
thin: it either starts the API server or sends a request to ``POST /reviews``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import click
import requests
import structlog
from dotenv import load_dotenv

from .llm import get_provider
from .workflow import ReviewWorkflow
from .workflow_models import ReviewRequest


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


@click.group()
def cli() -> None:
    """Run or call the earnings review API."""


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--reload", is_flag=True, help="Enable uvicorn reload for local development.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the FastAPI server."""
    load_dotenv()
    setup_logging()

    import uvicorn

    uvicorn.run("src.api:app", host=host, port=port, reload=reload)


@cli.command()
@click.option("--api-url", default="http://127.0.0.1:8000", show_default=True)
@click.option("--input-json", type=click.Path(exists=True, path_type=Path))
@click.option("--ticker", help="Ticker used when --input-json is not supplied.")
@click.option("--fiscal-period", "--quarter", help='Fiscal period, e.g. "2025Q3".')
@click.option("--filing-url", help="SEC filing URL used when fixture sections are absent.")
@click.option(
    "--out", "out_dir", default="outputs", show_default=True, type=click.Path(path_type=Path)
)
def run(
    api_url: str,
    input_json: Path | None,
    ticker: str | None,
    fiscal_period: str | None,
    filing_url: str | None,
    out_dir: Path,
) -> None:
    """Call POST /reviews and save the API response artifacts."""
    load_dotenv()
    setup_logging()

    payload = _load_payload(input_json, ticker, fiscal_period, filing_url)
    if api_url == "local" or (
        api_url == "http://127.0.0.1:8000" and os.getenv("LLM_PROVIDER", "").lower() == "fake"
    ):
        body = (
            ReviewWorkflow(get_provider())
            .run(ReviewRequest.model_validate(payload))
            .model_dump(mode="json")
        )
    else:
        response = requests.post(f"{api_url.rstrip('/')}/reviews", json=payload, timeout=300)
        response.raise_for_status()
        body = response.json()

    output_path = out_dir
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "workflow_result.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "report.md").write_text(body["markdown_report"], encoding="utf-8")

    verdict = body["judge_decision"]["verdict"]
    confidence = body["judge_decision"]["confidence"]
    click.echo(f"Verdict: {verdict} (confidence {confidence:.2f})")
    click.echo(str(output_path / "report.md"))


def _load_payload(
    input_json: Path | None,
    ticker: str | None,
    fiscal_period: str | None,
    filing_url: str | None,
) -> dict[str, Any]:
    if input_json is not None:
        return json.loads(input_json.read_text(encoding="utf-8"))

    if ticker is None or fiscal_period is None:
        raise click.UsageError("--ticker and --fiscal-period are required without --input-json")

    payload: dict[str, Any] = {
        "ticker": ticker,
        "fiscal_period": fiscal_period,
    }
    if filing_url:
        payload["filing_url"] = filing_url
    return payload


if __name__ == "__main__":
    cli()
