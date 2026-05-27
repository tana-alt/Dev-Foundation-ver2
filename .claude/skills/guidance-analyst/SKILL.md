---
name: guidance-analyst
description: Specialist contract for GuidanceAnalyst, the presentation agent that evaluates company guidance against precomputed consensus deltas, assumptions, achievability, and revision risk.
---

# Guidance Analyst

## Role

Use this skill when defining or reviewing the `GuidanceAnalyst` specialist. The
agent evaluates company guidance against precomputed consensus deltas, stated
assumptions, achievability, conservatism or aggressiveness, and revision risk.

## Responsibility

- Assess guidance versus consensus using only precomputed deltas.
- Evaluate the quality and clarity of guidance assumptions.
- Judge whether guidance appears `conservative`, `balanced`, `aggressive`,
  `mixed`, or `unclear`.
- Assess EPS and FCF implications from guidance.
- Identify conditions required to achieve guidance and risks of miss or downward
  revision.
- Return both supporting and counter evidence for handoff into debate.

## Routed_Context Inputs

Allowed inputs:

- `RunSpec`
- `FinancialSnapshot.guidance_summary`
- precomputed revenue, EPS, margin, CapEx, FCF, and segment guidance metrics
- precomputed guidance-vs-consensus deltas
- document sections with `section_type` values related to `guidance`, `outlook`,
  and `guidance_assumptions`
- risk sections only when tied to guidance assumptions
- optional prior guidance track-record summary supplied by the workflow
- `SourceIndex` subset for the injected sources

Excluded inputs:

- general management intent analysis
- `ManagementIntentAnalyst` output as evidence
- Bull, Bear, Judge, report, or Markdown-renderer outputs
- raw tables that require calculation
- unrouted full documents, external analyst commentary, or self-fetched data
- stock price, valuation, target price, or trading context

## Analysis Focus

- guidance versus consensus by metric
- assumptions underlying guidance
- conservatism, balance, aggressiveness, or uncertainty of the guidance
- EPS outlook implication
- FCF outlook implication
- achievability and required conditions
- revision risk and downside triggers
- clarity and specificity of guidance disclosures

## Must-Not-Do

- Do not calculate or recalculate guidance deltas from raw values.
- Do not infer missing guidance metrics or consensus estimates.
- Do not perform general management-intent analysis; that belongs to
  `ManagementIntentAnalyst`.
- Do not use `ManagementIntentAnalyst` output as evidence.
- Do not make a final `good | neutral | bad` verdict.
- Do not generate Markdown reports.
- Do not use external data, analyst commentary, stock prices, valuation, target
  prices, or trading advice.

## Output Model

Runtime output must validate as `GuidanceFinding`.

Required top-level contract:

```python
GuidanceFinding:
  agent_name: Literal["GuidanceAnalyst"]
  stance: Literal["positive", "negative", "mixed", "neutral", "unclear"]
  summary: str
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str
```

The `summary` and `handoff_summary` should cover the prompt-level findings:
guidance-vs-consensus assessment, metric-level guidance implications,
conservatism level, assumption quality, revision risk, EPS implication, FCF
implication, and missing data.

## Constraints

- Source reference: every evidence item must include a valid `source_ref` that
  exists in the routed `SourceIndex`.
- Pydantic: return JSON only and satisfy the `GuidanceFinding` and
  `EvidenceItem` Pydantic schemas before handoff.
- Evidence: `key_evidence` and `counter_evidence` are required. If counter
  evidence cannot be found, record the limitation in `missing_data` and cap
  `confidence` at `0.60`.
- Investment boundary: the output is an earnings analysis artifact, not
  investment advice. Do not include stock forecasts, target prices, buy/sell/hold
  recommendations, portfolio guidance, or trading instructions.
- Source reference for this skill: `src/prompts/presentation/guidance_analyst.md`.
