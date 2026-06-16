# Dev-Foundation-ver2 Contract Harness 改善計画 統合版

対象 repository: `tana-alt/Dev-Foundation-ver2`
対象範囲: contract harness / agent-facing docs / verification docs / acceptance planning
作成日: 2026-06-15
作業種別: docs 統合のみ。実装・テスト追加・repo 変更は含めない。

---

## 0. 統合方針

この文書は、2つの `imp-harness.md` 案を1本の実行可能な改善計画として統合する。

統合の判断基準は以下。

1. **現行設計を壊さない**
   `Dev-Foundation-ver2` は、agent 作業を goal-first / scoped context / machine evidence / human gate に寄せる foundation である。改善はこの方向に揃える。

2. **実装ではなく、docs 上の合意点を固定する**
   本文書では `src/`, `tests/`, `Makefile`, `README.md` 等への変更方針は書くが、実装差分は作らない。

3. **P-series と H-series を役割分担させる**
   - P-series: 現行 harness の構造的ボトルネックと改善順序を示す。
   - H-series: tests-first acceptance criteria と evidence/context hardening を示す。

4. **矛盾は「active surface の信頼性」を優先して解く**
   片方の案は `./harness init` / templates / role mismatch を最優先にし、もう片方は machine evidence / timeout envelope を先に置いている。統合版では、後続の evidence/context 改善を安定して検証するため、最初に active surface と bootstrap の不整合を解消する方針を採る。

---

## 1. Repository の前提モデル

`Dev-Foundation-ver2` は、エンドユーザー向けアプリケーションではない。目的は、人間監督下の agent 開発作業を、以下で縛る小さな foundation である。

- 最小の agent entrypoint
- 明示された scope と allowed / forbidden paths
- generated acceptance
- verifier plan
- candidate diff
- machine evidence
- review verdict
- gate result
- land / push policy
- human approval gate
- hook / eval / metrics / AB comparison
- runtime-neutral `AgentRuntime` port

この repository の基本原則は以下である。

```text
Goal -> Scope -> Done -> Plan -> Implement -> Verify -> Log result
```

ただし本統合文書では implementation step は扱わない。扱うのは、今後の実装 PR が迷わないための doc-level specification と acceptance plan である。

---

## 2. 現行 harness flow の共通理解

Contract harness task は概ね次の流れを持つ。

```text
.harness/tasks/<task_id>/task.yaml
  + .harness/{bottleneck,owners,verifiers,review}.yaml
  -> ./harness prepare <task_id>
  -> capsule / contract lock / verifier plan / forward scope map
  -> writer modifies allowed paths
  -> ./harness verify <task_id>
  -> candidate.diff / reverse scope map / quality / tool candidate / verify-result
  -> ./harness submit <task_id>
  -> submission evidence
  -> ./harness dispatch|integrate <task_id>
  -> reviews / gate / integration result
  -> ./harness land <task_id>
  -> integrator worktree commit
  -> ./harness push <task_id>
  -> protected external write policy
```

Harness の必須入力として扱うべきもの:

```text
.harness/bottleneck.yaml
.harness/owners.yaml
.harness/verifiers.yaml
.harness/review.yaml
.harness/tasks/<task_id>/task.yaml
.harness/rfc-decisions/
```

`policy.yaml` は `land` / `push` / integration target で必要になるため、minimal fixture には含める。

---

## 3. 統合されたボトルネック分類

### G0. Active surface / bootstrap が不十分

含まれる問題:

- clean checkout で `.harness` の最小入力が見えない。
- `./harness init` または first-party minimal template がない、または導線が弱い。
- reviewer-facing tool list と role permission が一致しない。
- `rfc` subcommand が parser 上に見えるが、実装・role allowlist・docs と一致していない。

影響:

- agent が何を作れば `prepare` できるか分からない。
- tool list を信じて実行しても role permission で拒否される。
- CLI help と実装状態の不一致により、phantom command を active surface と誤認する。

統合判断:

