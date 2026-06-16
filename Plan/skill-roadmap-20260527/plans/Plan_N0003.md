---
plan_id: Plan_N0003
project_id: skill-roadmap-20260527
status: completed
log_ref: Plan/skill-roadmap-20260527/logs/Plan_N0003.log.md
---

# Plan_N0003 Skill Authoring Governance

## Source Refs

- Plan/skill-imp-idea.md
- .agents/skills/skill-integrity-tuning-refactor/SKILL.md
- .agents/skills/skill-integrity-tuning-refactor/references/*
- .agents/skills/SKILL_INDEX.md

## Objective

Convert `skill-integrity-tuning-refactor` into `skill-authoring-governance`
without losing the existing empirical tuning mode.

## Minimal Tasks

- Rename directory/frontmatter to `skill-authoring-governance`.
- Preserve existing skill-integrity-tuning production workflow as a mode for
  existing skill empirical tuning.
- Add governance checks for creating, renaming, merging, deleting, and
  materially revising repo-local skills.
- Cover trigger overlap, progressive disclosure, reference boundaries,
  license/source attribution, index updates, and name/path consistency.

## Acceptance

- The new skill handles new-skill governance and existing-skill tuning.
- No current empirical tuning safety rule is silently dropped.
