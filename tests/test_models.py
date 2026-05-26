import pytest
from pydantic import ValidationError

from src.models import AnalystOpinion, EarningsContext, Verdict


def test_earnings_context_normalizes_ticker():
    ctx = EarningsContext(ticker="nvda", quarter="2025Q3", eps_actual=0.81)

    assert ctx.ticker == "NVDA"


def test_earnings_context_rejects_invalid_quarter():
    with pytest.raises(ValidationError):
        EarningsContext(ticker="NVDA", quarter="2025Q5", eps_actual=0.81)


def test_models_reject_extra_fields():
    with pytest.raises(ValidationError):
        Verdict(
            label="GOOD",
            confidence=0.7,
            one_liner="Strong print.",
            rationale="EPS quality and revenue growth were both solid.",
            eps_surprise_assessment="The beat appears operating-driven.",
            unexpected="not part of the contract",
        )


def test_verdict_confidence_must_be_probability():
    with pytest.raises(ValidationError):
        Verdict(
            label="GOOD",
            confidence=1.2,
            one_liner="Strong print.",
            rationale="EPS quality and revenue growth were both solid.",
            eps_surprise_assessment="The beat appears operating-driven.",
        )


def test_analyst_opinion_requires_evidence():
    with pytest.raises(ValidationError):
        AnalystOpinion(
            role="bull",
            headline="Revenue growth accelerated.",
            key_points=["Revenue grew year over year."],
            evidence=[],
        )