- `./harness init` と minimal template を最優先の改善対象にする。
- reviewer `review-collect` は reviewer に許可する方向を推奨する。
- `rfc` は「最終的には integrator/admin の evidence-bound human decision command として実装」する。ただし、実装されるまで docs / help / agent tools では active command として扱わない。

### G1. Machine evidence / failure semantics が弱い

含まれる問題:

- machine evidence hash が verifier id / status 中心で、command / exit_code / duration / artifact hash との束縛が弱い。
- verifier stdout / stderr の bounded evidence が弱い。
- timeout / subprocess error が result envelope として正規化されていない。
- verifier command が shell string 前提で、structured argv がない。

影響:

- gate / review / submit が同じ証跡集合を見ていると機械的に保証しにくい。
- fail 時の rework に必要な診断情報が不足する。
- agent loop が traceback や非構造化 stderr に依存する。

統合判断:

- `machine-evidence-manifest.json` を中心に evidence を束縛する。
- timeout / subprocess failure は共通 result envelope に落とす。
- stdout/stderr は tail のみ保存し、redaction と size cap を必須にする。
- `argv` schema を導入し、shell string は legacy mode として明示する。

### G2. Context visibility / reviewer packet が弱い

含まれる問題:

- `capsule.json` が visible inputs / denied context / known absences / human gates / evidence outputs を十分に含まない。
- `semantic_review` packet が full diff を unbounded に入れる可能性がある。
- acceptance checklist が capsule / explain / verify-result に十分露出していない。
- writer tool list が初手から広い。

影響:

- agent / reviewer が「実際に見えているもの」と「見えていないもの」を分離しにくい。
- context boundary 原則が review packet 上で弱くなる。
- Done 条件が verifier id の羅列に寄り、人間可読性が不足する。

統合判断:

- `capsule.json` v2 と `explain --json` を追加する方針で統一する。
- bounded `ContextManifest` を semantic review packet に導入する。
- `acceptance.generated_checks[]` を capsule / explain / verify-result に出す。
- tool list は将来的に `minimal/full` または `--phase` で分離する。

### G3. Typecheck / harness-specific gate が弱い

含まれる問題:

- `mypy.files` が `tests` 中心で、`src/workflow_core` を直接見ていない。
- harness 改善用の狭い gate が `make check-foundation` に埋もれている。
- clean checkout bootstrap smoke が弱い。

影響:

- core harness implementation の型劣化を tests 経由でしか拾えない。
- harness 改善 PR で必要な acceptance を明示的に回しにくい。

統合判断:

- `src/workflow_core`、少なくとも `src/workflow_core/contract_harness` を typecheck 対象に入れる。
- `make check-harness` を docs 上の推奨 gate として定義する。
- clean checkout bootstrap test を acceptance に含める。

### G4. Bottleneck / eval loop が弱い

含まれる問題:

- `bottleneck.yaml` が contract input として hash されるが、explain / gate / report / metrics での扱いが弱い。
- context self-report の名残があり、trajectory-backed evidence に寄り切れていない。
- integration lane の詰まりが読みにくい。

影響:

- bottleneck 改善が感想ベースになり、metrics / tests / gate と接続しない。
- agent が「読んだ」と主張した context と、実際に観測された context の区別が曖昧になる。
- land / push の安全性はあるが、詰まりの理由を読みづらい。

統合判断:

- `bottleneck.yaml` schema を docs で明確化し、capsule / explain / gate / report へ接続する。
- trajectory-backed context evidence を H10 として維持する。
- `./harness status <task_id>` は read-only diagnostic として後段に置く。

---

## 4. 統合ロードマップ

### Phase 0: Docs-only baseline

目的:

- 本統合文書を repository に追加する。
- 以後の実装 PR が参照する canonical improvement plan を固定する。

候補配置:

```text
docs/reference/contract-harness-improvement-plan.md
```

README からリンクする場合の文言例:

```md
- `docs/reference/contract-harness-improvement-plan.md`: contract harness の active surface, evidence, context, and acceptance hardening plan.
```

