"""Orchestrator: implements the Orchestrator-Workers and Evaluator-Optimizer
patterns from Anthropic's "Building Effective Agents".

Flow:
  1. Run 4 analysts in PARALLEL (Parallelization / Sectioning pattern)
  2. Summarize their opinions into discussion points (compress context
     before passing back — context engineering)
  3. Run a second round where Bull and Bear cross-examine each point
  4. Judge agent emits the final Verdict

Critically: each agent only ever sees what it needs. The full debate
log is NOT broadcast to every agent.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import structlog

from .agents import BearAnalyst, BullAnalyst, MacroAnalyst, QuantsAnalyst
from .llm import LLMProvider
from .models import (
    AnalystOpinion,
    DebatePoint,
    EarningsContext,
    FilingSection,
    Verdict,
)
from .structured import parse_model, parse_model_list

log = structlog.get_logger()


class Orchestrator:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.analysts = [
            BullAnalyst(llm),
            BearAnalyst(llm),
            QuantsAnalyst(llm),
            MacroAnalyst(llm),
        ]

    # ------------------------------------------------------------------ Round 1
    def round_one(
        self,
        context: EarningsContext,
        sections: list[FilingSection],
    ) -> list[AnalystOpinion]:
        """Parallel fan-out to all analysts."""
        log.info("round_one.start", n_analysts=len(self.analysts))
        with ThreadPoolExecutor(max_workers=len(self.analysts)) as ex:
            futures = [
                ex.submit(a.review, context, sections) for a in self.analysts
            ]
            opinions = [f.result() for f in futures]
        log.info("round_one.done", opinions=[o.role for o in opinions])
        return opinions

    # ------------------------------------------------------------------ Extract
    def extract_debate_points(
        self,
        opinions: list[AnalystOpinion],
    ) -> list[DebatePoint]:
        """Compress the four opinions into a small set of contested points.
        This is the key context-engineering step: we never feed all four
        raw opinions back into the next round.
        """
        summary = "\n\n".join(
            f"## {o.role.upper()}\n"
            f"Headline: {o.headline}\n"
            f"Key points: {o.key_points}\n"
            f"Concerns: {o.concerns}"
            for o in opinions
        )

        system = (
            "You are the debate chair. Read the four analyst opinions and "
            "extract 2-4 SPECIFIC, contested topics where the bulls and "
            "bears (or quants) disagree or where evidence is thin. Each topic "
            "should be resolvable with more reasoning, not just opinion."
        )
        user = (
            f"{summary}\n\n"
            "Return JSON: a list of objects with fields "
            '{"topic": str, "bull_view": str|null, "bear_view": str|null}. '
            "Return ONLY the JSON array."
        )
        resp = self.llm.complete(system=system, user=user, max_tokens=1500, temperature=0.4)

        points = parse_model_list(DebatePoint, resp.text)
        log.info("debate_points.extracted", n=len(points), topics=[p.topic for p in points])
        return points

    # ------------------------------------------------------------------ Round 2
    def round_two(
        self,
        context: EarningsContext,
        points: list[DebatePoint],
    ) -> str:
        """Cross-examination on the contested points. We send the bull and
        bear analyst ONE compressed prompt about the points — not the
        full filing or each other's round-1 raw output."""
        points_text = "\n\n".join(
            f"### Topic {i+1}: {p.topic}\n"
            f"- Bull view (round 1): {p.bull_view}\n"
            f"- Bear view (round 1): {p.bear_view}"
            for i, p in enumerate(points)
        )
        system = (
            "You are moderating a cross-examination between a bull and a bear "
            "analyst. For each topic, write a short back-and-forth (3-4 turns) "
            "where each side responds to the other's strongest argument. End "
            "each topic with a one-line resolution: which side was more "
            "persuasive AND WHY. Be concise."
        )
        user = (
            f"# Context\n```json\n{context.model_dump_json(indent=2)}\n```\n\n"
            f"# Contested topics\n{points_text}"
        )
        resp = self.llm.complete(system=system, user=user, max_tokens=2500, temperature=0.6)
        log.info("round_two.done", chars=len(resp.text))
        return resp.text

    # ------------------------------------------------------------------ Verdict
    def judge(
        self,
        context: EarningsContext,
        opinions: list[AnalystOpinion],
        debate_transcript: str,
    ) -> Verdict:
        """Final synthesis. Sees: numbers, one-line summary of each opinion,
        full round-2 transcript. Does NOT see round-1 raw output."""
        opinion_lines = "\n".join(
            f"- {o.role.upper()}: {o.headline}" for o in opinions
        )
        system = (
            "You are the final judge. Decide GOOD / MIXED / BAD for this "
            "earnings print, in the CONTEXT OF EPS SURPRISE — meaning a beat "
            "against a low bar with poor quality is not GOOD, and a slight "
            "miss against a stretched bar with strong quality is not BAD. "
            "Output strict JSON only."
        )
        user = (
            f"# Pre-extracted numbers\n```json\n{context.model_dump_json(indent=2)}\n```\n\n"
            f"# Analyst stances (one-liners)\n{opinion_lines}\n\n"
            f"# Cross-examination transcript\n{debate_transcript}\n\n"
            "Return JSON with fields: label (GOOD|MIXED|BAD), confidence (0-1), "
            "one_liner, rationale (2-3 sentences), eps_surprise_assessment "
            "(quality of the surprise itself, separately from the verdict)."
        )
        resp = self.llm.complete(system=system, user=user, max_tokens=1200, temperature=0.3)

        verdict = parse_model(Verdict, resp.text)
        log.info("verdict.done", label=verdict.label, confidence=verdict.confidence)
        return verdict
