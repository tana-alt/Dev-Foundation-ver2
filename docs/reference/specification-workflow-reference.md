---
status: reference
owner: foundation
source_of_truth_level: reference
created_at: 2026-06-05
---

# Specification Workflow Reference

Use this reference when converting a human goal into an observable behavior
specification, reviewing a specification before build, freezing an approved
specification, slicing it into parallel lanes, or coordinating subagent workflow
phases through records.

## Trigger

Open this reference when:

- a user request or task packet asks for a specification workflow;
- a goal must be turned into observable requirements and acceptance criteria;
- a specification must be reviewed before lane mapping or implementation;
- a human-approved specification must be frozen and sliced into parallel lane
  work;
- a subagent workflow must pass state through records rather than conversation;
- implementation policy must be separated from behavior authority;
- lane integration or rework requires an `INC-*` inconsistency register.

Do not open this reference when:

- a worker already has a complete lane work contract and no spec ambiguity
  exists;
- the task is only a small local code review against named source refs;
- the task only needs concrete Git branch/worktree mechanics;
- the task only needs current verification command selection;
- the task is ordinary implementation with no specification, lane split, or
  subagent handoff.

Adjacent references:

- Use `packet-evidence-and-rework-reference.md` for work-contract, evidence,
  verification, and rework record fields.
- Use `git-worktree-and-branch-reference.md` for concrete branch/worktree,
  changed-path, and conflict mechanics.
- Use `repo-boundary-and-storage-reference.md` for `Plan/`, `artifact/`,
  `src/`, and template placement.
- Use `verification-ci-and-pr-reference.md` for current verification commands
  and PR/handoff evidence.

Expected effect after opening:

- Keep specification records behavior-only.
- Put implementation policy in implementation-policy records or lane work
  contracts.
- Split approved specifications into bounded lane slices.
- Coordinate subagents through `main_lane` and record refs.
- Return rework when requirements are not observable, source refs are missing,
  implementation details leak into the spec, verification expectations are
  ambiguous, or unresolved `INC-*` items block convergence.

## Workflow

```text
human goal
  -> main_lane
  -> goal_run_record
  -> spec_drafter
  -> specification_packet
  -> spec_reviewer
  -> specification_review_record
  -> main_lane spec proposal
  -> human spec approval
  -> approved_spec_freeze
  -> lane_mapper
  -> parallel_lane_map / work_contracts
  -> build_worker(s)
  -> build_result(s)
  -> review_worker(s)
  -> review_record(s)
  -> integration_reviewer
  -> inconsistency_register
  -> rework_worker(s) if needed
  -> review_worker(s)
  -> integration_reviewer
  -> convergence_checker
  -> final_handoff_record
  -> human final review
  -> complete / rework / blocked
```

This workflow is a phase-and-record contract. It is not a runtime scheduler,
queue, lock ledger, worker heartbeat system, dashboard, or broad role hierarchy.

## Communication Rules

Forbidden:

- subagent directly returns to the human;
- subagent directly asks another subagent for scope or decisions;
- subagent changes an approved specification without explicit scope;
- subagent treats implementation policy as behavior authority;
- subagent expands source refs into broad repo context without recording why.

Allowed:

- `subagent -> result_record -> main_lane`;
- `subagent -> rework_request -> main_lane`;
- `subagent -> human_decision_required -> main_lane -> human`;
- `main_lane -> record refs -> next subagent`.

## Specification Boundary

Specifications define WHAT must be true.

Allowed in a specification:

- problem and desired outcome;
- user-visible behavior;
- public/data contracts;
- trust boundaries;
- side effects and safety constraints;
- acceptance criteria;
- invariants and non-goals;
- security, privacy, reliability, and observable performance constraints.

Forbidden in a specification:

- file layout;
- function, class, or module names;
- coding style, lint rules, or formatting policy;
- library choice;
- branch/worktree strategy;
- test command selection;
- refactor strategy;
- internal algorithm choice.

Exception: an implementation detail may be stated only when it is itself an
external contract, persistence or trust-boundary requirement, irreversible
behavior, safety/security constraint, or externally visible reliability
constraint.

## Implementation Policy Boundary

Implementation policy belongs in one of:

- a lane work contract;
- `artifact/<project_id>/output/implementation-policies/<work_id>/<lane>.yaml`;
- nearby existing source, test, Makefile, or tool configuration refs named by
  the lane.

Implementation policy records guide HOW to satisfy an approved specification
slice. They must not redefine WHAT behavior is required.

## Record Placement

Reusable blank templates:

```text
templates/specification-packet.yaml
templates/specification-review-record.yaml
templates/implementation-policy-record.yaml
templates/workflow-run-record.yaml
templates/inconsistency-register.yaml
```

Project-specific durable records:

```text
artifact/<project_id>/output/workflows/<work_id>.yaml
artifact/<project_id>/output/specs/<spec_id>.md
artifact/<project_id>/output/specs/<spec_id>.yaml
artifact/<project_id>/output/implementation-policies/<work_id>/<lane>.yaml
artifact/<project_id>/evidence/
artifact/<project_id>/verification/
Plan/<project_id>/lane-maps/<work_id>.yaml
```

Do not place loose specs, workflow records, plans, evidence, verification, or
project records directly under root-level folders. Do not store queues, locks,
heartbeats, worker polling, dashboards, local runtime state, or secrets.

## Goal Set

Goal set converts the user request into a minimal goal brief. It does not choose
implementation strategy.

Required content:

- problem;
- desired outcome;
- success criteria;
- non-goals;
- constraints;
- source refs;
- denied context;
- next action.

## Specification Draft

Specification draft converts the goal into observable requirements.

Each requirement should include:

- `REQ-*` ID;
- statement;
- observable outcome;
- acceptance criteria with `AC-*` IDs;
- non-goals when relevant;
- affected public/data/trust/side-effect surfaces when relevant.

## Specification Review

Specification review decides whether the spec is ready for human review. It is
not a code-quality review.

Review checks:

- goal traceability;
- observable requirements;
- verifiable acceptance criteria;
- explicit non-goals;
- no implementation-policy leakage;
- clear trust/side-effect/human-gate surfaces;
- clear unresolved questions and rework items.

Allowed decisions:

```text
approved_for_human_review
rework
```

Build does not start until human approval freezes the specification.

## Lane Map Integration

Approved specifications may be sliced into parallel lanes. Add optional spec
scope to lane maps when the map is driven by an approved specification:

```yaml
spec_scope:
  approved_spec_ref: artifact/<project_id>/output/specs/<spec_id>.md
  spec_review_ref: artifact/<project_id>/evidence/spec-review-<review-id>.yaml
  requirement_ids:
    - REQ-001
```

Each lane may name the requirement slice and implementation policy refs:

```yaml
lanes:
  - lane: api-contract
    requirement_ids:
      - REQ-001
    source_refs:
      - artifact/<project_id>/output/specs/<spec_id>.md#REQ-001
      - src/<project_id>/api/
      - tests/test_api_contract.py
    implementation_policy_refs:
      - pyproject.toml
      - Makefile
    allowed_write_targets:
      - src/<project_id>/api/
      - tests/test_api_contract.py
```

Workers should receive only their lane slice plus relevant approved spec
sections and implementation policy refs, not the full map unless they are
coordinating the split.

## Subagent Phase Contracts

### `main_lane`

Responsibilities:

- receive human goal;
- create or update workflow-run record;
- route phase-specific records to subagents;
- integrate results;
- maintain human gates;
- update the inconsistency register;
- return final handoff to the human.

Does not replace specialist review or implement every lane by itself.

### `spec_drafter`

Input:

- goal refs;
- source refs;
- constraints;
- non-goals.

Output:

- `specification_packet`.

Return rework if source refs or requirements are too ambiguous to produce
observable behavior.

### `spec_reviewer`

Input:

- specification packet;
- original goal refs;
- source refs.

Output:

- `specification_review_record`.

Decision:

```text
approved_for_human_review
rework
```

### `lane_mapper`

Input:

- human-approved spec ref;
- spec review ref;
- requirement IDs.

Output:

- `parallel_lane_map`;
- work contracts or work-contract refs.

### `build_worker`

Input:

- approved spec slice;
- lane work contract;
- implementation policy refs;
- allowed write targets.

Output:

- changed paths or artifact refs;
- evidence record;
- verification result;
- residual risk.

### `review_worker`

Input:

- approved spec slice;
- lane work contract;
- build result;
- changed paths;
- verification result.

Output:

- review record using evidence or verification record shape.

Decision:

```text
approved
rework
blocked
```

### `integration_reviewer`

Input:

- build results;
- review records;
- lane map;
- approved spec ref.

Output:

- integration review evidence;
- draft or updated inconsistency register.

### `rework_worker`

Input:

- one `INC-*` item;
- relevant spec, build, review, and verification refs.

Output:

- rework result;
- updated changed paths or artifact refs;
- verification result;
- residual risk.

A rework worker must target a specific `INC-*` item. If the specification is
wrong, return a spec rework request through `main_lane`.

### `convergence_checker`

Input:

- approved spec ref;
- lane map;
- build/review/rework refs;
- inconsistency register;
- verification records.

Output:

- convergence verification record;
- final decision.

Decision:

```text
converged
rework_required
blocked
human_review_required
```

## Inconsistency Register

Use `inconsistency-register.yaml` to track issues that block or qualify
convergence.

Common types:

```text
INC-001: spec_vs_implementation
INC-002: implementation_vs_tests
INC-003: lane_conflict
INC-004: missing_requirement
INC-005: verification_gap
INC-006: human_decision_required
```

Each item should include:

- ID;
- type;
- severity;
- status;
- requirement IDs;
- affected lanes;
- evidence refs;
- required rework or human decision;
- closure refs when resolved.

## Rework Rules

Return rework when:

- source refs are missing;
- requirements are not observable;
- acceptance criteria cannot be verified;
- implementation policy appears inside a specification;
- implementation refs are used as behavior authority;
- a build lane changes spec without scope;
- allowed write targets are missing or violated;
- subagent output bypasses `main_lane`;
- open critical/high `INC-*` items remain;
- human-gated surfaces lack approval;
- verification cannot be attempted or honestly reported.

## Convergence

A workflow may converge only when:

- every approved `REQ-*` is traced to evidence or a blocked reason;
- every `AC-*` has verification evidence or an explicit gap;
- no open critical/high inconsistency remains;
- medium/low items are resolved or accepted as residual risk;
- verification is honestly recorded;
- human final review has a clear next action.

## PR Evidence

Lane PRs and handoffs must include:

- intent;
- approved spec ref and requirement IDs;
- work contract or lane-map ref;
- changed paths or artifacts;
- verification results;
- docs impact;
- allowed-write-target check;
- sibling conflict status;
- human-gate status;
- resolved and open inconsistency IDs;
- residual risk;
- review focus.

Spec approval and merge remain human-only.
