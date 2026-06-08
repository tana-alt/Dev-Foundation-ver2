# Workflow Core State Model

Workflow Core is the canonical state boundary for the workflow UI, Codex
execution adapters, and CommonDB context adapters. External tools attach records
to this model; they do not become the source of truth.

## States

```text
IssueCandidate
  -> Issue
  -> ImplementationProposal
  -> ApprovalDecision
  -> ApprovedWorkContract
  -> ExecutionRun
  -> VerificationResult
  -> HandoffArtifact
```

Terminal or repair states are `blocked`, `rejected`, and
`changes_requested`. A `changes_requested` record may return to
`ImplementationProposal`; `blocked` and `rejected` do not execute.

## Transition Rules

| From | Allowed next states |
|---|---|
| `issue_candidate` | `issue`, `rejected` |
| `issue` | `implementation_proposal`, `blocked`, `rejected` |
| `implementation_proposal` | `approval_decision`, `changes_requested`, `rejected`, `blocked` |
| `approval_decision` | `approved_work_contract`, `changes_requested`, `rejected`, `blocked` |
| `approved_work_contract` | `execution_run`, `blocked` |
| `execution_run` | `verification_result`, `blocked` |
| `verification_result` | `handoff_artifact`, `changes_requested`, `blocked` |
| `handoff_artifact` | none |

## Execution Boundary

An execution adapter may start only from an approved work contract. The contract
must include non-empty `source_refs`, `allowed_write_targets`, and
`verification` requirements. It must also carry `git_scope`, `denied_context`,
`human_gate`, and risk metadata so SDK, App Server, and mock runners receive the
same bounded execution surface.

The local checker rejects execution when the current status is
`changes_requested`, `blocked`, or `rejected`; when approval is missing; or when
the approved work contract is incomplete.
