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

from .llm import LLMProvider, LLMResponse, get_provider
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
@click.option("--target-earnings-date", help="Target earnings event date, YYYY-MM-DD.")
@click.option("--target-period-end-date", help="Target fiscal period end date, YYYY-MM-DD.")
@click.option("--prior-fiscal-period", help='Prior fiscal period, e.g. "2025Q2".')
@click.option("--financial-data-as-of", help="Financial data cutoff date, YYYY-MM-DD.")
@click.option(
    "--document-file",
    "document_files",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Local PDF/text earnings document to ingest.",
)
@click.option(
    "--document-source-type",
    default="earnings_presentation",
    show_default=True,
    help="Source type for --document-file.",
)
@click.option("--document-id", help="Document ID for a single --document-file.")
@click.option("--document-title", help="Document title for a single --document-file.")
@click.option("--document-fiscal-period", help="Fiscal period for --document-file.")
@click.option("--document-published-date", help="Published date for --document-file, YYYY-MM-DD.")
@click.option(
    "--out", "out_dir", default="outputs", show_default=True, type=click.Path(path_type=Path)
)
def run(
    api_url: str,
    input_json: Path | None,
    ticker: str | None,
    fiscal_period: str | None,
    filing_url: str | None,
    target_earnings_date: str | None,
    target_period_end_date: str | None,
    prior_fiscal_period: str | None,
    financial_data_as_of: str | None,
    document_files: tuple[Path, ...],
    document_source_type: str,
    document_id: str | None,
    document_title: str | None,
    document_fiscal_period: str | None,
    document_published_date: str | None,
    out_dir: Path,
) -> None:
    """Call POST /reviews and save the API response artifacts."""
    load_dotenv()
    setup_logging()

    payload = _load_payload(
        input_json,
        ticker,
        fiscal_period,
        filing_url,
        target_earnings_date=target_earnings_date,
        target_period_end_date=target_period_end_date,
        prior_fiscal_period=prior_fiscal_period,
        financial_data_as_of=financial_data_as_of,
        document_files=document_files,
        document_source_type=document_source_type,
        document_id=document_id,
        document_title=document_title,
        document_fiscal_period=document_fiscal_period,
        document_published_date=document_published_date,
    )
    output_path = out_dir
    output_path.mkdir(parents=True, exist_ok=True)
    try:
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
    except Exception as exc:
        _write_json(output_path / "workflow_error.json", _error_payload(exc))
        raise click.ClickException(str(exc)) from exc

    (output_path / "workflow_result.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "report.md").write_text(body["markdown_report"], encoding="utf-8")

    verdict = body["judge_decision"]["verdict"]
    confidence = body["judge_decision"]["confidence"]
    click.echo(f"Verdict: {verdict} (confidence {confidence:.2f})")
    click.echo(str(output_path / "report.md"))


@cli.command("inspect-input")
@click.option("--input-json", type=click.Path(exists=True, path_type=Path))
@click.option("--ticker", help="Ticker used when --input-json is not supplied.")
@click.option("--fiscal-period", "--quarter", help='Fiscal period, e.g. "2025Q3".')
@click.option("--filing-url", help="SEC filing URL used when fixture sections are absent.")
@click.option("--target-earnings-date", help="Target earnings event date, YYYY-MM-DD.")
@click.option("--target-period-end-date", help="Target fiscal period end date, YYYY-MM-DD.")
@click.option("--prior-fiscal-period", help='Prior fiscal period, e.g. "2025Q2".')
@click.option("--financial-data-as-of", help="Financial data cutoff date, YYYY-MM-DD.")
@click.option(
    "--document-file",
    "document_files",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Local PDF/text earnings document to ingest.",
)
@click.option(
    "--document-source-type",
    default="earnings_presentation",
    show_default=True,
    help="Source type for --document-file.",
)
@click.option("--document-id", help="Document ID for a single --document-file.")
@click.option("--document-title", help="Document title for a single --document-file.")
@click.option("--document-fiscal-period", help="Fiscal period for --document-file.")
@click.option("--document-published-date", help="Published date for --document-file, YYYY-MM-DD.")
@click.option("--out", "out_dir", required=True, type=click.Path(path_type=Path))
@click.option(
    "--strict-guidance",
    is_flag=True,
    help="Fail when guidance is ambiguous or not found.",
)
def inspect_input(
    input_json: Path | None,
    ticker: str | None,
    fiscal_period: str | None,
    filing_url: str | None,
    target_earnings_date: str | None,
    target_period_end_date: str | None,
    prior_fiscal_period: str | None,
    financial_data_as_of: str | None,
    document_files: tuple[Path, ...],
    document_source_type: str,
    document_id: str | None,
    document_title: str | None,
    document_fiscal_period: str | None,
    document_published_date: str | None,
    out_dir: Path,
    strict_guidance: bool,
) -> None:
    """Inspect ingestion, routing, and context budget without LLM calls."""
    load_dotenv()
    setup_logging()

    try:
        request = ReviewRequest.model_validate(
            _load_payload(
                input_json,
                ticker,
                fiscal_period,
                filing_url,
                target_earnings_date=target_earnings_date,
                target_period_end_date=target_period_end_date,
                prior_fiscal_period=prior_fiscal_period,
                financial_data_as_of=financial_data_as_of,
                document_files=document_files,
                document_source_type=document_source_type,
                document_id=document_id,
                document_title=document_title,
                document_fiscal_period=document_fiscal_period,
                document_published_date=document_published_date,
            )
        )
        audit = ReviewWorkflow(_InspectionOnlyLLM()).inspect_input(
            request,
            strict_guidance=strict_guidance,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "normalized_input_summary.json", audit["normalized_input_summary"])
    _write_json(out_dir / "normalized_metrics.json", audit["normalized_metrics"])
    _write_json(out_dir / "source_manifest.json", audit["source_manifest"])
    _write_json(out_dir / "temporal_input_summary.json", audit["temporal_input_summary"])
    _write_json(out_dir / "metric_snapshots.json", audit["metric_snapshots"])
    _write_json(out_dir / "temporal_source_manifest.json", audit["temporal_source_manifest"])
    _write_json(out_dir / "temporal_validation.json", audit["temporal_validation"])
    _write_json(out_dir / "document_sections.preview.json", audit["document_sections_preview"])
    _write_json(out_dir / "guidance_audit.json", audit["guidance_audit"])
    _write_json(out_dir / "routing_report.json", audit["routing_report"])
    _write_json(out_dir / "context_budget.json", audit["context_budget"])

    failed_budgets = [item for item in audit["context_budget"] if item.get("status") == "failed"]
    if failed_budgets:
        failed_agents = ", ".join(item["agent_name"] for item in failed_budgets)
        raise click.ClickException(f"context budget failed for: {failed_agents}")

    click.echo(f"Input audit written to {out_dir}")


def _load_payload(
    input_json: Path | None,
    ticker: str | None,
    fiscal_period: str | None,
    filing_url: str | None,
    *,
    target_earnings_date: str | None = None,
    target_period_end_date: str | None = None,
    prior_fiscal_period: str | None = None,
    financial_data_as_of: str | None = None,
    document_files: tuple[Path, ...] = (),
    document_source_type: str = "earnings_presentation",
    document_id: str | None = None,
    document_title: str | None = None,
    document_fiscal_period: str | None = None,
    document_published_date: str | None = None,
) -> dict[str, Any]:
    if input_json is not None:
        payload = json.loads(input_json.read_text(encoding="utf-8"))
    else:
        if ticker is None or fiscal_period is None:
            raise click.UsageError("--ticker and --fiscal-period are required without --input-json")

        payload = {
            "ticker": ticker,
            "fiscal_period": fiscal_period,
        }

    if filing_url:
        payload["filing_url"] = filing_url
    for key, value in {
        "target_earnings_date": target_earnings_date,
        "target_period_end_date": target_period_end_date,
        "prior_fiscal_period": prior_fiscal_period,
        "financial_data_as_of": financial_data_as_of,
    }.items():
        if value:
            payload[key] = value
    if document_files:
        payload.setdefault("document_files", [])
        for index, document_file in enumerate(document_files, start=1):
            fallback_id = document_id or f"{document_file.stem}-document-{index}"
            payload["document_files"].append(
                {
                    "path": str(document_file),
                    "source_type": document_source_type,
                    "document_id": fallback_id,
                    "title": document_title or document_file.stem.replace("-", " ").title(),
                    "fiscal_period": document_fiscal_period or payload["fiscal_period"],
                    "published_date": document_published_date,
                    "period_role": "target_period_document",
                }
            )
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _error_payload(exc: Exception) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    if hasattr(exc, "diagnostics"):
        payload.update(exc.diagnostics())
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        payload["cause"] = {
            "error_type": type(cause).__name__,
            "message": str(cause),
        }
        if hasattr(cause, "diagnostics"):
            payload["cause"].update(cause.diagnostics())
            for key, value in cause.diagnostics().items():
                payload.setdefault(key, value)
    return payload


class _InspectionOnlyLLM(LLMProvider):
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        raise RuntimeError("inspect-input must not call an LLM provider")


if __name__ == "__main__":
    cli()
