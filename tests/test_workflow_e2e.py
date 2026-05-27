from __future__ import annotations

from src.llm import FakeProvider, get_provider
from src.workflow import ReviewWorkflow
from src.workflow_models import ReviewRequest
from tests.test_workflow_api import _request_payload


def test_fake_provider_factory(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    assert isinstance(get_provider(), FakeProvider)


def test_fake_provider_runs_seven_agent_workflow_without_keys(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    provider = FakeProvider()
    response = ReviewWorkflow(provider).run(ReviewRequest.model_validate(_request_payload()))

    assert len(provider.calls) == 7
    assert provider.calls.count("EarningsQualityAnalyst") == 1
    assert provider.calls.count("CashFlowRiskAnalyst") == 1
    assert provider.calls.count("ManagementIntentAnalyst") == 1
    assert provider.calls.count("GuidanceAnalyst") == 1
    assert provider.calls.count("BullAgent") == 1
    assert provider.calls.count("BearAgent") == 1
    assert provider.calls.count("JudgeAgent") == 1
    assert response.markdown_report
    for section in (
        "## Verdict",
        "## Summary",
        "## Positive Evidence",
        "## Negative Evidence",
        "## EPS Outlook",
        "## FCF Outlook",
    ):
        assert section in response.markdown_report
