---
schema_version: "0.1"
record_type: specification_packet
status: approved_spec_amendment_frozen
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-LOCAL-ONLY-APP-DEPLOY-MCP-DRY-RUN-001
created_at: "2026-06-10"
amends:
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md
  - artifact/workflow-ui-commondb-20260608/output/specs/obsidian-commondb-contract-integration-spec.md
approval_ref: user_request:2026-06-10-local-only-app-deploy-and-mcp-dry-run
source_refs:
  - AGENTS.md
  - docs/01-agent-operating-contract.md
  - docs/02-output-verification-contract.md
  - docs/03-repo-boundary-and-storage-contract.md
  - docs/reference/specification-workflow-reference.md
  - docs/reference/packet-evidence-and-rework-reference.md
  - .agents/skills/deploy-readiness/SKILL.md
  - .agents/skills/security-check/SKILL.md
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md
  - artifact/workflow-ui-commondb-20260608/output/specs/obsidian-commondb-contract-integration-spec.md
  - artifact/workflow-ui-commondb-20260608/output/reviews/obsidian-commondb-contract-integration-final-handoff-20260610.yaml
---

# Local-Only App Deploy And MCP Dry-Run Spec Amendment

## Purpose

Define the approved behavior amendment for turning the personal Mac workflow app
into a local-only personal app surface and verifying bounded CommonDB MCP
search behavior before any live or externally visible operation is enabled.

This amendment preserves Workflow Core as the state authority, Codex App as the
conversation and artifact review owner, and CommonDB as advisory context only.
It does not authorize implementation by `main_lane`, Qdrant enablement,
CommonDB indexing, live MCP calls, Obsidian write-back, public network exposure,
system-wide installation, launch agents, auto-start behavior, release,
notarization, CI/CD changes, protected Git actions, or external writes.

## Authority Model

- This amendment is behavior authority only for the local-only deploy and MCP
  dry-run verification surfaces named here.
- `main_lane` may coordinate, review records, and dispatch subagent lanes, but
  must not directly implement application code, MCP configuration, deploy
  packaging, E2E automation, or security dry-run behavior for this amendment.
- Implementation policy records and lane work contracts may choose the safest
  local mechanics, but must not redefine the requirements or acceptance
  criteria below.

## Requirements

### REQ-LD-001 Local-Only Deploy Boundary

The personal app must remain a local-only app surface for a single local user
until a later approved amendment expands deployment scope.

Observable outcome: running or installing the app does not expose a public
network service, does not create system-wide behavior, and has a clear rollback
path.

Acceptance criteria:

- AC-LD-001: The deploy surface is limited to a local user app artifact or the
  current user's `~/Applications` destination.
- AC-LD-002: System `/Applications` installation is blocked unless a later
  human-approved contract explicitly authorizes it.
- AC-LD-003: No public network listener, public tunnel, shared LAN service,
  remote access endpoint, or externally reachable callback is enabled.
- AC-LD-004: No launch agent, daemon, login item, background auto-start, or
  auto-start outside the local user scope is created unless a later approved
  contract explicitly authorizes it.
- AC-LD-005: Rollback instructions are visible in the deploy handoff and allow
  removal of the local app artifact and any local-only config created by the
  approved lane.

### REQ-LD-002 Local Build And Install Target

The app build/install target must stay local, reversible, and user-scoped.

Observable outcome: the app can be built and prepared for local review without
publishing, releasing, notarizing, or installing into system scope.

Acceptance criteria:

- AC-LD-006: A build artifact for local review may be produced only for the
  personal workflow app surface.
- AC-LD-007: Local install is blocked until a human approves the exact target
  and rollback step.
- AC-LD-008: Any accepted install target is limited to a local user app artifact
  or `~/Applications`.
- AC-LD-009: Deployment, release, notarization, package distribution, CI/CD
  release changes, dependency changes, and infrastructure changes remain
  human-gated and out of scope for this amendment.

### REQ-LD-003 E2E And Link-Check Observability

The local app must be verified through an end-to-end launch and link check
before the deploy surface is considered ready for human review.

Observable outcome: a reviewer can see that the app launches, the primary
window renders, link state is safe, CommonDB controls are present, and unsafe
content is absent from the UI.

Acceptance criteria:

- AC-LD-010: E2E verification proves the app launches and the primary window
  renders.
- AC-LD-011: The Codex App link button state and target URL/ref are checked
  without executing external writes.
- AC-LD-012: Codex App link/ref values remain opaque; raw thread bodies,
  artifact bodies, credentials, tokens, cookies, browser sessions, local paths,
  and terminal logs are not rendered.
- AC-LD-013: Broken, stale, unavailable, or missing Codex App links are shown as
  pending or blocked and do not trigger external writes.
- AC-LD-014: CommonDB controls for bounded search are visible.
- AC-LD-015: UI verification confirms raw memo bodies, raw source bodies,
  secrets, local paths, vault/corpus internals, vector payloads, embeddings,
  raw risky payloads, and Qdrant internals are absent from visible UI.

