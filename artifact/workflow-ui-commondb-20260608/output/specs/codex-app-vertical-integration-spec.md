---
schema_version: "0.1"
record_type: specification_packet
status: draft
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-CODEXAPP-VERTICAL-001
created_at: "2026-06-09"
source_refs:
  - AGENTS.md
  - docs/01-agent-operating-contract.md
  - docs/02-output-verification-contract.md
  - docs/03-repo-boundary-and-storage-contract.md
  - docs/reference/specification-workflow-reference.md
  - Plan/workflow-ui-commondb-20260608/plans/Plan_N0001.md
---

# Codex App Vertical Integration Specification

## Purpose

Define the target product behavior for a vertically integrated workflow where
Codex App owns stable conversation and artifact review, Obsidian owns memo
writing and human knowledge work, CommonDB owns searchable memo/context
retrieval, and the custom workflow UI owns goal setup, state transitions,
contracts, and CommonDB approval controls.

This specification is a draft behavior authority. It does not approve the real
Codex App Server bridge, persistent indexing, external writes, deployment, or
merge automation.

## Actors And Surfaces

- Human operator: sets goals, discusses with the agent, approves proposals,
  requests edits, approves CommonDB search/indexing, reviews artifacts, and
  accepts handoff.
- Codex App: stable conversation interface and artifact review surface for
  generated files, diffs, PRs, verification output, and handoff summaries.
- Codex App Server: transport that links Codex App conversation/action events to
  Workflow Core records through opaque thread/event references.
- Codex App Server project management layer: project-scoped registry that links
  workflow/project IDs to Codex App threads and artifact surfaces without
  becoming the workflow state authority.
- Workflow Core: canonical state authority for goals, proposal candidates,
  approvals, contracts, execution state, verification, and handoff.
- Custom workflow UI: state transition management surface for goal setup,
  contract status, approval state, and CommonDB permission/indexing controls.
- CommonDB: context and search adapter for memo/source references and sanitized
  snippets.
- Obsidian: human-facing memo authoring and review application. It may display
  source notes and task candidates, but it is not the Workflow Core state
  authority.

## Architectural Decision

The conversation interface and artifact inspection UI should be delegated to
Codex App. The custom workflow UI should not recreate chat. It should manage
workflow state, goal records, approvals, contracts, and CommonDB permissions.

```text
Obsidian
  memo writing / source review
      |
      v
CommonDB
  searchable context adapter
      |
      v
Workflow Core <-> Codex App Server <-> Codex App
  state authority    transport        conversation + artifact review
      ^
      |
Custom Workflow UI
  goal setup / state transition / contract / CommonDB approval controls
```

## Scope

### In Scope

- Goal setup screen in the custom workflow UI.
- Workflow state transition dashboard in the custom workflow UI.
- Contract and approval status display in the custom workflow UI.
- CommonDB memo source, search permission, and searchable-migration approval UI.
- Codex App thread linking through opaque refs.
- Codex App conversation as the primary agent dialogue interface.
- Codex App artifact review as the primary surface for files, diffs, PRs,
  generated HTML, verification output, and handoff records.
- State records that connect Codex App actions to Workflow Core transitions.
- Project-scoped Codex App Server management links between the custom workflow
  UI and Codex App.

### Out Of Scope

- Reimplementing a full chat interface in the custom workflow UI.
- Making Codex App Server the canonical workflow state store.
- Storing raw Codex thread bodies, raw terminal logs, browser sessions,
  credentials, local runtime state, or raw Obsidian note bodies in Workflow Core
  records.
- Automatically making memo content searchable without explicit human approval.
- Automatically executing, pushing, merging, deploying, or writing to protected
  surfaces without the existing human gates.
- Choosing a frontend framework, transport library, persistence engine, or file
  layout.
- Expanding task scope by treating goal drift, related ideas, or Out of Scope
  items as complete work without a specification amendment.

## Required Product Screens

