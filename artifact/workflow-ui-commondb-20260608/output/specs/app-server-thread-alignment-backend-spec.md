---
schema_version: "0.1"
record_type: specification_packet
status: approved
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-APP-SERVER-THREAD-ALIGNMENT-BACKEND-001
created_at: "2026-06-09"
source_refs:
  - AGENTS.md
  - docs/01-agent-operating-contract.md
  - docs/02-output-verification-contract.md
  - docs/03-repo-boundary-and-storage-contract.md
  - docs/reference/specification-workflow-reference.md
  - docs/reference/packet-evidence-and-rework-reference.md
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md#REQ-007
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md#REQ-009
  - artifact/workflow-ui-commondb-20260608/output/specs/codex-app-vertical-integration-spec.md#REQ-008
  - artifact/workflow-ui-commondb-20260608/output/specs/codex-app-vertical-integration-spec.md#REQ-009
  - src/workflow_adapters/codex_app_server_adapter.py
  - tests/workflow_adapters/test_codex_app_server_adapter.py
---

# App Server Thread Alignment Backend Specification

## Purpose

Define the backend behavior required to complete the mock-safe Codex App Server
thread surface and align it with main lane workflow authority.

The backend slice makes Codex App Server thread, event, project, and artifact
links observable through sanitized records. It must not make Codex App Server,
CommonDB, Obsidian, Git, or deployment systems authoritative for Workflow Core
state.

## Scope

### In Scope

- Mock-safe Codex App Server thread link records.
- Mock-safe Codex App Server project and artifact link records.
- Bounded event records that can explain thread status, gate status, verification
  status, handoff status, and scope-amendment status to main lane.
- Observable alignment between App Server records and approved goal, approved
  contract, verification, handoff, and completion guards.
- Sanitized refs, bounded summaries, and explicit human-gate status.

### Out Of Scope

- Live Codex App Server writes or live bridge execution.
- CommonDB live indexing, live search, or searchable migration.
- Obsidian write-back.
- Merge, deploy, release, protected Git actions, CI/CD changes, dependency
  changes, database/schema changes, infrastructure changes, or irreversible
  actions.
- Raw Codex thread bodies, raw artifact contents, raw terminal logs, browser
  sessions, credentials, tokens, secrets, vector payloads, or local runtime
  state.
- Treating App Server events as direct approval, execution, or completion
  authority.

## Authority Model

Workflow Core remains the canonical authority for approved goals, proposal
status, execution contracts, human gates, verification, handoff, scope
amendments, and completion. Codex App Server records are supporting link and
event observations only.

Main lane alignment means that App Server thread, event, project, and artifact
links make the current workflow status observable without bypassing Workflow
Core authority or changing the approved goal, contract, or completion guard.

## Requirements

### REQ-BE-001 Thread Link Observability

The backend must represent a Codex App thread link as a sanitized workflow
record that is useful for navigation and status inspection without storing raw
conversation content.

Observable outcome: a workflow can show whether a Codex App thread is linked,
missing, gated, or blocked while Workflow Core remains the state authority.

Acceptance criteria:

- AC-BE-001: A thread link record includes project identity, run or workflow
  identity, opaque thread ref, transport or link channel, and state-authority
  marker.
- AC-BE-002: A thread link record explicitly states that raw thread bodies,
  credentials, browser sessions, and local runtime state are not stored.
- AC-BE-003: Invalid or multi-line external refs are rejected instead of being
  recorded.

### REQ-BE-002 Project And Artifact Link Observability

The backend must represent project-scoped Codex App links and artifact refs as
bounded navigation/status records without becoming chat or artifact storage.

Observable outcome: a workflow can surface the relevant Codex App project,
conversation, and artifact review links from opaque refs while detailed review
stays in Codex App.

Acceptance criteria:

- AC-BE-004: A project link record includes project identity, workflow identity,
  opaque thread ref, opaque Codex App link ref, optional supported artifact refs,
  link status, bounded latest-event summary, and state-authority marker.
- AC-BE-005: Project link records explicitly state that raw thread bodies,
  artifact contents, credentials, browser sessions, and local runtime state are
  not stored.
- AC-BE-006: Unsupported artifact refs are rejected instead of being recorded.

### REQ-BE-003 Event Projection For Main Lane Alignment

