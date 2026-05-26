# Presentation Agent Index

This file is a review index, not a runtime prompt input.

## Runtime Prompts

- `../presentation/management_intent_analyst.md`
- `../presentation/guidance_analyst.md`

## Boundary Decision

Presentation analysis uses two LLM agents:

- `ManagementIntentAnalyst`: qualitative strategy, priorities, investment and
  cost actions, and time horizon.
- `GuidanceAnalyst`: guidance versus precomputed consensus deltas, assumptions,
  achievability, and revision risk.

These are not merged because management intent and guidance analysis have
different failure modes. Management analysis can become narrative-driven, while
guidance analysis needs strict comparison against structured expectations and
assumptions.
