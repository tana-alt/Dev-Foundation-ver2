---
plan_id: Plan_N0001
project_id: system-improvement
status: completed
log_ref: Plan/system-improvement/logs/Plan_N0001.log.md
---

# Repository System Design Improvement Plan

## 0. Positioning

This plan improves the quality of AI-agent-produced repository outputs without
turning system design into always-read doctrine.

Goal:

```text
Add a compact conditional system-design skill and a lightweight design gate for
architecture-significant work.
```

Method:

```text
- Keep active docs compact.
- Trigger system-design only for narrowly defined significant architecture work.
- Use a small work-contract gate, not a full design record template.
- Use existing evidence, verification, and human-gate contracts for review.
```

Non-goals:

```text
- no new active system-design doc
- no always-read architecture manual
- no repo-wide ADR directory
- no initial templates/design-record.yaml
- no Plan/<project_id>/design/ storage root
- no separate human_architecture_review_required work-contract field
```

## 1. Decision: Simplify The Gate

Choose gate simplification over gate hierarchy.

Reason:

```text
The repo already has a compact context model and existing human-gate rules.
Adding nested architecture-review levels would make agents spend too much effort
classifying process state instead of making a bounded design decision.
```

The design gate should answer only three questions:

```yaml
design_gate:
  architecture_significance: none
  system_design_skill_required: false
  reason: "Why the system-design skill is or is not required."
```

The `system_design_skill_required` value is derived from
`architecture_significance`:

```text
none        -> false
local       -> false
significant -> true
```

Human architecture review should not be a separate work-contract boolean. Use
the existing `human_gate` model and Human Gate rules when the work changes a
surface that already requires human approval.

## 2. Significance Classifier

### `none`

No system-design skill is required.

Examples:

```text
- typo, formatting, copy, comments
- small test-only repair
- mechanical cleanup with no behavior change
- updating a template example without changing its contract
- local docs/reference wording that does not change process behavior
```

### `local`

Local design reasoning is enough. No system-design skill is required.

Examples:

```text
- small internal utility
- narrow component or module edit inside an existing boundary
- small internal API adjustment following an established pattern
- validation or error-handling change on an existing contract
- repo-local skill wording or index update that does not add a new capability,
  external write path, trust boundary, or storage root
```

### `significant`

The system-design skill is required only when the change creates or materially
changes an architecture boundary or high-blast-radius behavior.

Use `significant` when at least one condition is true:

```text
- new app, service, module ownership boundary, or long-lived shared abstraction
- public or externally consumed API/contract with compatibility expectations
- persistent data ownership, schema, retention, deletion, or migration behavior
- auth, authorization, privacy, secret handling, or trust-boundary behavior
- external integration or agent external write path with side effects
- queue, worker, scheduler, or runtime workflow with retry/idempotency/failure concerns
- deployment/runtime topology that changes availability, rollback, or operations
- irreversible or hard-to-rollback change
- multiple plausible designs with material tradeoffs across reliability,
  security, data ownership, operations, or compatibility
```

Do not classify as `significant` merely because a change spans several files.
File count is evidence to inspect, not the deciding factor.

## 3. Human Review Scope

Do not add `human_architecture_review_required` to the work contract.

Human review is required through the existing Human Gate only for significant
work that includes one of these higher-risk surfaces:

```text
- public API or externally consumed contract
- auth, authorization, privacy, secrets, or trust boundary
- database schema, persistent data ownership, retention, deletion, or migration
- external integration, external write, payment, webhook, or irreversible side effect
- queue, worker, scheduler, deployment topology, or operational blast radius
- security-sensitive behavior
- release, deployment, CI/CD, dependency, infrastructure, or protected action
```

Significant internal design work can proceed without a human architecture gate
when it is reversible, internal-only, has no persistent data/trust/external-write
impact, and verification is clear.

## 4. Design Packet

For `architecture_significance: significant`, the agent reads
`.agents/skills/system-design/SKILL.md` and produces a compact design packet in
the answer, handoff, PR body, or existing evidence artifact. Do not require a
new `templates/design-record.yaml` in the initial PR.

