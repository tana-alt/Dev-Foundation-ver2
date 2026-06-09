---
schema_version: "0.1"
record_type: specification_packet
status: approved_for_mock_ui_shell
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-PERSONAL-MAC-WORKFLOW-001
created_at: "2026-06-09"
source_refs:
  - AGENTS.md
  - docs/01-agent-operating-contract.md
  - docs/02-output-verification-contract.md
  - docs/03-repo-boundary-and-storage-contract.md
  - docs/reference/specification-workflow-reference.md
  - artifact/workflow-ui-commondb-20260608/output/specs/codex-app-vertical-integration-spec.md
  - user_request:2026-06-09-personal-mac-workflow-app-direction
---

# Personal Mac Workflow App Specification

## Purpose

Define the product behavior for a personal macOS-integrated workflow app that
coordinates goal setup, workflow state, approvals, contracts, CommonDB controls,
and direct Codex App links.

Codex App remains the owner of conversation and artifact review. The custom app
does not replace Codex App chat, does not become a static HTML artifact, and does
not store raw thread bodies or secrets.

This specification is approved for a mock native Mac UI shell after human
selection of Direction B and the request to execute the UI/front-end workflow.
It does not authorize live Codex App Server writes, CommonDB indexing, Obsidian
write-back, protected Git operations, merge, deployment, or external side
effects.

## Product Boundary

### Primary Surfaces

- Human operator: defines the goal, reviews state, approves contracts, controls
  CommonDB use, reviews Codex App artifacts, and accepts or rejects completion.
- Personal Mac workflow app: local product surface for goal setup, workflow
  state transitions, approvals, execution contracts, CommonDB useful-source and
  approved-memo controls, and direct links into Codex App.
- Codex App: conversation surface and artifact review surface for agent dialogue,
  files, diffs, generated artifacts, verification output, handoff summaries, and
  human review.
- Codex App Server project layer: project-scoped link layer that associates the
  personal app's workflow records with Codex App conversation and artifact
  surfaces through opaque refs.
- Workflow Core: canonical workflow state authority for goal records, candidate
  proposal status, approvals, contracts, verification status, handoff status,
  and completion checks.
- CommonDB: searchable context record system limited in this direction to
  `useful_source` and `approved_memo` records.
- Obsidian: optional human knowledge surface for backup, memo writing, or
  source-review write-back only when the human explicitly requests that intent.

### Mac App Versus Web UI

The first-class product is a personal Mac-integrated app experience, not a
standalone static HTML page. A web UI may exist only as an implementation option
or preview surface if a later approved contract chooses it. The required product
behavior is local-personal workflow control with direct navigation to Codex App,
clear local state, and macOS-appropriate handoff between the app and Codex App.

This platform boundary is part of the external product requirement. This spec
does not choose a UI framework, persistence engine, process model, packaging
tool, or library.

## In Scope

- Create, revise, and submit a personal workflow goal.
- Display workflow state and allowed next actions.
- Preserve Codex App as the detailed conversation surface.
- Preserve Codex App as the detailed artifact review surface.
- Link directly from the personal app to relevant Codex App conversations and
  artifact surfaces.
- Display Codex App link status using opaque project, thread, and artifact refs.
- Select proposal candidates, request edits, reject candidates, or approve a
  candidate direction.
- Separate candidate approval from execution-contract approval.
- Display and approve work contracts before execution.
- Control CommonDB search and searchability for `useful_source` and
  `approved_memo` records.
- Require explicit scope amendment or contract revision before expanding work
  beyond the approved goal and acceptance criteria.
- Block completion when goal drift satisfies a newer or different goal while the
  approved goal remains unmet.
- Record bounded summaries, refs, statuses, gate decisions, and evidence refs.

## Non-Goals

- Rebuild Codex App chat inside the personal app.
- Replace Codex App artifact review.
- Treat a static HTML file as the primary product direction.
- Make Codex App Server the canonical workflow state authority.
- Use the repo as runtime storage for queues, locks, browser sessions, raw logs,
  local app state, or secrets.
