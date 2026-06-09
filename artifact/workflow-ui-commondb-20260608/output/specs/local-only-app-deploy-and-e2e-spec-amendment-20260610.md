---
schema_version: "0.1"
record_type: specification_packet
status: draft_for_spec_review
project_id: workflow-ui-commondb-20260608
spec_id: SPEC-LOCAL-ONLY-APP-DEPLOY-E2E-AMENDMENT-20260610
created_at: "2026-06-10"
amends:
  - artifact/workflow-ui-commondb-20260608/output/specs/local-only-app-deploy-and-mcp-dry-run-spec.md
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md
source_refs:
  - AGENTS.md
  - docs/01-agent-operating-contract.md
  - docs/02-output-verification-contract.md
  - docs/03-repo-boundary-and-storage-contract.md
  - docs/reference/specification-workflow-reference.md
  - artifact/workflow-ui-commondb-20260608/output/specs/local-only-app-deploy-and-mcp-dry-run-spec.md
  - artifact/workflow-ui-commondb-20260608/output/specs/personal-mac-workflow-app-spec.md
---

# Local-Only App Deploy And E2E Completion Amendment

## Purpose

Amend the local-only personal app deploy and CommonDB MCP dry-run behavior so
completion requires the actual personal app deployment path to be implemented
end to end. Completion cannot be claimed while deploy, installability, Codex
App deep links, MCP config wiring, E2E checks, link checks, or dry-run security
blocking remain "not implemented".

Personal app means an app that is downloadable or installable into the user's
own macOS Applications/app surface for local personal use. The app remains
local-only and user-scoped. It is not public distribution, notarization,
production infrastructure, Qdrant enablement, or Obsidian write-back.

## Authority And Boundary

This amendment defines WHAT must be observable before implementation can be
accepted. It does not choose source files, frameworks, packaging tools,
commands, scripts, or implementation strategy.

Allowed external-contract and trust-boundary details are limited to:

- macOS user app install/download target.
- Codex App deep link contract.
- Codex config target through CommonDB MCP search `dry_run`.
- Dry-run redaction and block behavior.
- Local-only and no-public-network safety.
- Human-gated secret-bearing or irreversible external actions.

## Requirements

### REQ-E2E-001 Personal App Deploy Completion

The local personal app deploy path must be real and end to end before this
scope can be complete.

Observable outcome: the reviewer can obtain or install the personal app into a
local user macOS app surface and launch the app through the same path that is
claimed as complete.

Acceptance criteria:

- AC-E2E-001: Completion evidence includes an actual local app artifact or
  installable user-scoped app surface for the personal workflow app.
- AC-E2E-002: The accepted app target is limited to the user's own macOS app
  surface, such as a downloadable app artifact or `~/Applications`.
- AC-E2E-003: The deploy path is not considered complete when marked "not
  implemented", stubbed, placeholder-only, preview-only, or documented-only.
- AC-E2E-004: The reviewer can launch the app from the accepted personal app
  surface without relying on a static HTML artifact as the completed product.
- AC-E2E-005: Rollback or removal of the local app surface is documented in
  completion evidence.

### REQ-E2E-002 Local-Only Deploy Safety

The personal app deploy path must stay local, reversible, and user-scoped.

Observable outcome: completing deploy does not create public distribution,
production infrastructure, or system-wide behavior.

Acceptance criteria:

- AC-E2E-006: No public network listener, public tunnel, shared LAN service,
  externally reachable callback, production endpoint, or public distribution
  path is enabled.
- AC-E2E-007: System `/Applications` installation, notarization, release,
  package distribution, CI/CD release changes, infrastructure changes, launch
  agents, daemons, login items, and background auto-start remain out of scope
  unless separately approved.
- AC-E2E-008: Any secret-bearing or irreversible external action remains
  blocked until a human gate explicitly approves that action.
- AC-E2E-009: Local config, local app deploy, local launch, and local link
  checks are in scope after human approval of this specification.

### REQ-E2E-003 Codex App Deep Link Completion

The personal app must expose and verify Codex App deep link wiring before
completion.

Observable outcome: the app can navigate from workflow state to the intended
Codex App project, conversation, or artifact surface through opaque refs.

Acceptance criteria:

- AC-E2E-010: Completion evidence includes a verified Codex App deep link from
  the personal app surface.
- AC-E2E-011: Deep link state includes opaque project, workflow, thread, or
  artifact refs as applicable; raw thread bodies, raw artifact bodies,
  credentials, tokens, cookies, browser sessions, terminal logs, and
  secret-bearing metadata are absent.
- AC-E2E-012: Broken, stale, missing, or unavailable Codex App links are
  represented as pending or blocked and prevent completion.
- AC-E2E-013: Deep link verification cannot remain "not implemented",
  placeholder-only, or manually asserted without observable link-check
  evidence.

### REQ-E2E-004 MCP Config To CommonDB Dry-Run Completion

The MCP config path from the Codex config target through CommonDB search
`dry_run` must be verified before completion.

Observable outcome: the approved local Codex config target can resolve the
CommonDB search MCP path in dry-run mode without enabling live search,
indexing, writes, or Qdrant.

Acceptance criteria:

- AC-E2E-014: Completion evidence names the human-approved local Codex config
  target and confirms it is the config surface used for the dry-run check.
- AC-E2E-015: The verified MCP path is limited to CommonDB search dry-run
  behavior.
