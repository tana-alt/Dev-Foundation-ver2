---
name: skill-authoring-governance
description: Use when creating, renaming, merging, deleting, materially revising, or empirically tuning repository-local skills. Enforces Agent Skills frontmatter/path consistency, trigger precision, progressive disclosure, reference boundaries, license/source attribution, index updates, and evidence before accepting skill changes.
---

# Skill Authoring Governance

Use this skill for repo-local skill lifecycle changes. Skills are a compact
discovery and execution layer, not a knowledge store; active repo contracts and
allowed write targets remain the source of truth.

## Modes

### Governance Mode

Use for creating, renaming, merging, deleting, or materially revising a
repo-local skill.

Required checks:

- Define the change type and why the existing inventory is insufficient.
- Check trigger overlap against current skill names and descriptions.
- Keep `SKILL.md` compact; move large, optional detail to direct
  `references/` files only when the workflow needs it.
- Ensure directory name equals frontmatter `name`.
- Ensure `description` is precise enough to trigger only when useful.
- Preserve source and license attribution for imported or derived material.
- Remove nonexistent sibling-skill references or mark them as external plugin
  routes.
- Update `.agents/skills/SKILL_INDEX.md` and any relevant `agents/openai.yaml`.
- Run the narrowest structural test that proves discovery still works.

Do not add a new local skill for project-specific, PDF-derived, one-off, or
narrow stack-specific material. Prefer an existing skill mode, `doc-lookup`, or
an official plugin when that covers the repeated failure mode.

### Empirical Integrity Tuning Mode

Use for the existing `skill-integrity-tuning` workflow: empirically validating
that an existing skill's description, body, references, and actual outputs align.

Production mode is allowed only when all are true:

1. A new subagent can be dispatched for each iteration.
2. Rubric and inner-loop scenarios are fixed before the loop starts.
3. The pre-change skill state can be snapshotted and rolled back.

If any prerequisite is missing, run only lightweight preflight or report
`integrity tuning skipped: dispatch unavailable`.

Detailed empirical workflow remains in:

- `references/operating-modes.md`
- `references/rubric-design.md`
- `references/templates.md`
- `references/example-log.md`

## Governance Workflow

1. Read the active request, allowed write targets, existing skill frontmatter,
   and only the directly relevant source refs.
2. Classify the request: add, rename, merge, delete, material revision, or
   empirical tuning.
3. For add/rename/merge/delete decisions, produce a short decision record:
   candidate, decision, compact-foundation reason, existing coverage, and later
   acceptance condition.
4. Make the smallest skill edits that satisfy the decision.
5. Verify directory/frontmatter/index consistency and any mode-specific checks.

## Acceptance Bar

- `SKILL.md` starts with parseable YAML frontmatter containing non-empty
  `name` and `description`.
- Frontmatter `name` equals the directory name.
- The skill does not override active docs, contracts, storage rules, human
  gates, or allowed write targets.
- Imported guidance has attribution, or the imported payload is removed.
- Retired duplicate skill directories are removed after consolidation.
- Logs or handoff notes record decisions, commands, verification, and residual
  risk.

## Output

Return:

- `decision`: add / rename / merge / delete / revise / tune / do_not_add.
- `reason`: compact-foundation rationale and existing coverage.
- `changed_paths`: skill, reference, index, and test paths.
- `verification`: command and result, or blocked reason.
- `residual_risk`: unresolved overlap, missing docs, or dispatch limits.