- Store raw Codex thread bodies, raw memo bodies, terminal logs, browser
  sessions, credentials, tokens, cookies, or secret-bearing metadata.
- Make Obsidian backup or write-back automatic.
- Make CommonDB records searchable without explicit approval.
- Index or search arbitrary memo bodies beyond `useful_source` and
  `approved_memo` records.
- Execute, push, merge, deploy, index, or write externally from a UI transition
  alone.
- Count shifted goals, adjacent ideas, or newly discovered scope as complete
  without an approved specification amendment or contract revision.

## Workflow States

The product must expose these observable workflow states:

| State | Meaning | Primary Surface |
|---|---|---|
| `goal_draft` | Human is drafting or revising the workflow goal. | Personal Mac app |
| `goal_submitted` | Goal is ready for agent proposal. | Personal Mac app |
| `codex_link_pending` | A Codex App link is needed or unavailable. | Personal Mac app |
| `codex_linked` | Opaque Codex App project/thread refs are available. | Personal Mac app / Codex App |
| `candidate_set_available` | One or more proposal candidates are available. | Codex App / Personal Mac app |
| `candidate_selected` | Human selected a candidate for approval or edits. | Personal Mac app |
| `changes_requested` | Human requested candidate, contract, artifact, or scope edits. | Codex App / Personal Mac app |
| `candidate_approved` | Human approved the direction, not execution. | Personal Mac app |
| `contract_draft` | Execution contract is being prepared or revised. | Personal Mac app |
| `contract_approved` | Human approved the execution contract, subject to gates. | Personal Mac app |
| `commondb_search_pending` | CommonDB search permission awaits approval. | Personal Mac app |
| `commondb_search_approved` | Bounded search is approved for current scope. | Personal Mac app |
| `commondb_searchability_pending` | Making records searchable awaits approval. | Personal Mac app |
| `commondb_searchability_approved` | Approved records may become searchable in the approved destination. | Personal Mac app |
| `execution_ready` | Execution may start only if all human gates are satisfied. | Personal Mac app |
| `execution_running` | Agent work is in progress in the approved workflow. | Codex App / Personal Mac app |
| `artifact_review` | Outputs are ready for detailed review in Codex App. | Codex App |
| `verification_review` | Verification evidence is ready for acceptance or rework. | Codex App / Personal Mac app |
| `handoff_ready` | Final handoff is ready for human acceptance. | Codex App / Personal Mac app |
| `complete` | Human accepted completion against the approved goal and acceptance criteria. | Personal Mac app |
| `spec_amendment_required` | Requested expansion requires specification amendment or contract revision. | Personal Mac app |
| `blocked` | A missing gate, missing evidence, failed check, or trust-boundary issue blocks progress. | Personal Mac app |

## Required Behavior

### REQ-001 Goal Setup And Drift Guard

The personal Mac app must be the primary surface for defining, revising, and
submitting the workflow goal.

Observable outcome: the workflow has an explicit approved goal and cannot be
completed by satisfying a different or drifted goal.

Acceptance criteria:

- AC-001: The goal record includes desired outcome, success criteria,
  constraints, non-goals, source refs, denied context, expected verification,
  and human-gate expectations.
- AC-002: Submitting a goal creates `goal_submitted` and does not create
  `execution_ready`, `execution_running`, or `complete`.
- AC-003: If the human or agent introduces materially different scope, the
  workflow moves to `spec_amendment_required` or `changes_requested`.
- AC-004: Completion checks reject work that satisfies a shifted goal while any
  approved success criterion remains unmet.

### REQ-002 Codex App Conversation Ownership

Codex App must own detailed conversation. The personal app must show link state,
available actions, and bounded summaries without storing or rendering raw
conversation bodies.

Observable outcome: the human uses Codex App for detailed agent conversation and
uses the personal app for workflow state and approvals.

Acceptance criteria:

- AC-005: The personal app displays Codex App link status and direct navigation
  to the linked conversation when an opaque ref exists.
