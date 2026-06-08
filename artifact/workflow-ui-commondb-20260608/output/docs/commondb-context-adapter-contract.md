# CommonDB Context Adapter Contract

## Purpose

The CommonDB context adapter gives Workflow Core bounded, sanitized context for a
workflow run without making CommonDB, a note vault, a corpus, Qdrant, local
filesystem paths, raw source bodies, terminal logs, or secrets part of this
repository boundary.

The adapter is a read adapter only. It returns workflow context records that can
be validated, rejected, or marked blocked before an execution adapter receives a
work contract.

## Transport Order

1. MCP is the primary transport for context lookup.
2. CLI is the fallback transport when MCP is unavailable.
3. HTTP is limited to health/status smoke checks unless a later approved work
   contract explicitly authorizes broader HTTP behavior.

Transport failures, unavailable context, policy denials, malformed results, and
upstream errors return a blocked or error `context_result`. They must not fall
back to model memory.

## Request Boundary

A `context_request` may contain only:

- stable workflow identifiers,
- a short task query,
- explicit `source_refs`,
- requested artifact types,
- limits for snippets and references,
- denied context categories,
- the expected adapter transport order.

A request must not contain local absolute paths, raw note bodies, raw source
files, runtime logs, vectors, embeddings, credentials, tokens, cookies, or
secret-bearing metadata.

## Result Boundary

A `context_result` may contain only:

- status: `ok`, `blocked`, or `error`,
- stable workflow identifiers,
- sanitized `source_refs`,
- bounded snippets,
- non-secret error code and message fields,
- verification notes proving the result was boundary-checked.

Snippets are for orientation only. They must be bounded, human-readable, and
free of raw source bodies, raw logs, secrets, embeddings, local paths, and
storage implementation details. Any oversized or boundary-unsafe context is
rejected before it reaches a work contract.

## Workflow Mapping

The demo lane validates this sequence:

```text
issue_candidate
  -> issue
  -> implementation_proposal
  -> approval_decision
  -> approved_work_contract
  -> execution_run
  -> verification_result
  -> handoff_artifact
```

CommonDB contributes only bounded context attached by `context_result_id` and
`source_refs`. Workflow Core remains the canonical state boundary.

## Validation Rules

- Source refs are stable identifiers, not local paths or storage internals.
- Requests and results include explicit denied context categories.
- Result snippets have maximum length and explicit source refs.
- `blocked` and `error` results are valid workflow context states.
- No model-memory fallback is allowed.
- Execution is valid only after proposal approval and an approved work contract.
- Verification and handoff records must refer to sanitized artifacts only.