検証方針:

```sh
uv sync --frozen --group dev
make check-foundation
```

この Phase では code / tests / Makefile の実装変更はしない。

### Phase 1: Active surface / bootstrap を揃える

統合対象:

- P0: clean checkout harness bootstrap
- P1: role/tool consistency
- P2 / H5: RFC active surface cleanup
- H6: minimal harness fixture / quickstart

目的:

- `.harness` の不可視入力を消す。
- agent-facing tool list と role permission を一致させる。
- CLI に見える command と実装済み behavior を一致させる。

Docs 上の仕様:

```text
templates/harness/minimal/
  bottleneck.yaml
  owners.yaml
  verifiers.yaml
  review.yaml
  policy.yaml
  tasks/T-0001/task.yaml
```

`./harness init` の仕様:

```sh
./harness init <task_id> --scope <scope> --summary <summary>
```

期待される責務:

- `.harness/` がない場合、minimal template から生成する。
- `.harness/tasks/<task_id>/task.yaml` を生成する。
- 既存ファイルを上書きしない。
- `acceptance.mode: generated` を固定する。
- `.harness/rfc-decisions/` を作る。
- 生成結果を JSON で返す。

Role/tool policy:

- reviewer に `review:collect` を許可する方向を推奨する。
- 代替として削除する場合は、reviewer tool list から `review-collect` を出してはいけない。
- placeholder 付き command は `template: true` として machine-readable にする。

RFC policy:

- 目標仕様は `integrator` または admin-equivalent role による evidence-bound human decision command。
- 実装されるまでは active command として docs / help / tools に出さない。
- 実装する場合、decision は `.harness/rfc-decisions/<rfc_id>.json` に書く。
- `prepare` 後に decision が変わる場合は semantic hash mismatch として再 prepare を要求する。

Acceptance examples:

```sh
./harness init T-demo --scope demo --summary "demo task"
./harness prepare T-demo
./harness explain T-demo --json
./harness scope-map T-demo --forward
./harness verify T-demo
```

期待:

- clean checkout で不可視 `.harness` input を前提にしない。
- `explain --json` が valid JSON object を返す。
- `capsule.json` に `visible_inputs`, `denied_context`, `required_gates`, `evidence_outputs`, `known_absences` が含まれる。
- emitted tool が role permission で拒否されない。

### Phase 2: Machine evidence / process result を強化する

統合対象:

- P4: bounded verifier evidence
- P5: verifier command argv schema
- H2: machine evidence manifest
- H3: timeout / subprocess result envelope

目的:

- verifier result を再現・診断可能な machine evidence にする。
- timeout / subprocess failure を traceback ではなく structured JSON result にする。

Docs 上の target artifact:

```text
machine-evidence-manifest.json
```

Manifest に含めるもの:

```json
{
  "task_id": "T-0001",
  "prepared_base_sha": "...",
  "candidate_diff_sha256": "sha256:...",
  "contract_semantic_sha256": "sha256:...",
  "scope_violation_count": 0,
  "artifacts": {
    "scope_map_reverse_sha256": "sha256:...",
    "quality_result_sha256": "sha256:...",
    "tool_candidates_sha256": "sha256:..."
  },
  "verifiers": [
    {
      "id": "unit",
      "execution_mode": "argv",
      "command_sha256": "sha256:...",
      "status": "pass",
      "exit_code": 0,
      "duration_ms": 1234,
      "timeout": false,
      "stdout_tail_sha256": "sha256:...",
      "stderr_tail_sha256": "sha256:..."
    }
  ]
}
```

Result envelope:

```json
{
  "status": "pass|fail|timeout|error",
  "exit_code": 0,
  "duration_ms": 1234,
  "stdout_tail": "bounded redacted text",
  "stderr_tail": "bounded redacted text",
  "reason": "timeout|nonzero_exit|subprocess_error|..."
}
```

Verifier schema:

```yaml
- id: unit
  argv:
    - make
    - test
```