### Screen: Goal Setup

The custom workflow UI must allow the human operator to create or revise a goal
before proposal generation.

Required fields:

- goal statement,
- desired outcome,
- success criteria,
- constraints,
- non-goals,
- target repo or workspace refs,
- denied context categories,
- preferred verification expectations,
- CommonDB usage preference,
- initial memo source set or source-selection intent,
- human gate defaults.

Observable behavior:

- Submitting a valid goal creates or updates a Workflow Core goal record.
- Submitting a goal does not execute work.
- Submitting a goal may open or link a Codex App conversation thread.
- The goal screen shows whether the linked Codex App thread is present, missing,
  or human-gated.

### Screen: Proposal Candidate State

Codex App is the primary conversation surface for agent-generated proposal
candidates. The custom workflow UI must show the current candidate state without
being the main proposal discussion surface.

Required behavior:

- show candidate IDs, titles, status, and selected candidate,
- show whether each candidate has required source refs, denied context,
  expected verification, risk flags, and CommonDB context refs,
- allow the human operator to select a candidate, request edits, or reject a
  candidate,
- link back to the Codex App thread or artifact view where the candidate was
  discussed.

### Screen: Workflow Conversation Link

The custom workflow UI must represent the Codex App conversation as a linked
external surface, not as embedded raw chat state.

Required behavior:

- show project-level Codex App Server link status,
- show opaque `app_server_thread_ref`,
- provide a direct navigation affordance from the custom workflow UI to the
  linked Codex App conversation or artifact surface,
- show bounded latest-event summaries,
- show available conversation actions derived from Workflow Core state,
- avoid storing or rendering raw thread bodies,
- route detailed conversation to Codex App.

### Screen: Approval And Edit Request

The custom workflow UI must separate approval from edit requests.

Required actions:

- approve selected candidate,
- approve candidate with constraints,
- request edits,
- reject candidate,
- approve contract for execution,
- hold execution pending human gate.

Observable behavior:

- Approving a candidate does not imply execution approval unless explicitly
  selected.
- Edit requests create a Workflow Core edit-request or changes-requested state.
- Approved execution requires an approved work contract with source refs,
  allowed write targets, denied context, verification expectations, human gate
  status, and git/workspace scope.

### Screen: CommonDB Memo Controls

The custom workflow UI must expose separate controls for memo search permission
and searchable-migration/indexing approval.

Required sections:

- memo source settings,
- search permission,
- context preview,
- searchable migration approval,
- excluded sources and reasons,
- raw-body and secret-boundary policy,
- Obsidian source/task candidate refs.

Observable behavior:

- Search permission allows bounded source refs and snippets for the current goal.
- CommonDB may make useful sources and approved memos searchable after the
  required approval exists.
- Search permission does not authorize durable migration unless the source is
  already an approved memo/useful source within the approved destination scope.
- Searchable migration approval is a separate action.
- Searchable migration approval shows a preview of source refs, inclusion
  policy, exclusion policy, and destination scope before approval.
- Workflow Core records only sanitized refs, bounded summaries, and approval
  state.

### Screen: Artifact Review State

Codex App is the primary artifact review surface. The custom workflow UI must
show artifact review state and links.

Required behavior:

- show current artifact refs,
- show PR refs when present,
- show verification refs and status,
- show unresolved review items,
- allow artifact reviewed, edit requested, or handoff accepted transitions,
- link to Codex App artifact view for detailed inspection.

## Workflow State Model

The workflow must support these externally observable states:

