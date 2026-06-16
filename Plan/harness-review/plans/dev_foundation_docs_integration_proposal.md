# Dev-Foundation-ver2 docs integration proposal

## 1. Integration principle

Prioritize harness robustness without enlarging the active operating surface.

Do not add broad implementation instructions to `AGENTS.md` or the three active docs unless they are short routing rules. Stable, detailed guidance should be folded into existing routed references. The current active docs model should remain:

- `AGENTS.md`
- `docs/01-agent-operating-contract.md`
- `docs/02-output-verification-contract.md`
- `docs/03-repo-boundary-and-storage-contract.md`

The main integration target should be `docs/reference/harness-observability-reference.md`, with small supporting updates to `docs/reference/verification-ci-and-pr-reference.md` and `docs/reference/repo-boundary-and-storage-reference.md`.

## 2. Proposed docs changes

### 2.1 `docs/reference/harness-observability-reference.md`

Add a new section after the current AB pipeline section:

```md
## Harness Robustness Roadmap

Open this section when changing AB measurement, completion gates, trajectory/eval scoring, metrics stores, or harness Make targets.

Robustness priority order:

1. prevent indefinite hangs;
2. preserve evidence-backed completion;
3. preserve hook fail-open behavior for interactive sessions;
4. keep AB worktrees outside the measured repo and marker-owned;
5. keep metric DB schemas compatible unless a migration is explicitly approved;
6. prefer additive targets and optional knobs over default-gate broadening.

Approved future changes:

- Add bounded timeout handling and bounded diagnostic log capture to `abrun` setup, measure, and server startup paths.
- Keep `runs.db`, `eval.db`, `nfr.db`, and `bench.db` as versionable project-scoped metric artifacts when useful, but do not change schemas casually.
- Keep Writer operations in separated worktrees when parallel write ownership is required.
- Replace raw prefix matching for `ExpectedEnvelope.allowed_write_targets` with normalized path-boundary matching.
- Keep `templates/serena-project.yml` multilingual; do not shrink the language list as cleanup.
- Add AB pipeline Make targets as explicit convenience targets.
- Align `scripts/completion_gate.py` with the Stop hook timeout knob, while preserving the Stop hook fail-open contract.
- Move reusable template/contract Pydantic models from `tests/test_contract_models.py` into `src/` only with parity tests and without importing them from hook-safe stdlib paths.

AB timeout and log-capture design constraints:

- Timeout fields must be optional or defaulted so existing configs remain valid.
- Timeout failures are measurement/tool errors, not quality regressions.
- Captured logs must be bounded, sanitized, and stored only under the owning project artifact path.
- Server stdout/stderr must not be stored unbounded or copied into repo-wide logs.
- Existing R6 exit-code meanings stay unchanged.

Path-boundary design constraints:

- Normalize relative paths against a repo/worktree root before comparison.
- Reject or classify paths that escape the root via `..` after normalization.
- Prevent sibling-prefix matches such as `src/foo` matching `src/foobar`.
- Preserve clear tests for trailing slashes, dot segments, absolute paths, and escaping paths.
- Treat this as eval/adaptor boundary behavior unless a separate enforcement contract says otherwise.

Completion gate timeout design constraints:

- `scripts/hook_stop.py` remains fail-open on environment failures and timeout.
- `scripts/completion_gate.py` may use the same `FOUNDATION_GATE_TIMEOUT_S` knob, but manual CLI timeout should be reported honestly as a blocked/tool-error condition, not as a pass.
- Do not let timeout alignment turn ordinary unplanned work into a Stop-hook loop.
```

### 2.2 `docs/reference/verification-ci-and-pr-reference.md`

Add a narrow subsection under current command mapping:

