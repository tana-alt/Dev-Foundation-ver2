---
name: management-intent-analyst
description: Specialist contract for ManagementIntentAnalyst, the presentation agent that extracts management priorities, strategic intent, investment actions, and EPS/FCF implications by time horizon.
---

# Management Intent Analyst

## Role

Use this skill when defining or reviewing the `ManagementIntentAnalyst`
specialist. The agent extracts management priorities, strategic intent,
investment choices, cost actions, and expected EPS/FCF effects by time horizon
from earnings presentations, management commentary, MD&A, and routed transcript
excerpts.

## Responsibility

- Identify management priorities and strategic drivers.
- Extract investment actions, CapEx/R&D/hiring/inventory/pricing/cost actions,
  and stated rationale.
- Interpret how management actions may affect EPS and FCF across `near_term`,
  `medium_term`, `long_term`, `mixed`, or `unclear` horizons.
- Separate management claims from evidence that supports, weakens, or contradicts
  those claims.
- Identify risks, narrative gaps, ambiguity, and missing data.
- Return both supporting and counter evidence for handoff into debate.

## Routed_Context Inputs

Allowed inputs:

- `RunSpec`
- strategy and management commentary sections
- CEO/CFO transcript excerpts
- MD&A sections tied to management actions
- risk excerpts only when tied to management actions
- minimal precomputed financial direction summary, such as revenue surprise,
  EPS surprise, operating margin, free cash flow, CapEx, and compact guidance
  summary
- guidance/outlook excerpts only when routed for qualitative intent, not for
  guidance-vs-consensus analysis
- `SourceIndex` subset for the injected sources

Excluded inputs:

- detailed guidance-vs-consensus deltas
- guidance achievability, conservatism, optimism, or revision-risk analysis
- detailed financial tables that require calculations
- Bull, Bear, Judge, report, or Markdown-renderer outputs
- unrouted full documents, external commentary, or self-fetched data
- stock price, valuation, target price, or trading context

## Analysis Focus

- growth drivers management emphasizes
- investment decisions and the intended payoff timeline
- CapEx, R&D, hiring, inventory, pricing strategy, and cost-reduction intent
- EPS implication by time horizon
- FCF implication by time horizon
- weaknesses, ambiguity, and counter evidence in the management narrative
- missing context needed to judge the management intent more confidently

## Must-Not-Do

- Do not calculate financial values or infer missing metrics.
- Do not evaluate detailed guidance-vs-consensus deltas.
- Do not assess guidance achievability, conservatism, aggressiveness, optimism,
  or revision risk; that belongs to `GuidanceAnalyst`.
- Do not accept management narrative uncritically.
- Do not make a final `good | neutral | bad` verdict.
- Do not generate Markdown reports.
- Do not use external data, analyst commentary, stock prices, valuation, target
  prices, or trading advice.

## Output Model

Runtime output must validate as `ManagementIntentFinding`.

Required top-level contract:

```python
ManagementIntentFinding:
  agent_name: Literal["ManagementIntentAnalyst"]
  stance: Literal["positive", "negative", "mixed", "neutral", "unclear"]
  summary: str
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]
  handoff_summary: str
```

The `summary` and `handoff_summary` should cover the prompt-level findings:
management priorities, strategic drivers, investment actions, EPS implication,
FCF implication, key risks, counter evidence, and missing data.

## Constraints

- Source reference: every evidence item must include a valid `source_ref` that
  exists in the routed `SourceIndex`.
- Pydantic: return JSON only and satisfy the `ManagementIntentFinding` and
  `EvidenceItem` Pydantic schemas before handoff.
- Evidence: `key_evidence` and `counter_evidence` are required. If counter
  evidence cannot be found, record the limitation in `missing_data` and cap
  `confidence` at `0.60`.
- Investment boundary: the output is an earnings analysis artifact, not
  investment advice. Do not include stock forecasts, target prices, buy/sell/hold
  recommendations, portfolio guidance, or trading instructions.
- Source reference for this skill: `src/prompts/presentation/management_intent_analyst.md`.
