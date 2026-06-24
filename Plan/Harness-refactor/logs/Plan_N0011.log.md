# Plan_N0011 Log

## 2026-06-24

- Recorded the human-corrected Harness director automation policy for later
  subagent review.
- Verified the local Codex command surface with `codex --help` and
  `codex exec --help`.
- Noted that `codex exec` is the correct fresh noninteractive role-agent
  command, while other Codex commands are interactive, review-specific,
  resume-specific, service-oriented, or sandbox-only surfaces.
- Noted that `codex exec` does not expose `--ask-for-approval` in current local
  help output, so Harness command generation must avoid appending
  `--ask-for-approval never` to `codex exec`.
- Corrected the review-after-gate policy: post-review pre-push CI/gate should
  be mechanized by Harness/integrator automation, while the director observes
  the result and checks plan/hash authority instead of manually running the same
  command every cycle.
- Implemented `post-review-gate` as the deterministic review-pass lifecycle
  command and PR precondition.
- Added invariant-axis tests for the ordinary review-pass path and role
  boundary.
- Added adversarial-axis tests for candidate hash mismatch and corrupt runtime
  JSON.
- Verified focused and related suites. The broad related suite passed but took
  427.38 seconds, which should remain visible as test-runtime evidence.
- Ran two read-only subagent reviews. Review is blocked by overlapping
  P1/High findings: PR creation/checks can be skipped before land, and existing
  post-review pass evidence is trusted too broadly. Additional findings cover
  local-vs-external PR semantics, non-AI reviewer auto-runs inside
  post-review-gate, strict outbox observation trust, and `python` fixture
  portability.

## 2026-06-25

- Applied review rework for the P1/High findings: status now routes
  post-review pass to PR creation, land blocks when PR evidence is missing after
  post-review gate, and `pr create` reruns post-review gate instead of trusting
  an existing pass artifact.
- Made the post-review gate path mechanical by calling `gate_task` without
  reviewer auto-run.
- Hardened strict outbox PR observation so tampered `pr-result.json` cannot be
  accepted as recovered unless the PR ref, diff hash, candidate id, and
  StateStore authority match.
- Fixed PR ref creation under worktree-local hooks by switching the PR worktree
  to `agent/<task_id>/integrator/pr-<candidate_id>` before committing.
- Added/updated invariant and adversarial tests for status next action, land
  PR precondition, stale post-review gate artifacts, tampered outbox PR
  observation, and hook-safe PR branch creation.
- Verified focused suites and lint/format checks. Remaining policy gap:
  `harness pr create` still represents local Harness PR-ref creation rather
  than external GitHub PR creation.
