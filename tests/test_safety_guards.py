from __future__ import annotations

import pytest

from src.workflow import MarkdownRenderer, ReviewWorkflow, WorkflowValidationError
from src.workflow_models import ReviewRequest
from tests.test_workflow_api import FakeLLM, InvestmentAdviceJudgeLLM, _request_payload


class InvestmentAdviceSpecialistLLM(FakeLLM):
    def _finding_json(self, role: str) -> str:
        return (
            super()
            ._finding_json(role)
            .replace(
                f"{role} summary",
                "Investors should buy the stock.",
                1,
            )
        )


class InvestmentAdviceMarkdownRenderer(MarkdownRenderer):
    def render(self, **kwargs) -> str:
        return "You should buy the stock.\n"


def test_specialist_output_containing_buy_the_stock_fails(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    workflow = ReviewWorkflow(llm=InvestmentAdviceSpecialistLLM())

    with pytest.raises(WorkflowValidationError, match="investment-advice language"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_judge_output_containing_target_price_language_fails(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    class TargetPriceJudgeLLM(InvestmentAdviceJudgeLLM):
        def _judge_json(self) -> str:
            return super()._judge_json().replace("buy the stock", "raise the price target")

    workflow = ReviewWorkflow(llm=TargetPriceJudgeLLM())

    with pytest.raises(WorkflowValidationError, match="investment-advice language"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_final_markdown_containing_investment_advice_fails(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    workflow = ReviewWorkflow(
        llm=FakeLLM(),
        renderer=InvestmentAdviceMarkdownRenderer(),
    )

    with pytest.raises(WorkflowValidationError, match="markdown_report contains"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_non_advice_disclaimer_continues_to_render(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    response = ReviewWorkflow(llm=FakeLLM()).run(ReviewRequest.model_validate(_request_payload()))

    assert "not investment advice" in response.markdown_report
    assert response.is_investment_advice is False
