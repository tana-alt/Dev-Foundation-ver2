# Harness Refactor Direction

## Policy Decision

This document supersedes the earlier AGENTS/docs synchronization and
task-aware skill injection direction.

The canonical active contracts are the docs under `docs/01-03`. `AGENTS.md`
remains unchanged as an entrypoint/instruction artifact, but it is not required
to be generated from, synchronized with, or tested against the active docs.
Tests that enforce AGENTS/docs consistency should be removed.

Skills must not be injected by the harness or context router as full context.
Skill instructions are treated as system-prompt-level context when the runtime
selects them. The router may pass skill identifiers or routing metadata for
diagnostics, but it must not duplicate `SKILL.md` bodies or reference contents
inside harness packets, session records, task YAML, review packets, or prompt
payloads.

Initial session context may include compact, task-specific data needed to start
work safely:

- `task_id`, role, agent id, worktree/cwd, and handoff commands
- `scope_contract`, allowed write targets, denied context, and source refs
- verifier ids, acceptance summary, policy/human-gate summary, and artifact refs
- next action and workflow instructions from the context router

The context router is responsible for turning the injected routing information
into a harness task and for instructing the agent to carry that task through the
normal execution and review path. The expected route is:

1. Compile or create the task from the router-provided goal, scope, refs,
   write targets, denied context, verification method, and review expectations.
2. Prepare the task so the harness writes the compiled contract and runtime
   artifacts.
3. Start or resume the appropriate role session with compact initial context.
4. Execute the task, verify on the closest real path, and submit evidence.
5. Run or request review, collect verdicts, and gate through harness authority.

The router-provided context is not completion authority. Completion remains
artifact-backed: contract, verification, submission, review verdicts, gate
results, and integration/land/push results must be written by harness-controlled
flows.

## Scope Contract Output

`scope_contract` should be emitted as compiled task context, not as skill
context. It belongs in the compiled contract and in compact initial session
context for every role that needs path boundaries. The minimum shape is:

```json
{
  "scope_contract": {
    "allowed_paths": [],
    "forbidden_paths": []
  }
}
```

The writer, reviewer, integrator, and strict daemon paths should read this from
the same compiled contract source. If a session record or daemon context omits
`scope_contract`, that is a harness parity bug to fix in implementation, not a
reason to inject skill bodies.
