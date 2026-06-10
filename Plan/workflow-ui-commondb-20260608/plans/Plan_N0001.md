---
plan_id: Plan_N0001
project_id: workflow-ui-commondb-20260608
status: draft
log_ref: Plan/workflow-ui-commondb-20260608/logs/Plan_N0001.log.md
---

# Workflow UI And CommonDB Task Plan

## Purpose

Turn the supplied two-text planning input into repository-routed task docs for a
cross-repo foundation slice:

- external-facing minimum improvement,
- app-server-managed UI surfaces,
- individual feature implementation lanes,
- separate repository execution with human-controlled merge.

This plan is a planning and handoff artifact only. It does not authorize edits
outside the named task packets, does not run Codex App Server, and does not make
App Server, CommonDB, Obsidian, or GitHub Issues the workflow state source of
truth.

## Source Refs

Required refs for workers before editing this repo:

- `AGENTS.md`
- `README.md`
- `docs/01-agent-operating-contract.md`
- `docs/02-output-verification-contract.md`
- `docs/03-repo-boundary-and-storage-contract.md`
- `docs/reference/packet-evidence-and-rework-reference.md`
- `docs/reference/git-worktree-and-branch-reference.md`
- `docs/reference/verification-ci-and-pr-reference.md`
- `templates/work-contract.yaml`
- `templates/parallel-lane-map.yaml`
- `Plan/workflow-ui-commondb-20260608/lane-maps/workflow-ui-commondb-20260608.yaml`

Planning inputs from the user conversation may guide priority, but repository
files above remain the source of truth for path placement, gates, verification,
and parallel work rules.

## Global Constraints

- Do not push directly to `main` or `master`.
- Do not merge; merge is human-only.
- Use one owned `agent/*` branch and one external worktree per parallel lane.
- Do not store runtime queues, lock ledgers, broad logs, raw Codex thread bodies,
  browser sessions, secrets, local paths, or credentials in repo files.
- Treat Codex SDK, Codex App Server, CommonDB, Obsidian, GitHub Issues, and any
  future UI as adapters around Workflow Core state, not as the canonical state
  source.
- Keep local work products in documented roots only: `Plan/`, `artifact/`,
  `src/`, `app/`, `templates/`, `scripts/`, `tests/`, or routed `docs/` files.

## Architecture Decision For This Slice

Workflow Core is the canonical state boundary:

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

Adapters attach to this state model:

- CommonDB context adapter: bounded `source_ref` plus snippet context only.
- Codex SDK adapter: headless execution fallback.
- Codex App Server adapter: rich execution UI, approvals, thread/event bridge.
- Workflow console: local/demo UI over sanitized records.

## Task Set

### D0 External-Facing Foundation Overview

Status: planned  
Lane: `external-docs`

Intent: make this repo understandable as a compact agent governance and workflow
foundation without implying an already-shipped product app.

Allowed write targets:

- `README.md`
- `artifact/workflow-ui-commondb-20260608/output/docs/external-facing-overview.md`
- `artifact/workflow-ui-commondb-20260608/output/demos/demo-foundation-overview/`

Expected outputs:

- external-facing overview,
- current runnable/check surfaces,
- non-goals and human gates,
- small demo artifact outline.

Verification:

- inspect changed docs and links,
- `make check-fast`,
- `make check-foundation` before PR handoff when tools are available.

### D1 Workflow Core State Model

Status: planned  
Lane: `workflow-core`

Intent: define the workflow state model independent of Obsidian, CommonDB,
Codex SDK, Codex App Server, GitHub Issues, or any single UI.

Allowed write targets:

- `src/workflow_core/`
- `tests/workflow_core/`
- `templates/workflow-core/`
- `artifact/workflow-ui-commondb-20260608/output/docs/workflow-core-state-model.md`

Expected outputs:

- state model,
- transition table,
- template fixtures,
- tests for valid and invalid transitions.

Verification:

