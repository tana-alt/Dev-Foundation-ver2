## hook event candidate

 Event                 Installed   Active      Description
  PreToolUse            0           0           Before a tool executes
  PermissionRequest     0           0           When permission is requested
  PostToolUse           0           0           After a tool executes
  PreCompact            0           0           Before context compaction
  PostCompact           0           0           After context compaction
  SessionStart          0           0           When a new session starts
  UserPromptSubmit      0           0           When the user submits a prompt
  SubagentStart         0           0           When a subagent is created
  SubagentStop          0           0           Right before a subagent ends i
  Stop                  0           0           Right before Codex ends its tu

## Note
You should not persist use hook by event above.
You can also evaluate hook usage by harness event.
You should use subagent if useful.

## Your Task
You have to make hook event or skills so that agent in harness can gain proper context.
Codex and Claude can discuss in `Harness-refactor/logs/Plan_N0009.log.md`
You have to decide implement plan by discussing until agreement

## Round policy
You should start broad idea and decide sophisticated　plan.
AGENTS.md or Harness context event is main candidate in my opinion.