Compatibility rule:

- `argv` があれば shell を使わない。
- 既存 `command: make test` は legacy shell mode として維持する。
- legacy shell mode は `execution_mode: shell` として evidence に残す。

Acceptance examples:

```sh
uv run pytest tests/workflow_core/test_contract_harness.py -k "machine_evidence or timeout or process_result or redacts"
make check-required
```

期待:

- `verify-result.machine_evidence_sha256` が manifest canonical hash と一致する。
- verifier exit_code / command hash / artifact hash が変われば evidence hash が変わる。
- manifest 改ざん時に gate が fail する。
- timeout は JSON result になり、通常経路で traceback を出さない。
- secret-like output は redaction される。

### Phase 3: Context capsule / reviewer packet / acceptance checklist を揃える

統合対象:

- P3: capsule v2 / explain --json
- H1: bounded reviewer context manifest
- H7: acceptance checklist

目的:

- agent / reviewer が「見えているもの」と「見えていないもの」を区別できるようにする。
- semantic reviewer packet を bounded にする。
- Done 条件を verifier id だけでなく human-readable checklist として出す。

`capsule.json` v2 の target keys:

```json
{
  "task_id": "T-0001",
  "scope": "demo",
  "intent": {},
  "visible_inputs": {
    "task_yaml": ".harness/tasks/T-0001/task.yaml",
    "owners_yaml": ".harness/owners.yaml",
    "verifiers_yaml": ".harness/verifiers.yaml",
    "review_yaml": ".harness/review.yaml",
    "bottleneck_yaml": ".harness/bottleneck.yaml",
    "rfc_decisions_dir": ".harness/rfc-decisions"
  },
  "known_absences": [],
  "denied_context": [],
  "scope_contract": {},
  "verifier_plan": [],
  "required_gates": ["verify", "submit", "review quorum", "gate", "land before push"],
  "human_gates": [],
  "acceptance": {
    "mode": "generated",
    "generated_checks": []
  },
  "evidence_outputs": {},
  "agent_tools": [],
  "agent_skills": [],
  "contract_semantic_sha256": "sha256:..."
}
```

Bounded context packet:

```json
{
  "candidate_diff_excerpt": "...",
  "candidate_diff_index": [],
  "candidate_diff_path": "candidate.diff",
  "candidate_diff_sha256": "sha256:...",
  "context_manifest": {
    "visible_items": [],
    "omitted_items": [],
    "full_artifact_paths": [],
    "hashes": {},
    "budget": {
      "max_bytes": 65536,
      "actual_bytes": 32000,
      "truncated": false
    }
  }
}
```

Acceptance checklist examples:

- `scope_violation_count == 0`
- `contract_semantic_sha256 reproducible`
- all required verifiers pass
- quality hard failures absent
- tool candidate hard failures absent
- semantic review required when quality/tool result requires review
- candidate diff hash matches submitted evidence

Acceptance examples:

```sh
uv run pytest tests/workflow_core/test_contract_harness.py -k "context_manifest or semantic_review_packet or acceptance_checklist or generated_acceptance"
make check-required
```

期待:

- large diff でも semantic reviewer packet size は上限以下。
- omitted context は manifest に記録される。
- manifest hash が reviewer freshness に反映される。
- `./harness explain` と `./harness explain --json` が acceptance checklist を出す。
- `verify-result.json` が each check status を持つ。

### Phase 4: Typecheck / harness-specific gate / clean checkout smoke を固定する

統合対象:

- P6: typecheck and clean checkout test
- H4: src mypy strict target
- H9: check-harness

目的:

- harness implementation の劣化を早く検出する。
- harness 改善 PR が必要な acceptance を狭く回せるようにする。

Typecheck policy:

```toml
[tool.mypy]
files = ["src", "tests"]
```

段階導入する場合:

```make
check-harness-types:
	$(UV) run mypy src/workflow_core/contract_harness
```

Harness gate target:

```make
check-harness: \
	format-check \
	lint \
	typecheck \
	check-hooks \
	check-shell \
	test-contract-harness \
	test-harness-eval-smoke
```

Clean checkout bootstrap smoke:

1. temp repo を init。
2. tracked minimal app / tests / Makefile を作る。
3. `./harness init T-boot --scope demo ...`。
4. `./harness prepare T-boot`。
5. `./harness explain T-boot --json`。
6. `src/...` に最小変更。
7. `./harness verify T-boot`。
8. `./harness submit T-boot`。

Acceptance examples:

```sh
uv run pytest tests/test_foundation_integrity.py -k mypy
make typecheck
make check-harness
make check-required
```

### Phase 5: Bottleneck / eval / diagnostics を閉ループ化する

統合対象:

- P7: read-only integration status
- H8: bottleneck.yaml connection
- H10: trajectory-backed context evidence
- secondary improvements: tool phase split, declared test mapping

目的:

- bottleneck を hashed input から actionable context / gate / metric に昇格する。
- context self-report から trajectory-backed evidence に寄せる。
- integration lane の詰まりを read-only に診断できるようにする。

`bottleneck.yaml` target schema:

```yaml
version: 1
bottlenecks:
  - id: reviewer-context-bloat
    surface: semantic_review_packet
    budget:
      max_packet_bytes: 65536
    signal:
      metric: context_packet_bytes
      fail_above: 65536
```

`./harness status <task_id>` target output:

```json
{
  "task_id": "T-0001",
  "prepared": true,
  "verified": true,
  "submitted": true,
  "review": {
    "fresh_approves": 2,
    "fresh_blocks": 0,
    "stale": []
  },
  "gate": {
    "mergeable": false,
    "reason": "review_quorum_unmet"
  },
  "integration": {
    "affected_classification": "PARTIAL",
    "lock": "free"
  },
  "next_action": "run missing reviewer or fix machine gate"
}
```

Trajectory-backed context evidence:

- `TrajectoryEvent` に context read target を観測できる event を追加する、または既存 `tool_call` target から read refs を aggregate する。
- `measure_eval.py` が `read_refs`, `write_targets`, `unexpected_reads` を集計する。
- `eval-envelope.json` に `allowed_read_refs` を追加する。
- `check-context-scope.py` は legacy/self-report check と位置付け、trajectory-backed check を追加する。

Acceptance examples:

```sh
uv run pytest tests/workflow_core/test_measure.py tests/test_context_scope_check.py -k "context_evidence or allowed_refs"
uv run pytest tests/workflow_core/test_contract_harness.py -k bottleneck
make check-required
```

---

## 5. 統合後の最小 PR 分割案

### PR 0: Docs-only canonical plan

Scope:

- Add this integrated plan under `docs/reference/`.
- Optionally add a routed link from `README.md`.

No implementation.

Validation:

```sh
uv sync --frozen --group dev
make check-foundation
```

### PR 1: Active surface + minimal fixture

Scope:

- `./harness init`
- `templates/harness/minimal/`
- quickstart docs
- role/tool consistency
- RFC active surface cleanup

Rationale:

- Later evidence/context tests need a stable, visible minimal task surface.

### PR 2: Machine evidence + process envelope

Scope:

- `machine-evidence-manifest.json`
- bounded verifier stdout/stderr evidence
- structured process result for timeout/error
- `argv` verifier schema

Rationale:

- Review/gate correctness depends on reliable machine evidence.

### PR 3: Context manifest + acceptance checklist

Scope:

- `capsule.json` v2
- `explain --json`
- bounded semantic review packet
- `acceptance.generated_checks[]`

Rationale:

- Agent/reviewer must know exactly what was visible, omitted, required, and verified.

### PR 4: Typecheck + check-harness

Scope:

- include `src` or `src/workflow_core/contract_harness` in mypy
- `make check-harness`
- clean checkout bootstrap smoke

Rationale:

- Harness improvements need their own focused gate.

### PR 5: Bottleneck + trajectory evidence + status

Scope:

- `bottleneck.yaml` schema and wiring
- trajectory-backed context evidence
- read-only `harness status`
- optional tool phase split / declared test mapping

Rationale:

- Close the loop between stated bottlenecks, observed behavior, and gate/report output.

---

## 6. Definition of Done for the whole improvement stream

この改善群を merge-ready と呼べる条件:

1. 変更対象の files / scope / denied context が明示されている。
2. 新規 behavior ごとに tests-first acceptance が追加されている。
3. clean checkout で minimal harness task を生成・prepare・explain・verify・submit できる。
4. agent-facing tool list と role permission が一致している。
5. `rfc` は実装済み active command か、active surface から消えている。
6. `capsule.json` と `explain --json` は visible inputs / denied context / known absences / required gates / human gates / evidence outputs / acceptance checklist を含む。
7. semantic reviewer packet は bounded context manifest を持つ。
8. machine evidence は manifest hash に束縛され、verifier command / execution mode / exit_code / duration / artifact hashes を含む。
9. timeout / subprocess failure は JSON / structured result で返り、通常経路で traceback を出さない。
10. verifier は `argv` schema をサポートし、shell command は legacy mode として evidence に残る。
11. `make typecheck` が `src` と `tests`、少なくとも `src/workflow_core/contract_harness` と `tests` を対象に通る。
12. `make check-harness` が存在し、contract harness acceptance tests と eval smoke を含む。
13. `bottleneck.yaml` が capsule / explain / gate / report / metrics のいずれかに接続されている。
14. context self-report は legacy として扱われ、trajectory-backed context evidence が評価に使われる。
15. `make check-required` が通る。
16. high-risk / PR-ready change では `make check-foundation` が通る。

推奨最終検証:

```sh
uv sync --frozen --group dev
make format-check
make lint
make typecheck
uv run pytest tests/workflow_core/test_contract_harness.py
uv run pytest tests/workflow_core/test_contract_harness_policy_acceptance.py
uv run pytest tests/workflow_core/test_contract_harness_land_push_acceptance.py
make check-harness
make check-required
make check-foundation
```

---

## 7. 統合上の採用・非採用判断

### 採用

- clean checkout bootstrap を最初に整える。
- reviewer `review-collect` mismatch は修正対象にする。
- `rfc` は active surface と実装状態を一致させる。最終 target は evidence-bound human decision command。
- capsule v2 / explain --json / visible inputs / denied context を採用する。
- bounded reviewer context manifest を採用する。
- machine evidence manifest を採用する。
- timeout / subprocess result envelope を採用する。
- `argv` verifier schema を採用する。
- `src` mypy 対象化を採用する。
- `make check-harness` を採用する。
- bottleneck.yaml を explain / gate / report / metrics に接続する。
- trajectory-backed context evidence へ移行する。

### 後段または optional

- `tools --phase` / minimal-full tool list 分離。
- owners/verifiers の declared test mapping。
- read-only `harness status`。
- integration lock diagnostic。

### 非採用

- runtime queue / dashboard / ledger の追加。
- raw full logs の保存。
- secret-bearing output の無制限保存。
- provider-specific runtime import を core harness に持ち込むこと。
- reviewer approval による failing machine gate の override。
- human approval なしの external write / destructive action。

---

## 8. 結論

2案は競合しているというより、焦点が違う。

- 1案目は、harness を agent が実際に使える active surface にするための入口・role・CLI・capsule・evidence の問題を整理している。
- 2案目は、tests-first で evidence / context / timeout / typecheck / eval を強化する実装受け入れ条件を具体化している。

統合版では、まず active surface を正し、次に machine evidence と process result を強化し、その後 context manifest と acceptance checklist を整え、最後に typecheck / check-harness / bottleneck / trajectory evidence で改善ループを閉じる。

この順序なら、現行 repository の goal-first / scoped context / machine evidence / human gate という設計思想を維持したまま、contract harness を「agent の自己申告」ではなく「見えている contract と hash-bound evidence」で運用できる状態へ近づけられる。