Required packet fields:

```yaml
design_verdict: proceed | rework | blocked | needs_human_review
architecture_significance: significant
problem:
actors:
success_criteria:
non_goals:
constraints:
boundaries:
options:
decision:
verification:
rollback_or_mitigation:
residual_risk:
human_gate:
skill_refs_used:
  - .agents/skills/system-design/SKILL.md
```

Return rework when:

```text
- problem, actors, or success criteria are unclear
- affected boundary is unknown
- quality target or verification is not observable
- non-trivial design has only one option
- rollback or mitigation is undefined for risky work
- existing Human Gate rules require review and the gate is missing
```

## 5. Target Change Set

Add:

```text
.agents/skills/system-design/SKILL.md
tests/test_system_design_integrity.py
```

Modify:

```text
.agents/skills/SKILL_INDEX.md
templates/work-contract.yaml
docs/reference/packet-evidence-and-rework-reference.md
tests/test_contract_models.py
Makefile
```

Do not add:

```text
templates/design-record.yaml
docs/04-system-design-contract.md
docs/system-design.md
docs/architecture-principles.md
docs/adr-guidelines.md
Plan/<project_id>/design/
repo-wide ADR directory
```

## 6. P0 Implementation Detail

### 6.1 Add `.agents/skills/system-design/SKILL.md`

Content shape:

```md
---
name: system-design
description: "Use before implementing a new app/service/module boundary, public or external contract, persistent data ownership, trust boundary, external write path, queue/worker/scheduler, deployment topology, irreversible migration, or materially tradeoff-heavy architecture change."
---

## Purpose

Improve significant architecture work before implementation without expanding
active docs or broad repo context.

## Use when

- Creating or materially changing a long-lived boundary or shared abstraction.
- Adding or changing a public or externally consumed contract.
- Changing persistent data ownership, auth, privacy, secrets, or trust boundaries.
- Adding an external write path, queue, worker, scheduler, deployment topology,
  irreversible migration, or hard-to-rollback behavior.
- Multiple plausible designs have material reliability, security, data,
  operations, or compatibility tradeoffs.

## Do not use when

- The change is typo, formatting, copy, or mechanical cleanup.
- The change is a small internal edit inside an existing boundary.
- Existing repo patterns make the design choice obvious and reversible.

## Required design packet

- problem, actors, success criteria, and non-goals
- constraints and affected boundaries
- observable quality targets
- options considered
- selected option and tradeoffs
- verification
- rollback or mitigation
- residual risk
- human gate status when required by existing repo rules

## Stop conditions

Return rework when required design inputs, verification, rollback/mitigation, or
an existing required human gate is missing.

## Constraints

- Do not read broad docs by default.
- Do not create repo-wide ADRs for local edits.
- Do not add dependencies, services, queues, or storage roots without explicit need.
- Prefer existing repo patterns over new abstractions.

## Output

- `design_verdict`: proceed / rework / blocked / needs_human_review
- `architecture_significance`: significant
- `design_packet`
- `skill_refs_used`
- `residual_risk`
```

### 6.2 Modify `.agents/skills/SKILL_INDEX.md`

Add `system-design` under Conditional skills, not Core skills.

```diff
 ## Conditional skills

+- `system-design`
 - `tdd-scope`
 - `db-migration`
 - `deploy-readiness`
 - `browser-verification`
```

### 6.3 Modify `templates/work-contract.yaml`

Add the simplified design gate:

```yaml
design_gate:
  architecture_significance: none
  system_design_skill_required: false
  reason: "Why the system-design skill is or is not required."
```

### 6.4 Modify `tests/test_contract_models.py`

Add `DesignGate`:

```python
class DesignGate(StrictModel):
    architecture_significance: Literal["none", "local", "significant"]
    system_design_skill_required: bool
    reason: str

    @model_validator(mode="after")
    def design_gate_must_be_consistent(self) -> Self:
        if self.architecture_significance == "significant":
            if not self.system_design_skill_required:
                raise ValueError("significant work requires system-design skill")
        if self.architecture_significance != "significant":
            if self.system_design_skill_required:
                raise ValueError("system-design skill is only required for significant work")
        if not self.reason.strip():
            raise ValueError("design_gate reason must be explicit")
        return self
```