- AC-006: Workflow records store opaque Codex App refs, bounded summaries, event
  IDs, state IDs, and evidence refs only.
- AC-007: Raw thread bodies, credentials, tokens, browser sessions, terminal
  logs, and secret-bearing metadata are absent from workflow records.

### REQ-003 Codex App Artifact Review Ownership

Codex App must own detailed artifact review. The personal app must display
artifact review state, unresolved items, verification status, and direct links
to Codex App artifact surfaces.

Observable outcome: the human can inspect artifacts in Codex App and update
workflow state in the personal app.

Acceptance criteria:

- AC-008: Artifact review state includes artifact refs, verification refs,
  unresolved review items, and Codex App artifact links when available.
- AC-009: The personal app offers state actions for artifact reviewed, edits
  requested, verification accepted, handoff accepted, or blocked.
- AC-010: Detailed artifact contents are not copied into workflow state records.

### REQ-004 Proposal Candidate And Approval Separation

The workflow must distinguish proposal candidate selection, candidate approval,
and execution-contract approval.

Observable outcome: approving a direction cannot start work unless a separate
approved contract and required gates exist.

Acceptance criteria:

- AC-011: Candidate state includes candidate ID, status, selected flag, source
  refs, risk flags, verification expectation, CommonDB context refs when used,
  and Codex App discussion ref.
- AC-012: Candidate approval creates `candidate_approved` and does not create
  `execution_ready`.
- AC-013: Execution requires `contract_approved` plus satisfied gates for write
  targets, source refs, denied context, verification expectations, and any
  external side effects.

### REQ-005 Contract Control Surface

The personal app must own the human-facing contract review and approval surface
for workflow execution.

Observable outcome: the human can see exactly what work is authorized before
execution starts.

Acceptance criteria:

- AC-014: A contract view shows scope, allowed write targets, denied context,
  source refs, expected outputs, verification expectations, human gates, and
  residual risks.
- AC-015: Requesting edits returns the workflow to `changes_requested` or
  `contract_draft`.
- AC-016: Approving a contract records `contract_approved` without bypassing
  human gates for external writes, CommonDB indexing, Obsidian write-back,
  protected Git actions, merge, deployment, or secret handling.

### REQ-006 CommonDB Useful Source And Approved Memo Controls

The personal app must provide explicit controls for CommonDB records that may be
searched or made searchable, limited to `useful_source` and `approved_memo`.

Observable outcome: CommonDB can help the workflow without turning raw notes or
threads into unbounded searchable storage.

Acceptance criteria:

- AC-017: CommonDB controls distinguish search permission from searchability or
  indexing approval.
- AC-018: Search permission is bounded to the current goal, approved source
  refs, snippets, and summaries.
- AC-019: Searchability approval is allowed only for `useful_source` and
  `approved_memo` records within the approved destination scope.
- AC-020: The approval preview shows included refs, excluded refs, destination
  scope, raw-body boundary, and secret boundary.
- AC-021: Raw memo bodies, raw thread bodies, vector payloads, and secrets are
  not stored in workflow records.

### REQ-007 Codex App Server Project Link Layer

The product must include a project-scoped Codex App Server link layer as an
external integration requirement. This layer links workflow records to Codex App
conversation and artifact surfaces without becoming workflow state authority.

Observable outcome: the personal app can open the right Codex App project,
conversation, or artifact surface while Workflow Core remains canonical for
workflow state.

Acceptance criteria:

- AC-022: Link state includes project ID, workflow ID, opaque thread ref,
  optional artifact refs, link status, and bounded latest-event summary.
- AC-023: Missing or stale links are visible as `codex_link_pending` or
  `blocked`.
- AC-024: Codex App Server link records cannot override Workflow Core state,
  approvals, contracts, verification status, or completion status.

### REQ-008 Obsidian Optionality

Obsidian backup or write-back must be optional and explicit. It must not be a
default persistence path for workflow state, raw conversation, or artifact
review.

Observable outcome: Obsidian is used only when the human asks for backup,
memo-writing, or source-review write-back.

