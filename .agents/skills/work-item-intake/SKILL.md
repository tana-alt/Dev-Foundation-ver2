---
name: work-item-intake
description: Use when a new idea or request must be converted into a bounded work item with owner, objective, verification, and next action.
---

Convert a loose request into a Work Item.

Read path:
- start from `Project-App/AGENTS.md` and the app runtime packets when an app bundle already exists
- default to the latest state only; do not reread full progress history unless the runtime packets flag missing context

Output format:
- title
- objective
- stream
- phase
- owner_agent
- status
- verification
- dependencies
- first_next_action

Also include:
- what is out of scope
- what artifact should exist before implementation starts

Do not:
- leave phase blank
- assign multiple owners
- skip verification
