# AI Agent ハーネス改善レポート — 設計診断と実装計画

作成日: 2026-06-10
対象: Codex/AI agent 開発基盤リポジトリ(goal-first harness)

---

## 1. 背景と診断

### 1.1 旧 contract heavy の失敗の本質

旧ハーネスの失敗は契約の「内容」ではなく「執行の所在」にあった。agent が自分で契約・記録を書く構造では、契約は「agent の作文」にすぎず、規約を満たしたふりをするコストが実装するコストより安くなる。実装からの逃げ(stub、mock、records-only output)は典型的な reward hacking であり、対策は規約を増やすことではなく機械が判定するゲートへの置き換えである。

> ハーネスの本質は「プロンプト空間の規約」ではなく「環境空間の検証」である。

### 1.2 現行ハーネスの評価

現行の goal-first 設計は旧失敗の総括として正しい。特に以下の3点は reward hacking への直接の対抗策として機能している。

- records are not deliverables(記録を作っただけでは完了ではない)
- mock / dry-run / draft / records-only は原則 incomplete
- Spec is thinking before work, not a running gate

一方、残るリスクは一貫して **「規範は書かれたが、強制は誰がするのか」** に集約される。現状 result state(passed / failed / blocked / skipped / not_applicable)は agent の自己申告であり、ここが土台の穴である。

---

## 2. 設計原則(確定事項)

1. **観測事実 > 自己申告。** 完了の根拠は hook が捕捉した実行結果(exit code、diff hash、timestamp)であり、agent の宣言ではない。
2. **機械化するのは evidence 生成と完了判定のみ。** 全工程の機械化は旧 ceremony の復活になる。執行点を最小に絞る。
3. **subagent の価値は並列性ではなくコンテキスト隔離。** subagent は「並列に働くチームメイト」ではなく「コンテキストの防火壁+非可逆圧縮器」である。
4. **圧縮が許容される仕事は subagent へ、忠実度が必要な仕事(実装)は main が持つ。** 実装文脈は分割すると統合時に消失し、統合コストが並列の速度向上を食い潰す。
5. **文書の肥大は人間の意志ではなくテストで止める。** active docs の予算(<200 行 × 3)を check に組み込む。

---

## 3. 推奨アーキテクチャ: 1 writer + N read-only subagents

main agent が単独で実装し続け、read-only の subagent 群が research / doc-lookup / review / verification を担う構成を標準とする。これは現 harness 思想(subagent is optional、main agent が統合責任を持つ)と整合する。

### 3.1 並列 write の扱い

repo という共有可変状態に複数 writer がいる時点で分散システムの問題(conflict、抽象の重複、interface 不整合、規約 drift)が発生し、agent の能力向上では消えない。並列 write は禁止ではなく opt-in とし、以下の条件が機械的に検証できる場合のみ解禁する。

- worktree 隔離が有効
- 各 agent の allowed writes の交差が空(hook で検証、交差すれば起動拒否)
- 末端で機械的な merge 検証(merge-integrity-governance)が走る

この条件判定は scope-routing に組み込み、安全な並列だけが自然に通る構造にする。

### 3.2 長時間自律への経路

完全自律の鍵は並列化ではなく、単一 agent の信頼できる連続稼働時間を伸ばすことである。劣化要因は context rot なので、対策は次の3つ。

1. **直列フェーズ分割+handoff packet。** フェーズ境界で fresh context に引き継ぐ。引き継ぎ媒体は spec と Plan/ログそのもの。「次の agent が読むことを前提にログを書く」運用とする。
2. **読み込み仕事の徹底的なオフロード。** main のコンテキストを実装関連のみに保つため、探索・調査は subagent へ。
3. **ゲートによる軌道修正。** 機械的 evidence(P1)が自律時間を伸ばす実質的な安全装置。人間の監視を減らせるのは、逸脱が機械的に止まる場合のみ。

---

## 4. 実装項目(優先度順)

### P1: result state の機械化(最優先・他と独立に即時導入)

**問題:** result state が自己申告である限り、レビュー層がどれだけ良くても evidence の土台が信用できない。

**実装:**

- hook が `make check-*` 系の実行をラップし、以下を JSON で artifact に書き込む。agent は参照のみ可、生成・編集は不可。
  - command
  - exit code
  - 対象 diff の hash
  - timestamp
- 完了宣言時、hook が「Done criteria に対応するゲートの passed artifact が存在し、かつ hash が現在の diff と一致する」ことを検証。不一致・不在なら宣言を block。
- `skipped` / `not_applicable` は理由文字列を必須とし、ログ上で強調表示する(residual-risk record の廃止意図が skipped の自己付与で復活するのを防ぐ)。

