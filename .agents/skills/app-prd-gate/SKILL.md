---
name: app-prd-gate
description: Use when research findings need to be converted into a PRD with measurable goals, functional requirements, and non-functional requirements.
---

Convert research into a buildable PRD.

Read path:
- start from `Project-App/AGENTS.md` and the app runtime packets
- read `Apps/<app-slug>/artifacts/runtime/current-state.yaml` and `latest-delta.yaml` before `02-research.md` / `03-plan.md`
- only expand to broader history when the runtime packets flag a blocker or drift that the latest planning surfaces do not explain

Required sections:
- user goal
- business goal
- persona
- functional requirements
- non-functional requirements
- acceptance criteria
- KPI
- instrumentation plan
- out_of_scope

For non-functional requirements include:
- p95 latency target
- availability assumption
- privacy / security assumption
- scalability assumption

Do not:
- pass vague aspirations to engineering
- omit acceptance criteria