### REQ-LD-004 CommonDB MCP Dry-Run Scope

Only CommonDB search MCP behavior is eligible for initial enablement, and only
in dry-run mode.

Observable outcome: the workflow can inspect a safe dry-run search path without
using Qdrant, live search, indexing, searchability migration, or external
writes.

Acceptance criteria:

- AC-LD-016: The only MCP tool eligible for the first enablement scope is
  `commondb.search`.
- AC-LD-017: Qdrant remains disabled, unused, and out of scope.
- AC-LD-018: Initial MCP behavior is dry-run only and cannot perform live search
  or external writes.
- AC-LD-019: Dry-run results are treated as untrusted tool output and advisory
  data, not as instructions, authority, verification evidence, or completion
  evidence.
- AC-LD-020: Searchability, indexing, vector persistence, Obsidian write-back,
  and any live MCP call require separate explicit human gates.

### REQ-LD-005 Security Dry-Run Blocking

The MCP dry-run security check must prove that a fake security-risk search
result is blocked or redacted before it can influence agent authority.

Observable outcome: unsafe dry-run search output cannot become prompt
authority, cannot expand scope, cannot authorize side effects, and is not
visible to the agent as raw risky payload.

Acceptance criteria:

- AC-LD-021: The dry-run security verification uses a fake security-risk query
  result with no real secret, credential, exploit payload, or protected data.
- AC-LD-022: The result is recorded as blocked or redacted before agent
  consumption.
- AC-LD-023: The blocked/redacted result cannot be injected into prompts,
  workflow authority, contract authority, verification authority, handoff
  authority, or completion authority.
- AC-LD-024: The agent-visible output contains only safe status, non-secret
  reason, safe source refs when available, and evidence refs.
- AC-LD-025: Any raw risky payload, raw body, local path, vector payload,
  embedding, credential, token, cookie, or secret-bearing material remains
  absent from prompts, UI, artifacts, logs, and handoff records.

### REQ-LD-006 Human Gates And Blocked States

Gated operations must remain explicit, visible, and blocked until approved.

Observable outcome: the local-only deploy and dry-run plan cannot silently turn
into config mutation, live search, indexing, write-back, install, release, or
external side effects.

Acceptance criteria:

- AC-LD-026: Editing MCP config requires a human-approved lane contract naming
  the exact local config target and rollback path.
- AC-LD-027: Live MCP calls are blocked until explicitly approved after dry-run
  review.
- AC-LD-028: Local install is blocked until the human approves the exact local
  user destination.
- AC-LD-029: Searchability, indexing, and vector persistence remain blocked
  until separately approved.
- AC-LD-030: Obsidian read/write and write-back remain blocked until separately
  approved.
- AC-LD-031: Missing evidence, broken links, unsafe MCP output, unavailable
  CommonDB, or Qdrant usage is represented as blocked, pending, or rejected and
  cannot be treated as completion.

## Non-Goals

- Implementing app code, tests, MCP config, packaging, install scripts, or E2E
  automation in `main_lane`.
- Enabling Qdrant.
- Enabling MCP tools other than `commondb.search`.
- Running live MCP calls before dry-run review and explicit human approval.
- CommonDB indexing, searchability migration, vector persistence, or reusable
  corpus creation.
- Obsidian vault read/write or write-back.
- Public deployment, release, notarization, package distribution, CI/CD release
  changes, dependency changes, infrastructure changes, or system-wide install.
- Creating launch agents, daemons, login items, background auto-start, or
  auto-start outside the local user scope.
- Storing or rendering raw thread bodies, raw memo bodies, raw source bodies,
  secrets, browser sessions, local paths, vector payloads, embeddings, terminal
  logs, Qdrant internals, or raw risky payloads.

## Verification Expectations

- Specification review confirms traceability to the source refs, observable
  acceptance criteria, explicit human gates, and no implementation-policy
  leakage.
- Freeze record lists all REQ-LD and AC-LD IDs.
- Lane map keeps all implementation lanes planned and unassigned until
  `main_lane` dispatches subagents.
- Implementation policy records local-only deployment constraints, dry-run MCP
  boundaries, rollback expectation, and security redaction expectations.
- Records parse successfully as YAML where applicable.
- Link and E2E checks are required for implementation lanes but are not run in
  this records-only design phase.
- Security dry-run verification is required for implementation lanes but is not
  run in this records-only design phase.

## Human Gates

The following gates remain required after this amendment:

- MCP config edit.
- Any live MCP call.
- Local install into a user destination.
- CommonDB searchability, indexing, vector persistence, or Qdrant enablement.
- Obsidian read/write or write-back.
- Public network exposure, launch agent, login item, daemon, auto-start, system
  install, release, notarization, package distribution, CI/CD release change,
  dependency change, infrastructure change, protected Git action, merge, or
  external write.
- Handling secrets or secret-bearing material.

## Next Action

`main_lane` should use the approved freeze record and lane map to dispatch
bounded subagent lanes. Implementation must not begin in `main_lane`.
