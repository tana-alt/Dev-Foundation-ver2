# Financial Agent Index

This file is a review index, not a runtime prompt input.

## Runtime Prompts

- `../financial/earnings_quality_analyst.md`
- `../financial/cash_flow_risk_analyst.md`

## Boundary Decision

Financial analysis uses two LLM agents:

- `EarningsQualityAnalyst`: EPS quality plus P&L profitability context.
- `CashFlowRiskAnalyst`: CFS/FCF context plus balance-sheet risk context.

The older four-way split of EPS, P&L, CFS, and BS is not used as the runtime
prompt design. It is too expensive for an intern MVP because EPS/P&L and CFS/BS
each duplicate context heavily.

What stays independent:

- accounting earnings and operating structure are separate from cash generation
  and financial constraint
- EPS and FCF outlooks remain separate fields in downstream outputs
- Bull, Bear, and Judge still receive both financial perspectives separately

What is intentionally not an LLM agent:

- financial API retrieval
- financial metric calculation
- document sectioning
- evidence aggregation
- Markdown rendering