| State | Meaning | Primary UI Surface |
|---|---|---|
| `goal_draft` | Goal is being edited. | Custom workflow UI |
| `goal_submitted` | Goal is ready for agent proposal. | Custom workflow UI / Codex App |
| `conversation_linked` | Codex App thread is linked by opaque ref. | Custom workflow UI |
| `candidate_set_available` | Agent proposal candidates exist. | Codex App / Custom workflow UI |
| `candidate_selected` | Human selected a candidate for refinement or approval. | Custom workflow UI |
| `changes_requested` | Human requested edits before approval. | Codex App / Custom workflow UI |
| `candidate_approved` | Candidate is approved as proposal direction. | Custom workflow UI |
| `contract_draft` | Approved work contract is being formed. | Custom workflow UI |
| `contract_approved` | Contract is approved for execution subject to gates. | Custom workflow UI |
| `commondb_search_pending` | Memo search permission is not yet approved. | Custom workflow UI |
| `commondb_search_approved` | Bounded search/snippet retrieval is approved. | Custom workflow UI |
| `commondb_migration_pending` | Searchable migration/indexing awaits approval. | Custom workflow UI |
| `commondb_migration_approved` | Searchable migration/indexing approval exists. | Custom workflow UI |
| `execution_ready` | Execution may start when gates are satisfied. | Custom workflow UI |
| `execution_running` | Agent execution is in progress. | Codex App / Custom workflow UI |
| `artifact_review` | Human reviews outputs and evidence. | Codex App |
| `verification_review` | Verification result is visible for review. | Codex App / Custom workflow UI |
| `handoff_ready` | Final handoff is ready for human acceptance. | Codex App / Custom workflow UI |
| `spec_amendment_required` | Requested scope expansion must change the spec before work expands. | Custom workflow UI |
| `blocked` | Human gate, missing evidence, or failed verification blocks progress. | Custom workflow UI |

## Allowed State Transitions

| From | To | Trigger |
|---|---|---|
| `goal_draft` | `goal_submitted` | Human submits goal. |
| `goal_submitted` | `conversation_linked` | Codex App thread is linked. |
| `conversation_linked` | `candidate_set_available` | Agent proposes candidates. |
| `candidate_set_available` | `candidate_selected` | Human selects candidate. |
| `candidate_selected` | `changes_requested` | Human requests edits. |
| `changes_requested` | `candidate_set_available` | Agent returns revised candidates. |
| `candidate_selected` | `candidate_approved` | Human approves candidate. |
| `candidate_approved` | `contract_draft` | Contract is generated from approved candidate. |
| `contract_draft` | `contract_approved` | Human approves execution contract. |
| `goal_submitted` | `commondb_search_pending` | Goal requests CommonDB context. |
| `commondb_search_pending` | `commondb_search_approved` | Human approves bounded search. |
| `commondb_search_approved` | `commondb_migration_pending` | Searchable migration is proposed. |
| `commondb_migration_pending` | `commondb_migration_approved` | Human approves searchable migration. |
| `contract_approved` | `execution_ready` | Required gates are satisfied. |
| `execution_ready` | `execution_running` | Human or approved runner starts execution. |
| `execution_running` | `artifact_review` | Outputs are ready for review. |
| `artifact_review` | `changes_requested` | Human requests edits from artifacts. |
| `artifact_review` | `verification_review` | Human marks artifacts reviewed. |
| `verification_review` | `handoff_ready` | Verification evidence is accepted. |
| Any state | `spec_amendment_required` | Agent or human requests task scope expansion beyond the approved spec. |
| Any nonterminal state | `blocked` | Gate, evidence, permission, or verification blocks progress. |

## Event Contract

Workflow events emitted by Codex App Server or the custom workflow UI must be
mapped into Workflow Core records. Each event must include:

- event ID,
- project ID,
- workflow or goal ID,
- previous state,
- requested next state,
- actor category,
- source surface (`codex_app`, `custom_workflow_ui`, `commondb`, `obsidian`),
- bounded summary,
- external refs when applicable,
- human gate status when applicable,
- evidence refs when applicable.

Required event kinds:

