from __future__ import annotations

from src.workflow import MarkdownRenderer, ReviewWorkflow
from src.workflow_models import ReviewRequest
from src.workflow_validation import WorkflowValidationGate
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


def test_specialist_output_containing_buy_the_stock_warns(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    workflow = ReviewWorkflow(llm=InvestmentAdviceSpecialistLLM())

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert response.warnings
    assert "potential investment-advice language" in response.warnings[0]
    assert "## Warnings" in response.markdown_report


def test_judge_output_containing_target_price_language_warns(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    class TargetPriceJudgeLLM(InvestmentAdviceJudgeLLM):
        def _judge_json(self) -> str:
            return super()._judge_json().replace("buy the stock", "raise the price target")

    workflow = ReviewWorkflow(llm=TargetPriceJudgeLLM())

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert any("price target" in warning for warning in response.warnings)
    assert "## Warnings" in response.markdown_report


def test_final_markdown_containing_investment_advice_warns(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    workflow = ReviewWorkflow(
        llm=FakeLLM(),
        renderer=InvestmentAdviceMarkdownRenderer(),
    )

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert any("markdown_report" in warning for warning in response.warnings)
    assert "## Warnings" in response.markdown_report


def test_business_condition_hold_acronym_is_not_investment_advice():
    WorkflowValidationGate().validate_no_investment_advice_text(
        "Conditions needed: hold GB200 ramp timing and margin discipline.",
        "bull_case.conditions_needed[0]",
    )


def test_ticker_stock_hold_language_still_fails():
    validator = WorkflowValidationGate()

    validator.validate_no_investment_advice_text(
        "Investors should hold NVDA shares.",
        "judge_decision.summary",
    )

    assert validator.warnings
    assert "judge_decision.summary" in validator.warnings[0]


def test_non_advice_disclaimer_continues_to_render(monkeypatch):
    monkeypatch.setattr("src.workflow._fetch_consensus", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.workflow._fetch_filing_html", lambda *args, **kwargs: "")

    response = ReviewWorkflow(llm=FakeLLM()).run(ReviewRequest.model_validate(_request_payload()))

    assert "not investment advice" in response.markdown_report
    assert response.is_investment_advice is False
    assert response.warnings == []
