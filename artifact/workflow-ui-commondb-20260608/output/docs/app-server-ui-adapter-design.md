# App Server UI Adapter Design

## Purpose

The App Server UI adapter lets a Codex App Server thread appear in workflow UI
records without making the App Server the source of truth. Workflow Core remains
canonical for issue, proposal, approval, approved contract, execution,
verification, and handoff state. App Server identifiers are external references
attached to an `ExecutionRun`.

This design covers the local/mock lane. A real App Server bridge is
human-gated and must not run, connect, or smoke test until explicitly approved.

## State Authority

Workflow Core owns durable state:

- `IssueCandidate`
- `Issue`
- `ImplementationProposal`
- `ApprovalDecision`
- `ApprovedWorkContract`
- `ExecutionRun`
- `VerificationResult`
- `HandoffArtifact`

The App Server adapter may attach these external references to an
`ExecutionRun`:

- `app_server_thread_ref`
- `app_server_turn_ref`
- `app_server_event_ref`
- `app_server_transport`

Those values are references only. They do not carry raw thread bodies, raw
terminal output, browser session data, credentials, local runtime paths, or
secret-bearing metadata.

## Event Mapping

App Server activity maps into sanitized run events:

| App Server activity | Workflow event kind | Notes |
|---|---|---|
| thread linked | `thread_linked` | Records thread reference and transport only. |
| turn started | `turn_started` | Starts an execution event span for an approved contract. |
| event received | `event_received` | Stores event type, status, and bounded summary. |
| approval requested | `approval_requested` | Records prompt metadata and required human gate. |
| user input requested | `user_input_requested` | Records request metadata without raw prompt body. |
| blocked/error | `blocked` or `error` | Records sanitized reason and next action. |
| verification recorded | `verification_recorded` | References local verification evidence. |
| handoff recorded | `handoff_recorded` | References final handoff artifact. |

Approval prompts and user-input requests are workflow events. They are not
implicit state transitions. Workflow Core must still record the resulting
approval decision before any execution action that requires approval.

## Local Mock Console

The local console renders sanitized fixtures only. It supports these screens:

- work queue
- proposal review
- approved contract
- execution run
- verification
- handoff

The console is suitable for static tests and local inspection. It must not read
local runtime ledgers, browser sessions, App Server logs, or raw Codex thread
bodies.

## Real Bridge Gate

D7 real App Server bridge remains blocked on a human gate. Before enabling it,
the follow-up work contract must name:

- approved transport, with `stdio` preferred first,
- allowed external read/write actions,
- required mock JSON-RPC tests,
- real smoke target and rollback note,
- secret and raw-body handling constraints,
- approval prompt behavior.

Until that gate is approved, real App Server smoke is recorded as `skipped`.

## Compatibility

SDK and mock runners remain valid without App Server. A workflow run can be
replayed from Workflow Core records and sanitized event refs alone. App Server
thread/event refs improve UI navigation, but they are not required for state
validation or handoff.
