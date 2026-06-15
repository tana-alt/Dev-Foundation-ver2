---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-06-08
---

# Agent Operationalization 9.5 Hardening Reference

Use this reference when a task involves context-slimming score, robustness
status semantics, checker result envelopes, source snapshots, auditability, hook
promotion maturity, canonical fixtures, or a 9.5+ quality claim.

## Trigger

Open this reference when:

- a task names the Agent Operationalization 9.5 hardening pack;
- a context budget exception or budget override is needed;
- a checker result must distinguish pass, fail, not applicable, missing required
  context, and not run;
- a source snapshot lock or audit trail index is required;
- a final handoff audit or operational scorecard claim is made;
- hook promotion needs phase maturity or false-positive review evidence.

Do not open this reference for routine context scoping, ordinary review records,
small template edits, command selection, or Git mechanics unless hardening
semantics are specifically in scope.

## Added Records

The hardening layer adds reusable templates:

```text
templates/budget-override-record.yaml
templates/check-result-envelope.yaml
templates/phase-gate-matrix.yaml
templates/source-snapshot-lock.yaml
templates/audit-trail-index.yaml
templates/operational-scorecard.yaml
```

Completed records belong under the owning `artifact/<project_id>/` surface, not
in runtime queues, logs, dashboards, or root-level source-pack folders.

## Context Slimming

The default budget is the context budget block in
`.agents/skills/scope-routing-governance/SKILL.md` (single source of truth;
do not restate it here).

Budget overrides are allowed only when a selected skill, phase rule, or review
mode explicitly allows them. Allowed examples are wide review, security review,
final convergence, and source snapshot verification. Forbidden reasons include
"understand the repo", "searched broadly to be safe", or reading all docs/tests
to compare.

Use `templates/budget-override-record.yaml` when a default limit is exceeded.
The record must include the base budget, requested budget, reason, allowed-by
refs, scope controls that still forbid secrets/runtime/broad scans, narrowed
refs, and a decision.

## Checker Status Taxonomy

All operational checkers use this status set:

```text
pass
fail
not_applicable
required_context_missing
not_run
```

`not_applicable` means the check is genuinely outside the task. It is not the
same as missing required context. `required_context_missing` and `not_run`
cannot support completion unless carried as residual risk or rework with source
refs and next-flow seed.

Use `templates/check-result-envelope.yaml` for normalized checker output. Every
non-pass result needs reason, severity, evidence, and next action.

## Phase Gate Matrix

Use `templates/phase-gate-matrix.yaml` before hook promotion. Maturity states:

```text
not_started
templates_added
checker_added
tests_added
make_target_added
false_positive_reviewed
pre_commit_ready
pre_push_ready
hook_wired
```

Hook promotion requires checker, tests, Make target, and false-positive review.
Full-gate promotion also requires negative and required-context-missing
fixtures. Missing maturity evidence is residual risk or rework, not a silent
pass.

## Source Snapshots And Audit Trail

Important records require source snapshot locking:

```text
context-scope manifest
budget override
residual-risk carryover
change-impact classification
review assignment
review records
fix handoff
traceability matrix
convergence decision
final handoff
audit trail index
```

Use `templates/source-snapshot-lock.yaml` to pin source refs with commit,
line range, content hash, hash status, opener, reason, and required-by record.
Local important source refs should have `sha256:<hash>` with `hash_status:
present`. Unknown or unavailable hashes must be explicit and carried as risk
when important.

Use `templates/audit-trail-index.yaml` as the compact final entry point for
context scope, budget overrides, check results, verification, reviews,
traceability, convergence, residual risk, source snapshots, and final handoff.
Final handoff without an audit index cannot support a 9.5+ claim.

## Operational Scorecard

Use `templates/operational-scorecard.yaml` to claim 9.5+ quality. Dimensions:

```yaml
context_slimming:
  required_min: 9.5
robustness:
  required_min: 9.5
auditability:
  required_min: 9.5
```

A 9.5+ claim is allowed only when every dimension is at least 9.5, required
success and failure fixtures exist, no critical item is open, and no high item
lacks owner or human path. Scores must be recomputed from observed violations
where possible; manual score inflation is invalid.

Canonical fixture coverage:

```text
success_minimal
success_with_wide_review_override
fail_broad_context
fail_required_context_missing
fail_unrun_check_claimed_passed
fail_source_snapshot_missing_hash
residual_human_gate_pending
residual_deferred_implementation
```

## Acceptance

The implementation can claim 9.5+ only when:

- no broad context is accepted without explicit override;
- no required check is silently treated as not applicable;
- important records have source snapshots with hashes or explicit risk;
- final handoff has traceable verification, review, residual risk, source
  snapshot, and audit refs;
- checker results use the common envelope;
- phase maturity is recorded before hook promotion;
- canonical fixtures cover both success and failure paths.
