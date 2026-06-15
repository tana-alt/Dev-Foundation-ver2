---
plan_id: Plan_N0001
project_id: foundation-subagent-spec-workflow
status: completed
log_ref: Plan/foundation-subagent-spec-workflow/logs/Plan_N0001.log.md
---

# Subagent Specification Workflow Implementation

## Source Refs

- AGENTS.md
- docs/01-agent-operating-contract.md
- docs/02-output-verification-contract.md
- docs/03-repo-boundary-and-storage-contract.md
- subagent_workflow_package/codex_subagent_workflow_spec.md
- subagent_workflow_package/proposed_docs_and_skill_set.md
- subagent_workflow_package/proposal_tradeoff_notes.md

## Allowed Write Targets

- AGENTS.md
- docs/reference/packet-evidence-and-rework-reference.md
- docs/reference/specification-workflow-reference.md
- templates/README.md
- templates/specification-packet.yaml
- templates/specification-review-record.yaml
- templates/implementation-policy-record.yaml
- templates/workflow-run-record.yaml
- templates/inconsistency-register.yaml
- templates/parallel-lane-map.yaml
- .agents/skills/subagent-workflow-governance/SKILL.md
- .agents/skills/SKILL_INDEX.md
- tests/test_contract_models.py
- tests/test_foundation_integrity.py
- scripts/check-lane-map.py
- Plan/foundation-subagent-spec-workflow/

## Work Plan

1. Add the routed specification workflow reference and compact AGENTS route. Done.
2. Add blank reusable templates for specification, review, implementation policy, workflow run, and inconsistency register records. Done.
3. Extend the lane-map template and checker with optional specification scope fields. Done.
4. Add one compact governance skill and index entry. Done.
5. Extend contract and foundation integrity tests for the new workflow surface. Done.
6. Run targeted checks, then report verification, human gates, and residual risk. Done.

## Human Gates

- Human approval is required before any future approved-spec freeze created by this workflow.
- Merge remains human-only.
- CI/CD changes, dependency changes, release, deployment, secrets, auth, database, infrastructure, and external writes are out of scope.

## Residual Blockers

- Official Make gates are blocked by a pre-existing `pyproject.toml` conflict marker.
- Clean-checkout reproducibility for new `.agents/` and `Plan/` paths is blocked by
  pre-existing `.gitignore` conflict content that currently ignores those roots.
