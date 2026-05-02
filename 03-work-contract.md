---
status: draft
owner: foundation
source_of_truth_level: primary
created_at: 2026-05-02
---

# Work Contract

## Purpose

A work contract defines a bounded unit of work without depending on agent roles.
It can be executed by a human, LLM session, script, automation, or review lane.

## Contract Shape

A useful work contract answers:

- What is the task intent?
- What input refs are required?
- What outputs must be produced?
- Where may files be changed?
- What evidence must be carried forward?
- What verification is required?
- What should happen if the task is blocked?
- What is the next action or next owner?

## Contract Fields

### Identity

- `work_id`
- `project_id`
- `work_type`
- `status`

### Intent

- `task_intent`
- `success_criteria`
- `non_goals`

### Inputs

- `source_refs`
- `required_context`
- `optional_context`
- `templates`

### Outputs

- `expected_outputs`
- `changed_paths`
- `artifact_refs`
- `decision_refs`

### Boundaries

- `allowed_write_targets`
- `denied_context`
- `risk_flags`

### Evidence And Verification

- `evidence_required`
- `verification_required`
- `verification_results`
- `residual_risk`

### Continuation

- `blockers`
- `open_questions`
- `next_action`

## Artifact Dependency

Workflow should be derived from artifact compatibility instead of a fixed role
sequence.

Example:

```text
research_note -> product_plan
product_plan -> implementation_slice
implementation_slice -> verification_record
verification_record -> release_note or rework_record
```

Each arrow means the prior output satisfies the next work contract's input
requirements.

## Valid Output

A valid work output includes:

- expected artifacts
- evidence refs
- changed paths
- verification results
- blockers or open questions when present
- next action

If these cannot be provided, the output should be a rework record instead.