Acceptance criteria:

- AC-025: Routine workflow operation does not require Obsidian.
- AC-026: Any Obsidian write-back requires explicit human intent and a bounded
  destination.
- AC-027: Obsidian write-back cannot include raw thread bodies, secrets, or
  protected material unless a later human-approved contract explicitly allows a
  safe transformed output.

### REQ-009 Completion Integrity

The product must prevent completion unless the approved goal, acceptance
criteria, verification expectations, and human gates are satisfied.

Observable outcome: completion means the approved work is done, not merely that
some useful adjacent work happened.

Acceptance criteria:

- AC-028: Completion review shows approved goal, acceptance criteria status,
  verification status, artifact refs, unresolved items, and residual risks.
- AC-029: Unresolved required acceptance criteria prevent `complete`.
- AC-030: New or expanded scope remains outside completion unless approved by
  specification amendment or contract revision.

## Human Gates

The following actions require explicit human approval before they occur:

- Freezing this specification as behavior authority.
- Running live Codex App Server operations beyond safe link inspection.
- Starting execution from an approved contract.
- Making CommonDB records searchable or indexing records.
- Writing to Obsidian.
- Handling secrets or secret-bearing material.
- Writing outside approved local targets.
- Pushing, opening, or updating a PR unless authorized by an owned review-branch
  contract.
- Merging, deployment, release, protected Git actions, dependency changes,
  infrastructure changes, database/schema changes, or irreversible actions.

## Acceptance Criteria Summary

The specification is acceptable for human review when:

- The product direction is a personal Mac-integrated workflow app, not static
  HTML.
- Codex App is clearly the conversation and artifact review owner.
- The personal app clearly owns goal setup, workflow state transitions,
  approvals, contracts, CommonDB controls, and direct Codex App links.
- Codex App Server project links are defined as an external product requirement
  and not as workflow state authority.
- CommonDB searchable records are limited to `useful_source` and
  `approved_memo`.
- Obsidian backup/write-back is optional and explicit.
- Raw thread bodies, raw memo bodies, secrets, runtime state, and browser
  sessions are excluded from storage.
- Scope expansion requires specification amendment or contract revision.
- Goal drift cannot count as complete.
- Human gates are explicit and preserved.
- Open questions are recorded instead of hidden as implementation assumptions.

## Verification Expectations

Before implementation is accepted, verification should prove:

- Goal submission cannot start execution.
- Candidate approval and contract approval are distinct.
- Scope expansion moves to `spec_amendment_required` or an equivalent
  changes-requested state.
- Completion fails when approved acceptance criteria remain unmet.
- Workflow records contain opaque Codex App refs and bounded summaries only.
- Raw thread bodies, raw memo bodies, terminal logs, browser sessions, and
  secrets are not stored.
- CommonDB search permission and searchability approval are distinct.
- CommonDB searchability is limited to `useful_source` and `approved_memo`.
- Obsidian write-back is absent unless explicit human intent exists.
- The personal app can directly link to Codex App conversation and artifact
  surfaces when valid refs exist.

## Open Questions

- OQ-001: What exact local deep-link shape should open a Codex App project,
  conversation, or artifact surface from the personal Mac app?
- OQ-002: Which Codex App Server project-layer operations are read-only link
  inspection, and which are external writes requiring a separate human gate?
- OQ-003: What minimum macOS integration is required for first acceptance:
  menu-bar presence, document-style app, URL scheme handling, notifications,
  file coordination, or another user-visible integration?
- OQ-004: What is the human-approved destination scope for CommonDB
  `useful_source` and `approved_memo` searchability?
- OQ-005: Should Obsidian write-back be excluded from the first implementation
  entirely, or included only as a gated optional flow?
- OQ-006: What exact evidence should main_lane require before freezing this
  replacement direction over the previous static HTML direction?

## Next Action

Main_lane should review this draft with the human, resolve or explicitly carry
the open questions, and freeze an approved specification before any app-code
implementation or lane slicing begins.