- `uv run pytest tests/workflow_core -q`,
- `make check-fast`.

### D2 ApprovedWorkContract Schema V1

Status: planned  
Lane: `workflow-core`

Intent: convert approved proposals into bounded execution contracts that SDK,
App Server, or mock runners can execute without weakening repo gates.

Allowed write targets:

- `templates/approved-work-contract.yaml`
- `src/workflow_core/contracts.py`
- `tests/workflow_core/test_approved_work_contract.py`

Required contract fields:

- `work_contract_id`
- `issue_id`
- `proposal_id`
- `project_id`
- `goal`
- `source_refs`
- `allowed_write_targets`
- `denied_context`
- `verification`
- `human_gate`
- `risk_flags`
- `git_scope`

Verification:

- targeted schema tests,
- `make check-contracts`,
- `make check-fast`.

### D3 Workflow State Transition Checker

Status: planned  
Lane: `workflow-core`

Intent: add a local checker that rejects invalid workflow records before they are
used by an execution adapter.

Allowed write targets:

- `scripts/check-workflow-state.py`
- `src/workflow_core/checks.py`
- `tests/workflow_core/test_state_transitions.py`
- `Makefile`

Required checks:

- no execution without approval,
- no execution from `changes_requested`, `blocked`, or `rejected`,
- no approved work contract with empty source refs,
- no approved work contract with empty allowed write targets,
- no approved work contract with empty verification requirements.

Verification:

- `uv run pytest tests/workflow_core -q`,
- `make check-fast`,
- `make check-required` if Makefile or shared checker wiring changes.

### D4 Codex SDK Runner

Status: planned  
Lane: `codex-runner`

Intent: provide a headless execution adapter for approved work contracts.

Allowed write targets:

- `src/workflow_adapters/codex_sdk_adapter.py`
- `scripts/run-approved-work-contract.py`
- `templates/codex-sdk-run-config.yaml`
- `artifact/workflow-ui-commondb-20260608/output/demos/demo-codex-sdk-run/`
- `tests/workflow_adapters/`

Non-goals:

- real merge,
- release,
- deployment,
- CI/CD mutation,
- secret handling,
- automatic approval.

Verification:

- mock SDK tests,
- `make check-fast`,
- real SDK smoke only as an optional human-gated check.

### D5 Codex App Server UI Adapter Design

Status: planned  
Lane: `app-server-ui`

Intent: document how Codex App Server maps to Workflow Core execution runs
without becoming the state source of truth.

Allowed write targets:

- `artifact/workflow-ui-commondb-20260608/output/docs/app-server-ui-adapter-design.md`
- `templates/app-server-thread-link.yaml`
- `templates/app-server-run-event.yaml`

Expected design decisions:

- App Server thread/event IDs are external refs on `ExecutionRun`,
- approval prompts and user-input requests are event records,
- Workflow Core remains canonical,
- SDK and mock runners remain valid without App Server.

Verification:

- docs inspection,
- template consistency review,
- `make check-fast` when available.

### D6 Minimal Workflow Run UI Prototype

Status: planned  
Lane: `app-server-ui`

Intent: provide a small local/demo UI over sanitized workflow fixtures.

Allowed write targets:

- `app/workflow_console/`
- `src/workflow_ui/`
- `scripts/run-workflow-console.py`
- `tests/workflow_ui/`

Screens:

- work queue,
- proposal review,
- approved contract,
- execution run,
- verification,
- handoff.

Verification:

- UI smoke or static test,
- no local path, secret, raw log, or raw thread-body scan,
- `make check-fast`.

### D7 Real Codex App Server Bridge

Status: planned; human gate required  
Lane: `app-server-ui`

Intent: connect the minimal UI to a real local Codex App Server after design and
mock UI pass.

Allowed write targets:

- `src/workflow_adapters/codex_app_server_adapter.py`
- `app/workflow_console/`
- `tests/workflow_adapters/`

