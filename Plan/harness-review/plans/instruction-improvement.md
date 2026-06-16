## 前提
- artifact/fable-thoughtには60 session, 4600 rowに及ぶFableのコーディング時の原則や思考が抽出してある。

## goal
このrepositoryにFableの思考を下ろしてシステムプロンプトやskillを作成することで、Fable並みの正確かつロバストな振る舞いができるようになることを期待しています。

## 方法
artifat/fable-thoughtにある原理原則抽出後のテキストをみて、こちらのハーネスの設計思想に合う部分を抽出してactiveやskillに昇格する作業を行います。
必ずこのレポジトリの設計思想理解->抽出の順で行い、active docs<200lineの原則も守ること。

## 制約
システムプロンプト: 長すぎる抽出禁止、エージェントに常時読ませるだけの価値があることを確認する。
skill: マイナーすぎるskillではなく、常時読む必要はないがしばしば利用またはfallbackとして有用な場合のみ採用する。

## 実行ログ 2026-06-15

- decision: active docs は短文原則のみ revise。汎用 fallback として
  `implementation-slice-verification` skill を add。
- reason: Fable 抽出で繰り返された「runnable slice」「中核経路優先」
  「検証足場を実装と同時に作る」「失敗時に観測層を変える」は、この
  repo の goal-first / bounded / verifiable 思想に合う。一方、視覚・
  ML・運用などの詳細例は active docs に常時読む価値まではないため
  昇格しない。
- source_refs:
  `artifact/fable-thought/principles_sets_01_05.md`,
  `artifact/fable-thought/principles_sets_06_10.md`,
  `artifact/fable-thought/optional_skill_sets_01_05.md`,
  `artifact/fable-thought/optional_skill_sets_06_10.md`
- changed_paths: `docs/01-agent-operating-contract.md`,
  `docs/02-output-verification-contract.md`,
  `.agents/skills/implementation-slice-verification/SKILL.md`,
  `.agents/skills/SKILL_INDEX.md`
- verification: `python3 scripts/check-skill-routes.py` passed;
  `python3 -m pytest tests/test_foundation_integrity.py -q -k
  'active_agent_context_stays_under_budget or
  agents_routes_to_active_docs_and_references or skill_roots_are_explicit'`
  passed; active docs total is 320 lines.

## 追加整理 2026-06-15

- decision: `AGENTS.md` の `Skill Routes` セクションを削除し、skill
  discovery の正を `.agents/skills/SKILL_INDEX.md` に寄せた。
- changed_paths: `AGENTS.md`, `scripts/agent_operational_checks.py`
- verification: `python3 scripts/check-skill-routes.py` passed;
  `python3 -m pytest tests/test_skill_route_check.py -q` passed;
  focused foundation integrity check passed; active docs total is 299 lines.

## 再現計画実行 2026-06-15

- decision: reference 一覧は残し、human gate / records / output shape /
  storage detail の重複を active docs 内で圧縮した。
- changed_paths: `AGENTS.md`, `docs/01-agent-operating-contract.md`,
  `docs/02-output-verification-contract.md`,
  `docs/03-repo-boundary-and-storage-contract.md`
- verification: `python3 -m pytest tests/test_foundation_integrity.py -q`
  passed; `python3 scripts/check-skill-routes.py` passed;
  `python3 -m pytest tests/test_skill_route_check.py -q` passed; active docs
  total is 250 lines.
