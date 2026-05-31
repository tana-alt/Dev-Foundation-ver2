from __future__ import annotations

import json

from click.testing import CliRunner

from src.main import cli


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