- AC-E2E-016: The MCP config and dry-run path cannot be marked complete while
  "not implemented", unconfigured, unreachable, or asserted only in text.
- AC-E2E-017: Dry-run output is treated as untrusted advisory tool output, not
  as workflow authority, prompt authority, verification authority, or
  completion authority.
- AC-E2E-018: Live MCP calls, searchability, indexing, vector persistence,
  external writes, and Obsidian write-back remain blocked unless separately
  approved.

### REQ-E2E-005 Dry-Run Security Block Verification

Completion must include proof that unsafe dry-run output is blocked or
redacted before it can influence agent authority.

Observable outcome: a fake security-risk dry-run result cannot enter prompts,
workflow authority, handoff authority, UI raw bodies, or completion evidence.

Acceptance criteria:

- AC-E2E-019: Security verification uses fake non-secret risk content only.
- AC-E2E-020: The dry-run result is blocked or redacted before agent
  consumption.
- AC-E2E-021: Agent-visible output contains only safe status, non-secret
  reason, safe refs when available, and evidence refs.
- AC-E2E-022: Raw risky payloads, local paths, raw memo bodies, raw source
  bodies, vector payloads, embeddings, credentials, tokens, cookies, and other
  secret-bearing material are absent from prompts, UI, artifacts, logs, and
  handoff records.
- AC-E2E-023: Dry-run security blocking cannot remain "not implemented",
  skipped, or manually asserted at completion.

### REQ-E2E-006 E2E Deploy And Link Checks

Completion requires end-to-end app, deploy, deep link, MCP dry-run, and block
checks against the implemented personal app path.

Observable outcome: completion evidence demonstrates the same local personal
app surface that the user will run, with required links and dry-run safety
checks functioning.

Acceptance criteria:

- AC-E2E-024: E2E verification launches the personal app from the accepted
  local user app surface.
- AC-E2E-025: E2E verification confirms the primary app functionality required
  by the personal Mac workflow app specification is present.
- AC-E2E-026: E2E verification includes Codex App deep link checks.
- AC-E2E-027: E2E verification includes the Codex config target to CommonDB
  search dry-run path.
- AC-E2E-028: E2E verification includes dry-run block or redaction behavior.
- AC-E2E-029: Any failed, missing, unavailable, placeholder, stubbed, or "not
  implemented" result for deploy, deep link, MCP config, dry-run block, or
  E2E/link checks prevents completion.

### REQ-E2E-007 Qdrant Future Optionality

Qdrant is not required and must not block this pass.

Observable outcome: Qdrant is recorded only as future planned or optional work.

Acceptance criteria:

- AC-E2E-030: Qdrant enablement is explicitly out of scope for this pass.
- AC-E2E-031: Absence of Qdrant does not block deploy, Codex deep link, MCP
  dry-run, E2E, link-check, or dry-run block completion.
- AC-E2E-032: Any Qdrant use, vector persistence, embedding storage, or Qdrant
  internals exposure requires a separate approved specification or contract.

## Explicit Completion Criteria

Implementation cannot be accepted as complete unless all of the following are
true:

- CC-E2E-001: The personal app has app functionality present in the actual
  local user app surface.
- CC-E2E-002: The local deploy/install/download path is implemented and
  verified end to end.
- CC-E2E-003: Codex App deep link wiring is implemented and verified.
- CC-E2E-004: The human-approved Codex config target through CommonDB search
  dry-run path is implemented and verified.
- CC-E2E-005: E2E deploy checks and link checks are part of completion
  evidence.
- CC-E2E-006: Dry-run security block or redaction behavior is verified.
- CC-E2E-007: No required deploy, deep link, MCP config, dry-run block,
  E2E/link check, or personal app functionality surface is "not implemented",
  placeholder-only, stubbed, skipped, or asserted without evidence.
- CC-E2E-008: Qdrant remains future planned or optional and is not a current
  blocker.

## Human Gates

Human approval is required before:

- Secret-bearing actions or handling secret-bearing material.
- Irreversible external actions.
- Public network exposure.
- Live MCP calls.
- Searchability, indexing, vector persistence, or Qdrant enablement.
- Obsidian write-back.
- Public distribution, notarization, release, production infrastructure, CI/CD
  release changes, dependency changes, system installation, launch agents,
  daemons, login items, or auto-start behavior.

After human approval of this specification, local config/app deploy/link checks
are in scope when they remain local-only, user-scoped, reversible, and free of
secret-bearing or irreversible external actions.

## Non-Goals

- Public distribution.
- Notarization.
- Production infrastructure.
- Qdrant enablement.
- Vector persistence or embedding storage.
- Obsidian write-back unless separately approved.
- Live MCP calls unless separately approved.
- System-wide install, launch agents, daemons, login items, or background
  auto-start.
- Replacing Codex App chat or artifact review.
- Storing or rendering raw thread bodies, raw artifact bodies, raw memo bodies,
  raw source bodies, terminal logs, browser sessions, credentials, tokens,
  cookies, local paths, vector payloads, embeddings, Qdrant internals, or raw
  risky payloads.

## Spec Review Focus

The spec reviewer should check that this amendment:

- Preserves WHAT-only behavior except for necessary external contracts and
  trust boundaries.
- Makes completion impossible while required surfaces remain "not implemented".
- Treats local app deploy, Codex deep links, MCP config dry-run, E2E checks,
  link checks, and dry-run block verification as required completion evidence.
- Carries Qdrant only as future planned or optional.
- Preserves human gates for secret-bearing and irreversible external actions.