Acceptance:

- use `stdio` first unless an explicit design review chooses another transport,
- map thread start, turn start, event stream, blocked/error, and approval prompts
  into sanitized run records,
- do not store raw thread bodies, raw terminal logs, credentials, browser session
  data, or local runtime state.

Verification:

- mock JSON-RPC tests,
- local App Server smoke only with explicit human approval,
- `make check-fast`.

### D8 Vertical Workflow Demo Artifact

Status: planned  
Lane: `demo-context`

Intent: create a replayable sanitized demo that proves issue candidate,
proposal, approval, work contract, execution record, verification, and handoff
can be validated as one slice.

Allowed write targets:

- `artifact/workflow-ui-commondb-20260608/output/demos/demo-workflow-001/`
- `scripts/check-demo-workflow.py`
- `tests/workflow_core/test_demo_fixture.py`

Verification:

- `uv run python scripts/check-demo-workflow.py`,
- `make check-fast`.

### X1 CommonDB Context Adapter Contract

Status: planned  
Lane: `demo-context`

Intent: define the Dev-Foundation side of the CommonDB context adapter.

Allowed write targets:

- `artifact/workflow-ui-commondb-20260608/output/docs/commondb-context-adapter-contract.md`
- `src/workflow_adapters/commondb_context_adapter.py`
- `templates/context-request.yaml`
- `templates/context-result.yaml`
- `tests/workflow_adapters/test_commondb_context_adapter.py`

Acceptance:

- MCP primary,
- CLI fallback,
- HTTP only for health/status smoke unless a later approved contract says
  otherwise,
- blocked/error returned as blocked workflow context, not model-memory fallback.

Verification:

- mocked adapter tests,
- `make check-fast`.

### X2 Workflow UI Context Panel

Status: planned  
Lane: `demo-context`

Intent: show CommonDB context results in the workflow console using only safe
`source_ref`, bounded snippet, status, and error fields.

Allowed write targets:

- `app/workflow_console/`
- `src/workflow_ui/`
- `tests/workflow_ui/`

Verification:

- UI static tests,
- adapter mock tests,
- leak scan.

### X3 Dual-Repo Vertical Demo

Status: planned  
Lane: `demo-context`

Intent: assemble a sanitized demo where CommonDB produces bounded context and
this repo validates the resulting workflow artifact.

Allowed write targets:

- `artifact/workflow-ui-commondb-20260608/output/demos/demo-workflow-commondb-run/`
- `scripts/check-demo-workflow.py`
- `tests/workflow_core/`

Acceptance:

- CommonDB artifact is consumed as `source_ref`/bounded context only,
- no vault, corpus, Qdrant storage, local path, raw source body, vector, log, or
  secret crosses the repo boundary,
- both repos remain separately verifiable.

Verification:

- Dev repo: `make check-fast` or `make check-foundation` before PR handoff,
- CommonDB repo: consume only its sanitized demo context artifact after its own
  verification passes.

## Merge Order

1. D0 external-facing foundation overview.
2. D1/D2/D3 Workflow Core state and checks.
3. D5 App Server adapter design.
4. D6 minimal mock workflow console.
5. D4 Codex SDK runner.
6. X1 CommonDB context adapter contract.
7. D8/X2/X3 demo and UI context slice.
8. D7 real App Server bridge only after explicit human approval.

## Human Gates

Human approval is required before:

- merge,
- direct App Server integration,
- real Codex SDK execution that can write files,
- CI/CD or dependency changes,
- release or deployment,
- credential or auth handling,
- external writes outside an owned review branch or PR.

## Verification Strategy

Start narrow and widen only when the touched surface requires it:

1. targeted docs/schema/unit/static checks,
2. `make check-fast`,
3. `make check-required` for Makefile, scripts, tests, shared behavior, or PR
   handoff,
4. `make check-foundation` for full PR readiness or high-risk review handoff.

No verification has been run for this planning file at creation time.
