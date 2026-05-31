# Debate And Judge Agent Index

This file is a review index, not a runtime prompt input.

## Runtime Prompts

- `../debate/bull_agent.md`
- `../debate/bear_agent.md`
- `../debate/judge_agent.md`

## Boundary Decision

Debate and judgment use three LLM agents:

- `BullAgent`: strongest evidence-backed good case.
- `BearAgent`: strongest evidence-backed bad or neutral case, including direct
  challenge to `BullCaseSummary`.
- `JudgeAgent`: final structured `good | neutral | bad` verdict.

Bull and Bear stay separate because opposing objectives reduce anchoring on one
balanced but shallow answer. Judge stays separate because it should compare
validated cases, not generate new arguments or Markdown.

The report renderer is deterministic Python, not an LLM agent.
