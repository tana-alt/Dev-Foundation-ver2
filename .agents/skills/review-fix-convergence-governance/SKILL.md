---
name: review-fix-convergence-governance
description: Govern narrow/wide/security reviews, fix handoff, fix review, convergence decision, and final handoff.
---

# Review Fix Convergence Governance

## Purpose

Make review, fix, re-review, convergence, and final handoff record-based rather
than conversation-based.

## Use When

- Review records are added or evaluated.
- Fix handoff is created from review findings.
- Fix review or regression review is required.
- Convergence or final handoff is in scope.

## Do Not Use When

- Task only chooses context or routes to another operational skill.
- No review, fix, or final decision surface exists.

## Read First

- `templates/change-impact-classification-record.yaml`
- `templates/narrow-review-record.yaml`
- `templates/wide-review-record.yaml`
- `templates/security-review-record.yaml`
- `templates/fix-handoff-record.yaml`
- `templates/fix-review-record.yaml`
- `templates/convergence-decision-record.yaml`
- `templates/final-handoff-record.yaml`

## Context Budget

```yaml
max_selected_skills: 2
narrow_review_max_source_refs: 6
wide_review_max_source_refs: 10
security_review_max_source_refs: 8
broad_repo_scan_allowed: false
```

## Method

1. Classify change impact.
2. Assign review modes.
3. Keep narrow, wide, and security review records separate.
4. Convert accepted findings into fix handoff with must_fix and must_not_change.
5. Run fix review with new-risk checks.
6. Update traceability matrix.
7. Produce convergence decision and final handoff.

## Output

- change impact record
- review records
- fix handoff and fix review
- convergence decision
- final handoff
- residual risk carryover if needed

## Stop / Carryover Conditions

Do not claim completion with unresolved critical/high `INC-*`, unresolved
`FIX-*`, missing required verification, or missing human decision path.