- `goal_submitted`,
- `conversation_linked`,
- `candidate_set_available`,
- `candidate_selected`,
- `edit_requested`,
- `candidate_approved`,
- `contract_approved`,
- `commondb_search_permission_requested`,
- `commondb_search_permission_approved`,
- `commondb_searchable_migration_requested`,
- `commondb_searchable_migration_approved`,
- `spec_amendment_requested`,
- `spec_amendment_approved`,
- `execution_started`,
- `artifact_reviewed`,
- `verification_recorded`,
- `handoff_accepted`,
- `blocked`.

## Data And Trust Boundaries

- Workflow Core may store opaque Codex App refs, bounded summaries, state IDs,
  contract refs, source refs, and verification refs.
- Workflow Core or Codex App Server may manage thread/workflow references when
  those references are needed for active workflow operation and are not being
  used as local repo backup.
- Workflow Core must not store raw Codex thread bodies, raw terminal logs,
  browser sessions, credentials, local runtime state, raw Obsidian note bodies,
  vector payloads, or secret-bearing material.
- CommonDB context results must be source-ref based and snippet-bounded.
- CommonDB searchable destinations are limited to useful source records and
  approved memo records unless a future spec amendment expands the destination
  scope.
- Search permission and searchable migration approval must be separate records
  unless the source is already approved for searchability under the current
  destination scope.
- Obsidian backup/write-back is optional and must be tied to an explicit backup,
  memo-writing, or source-review intent. Routine thread/workflow management does
  not require local repo backup into Obsidian.
- Obsidian writes, CommonDB indexing, GitHub writes, pushes, merges,
  deployments, and protected actions remain human-gated unless explicitly
  approved by a later work contract.

## Behavior Requirements

### REQ-001 Goal Setup Authority

The custom workflow UI must be the primary surface for creating and revising the
workflow goal record.

Observable outcome: a submitted goal produces a Workflow Core goal state and
does not execute work.

Acceptance criteria:

- AC-001: Inspection shows goal fields for outcome, success criteria,
  constraints, non-goals, denied context, and CommonDB preference.
- AC-002: Submitting a goal records `goal_submitted` without recording
  `execution_started`.

### REQ-002 Conversation Delegation

The system must delegate agent conversation to Codex App and represent it in
Workflow Core only through opaque refs and bounded event summaries.

Observable outcome: the custom workflow UI links to the Codex App conversation
without storing raw conversation content.

Acceptance criteria:

- AC-003: Conversation records contain an opaque app server thread ref.
- AC-004: Denied markers for raw thread bodies, credentials, browser sessions,
  and local runtime state are rejected or absent.

### REQ-003 Proposal Candidate Review

The system must expose proposal candidate state in the custom workflow UI while
allowing detailed candidate discussion in Codex App.

Observable outcome: the human can select, reject, or request edits for a
candidate without leaving the canonical state model ambiguous.

Acceptance criteria:

- AC-005: Candidate state includes ID, status, selected flag, risk flags,
  source refs, verification expectation, and Codex App discussion ref.
- AC-006: Edit request moves state to `changes_requested`.

### REQ-004 Approval Separation

The system must distinguish candidate approval from execution-contract
approval.

Observable outcome: approving a proposal direction cannot start execution until
an approved work contract exists.

Acceptance criteria:

- AC-007: `candidate_approved` and `contract_approved` are separate states or
  events.
- AC-008: Execution requires source refs, allowed write targets, denied context,
  verification expectations, human gate status, and git/workspace scope.

### REQ-005 CommonDB Permission Separation

The system must separate bounded search permission from searchable
migration/indexing approval.

Observable outcome: a memo can be searched for one goal without being migrated
or made broadly searchable.

Acceptance criteria:

- AC-009: `commondb_search_permission_approved` does not imply
  `commondb_searchable_migration_approved`.
- AC-010: Searchable migration approval displays source refs, destination
  scope, inclusion policy, exclusion policy, and raw-body boundary before
  approval.

### REQ-006 Artifact Review Delegation

Codex App must be the primary detailed artifact review surface. The custom
workflow UI must manage artifact review state and refs.