```md
## AB / Harness Make Targets

AB targets are explicit harness commands, not default local or CI gates unless a future policy says otherwise.

Recommended additive target surface:

- `make ab-run CONFIG=... [REPO=...]`: run `scripts/abrun.py run`.
- `make ab-clean CONFIG=... [REPO=...]`: run `scripts/abrun.py clean`.
- `make ab-check RUN_ID=... WORKTREE=... CMD='name=cmd'`: run `scripts/check_runner.py run`.
- `make ab-verdict BASELINE_RUN=... CANDIDATE_RUN=... METRIC=... POLICY=...`: run `scripts/verdict.py compare`.
- `make ab-gate BASELINE_RUN=... CANDIDATE_RUN=... POLICY=...`: run `scripts/quality_gate.py evaluate`.

Do not add these targets to `check-fast`, `check-required`, `check-ci`, or `check-foundation` by default. They can create worktrees, run measured commands, depend on local benchmark state, or return inconclusive results. Default gates must stay deterministic local verification gates.
```

### 2.3 `docs/reference/repo-boundary-and-storage-reference.md`

Add a storage-policy subsection near the artifact/metrics placement rules:

```md
## Metrics DB Storage Policy

Project-scoped metrics DB files may be durable repo artifacts when they are intentionally used as evidence or baseline material:

- `artifact/<project_id>/metrics/runs.db`
- `artifact/<project_id>/metrics/eval.db`
- `artifact/<project_id>/metrics/nfr.db`
- `artifact/<project_id>/metrics/bench.db`

Rules:

- Treat these DB files as project-scoped evidence, not repo-wide runtime state.
- Do not commit broad logs, raw unbounded payloads, credentials, terminal transcripts, or machine-local state into these DBs.
- Do not alter DB schemas, table names, column names, retention semantics, or migration behavior without an explicit schema-change plan.
- If DB files are updated, report whether they are evidence refreshes, baseline updates, or accidental local measurement residue.
- Prefer bounded retention and deterministic provenance fields so DB diffs remain explainable.
```

Add a worktree-policy note near lane-map/worktree guidance:

```md
## Writer Worktree Separation

When multiple writer agents or write lanes are active, each Writer should write in its own explicitly owned branch/worktree. Do not require worktrees for ordinary single-writer local changes. Worktree creation and cleanup must respect the existing branch/worktree human gates, and deletion remains protected.
```

Add a local environment template note:

```md
## Serena Template Language List

The multilingual `templates/serena-project.yml` language list is intentional for this foundation template. Do not reduce it merely because the current tracked repo is mostly Python, Shell, and Makefile.
```

### 2.4 Active docs

No substantive active-doc expansion is recommended.

- `AGENTS.md`: no change required because it already routes harness observability work to `docs/reference/harness-observability-reference.md`.
- `docs/01-agent-operating-contract.md`: no change required.
- `docs/02-output-verification-contract.md`: no change required; DB migrations, branch/worktree deletion, CI/CD, dependency changes, release/deploy, secrets, and external writes are already human-gated.
- `docs/03-repo-boundary-and-storage-contract.md`: no change required unless a one-line route to metrics DB policy is desired.

## 3. Stop-risk callouts

### High stop-risk if implemented carelessly

1. **AB Makefile targets added to default gates**
   - Risk: can create worktrees, start servers, run slow benchmarks, return inconclusive results, or depend on local metrics state.
   - Docs position: additive only; never part of `check-fast`, `check-required`, `check-ci`, or `check-foundation` by default.

2. **Completion gate timeout with fail-closed Stop-hook behavior**
   - Risk: a slow or hung local check could trap the agent session.
   - Docs position: Stop hook remains fail-open on timeout; manual `completion_gate.py` may time out but must report honestly and must not claim pass.

3. **Path normalization applied as enforcement without migration tests**
   - Risk: existing evaluations or adapter fixtures that passed under prefix semantics may become unexpected-action failures.
   - Docs position: allowed and preferred, but must be test-pinned and rolled out as a boundary-semantics change.

4. **Moving Pydantic contract models into import paths used by hooks**
   - Risk: plain `python3` hook paths can fail if they import Pydantic-dependent modules outside the uv environment.
   - Docs position: extraction to `src/` is allowed, but hook-safe modules and package lazy exports must not import the new models eagerly.

### Medium stop-risk / repo-noise risk