Add `design_gate: DesignGate` to `WorkContractTemplate`.

Add focused negative tests:

```python
def test_work_contract_rejects_significant_design_without_skill() -> None:
    data = load_yaml("templates/work-contract.yaml")
    data["design_gate"]["architecture_significance"] = "significant"
    data["design_gate"]["system_design_skill_required"] = False

    with pytest.raises(ValidationError):
        WorkContractTemplate.model_validate(data)


def test_work_contract_rejects_non_significant_design_with_skill() -> None:
    data = load_yaml("templates/work-contract.yaml")
    data["design_gate"]["architecture_significance"] = "local"
    data["design_gate"]["system_design_skill_required"] = True

    with pytest.raises(ValidationError):
        WorkContractTemplate.model_validate(data)
```

### 6.5 Add `tests/test_system_design_integrity.py`

The test should verify:

```text
- system-design skill exists and is compact
- skill frontmatter includes name: system-design
- skill is registered under Conditional skills
- active docs did not expand with system-design docs
- work contract has simplified design_gate
- templates/design-record.yaml does not exist in the initial PR
```

### 6.6 Modify `Makefile`

Include the new fast structural test:

```diff
 test-fast:
-	$(UV) run pytest -q tests/test_contract_models.py tests/test_extension_surface_integrity.py
+	$(UV) run pytest -q tests/test_contract_models.py tests/test_extension_surface_integrity.py tests/test_system_design_integrity.py
```

### 6.7 Modify `docs/reference/packet-evidence-and-rework-reference.md`

Add a compact reference section:

~~~md
## Design Gate

Use `design_gate` to decide whether `.agents/skills/system-design/SKILL.md`
is required before implementation.

Set `architecture_significance` to:

- `none`: no design work needed
- `local`: local design reasoning is enough
- `significant`: system-design skill is required

Use `significant` only for material architecture boundaries or high-blast-radius
behavior: public/external contracts, persistent data ownership, trust boundaries,
external write paths, queues/workers/schedulers, deployment topology,
irreversible changes, or material design tradeoffs.

For significant work, output should name:

```yaml
skill_refs_used:
  - .agents/skills/system-design/SKILL.md
```

Use existing `human_gate` rules when significant work also touches public APIs,
trust boundaries, persistent data, external writes, deployment, security,
dependencies, CI/CD, release, infrastructure, or irreversible/protected actions.

Return rework when required design inputs, verification, rollback/mitigation, or
an existing required human gate is missing.
~~~

## 7. Agent Workflow After This PR

1. Start from the current user request, task packet or provided scope, named
   source refs, and active contracts.
2. Classify `architecture_significance`.
3. Read `.agents/skills/system-design/SKILL.md` only when significance is
   `significant`.
4. Produce a compact design packet only for significant work.
5. Apply existing write preconditions before implementation.
6. Apply existing verification order.
7. Apply existing Human Gate only when the significant work touches a gated
   risk surface.

## 8. Verification

Expected commands:

```sh
uv run pytest -q tests/test_contract_models.py tests/test_system_design_integrity.py
make test-fast
make check-foundation
```

Run `uv sync --frozen --group dev` first if dependencies are not installed.

## 9. Acceptance Criteria

The PR is acceptable if all are true:

```text
- .agents/skills/system-design/SKILL.md exists.
- .agents/skills/SKILL_INDEX.md registers `system-design` under Conditional skills.
- templates/work-contract.yaml contains simplified design_gate.
- templates/design-record.yaml does not exist.
- tests/test_system_design_integrity.py exists.
- tests/test_contract_models.py validates simplified DesignGate.
- Makefile test-fast includes tests/test_system_design_integrity.py.
- docs/reference/packet-evidence-and-rework-reference.md explains design_gate.
- active docs remain compact.
- docs/04-system-design-contract.md does not exist.
- docs/system-design.md does not exist.
- no repo-wide ADR directory is added.
- make test-fast passes.
- make check-foundation passes.
```