Observable outcome: humans review artifacts in Codex App while Workflow Core
records artifact review status and evidence refs.

Acceptance criteria:

- AC-011: Artifact review state includes artifact refs, PR refs when present,
  verification refs, and unresolved review items.
- AC-012: Artifact review can transition to edit requested, verification
  review, or blocked.

### REQ-007 Human Gate Preservation

The system must preserve existing human gates for real App Server bridge use,
external writes, CommonDB indexing, protected Git actions, deployment, and
merge.

Observable outcome: no protected side effect happens from state transition
alone.

Acceptance criteria:

- AC-013: Real App Server bridge execution remains blocked without explicit
  approval.
- AC-014: Merge and deployment remain human-only.

### REQ-008 Project Link Management

The system must expose a project-scoped Codex App Server management layer that
links the custom workflow UI directly to Codex App conversation and artifact
surfaces.

Observable outcome: the custom workflow UI can show the Codex App project link
state and open the relevant Codex App surface without becoming the chat UI.

Acceptance criteria:

- AC-015: Project link state includes project ID, workflow ID, Codex App thread
  ref, artifact surface refs when present, link status, and bounded latest
  event summary.
- AC-016: Link records store opaque refs only and do not store raw conversation
  bodies or artifact contents.

### REQ-009 Scope Amendment Guard

The system must allow task scope to expand only through an explicit
specification amendment or approved contract revision.

Observable outcome: the agent cannot mark shifted goals, Out of Scope work, or
unbounded expansion as complete work.

Acceptance criteria:

- AC-017: A requested expansion beyond the approved spec moves the workflow to
  `spec_amendment_required` or `changes_requested`.
- AC-018: Completion checks reject work that satisfies a shifted goal while
  leaving the approved goal or acceptance criteria unmet.
- AC-019: Out of Scope items remain blocked unless a human-approved spec
  amendment brings them into scope.

## Verification Expectations

Before implementation is accepted, verification should prove:

- goal submission cannot trigger execution,
- raw conversation and raw memo bodies are not stored in Workflow Core records,
- proposal approval and execution-contract approval are separate,
- CommonDB search and searchable migration approvals are separate,
- custom workflow UI can display state and action availability from records,
- Codex App refs are opaque and bounded,
- artifact review state can be linked back to Codex App surfaces,
- invalid state transitions are rejected,
- scope expansion requires a spec amendment or approved contract revision,
- completion cannot be claimed through goal drift.

## Resolved Questions

- RQ-001: The first implementation should include an App Server
  project-management layer and direct custom workflow UI links to Codex App.
- RQ-002: The minimum Codex App link shape is project ID, workflow ID, opaque
  thread ref, optional artifact refs, link status, and bounded latest-event
  summary.
- RQ-003: Obsidian write-back is not mandatory for routine thread/workflow
  management. It is used when there is an explicit backup, memo-writing, or
  source-review intent.
- RQ-004: CommonDB searchable destinations are useful source records and
  approved memo records.
- RQ-005: Scope expansion is allowed only through spec amendment or approved
  contract revision; goal drift, Out of Scope work, and unbounded expansion must
  not be treated as completion.

## Open Questions

- OQ-006: Which exact Codex App deep-link format should be used for local app
  navigation once the real App Server bridge is approved?
- OQ-007: Which App Server project-management operations are read-only and which
  are external writes requiring a separate human gate?

## Human Gate Status

- Specification review: required.
- Real Codex App Server bridge: required for live transport beyond mock-safe
  project/thread refs.
- CommonDB searchable migration/indexing: required.
- Obsidian write-back: required.
- External push/PR update: allowed only on owned review branches with clear
  scope and verification.
- Merge/deployment/protected writes: human-only.

## Next Action

Review this draft specification, resolve open questions that block state or
trust-boundary design, then freeze an approved specification before slicing
implementation into UI state, App Server adapter, CommonDB permission, and
Codex App artifact-link lanes.