The backend must represent App Server events as bounded observations that main
lane can use to inspect workflow progress, gate state, verification state,
handoff state, and scope-amendment state.

Observable outcome: App Server event records explain what was observed or
blocked, but do not themselves approve work, start execution, satisfy
verification, or complete the workflow.

Acceptance criteria:

- AC-BE-007: Event records include project identity, run identity, event ID,
  supported event kind, status, bounded summary, opaque external event ref, and
  state-authority marker.
- AC-BE-008: Unsupported event kinds, unsupported statuses, unbounded summaries,
  and invalid external refs are rejected.
- AC-BE-009: Event records explicitly state that raw thread bodies and raw
  terminal logs are not stored.
- AC-BE-010: Events that imply approval, verification, handoff, or scope
  amendment remain observations until Workflow Core records the corresponding
  approved goal, approved contract, verification evidence, handoff evidence, or
  approved amendment.

### REQ-BE-004 Workflow Core Authority Preservation

The backend must preserve Workflow Core as the only authority for approved goal,
approved contract, verification, handoff, scope amendment, and completion
decisions.

Observable outcome: App Server thread and event records can be present while
completion is still blocked when approved acceptance criteria, verification, or
human gates remain unmet.

Acceptance criteria:

- AC-BE-011: Link or event records cannot override approved goal state,
  execution-contract approval, verification status, handoff status, human-gate
  status, or completion status.
- AC-BE-012: Completion remains unavailable when required approved acceptance
  criteria, verification expectations, unresolved items, or human gates are
  unmet, even if App Server events show useful adjacent progress.
- AC-BE-013: Scope expansion remains blocked or changes-requested unless an
  approved specification amendment or approved contract revision exists.

### REQ-BE-005 Human Gate Preservation

The backend must keep live integrations and protected side effects human-gated
for this slice.

Observable outcome: attempting to use a live bridge, live CommonDB integration,
Obsidian write-back, or protected operation without explicit approval produces a
blocked or skipped status rather than a side effect.

Acceptance criteria:

- AC-BE-014: Live Codex App Server bridge execution is blocked without explicit
  human approval.
- AC-BE-015: CommonDB live search, CommonDB indexing, searchable migration,
  Obsidian write-back, merge, deploy, release, protected Git actions, and other
  protected side effects remain out of scope for this backend slice.
- AC-BE-016: Human-gated operations report gate status without embedding secret
  material, raw bodies, or protected output.

### REQ-BE-006 Sanitized Evidence Contract

The backend must expose enough sanitized evidence for implementation review and
main lane convergence without storing protected content.

Observable outcome: reviewers can trace thread, project, event, gate,
verification, handoff, and completion-alignment behavior through refs and
bounded summaries.

Acceptance criteria:

- AC-BE-017: Records use opaque refs, bounded summaries, status values, and
  evidence refs instead of raw bodies or logs.
- AC-BE-018: Records can be inspected to confirm App Server observations did
  not seize Workflow Core authority.
- AC-BE-019: Review evidence can distinguish passed, failed, blocked, skipped,
  and not-applicable checks without relying on runtime state.

## Verification Expectations

Before implementation is accepted, verification should prove:

- Thread link records preserve Workflow Core authority and exclude raw bodies,
  credentials, browser sessions, and local runtime state.
- Project link records use opaque refs, bounded summaries, supported artifact
  refs, and no raw artifact contents.
- Event records reject unsupported event kinds, unsupported statuses, unbounded
  summaries, invalid refs, and raw log/body storage.
- Approval, verification, handoff, and scope-amendment events remain
  observations until Workflow Core has matching authoritative records.
- Completion cannot be claimed through App Server event presence or goal drift.
- Live Codex App Server bridge execution and other protected side effects remain
  human-gated.
- CommonDB live integration remains absent from this slice.

## Open Questions

- OQ-BE-001: Which exact Codex App deep-link shapes will be approved for live
  navigation in a later slice?
- OQ-BE-002: Which App Server operations are read-only link inspection versus
  external writes requiring a separate human gate?
- OQ-BE-003: What separate contract will authorize CommonDB live search,
  indexing, or searchable migration?

## Handoff

This specification is frozen for the backend mock-safe thread-alignment lane.
Implementation policy and lane records may choose how to satisfy it, but may not
redefine its behavior authority, requirements, acceptance criteria, human gates,
or out-of-scope surfaces.
