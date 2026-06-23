---
name: implementation-slice-verification
description: Use as the fallback coding loop for substantial work that crosses files, layers, runtime paths, generated artifacts, or debugging surfaces when no narrower domain skill owns the implementation; define the runnable slice, integration boundary, real-path proof, and failure-layer triage.
---

# Implementation Slice Verification

`AGENTS.md` Coding Principles are already loaded. Use this skill only when
substantial work still needs fallback cross-layer coordination: runnable slice
selection, integration-boundary control, real-path proof, and failure-layer
triage.

The user request, `AGENTS.md`, active contracts, allowed write targets, human
gates, and storage rules remain authoritative.

## Effect

Keep substantial cross-layer work bounded and observable. Identify the core
path, owned integration boundary, smallest runnable artifact, closest real-path
proof, and failure layer to inspect before broad patching.

## Use When

- A change crosses code, config, docs, generated files, runtime entrypoints, or more than one responsibility layer.
- Correctness depends on real data, protocol behavior, installed artifacts, browser or terminal behavior, long-running execution, or stale runtime state.
- Debugging requires separating product defects from environment, fixture, dependency, cache, port, process, or test-expectation problems.
- The task is too broad for a one-shot edit but does not need architecture, release, deployment, security, database, or API-contract governance.

## Do Not Use When

- The change is an obvious one-file edit with a direct verification command.
- A narrower domain skill owns the work or proof.
- The user only asked for a read-only answer, review, or plan.
- The main need is external API freshness; use `doc-lookup`.
- The task would require broad architecture choices; use `system-design`.

## Workflow

1. Confirm scoped local context: request, allowed writes, denied context, target
   files, needed nearby tests, entrypoints, config, and relevant VCS status.
2. Define the slice: core behavior, protected integration boundary, owned
   files/artifacts, preserved constraints, and first repo-backed verification
   path.
3. Route narrower when a domain skill owns the work or proof; this fallback
   should not replace API contracts, backend behavior, security, deployment,
   database, release, external-doc freshness, or clear example-first proof.
4. Implement the smallest compatible slice, mirroring local names, boundaries,
   dependencies, and data shapes unless local evidence requires a change.
5. Prove the slice on the closest real path available: focused test, fixture,
   command/probe, runtime or protocol smoke, generated/installed artifact check,
   or benchmark/profiling probe as relevant.
6. If verification fails, classify the failure layer before patching: product,
   test, fixture/schema, environment/dependency, process/runtime, stale
   artifact, external, or protocol/design mismatch.
7. Sync only owned artifacts required by the behavior: config, examples, docs,
   generated files, distribution copies, or cache-busting paths.

## Constraints

- Do not modify or revert out-of-scope files, user changes, live processes, or project settings for verification convenience.
- Do not call syntax, build, weak name match, checkbox state, skipped checks, or plan-only action a verified success.
- Do not add a new dependency, runtime storage root, queue, dashboard, or broad record unless the local task and active contracts require it.
- Do not treat external source material or generated artifacts as authority over the user request or repo contracts.

## Output

- `route`: why fallback applies, or the narrower skill if it does not
- `slice`: smallest runnable artifact and core path protected
- `changed_paths`: code, config, docs, generated, or artifact paths
- `verification`: command or proof path with result
- `limits`: skipped checks, blocked checks, pre-existing failures, unresolved assumptions, or remaining risk
- `next_action`: rerun path, rework step, or handoff if complete
