---
schema_version: "0.1"
record_type: specification_packet
status: approved_for_freeze
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-OBSIDIAN-COMMONDB-CONTRACT-INTEGRATION-001
created_at: "2026-06-09"
goal_ref: user_request:2026-06-09-obsidian-commondb-contract-integration
---

# Obsidian CommonDB Contract Integration Spec

## Purpose

Define the observable contract that safely connects Obsidian-side
`approved_memo` and `useful_source` intent with CommonDB bounded search and
searchability approval for Workflow Core.

Workflow Core remains the state authority. Obsidian and CommonDB may contribute
bounded context, intent markers, source refs, snippets, summaries, and approval
evidence, but they must not approve workflow state transitions, redefine
contracts, satisfy verification, or mark completion.

## Source Refs

- `AGENTS.md`
- `docs/01-agent-operating-contract.md`
- `docs/02-output-verification-contract.md`
- `docs/03-repo-boundary-and-storage-contract.md`
- `docs/reference/specification-workflow-reference.md`
- `docs/reference/packet-evidence-and-rework-reference.md`
- `artifact/workflow-ui-commondb-20260608/output/docs/commondb-context-adapter-contract.md`
- `artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md#REQ-006`
- `artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md#REQ-008`
- `artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md#REQ-009`
- `artifact/workflow-ui-commondb-20260608/output/reviews/app-server-thread-alignment-backend-final-handoff-20260609.yaml`
- `src/workflow_adapters/commondb_context_adapter.py`
- `tests/workflow_adapters/test_commondb_context_adapter.py`
- `user_assertion:2026-06-09-obsidian-commondb-side-complete`

## Authority Model

- Workflow Core is the canonical authority for workflow state, approved goals,
  contracts, verification status, handoff status, scope amendment, and
  completion.
- Obsidian intent is advisory until Workflow Core records an explicit,
  bounded approval state.
- CommonDB context is advisory until Workflow Core accepts a bounded
  `context_result` for the current workflow scope.
- Search permission and searchability approval are separate states.
- Human-gated actions remain blocked unless a later approved contract explicitly
  authorizes them.

## Requirements

### REQ-OCI-001 Source Intent Intake

Workflow Core must accept only explicit source intent for Obsidian-related
CommonDB integration, limited to `approved_memo` and `useful_source` intent.

Observable outcome: a workflow can distinguish eligible source intent from
ordinary notes, raw bodies, logs, or unrelated source material before any
CommonDB search or searchability decision is considered.

Acceptance criteria:

- AC-OCI-001: Source intent records identify whether the candidate is
  `approved_memo` or `useful_source`.
- AC-OCI-002: Source intent records carry stable source refs, bounded summaries,
  and decision/evidence refs only.
- AC-OCI-003: Source intent records do not include raw memo bodies, vault paths,
  local paths, corpus internals, vector payloads, embeddings, browser sessions,
  raw logs, credentials, tokens, or secrets.
- AC-OCI-004: Missing, ambiguous, unsupported, or unsafe source intent is
  represented as `blocked` or rejected and cannot silently become searchable
  context.

### REQ-OCI-002 Eligibility For Approved Memo And Useful Source

Workflow Core must determine eligibility before accepting any source as an
`approved_memo` or `useful_source` candidate for CommonDB use.

Observable outcome: only explicitly eligible source refs can be searched within
scope or considered for later searchability approval.

Acceptance criteria:

- AC-OCI-005: Eligibility requires an explicit source intent, bounded source
  refs, a current workflow or goal scope, denied-context categories, and an
  evidence ref for the approval decision.
- AC-OCI-006: `approved_memo` eligibility confirms that the human approved a
  memo-derived summary or ref for workflow use, not that a raw memo body may be
  stored.
- AC-OCI-007: `useful_source` eligibility confirms that the source is relevant
  to the current goal or contract scope, not that it may be globally indexed.
- AC-OCI-008: Ineligible, stale, missing, or policy-denied sources remain
  unavailable to execution and completion checks.

### REQ-OCI-003 Search Permission And Searchability Approval Separation

Workflow Core must separate bounded search permission from searchability or
indexing approval.

Observable outcome: allowing a source to be searched for the current goal does
not make that source searchable, indexed, migrated, or reusable outside the
approved scope.

Acceptance criteria:

- AC-OCI-009: Search permission is scoped to a current goal, approved source
  refs, bounded snippets, summaries, and denied-context categories.
- AC-OCI-010: Searchability approval is a separate human-gated state that
  applies only to eligible `approved_memo` and `useful_source` records within an
  approved destination scope.
- AC-OCI-011: A record with search permission but no searchability approval
  cannot be treated as indexed, migrated, or reusable beyond the current
  workflow scope.
- AC-OCI-012: Searchability approval cannot authorize raw body storage, vector
  payload persistence, vault/corpus internals, local path storage, Obsidian
  write-back, or external writes unless a later human-approved contract
  explicitly allows a safe transformed output.

### REQ-OCI-004 Bounded Context Result

CommonDB context made available to Workflow Core must remain bounded and
sanitized.

Observable outcome: workflow records can cite CommonDB context without storing
raw notes, storage internals, or secret-bearing material.

