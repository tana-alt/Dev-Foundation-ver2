# Plan-0008: Investment Advice Guard Expansion

## Objective

Ensure investment-advice, stock-price-forecast, target-price, and trading
recommendation language cannot pass through specialist outputs or the final
Markdown report.

## Scope

- specialist findings
- Bull and Bear cases
- Judge decision
- final `markdown_report`
- English and Japanese banned phrase patterns already present in workflow

## Out of Scope

- Financial compliance certification
- New investment analysis features
- README rewrite

## Dependencies

- `Plan-0001`

## Parallelization

Can run in parallel with `Plan-0002`, `Plan-0003`, and `Plan-0004`.

## Deliverables

- Guard application at all workflow output boundaries
- Negative tests for specialist and final report contamination

## Acceptance Criteria

- Specialist output containing `buy the stock` fails.
- Judge output containing target-price language fails.
- Final Markdown containing banned investment advice language fails.
- Existing non-advice disclaimer continues to render.

## Commands

```bash
.venv/bin/python -m pytest tests/test_safety_guards.py -q
```

## Log

### 2026-05-27

- Branch: `safety/0008-investment-guard`
- Commits: pending commit
- Done: Applied investment-advice scanning to financial specialist findings,
  presentation specialist findings, and final Markdown output. Added negative
  tests for specialist, judge target-price, and final report contamination.
- Decisions: Treat final Markdown as an output boundary that must be scanned.
- Validation:
  - `.venv/bin/python -m pytest tests/test_safety_guards.py -q` passed with 4 tests.
  - `.venv/bin/python -m pytest tests/test_workflow_api.py -q` passed with 5 tests.
- Risks / Follow-up: Avoid false positives for source-text quotes unless they
  are converted into agent advice.