## 10. Suggested PR Title And Body

PR title:

```text
Add lightweight system-design gate for significant architecture work
```

PR summary:

```md
## Summary

Adds a compact conditional system-design skill and a simplified design gate for
significant architecture work.

The gate stays small: `architecture_significance`,
`system_design_skill_required`, and `reason`. Durable design records and a
separate architecture-review boolean are intentionally deferred.

## Changes

- Add `.agents/skills/system-design/SKILL.md`
- Register `system-design` under Conditional skills
- Add simplified `design_gate` to `templates/work-contract.yaml`
- Add DesignGate validation
- Add system design integrity tests
- Include the new test in `make test-fast`
- Document design_gate in packet/evidence/rework reference

## Non-goals

- No new active design doc
- No repo-wide ADR directory
- No always-read architecture manual
- No `templates/design-record.yaml` in this PR
- No `human_architecture_review_required` work-contract field

## Verification

- [ ] `uv run pytest -q tests/test_contract_models.py tests/test_system_design_integrity.py`
- [ ] `make test-fast`
- [ ] `make check-foundation`

## Human review focus

- Confirm the `significant` threshold is narrow enough.
- Confirm human review remains routed through existing Human Gate rules.
- Confirm active docs did not expand.
```

## 11. Implementation Order

Phase 1:

```text
1. Add .agents/skills/system-design/SKILL.md
2. Add system-design to .agents/skills/SKILL_INDEX.md
3. Add simplified design_gate to templates/work-contract.yaml
```

Phase 2:

```text
4. Add DesignGate to tests/test_contract_models.py
5. Add tests/test_system_design_integrity.py
6. Add tests/test_system_design_integrity.py to Makefile test-fast
```

Phase 3:

```text
7. Add design_gate section to docs/reference/packet-evidence-and-rework-reference.md
```

Phase 4:

```text
8. uv run pytest -q tests/test_contract_models.py tests/test_system_design_integrity.py
9. make test-fast
10. make check-foundation
```

## 12. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| system-design over-triggers | Slower work, more boilerplate | Narrow `significant` to material boundaries and high-blast-radius behavior |
| gate is too weak | Architecture risk slips through | Existing Human Gate still covers security, data, external writes, deployment, release, and protected actions |
| active docs expand | Existing repo strength weakens | Static test forbids new system-design active docs |
| design packets become long prose | Context and review cost increase | Keep packet fields compact and output-based |
| validators become too strict | Legitimate work blocked | Validate only consistency and explicit reason |

## 13. Final Decision

Implement the proposal as:

```text
system-design = conditional skill
design_gate = simplified work-contract trigger
design packet = output/handoff shape for significant work
human review = existing Human Gate only
design-record template = deferred
tests = enforcement surface
active docs = unchanged
```

This keeps the original proposal's useful part: architecture-significant work
gets explicit reasoning and verification. It removes the heavy part: a durable
design-record template and a second human-review boolean in every work contract.

## 14. Source References

Repository files to inspect during implementation:

```text
README.md
AGENTS.md
.agents/skills/SKILL_INDEX.md
templates/work-contract.yaml
docs/reference/packet-evidence-and-rework-reference.md
tests/test_contract_models.py
tests/test_extension_surface_integrity.py
Makefile
Plan/README.md
artifact/README.md
```

Research references informing the policy:

```text
SWE-PRBench: Benchmarking AI Code Review Quality Against Pull Request Feedback
https://arxiv.org/abs/2603.26130

AIDev: Studying AI Coding Agents on GitHub
https://arxiv.org/abs/2602.09185

Agentic Much? Adoption of Coding Agents on GitHub
https://arxiv.org/abs/2601.18341

Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild
https://arxiv.org/abs/2603.28592

On Training Large Language Models for Long-Horizon Tasks: An Empirical Study of Horizon Length
https://arxiv.org/abs/2605.02572

Building Effective Agents - Anthropic
https://www.anthropic.com/engineering/building-effective-agents
```
