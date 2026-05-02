# E2E Verification Checklist

- Can the agent reach the target page or state from a realistic starting point?
- Can the required action be performed without guesswork?
- Does the expected visible result appear after the action?
- Are errors, blocked transitions, and stale UI states surfaced as failures?
- Do screenshots reflect the state change or final success condition?
- If the interface claims a structural capability, verify it in the browser instead of inferring it from labels alone.
- If the interface exposes relationships between entities, verify that those relationships remain understandable from the rendered state.
- If the interface claims non-linear behavior such as branching, parallelism, or multiple active paths, verify that the visible interaction model can actually express it.
