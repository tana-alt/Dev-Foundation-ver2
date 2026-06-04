from __future__ import annotations

import json

from click.testing import CliRunner

from src.llm import LLMProvider, ProviderCallError
from src.main import cli
from src.workflow_models import FinancialMetrics


class FailingProvider(LLMProvider):
    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        raise AssertionError("structured path should be used")

    def complete_structured(self, system, user, output_model, max_tokens=2048, temperature=0.7):
        raise ProviderCallError(
            provider="test-provider",
            model="test-model",
            stage="structured_call",
            message="simulated provider failure",
        )


def test_cli_fake_smoke_writes_report_and_workflow_result(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--input-json",
            "samples/request.example.json",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    workflow_result = json.loads((out_dir / "workflow_result.json").read_text(encoding="utf-8"))

    assert workflow_result["ticker"] == "NVDA"
    assert workflow_result["fiscal_period"] == "2025Q3"
    assert workflow_result["judge_decision"]["verdict"] in {"good", "neutral", "bad"}
    for expected in (
        "NVDA",
        "2025Q3",
        "## Verdict",
        "## Positive Evidence",
        "## Negative Evidence",
        "## EPS Outlook",
        "## FCF Outlook",
    ):
        assert expected in report


def test_cli_run_writes_error_artifact_for_local_workflow_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("src.main.get_provider", lambda: FailingProvider())

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--api-url",
            "local",
            "--input-json",
            "samples/request.example.json",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code != 0
    error = json.loads((out_dir / "workflow_error.json").read_text(encoding="utf-8"))
    assert error["error_type"] in {
        "AgentProviderCallError",
        "ParallelAgentExecutionError",
    }
    assert error["agent_name"] == "EarningsQualityAnalyst"
    assert error["provider"] == "test-provider"
    assert error["model"] == "test-model"
    assert error["stage"] == "structured_call"


def test_cli_fake_smoke_accepts_document_files(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--input-json",
            "samples/request.document-files.example.json",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    report = (out_dir / "report.md").read_text(encoding="utf-8")
    workflow_result = json.loads((out_dir / "workflow_result.json").read_text(encoding="utf-8"))
    assert workflow_result["ticker"] == "NVDA"
    assert workflow_result["judge_decision"]["verdict"] in {"good", "neutral", "bad"}
    assert "## Negative Evidence" in report


def test_inspect_input_writes_audit_without_calling_llm(monkeypatch, tmp_path):
    def fail_provider(*args, **kwargs):
        raise AssertionError("inspect-input must not instantiate or call an LLM provider")

    monkeypatch.setattr("src.main.get_provider", fail_provider)

    payload_path = tmp_path / "request.json"
    payload_path.write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "fiscal_period": "2025Q3",
                "financial_metrics": {
                    "ticker": "NVDA",
                    "fiscal_period": "2025Q3",
                    "eps": 0.81,
                    "eps_consensus": 0.75,
                    "revenue": 35_000_000_000,
                    "revenue_consensus": 33_000_000_000,
                },
                "document_sections": [
                    {
                        "section_id": "deck:p4:section-1",
                        "source_ref": {
                            "source_id": "deck:p4:section-1",
                            "source_type": "earnings_presentation",
                            "document_id": "deck",
                            "section_id": "deck:p4:section-1",
                            "page": 4,
                            "title": "Investor presentation",
                        },
                        "heading": "Investor presentation page 4",
                        "text": "Q2 FY2027 outlook: revenue is expected to be approximately $28 billion.",
                        "start_page": 4,
                        "end_page": 4,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "audit"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "inspect-input",
            "--input-json",
            str(payload_path),
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert not (out_dir / "workflow_result.json").exists()
    assert not (out_dir / "report.md").exists()

    guidance_audit = json.loads((out_dir / "guidance_audit.json").read_text(encoding="utf-8"))
    routing_report = json.loads((out_dir / "routing_report.json").read_text(encoding="utf-8"))
    guidance_report = next(
        report for report in routing_report if report["agent_name"] == "GuidanceAnalyst"
    )

    assert guidance_audit["status"] == "found"
    assert guidance_audit["candidate_section_ids"] == ["deck:p4:section-1"]
    assert guidance_report["routed_section_ids"] == ["deck:p4:section-1"]


def test_inspect_input_cli_builds_temporal_yfinance_payload(monkeypatch, tmp_path):
    def fail_provider(*args, **kwargs):
        raise AssertionError("inspect-input must not instantiate or call an LLM provider")

    monkeypatch.setattr("src.main.get_provider", fail_provider)
    monkeypatch.setattr(
        "src.workflow._fetch_consensus",
        lambda *args, **kwargs: FinancialMetrics(
            ticker="NVDA",
            fiscal_period="2025Q3",
            earnings_date="2025-11-19",
            period_end_date="2025-10-31",
            source_provider="yfinance",
            source_row_date="2025-11-19",
            source_table_column_date="2025-10-31",
            eps=0.81,
            eps_consensus=0.75,
            revenue=35_000_000_000,
            temporal_snapshots={
                "reported_period_actuals": {"metrics": {"eps": 0.81}},
                "prior_period_actuals": {"metrics": {"eps": 0.73}},
                "pre_earnings_consensus": {"metrics": {"eps_consensus": 0.75}},
            },
        ),
    )

    runner = CliRunner()
    out_dir = tmp_path / "audit"
    result = runner.invoke(
        cli,
        [
            "inspect-input",
            "--ticker",
            "NVDA",
            "--fiscal-period",
            "2025Q3",
            "--target-earnings-date",
            "2025-11-19",
            "--target-period-end-date",
            "2025-10-31",
            "--prior-fiscal-period",
            "2025Q2",
            "--document-file",
            "tests/fixtures/sample_presentation.txt",
            "--document-id",
            "sample-presentation",
            "--document-fiscal-period",
            "2025Q3",
            "--out",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    temporal_summary = json.loads(
        (out_dir / "temporal_input_summary.json").read_text(encoding="utf-8")
    )
    assert temporal_summary["target_earnings_date"] == "2025-11-19"
    assert temporal_summary["target_period_end_date"] == "2025-10-31"
    assert temporal_summary["selected_yfinance_row_date"] == "2025-11-19"
    assert temporal_summary["selected_yfinance_table_column_date"] == "2025-10-31"
    assert (out_dir / "metric_snapshots.json").exists()
    assert (out_dir / "temporal_validation.json").exists()


def test_inspect_input_strict_guidance_rejects_not_found(monkeypatch, tmp_path):
    def fail_provider(*args, **kwargs):
        raise AssertionError("inspect-input must not instantiate or call an LLM provider")

    monkeypatch.setattr("src.main.get_provider", fail_provider)

    payload_path = tmp_path / "request.json"
    payload_path.write_text(
        json.dumps(
            {
                "ticker": "NVDA",
                "fiscal_period": "2025Q3",
                "financial_metrics": {
                    "ticker": "NVDA",
                    "fiscal_period": "2025Q3",
                    "eps": 0.81,
                    "eps_consensus": 0.75,
                },
                "document_sections": [
                    {
                        "section_id": "filing:eps",
                        "source_ref": {
                            "source_id": "filing:eps",
                            "source_type": "filing",
                            "document_id": "10q-2025q3",
                            "section_id": "eps",
                        },
                        "heading": "EPS",
                        "text": "Diluted EPS exceeded consensus.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "inspect-input",
            "--input-json",
            str(payload_path),
            "--out",
            str(tmp_path / "audit"),
            "--strict-guidance",
        ],
    )

    assert result.exit_code != 0
    assert "Strict guidance inspection requires" in result.output
