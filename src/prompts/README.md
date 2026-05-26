# Agent Prompt References

This directory stores prompt bases for the specialist agents used by the
earnings debate workflow. Runtime loading is agent-scoped: the orchestrator
should compose shared policies with exactly one agent prompt file.

## Runtime Agent Set

The completed LLM agent set has seven agents:

1. `EarningsQualityAnalyst`
2. `CashFlowRiskAnalyst`
3. `ManagementIntentAnalyst`
4. `GuidanceAnalyst`
5. `BullAgent`
6. `BearAgent`
7. `JudgeAgent`

Financial analysis is intentionally two agents, not four. EPS and P&L are
merged because both use the same earnings-quality, revenue, margin, segment,
tax, share-count, and one-time-item context. CFS and BS are merged because cash
generation, CapEx, working capital, liquidity, debt, and financing constraints
are tightly coupled in the FCF outlook.

Presentation, debate, and judge roles stay independent because their context and
failure modes differ: management intent can anchor too much on narrative,
guidance must compare forward targets against precomputed expectations,
Bull/Bear must argue opposite theses, and Judge must compare validated outputs
without generating a report draft.

## Runtime Composition

For each LLM call, compose:

```text
shared/global_policy.md
+ shared/evidence_policy.md
+ shared/output_policy.md
+ one agent prompt file
```

Do not load another agent's prompt or an index file into the same call.

## Files

Shared policies:

- `shared/global_policy.md`
- `shared/evidence_policy.md`
- `shared/output_policy.md`

Runtime agent prompts:

- `financial/earnings_quality_analyst.md`
- `financial/cash_flow_risk_analyst.md`
- `presentation/management_intent_analyst.md`
- `presentation/guidance_analyst.md`
- `debate/bull_agent.md`
- `debate/bear_agent.md`
- `debate/judge_agent.md`

Review-only indexes:

- `index/financial_agents.md`
- `index/presentation_agents.md`
- `index/debate_judge_agents.md`

Index files are not prompt inputs. They exist only so reviewers can see why the
agent boundaries were chosen.

## Global Rules

- Data fetching, financial calculations, document sectioning, aggregation, and
  Markdown rendering stay outside LLM agents.
- Agents receive only precomputed values and routed document sections.
- Agents return JSON only; Pydantic validation is required before handoff.
- Evidence must include a traceable `source_ref`.
- Positive and counter evidence must both be considered.
- No agent may provide stock-price forecasts, target prices, or trading advice.