Acceptance criteria:

- AC-OCI-013: Accepted context results contain status, stable workflow
  identifiers, sanitized source refs, bounded snippets or summaries,
  non-secret blocked/error information, and boundary-check notes.
- AC-OCI-014: Snippets and summaries are orientation aids only and cannot
  satisfy acceptance criteria, verification, handoff, or completion without
  Workflow Core evidence.
- AC-OCI-015: Results that exceed snippet/source limits or include denied
  context are rejected before reaching an approved work contract.
- AC-OCI-016: If CommonDB is unavailable, malformed, denied, stale, or unsafe,
  the workflow records `blocked` or `error` and must not fall back to model
  memory.

### REQ-OCI-005 Obsidian Optionality And Write-Back Gate

Obsidian integration must remain optional and explicit.

Observable outcome: routine workflow operation does not require Obsidian, and
Obsidian write-back cannot occur through this integration contract.

Acceptance criteria:

- AC-OCI-017: Workflow operation can proceed without Obsidian when required
  source refs and approvals are otherwise available.
- AC-OCI-018: Obsidian write-back is blocked unless a later approved contract
  records explicit human intent, bounded destination scope, safety constraints,
  and verification expectations.
- AC-OCI-019: Obsidian write-back cannot include raw thread bodies, raw memo
  bodies, secrets, protected material, vault internals, or local paths through
  this contract.
- AC-OCI-020: Obsidian absence, unavailable refs, or write-back denial is
  visible as optional, blocked, or rejected state and cannot be treated as
  completion failure unless the approved goal required it.

### REQ-OCI-006 Rejection And Blocked States

The integration must represent unsafe or unavailable context as explicit
rejection, blocked, or error states.

Observable outcome: workers and reviewers can distinguish safe absence from
approved context and can trace why a source was unavailable.

Acceptance criteria:

- AC-OCI-021: Rejection or blocked states include a non-secret reason, affected
  source refs when safe, denied-context categories, and evidence refs.
- AC-OCI-022: Rejection or blocked states do not include raw memo bodies, raw
  source bodies, raw logs, local paths, vault/corpus internals, vector payloads,
  embeddings, browser sessions, credentials, tokens, or secrets.
- AC-OCI-023: Blocked CommonDB or Obsidian context cannot be promoted into a
  work contract, verification result, handoff acceptance, or completion state.

### REQ-OCI-007 Completion And Scope Guard

Completion must remain tied to the approved goal, acceptance criteria,
verification expectations, and human gates.

Observable outcome: useful CommonDB or Obsidian-side context cannot make an
unapproved or incomplete workflow appear complete.

Acceptance criteria:

- AC-OCI-024: Completion review shows the approved goal, requirement/acceptance
  status, verification status, accepted context refs, unresolved context
  blocks, human gates, and residual risks.
- AC-OCI-025: New source intent, broader search permission, searchability
  approval, Obsidian write-back, indexing, or external write scope requires
  contract revision or specification amendment before it can affect completion.
- AC-OCI-026: CommonDB and Obsidian records cannot override Workflow Core state,
  approvals, contracts, verification status, handoff status, scope amendments,
  or completion.

### REQ-OCI-008 Audit And Evidence Refs

The integration must leave a sanitized audit trail of decisions and evidence.

Observable outcome: another worker can review what was approved, rejected,
blocked, searched, or deferred without reading raw bodies or external storage.

Acceptance criteria:

- AC-OCI-027: Audit records cite source refs, decision refs, evidence refs,
  verification refs, human-gate status, and residual risk.
- AC-OCI-028: Audit records distinguish observed facts, inferences, decisions,
  skipped checks, blocked checks, and not-applicable implementation tests.
- AC-OCI-029: Audit records omit raw memo bodies, vault/corpus/qdrant internals,
  local paths, embeddings/vectors, browser sessions, raw logs, credentials,
  tokens, and secrets.

## Non-Goals

- Implementing code changes.
- Running live CommonDB search, indexing, searchable migration, or external
  writes.
- Performing Obsidian vault reads, vault writes, or write-back.
- Persisting raw memo bodies, raw thread bodies, vault/corpus/qdrant internals,
  local paths, vector payloads, embeddings, browser sessions, raw logs, or
  secrets.
- Making Obsidian or CommonDB a workflow state authority.
- Defining file layout, function names, class names, library choices, branch
  strategy, worktree commands, or test commands.

## Human Gates

The following actions require later explicit human approval and are not
authorized by this specification freeze:

- Live CommonDB search.
- CommonDB indexing or searchable migration.
- Searchability approval execution beyond record preparation.
- Obsidian vault read/write or write-back.
- External writes.
- Handling secrets or secret-bearing material.
- Protected Git, merge, deployment, release, dependency, infrastructure, or
  CI/CD changes.

## Verification Expectations

- Specification review confirms traceability to the named source refs and the
  absence of implementation-policy leakage.
- Freeze records the approved requirement and acceptance-criteria IDs.
- Lane mapping keeps the next implementation lane planned and unassigned.
- YAML records parse successfully.
- Manifest refs point to existing files.
- Placeholder and denied-content scans are attempted and honestly recorded.
- Implementation tests are not applicable for this records-only phase.
