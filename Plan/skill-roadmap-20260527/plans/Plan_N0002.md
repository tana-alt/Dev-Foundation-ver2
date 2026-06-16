---
plan_id: Plan_N0002
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0002.log.md
---

# Plan_N0002 Skill Integrity Test Baseline

## Source Refs

- Plan/skill-imp-idea.md
- tests/test_extension_surface_integrity.py
- .agents/skills/SKILL_INDEX.md
- .agents/skills/*/SKILL.md frontmatter

## Objective

Implement the Plan requirement that each local skill directory name must match
its frontmatter `name`, and make the test fail until renamed skills comply.

## Minimal Tasks

- Add `skill_dir.name == metadata["name"]` coverage for local skills.
- Keep parseable frontmatter, non-empty description, duplicate-name, and index
  coverage checks.
- Update the skill index coverage only after renamed directories exist.

## Acceptance

- The structural test would catch current mismatched skill names before rename.
- After later Plans complete, the test passes without exception lists.