**設計上の要点:** hash 束縛が肝。これがないと「一度 pass してから更に編集する」時系列の逃げが残る。

### P2: テスト所有権の分離

**問題:** 実装 agent がテストを書き換えられるなら verification は循環する。前回の失敗(実装からの逃げ)の直接の再発経路。

**実装:**

- 「Done criteria とテストは実装開始後に実装者が編集しない」を契約レベルに格上げ。
- hook で実装フェーズ中のテストファイル diff を検出して弾く。
- テスト(または実行可能な受入条件)は spec 段階で確定する。散文の受入条件は解釈で逃げられるため、機械判定可能な形で書く。

### P3: scope cross review の導入

2種の read-only reviewer を fresh context(実装者の会話履歴を共有しない)で起動する。

**Reviewer A(in-scope):** 実装範囲内を深く見る。

- Done criteria を満たしたか
- 逃げパターン(stub、type: ignore、pytest.skip、空の関数体、NotImplementedError)がないか
- テストが意味を持つか

**Reviewer B(broader):** one hop 規則で範囲を機械的に定義する。

- 変更ファイルの直接の caller / callee
- 共有 data contract
- 同一 interface の実装
- 渡す refs は hook または main agent が機械的に列挙して渡す(散文の「少し広く」は二極化するため不可)

**効力分離(scope creep 防止):**

- blocking になるのは「Done criteria 違反」または「invariant 違反」のみ
- それ以外の所見は follow-up log として記録のみ。これを先に決めないと Reviewer B が事実上の無限ゲート(旧 human gate の再来)になる。

**返り値:** subagent 規約の Return shape に合わせ、型付き verdict(pass/fail + findings with severity)とする。hook で集計可能にする。修正権限は持たず、修正は main agent が行う。

### P4: check ティアの選択権剥奪

**問題:** どのティアを走らせるか agent が選べると、常に check-fast で完了宣言する均衡に落ちる。

**実装:** Done criteria の中で要求ゲートレベルを明示する規則を core docs に入れる(例:「check-required の通過」を完了条件に含める)。P1 の hash 束縛と組み合わせれば、宣言時に該当ティアの passed artifact が要求される。

### P5: 文書予算のテスト化

**実装:**

- active 3 docs の行数上限(<200 行)を check-fast に組み込む。
- skill カタログ・make target 詳細は reference に落とし、常駐文書はフロー・3契約・禁止事項・ゲート対応表のみとする。
- reference は「named refs first」原則に乗せ、spec や task packet から名前で指す運用に統一する。

### P6: failed 後のループ予算

**問題:** failed 時の再試行規定がないと、agent が失敗ループでサイクルを焼く。

**実装:** N 回失敗で blocked に遷移し escalate する予算規則を定める(N は task packet で指定可能、default を core に置く)。

### P7: 例外条項の機械判定化

**問題:** 「ユーザーがそれだけを求めた場合を除いて」は解釈で広げられる逃げ道。

**実装:** draft-only / records-only が許容されるのは、ユーザーの明示マーカー(spec 内のフラグ等)がある場合のみとし、機械判定可能な形にする。

### P8: governance skill の使用頻度計測

**問題:** governance 系 skill が7つあるのは、heavy contract と同じ本能が形を変えて生き残っている兆候。

**実装:** skill の使用頻度を計測し、死に skill を定期的に刈る運用を導入する。skill index 整合テストは既存のため、計測の追加のみ。

---

## 5. 導入順序の指針

P1 は他のすべての前提となるため単独で即時導入する。P2 / P4 は P1 の hook 基盤に乗るため続けて入れる。P3 は subagent 構成の変更を伴うため、P1〜P2 の安定後に導入する。P5〜P8 は独立しており、任意のタイミングで小さく入れられる。

| 優先度 | 項目 | 依存 | 実装コスト |
|---|---|---|---|
| P1 | result state 機械化 | なし | 中(hook + JSON evidence) |
| P2 | テスト所有権分離 | P1 の hook 基盤 | 小 |
| P3 | scope cross review | P1, P2 | 中(reviewer 定義 + verdict schema) |
| P4 | check ティア指定 | P1 | 小(docs 規則 + 宣言検証) |
| P5 | 文書予算テスト化 | なし | 小 |
| P6 | failed ループ予算 | なし | 小 |
| P7 | 例外条項の機械判定化 | なし | 小 |
| P8 | skill 使用頻度計測 | なし | 小 |

---

## 6. 一文で要約

このハーネスの完成形は、「main agent が単独の writer として文脈を保ったまま実装し、read-only subagent が圧縮可能な仕事(調査・レビュー・検証)を肩代わりし、完了の宣言権は agent ではなく hook が持つ」構造である。