5. **Versioning metric DB files indiscriminately**
   - Risk: binary diffs, merge conflicts, stale baselines, hygiene failures, and repo growth.
   - Docs position: allowed as evidence/baseline artifacts; not every local run should be committed.

6. **AB timeouts too aggressive by default**
   - Risk: valid long measurements become tool errors.
   - Docs position: defaulted/overridable timeout knobs; timeout means tool error, not quality regression.

7. **Server log capture without bounds or sanitization**
   - Risk: secrets, massive logs, or unrelated runtime state enter artifacts.
   - Docs position: bounded tails only, sanitized, stored under project artifact metrics/evidence paths.

8. **Mandating worktree separation for all writes**
   - Risk: unnecessary setup friction and protected cleanup operations.
   - Docs position: required for parallel/multi-writer lanes, not ordinary single-writer work.

### Low stop-risk / preserve as documentation

9. **Serena multilingual template note**
   - Risk of change is mainly accidental narrowing. Documentation should mark it intentional.

## 4. Implementation sequencing for a future code pass

### Phase 0 — docs-only integration

- Update only reference docs.
- Do not change code, Makefile, tests, schemas, templates, or hooks.
- Run doc/structure checks only if applying the docs change in a worktree.

Recommended checks after docs-only change:

```sh
make check-doc-consistency
make check-fast
```

If `shellcheck` or `gitleaks` is missing, report the blocked command and run the closest narrower checks.

### Phase 1 — tests before behavior

Add or strengthen tests for:

- `abrun` timeout and bounded log behavior;
- `completion_gate.py` timeout handling distinct from Stop-hook fail-open behavior;
- normalized allowed-write path boundary cases;
- DB schema compatibility and schema-change detection;
- template-model extraction parity;
- hook import safety without Pydantic/PyYAML in hook-safe paths;
- AB Makefile targets not being dependencies of default gates.

### Phase 2 — implementation slices

Only after tests:

1. completion gate timeout parity;
2. `abrun` timeout/log capture;
3. AB Make targets as additive targets;
4. path-boundary normalization helper;
5. template model extraction to `src/`;
6. DB schema policy checks or migration notes without schema mutation.

### Phase 3 — verification

Area-specific checks:

- AB/eval/runstore/verdict/gate:
  - `uv run pytest -q tests/workflow_core/test_abrun.py`
  - `uv run pytest -q tests/workflow_core/test_runstore.py`
  - `uv run pytest -q tests/workflow_core/test_verdict.py`
  - `uv run pytest -q tests/workflow_core/test_checkrun.py`
  - `uv run pytest -q tests/workflow_core/test_quality_gate.py`
  - `make check-fast`

- completion/hook:
  - `uv run pytest -q tests/workflow_core/test_completion.py`
  - `uv run pytest -q tests/workflow_core/test_runtime_port.py`
  - `make check-hooks`
  - `make check-fast`

- docs/repo boundary:
  - `make check-doc-consistency`
  - `make check-hygiene`
  - `make check-fast`

## 5. Final reporting shape for future implementation

```md
## Summary

- What changed:
- What did not change:
- Behavior preserved:

## Baseline

- Initial branch:
- Initial `git status --short`:
- Baseline commands run:
- Baseline results:

## Changed Paths

- path: reason

## Verification

| Command | Result | Notes |
|---|---:|---|
| `...` | passed/failed/blocked/skipped/not_applicable | ... |

## Stop-risk Review

- Added risks:
- Mitigations:
- Remaining risks:

## Unverified Surfaces

- command/surface:
- reason:
- needed to run:

## Stop Conditions Encountered

- none / list

## Final Git State

- `git status --short`:
```

## 6. Out of scope for this docs integration

- Code implementation.
- CI/CD or dependency changes.
- DB schema changes or migrations.
- Adding AB targets to default gates.
- Changing hook fail-open/fail-closed semantics.
- Worktree deletion or protected branch operations.
- Secret/auth/billing/protected-data behavior.
- Production UI, service, queue, scheduler, or multi-user runtime.
- Broad formatting-only edits.
