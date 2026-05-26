import pytest
from pydantic import ValidationError

from src.models import DebatePoint, Verdict
from src.structured import parse_model, parse_model_list, strip_json_fence


def test_strip_json_fence_accepts_markdown_json_block():
    text = '```json\n{"label": "GOOD"}\n```'

    assert strip_json_fence(text) == '{"label": "GOOD"}'


def test_parse_model_validates_llm_json():
    verdict = parse_model(
        Verdict,
        """
        {
          "label": "MIXED",
          "confidence": 0.55,
          "one_liner": "The print had both strengths and quality concerns.",
          "rationale": "The EPS beat was positive, but the evidence is not one-sided.",
          "eps_surprise_assessment": "The surprise needs quality checks before calling it good."
        }
        """,
    )

    assert verdict.label == "MIXED"


def test_parse_model_rejects_uncontracted_json_fields():
    with pytest.raises(ValidationError):
        parse_model(
            Verdict,
            """
            {
              "label": "GOOD",
              "confidence": 0.9,
              "one_liner": "Strong beat.",
              "rationale": "Revenue and EPS both beat consensus.",
              "eps_surprise_assessment": "The beat appears high quality.",
              "trading_signal": "BUY"
            }
            """,
        )


def test_parse_model_list_validates_each_item():
    points = parse_model_list(
        DebatePoint,
        """
        [
          {
            "topic": "Was EPS quality operating-driven?",
            "bull_view": "Margins improved.",
            "bear_view": "Tax helped the print."
          }
        ]
        """,
    )

    assert points[0].needs_resolution is True
