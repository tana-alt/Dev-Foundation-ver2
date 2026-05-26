"""Basic import + structural tests. Real LLM calls are NOT made here —
those should live in an evaluation harness (see README §2.4 "Rabbit
holes": regression set on 5 prints).
"""
from src.agents import BearAnalyst, BullAnalyst, MacroAnalyst, QuantsAnalyst
from src.models import AnalystOpinion, EarningsContext, Verdict


def test_models_roundtrip():
    ctx = EarningsContext(
        ticker="NVDA", quarter="2025Q3",
        eps_actual=0.81, eps_consensus=0.75, eps_surprise_pct=8.0,
    )
    assert ctx.eps_surprise_pct == 8.0


def test_analyst_roles_distinct():
    classes = [BullAnalyst, BearAnalyst, QuantsAnalyst, MacroAnalyst]
    roles = {c.role for c in classes}
    assert roles == {"bull", "bear", "quants", "macro"}


def test_verdict_labels():
    v = Verdict(
        label="GOOD", confidence=0.7,
        one_liner="x", rationale="y", eps_surprise_assessment="z",
    )
    assert v.label == "GOOD"
