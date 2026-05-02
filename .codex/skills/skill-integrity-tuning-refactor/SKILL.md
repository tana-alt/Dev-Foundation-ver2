---
name: skill-integrity-tuning
description: 既存 skill の description と実出力の整合を empirical に検証し、1 iter 1 テーマで skill 本文を改善する。Task tool で新規 subagent を dispatch できる環境でのみ動作する。改修対象は既存 skill のみで、新規 skill 作成は範囲外。
---

# skill-integrity-tuning

## 1. 目的

- 既存 skill の概要 (frontmatter description) と、実際に skill を適用したときの出力の整合度を高める。
- agent 主導で回す。human-in-the-loop は escalation 時のみ。
- reward hacking は human ではなく、session 分離・rubric 固定・シナリオ固定で防ぐ。
- 本 skill は **既存 skill の改善専用**。新規 skill 作成は扱わない。

## 2. 対象 / 対象外

- **対象**: 既存 skill の SKILL.md 本文、および references 配下のファイル。
- **対象外**:
  - 新規 skill の作成
  - skill contract の変更
  - inner loop 中の rubric 改訂

## 3. 実行前ガード

以下の 3 点が揃わない場合、**production mode** は実行しない。

1. Task tool で新規 subagent を dispatch 可能。
2. rubric とシナリオを inner loop 中は固定できる。
3. 改修前の skill 状態 (SKILL.md + references) を snapshot し、rollback できる。

揃わない場合は `references/operating-modes.md` に従い、
- lightweight-preflight のみ実施する、または
- `integrity tuning skipped: dispatch unavailable` を明示して終了する。

## 4. 実行モード

この skill には 2 つの運用モードがある。

### A. lightweight-preflight

- 用途: 事前整理、静的整合チェック、軽い文言整理、構造審査。
- 中身: **Iteration 0 + 必要なら構造審査モード**。
- 制約:
  - empirical な合格判定には使わない。
  - merge / accept の根拠にしない。
  - hold-out / regression / 連続 2 回達成の代替にしない。

### B. production

- 用途: 本番の integrity tuning。
- 中身: **Iteration 0 → Iteration 0.5 → Iteration 1..N → hold-out → Stage 2**。
- 備考: merge / accept 判定に使ってよいのはこのモードのみ。

詳細なモード定義は `references/operating-modes.md` を参照。

## 5. 不変ルール

以下は inner loop 中に崩してはいけない。

1. **Iteration 0 を先に行う**。
2. **rubric と inner loop 用シナリオは事前固定し、loop 中に変更しない**。
3. **hold-out シナリオは封緘し、停止判定直後まで使わない**。
4. **1 iter 1 テーマ**で改修する。
5. **毎 iter 新規 subagent を dispatch**し、直前 subagent の continuation にしない。
6. **自己再読を評価代替に使わない**。
7. **構造審査は補助であり、empirical 評価の代替ではない**。
8. **新規 skill 作成や contract 変更を混ぜない**。

## 6. production mode の標準フロー

### Step 0. 静的整合チェック

description と body の乖離を潰す。

- description が謳う trigger・用途・範囲を列挙する。
- SKILL.md と references の実質カバー範囲を抽出する。
- 以下を具体化する。
  - description にあるが body にないもの
  - body にあるが description にないもの
- 乖離があるうちは empirical loop に進まない。

### Step 0.5. rubric / シナリオ固定

- rubric を設計し、inner loop 中は固定する。
- inner loop 用シナリオ 2〜3 本を固定する。
- hold-out 用シナリオ 1 本を別途確保し、停止判定直後まで封緘する。

rubric 設計とテンプレートは以下を参照。
- `references/rubric-design.md`
- `references/templates.md`

### Step 1..N. empirical 改修ループ

各 iter で以下を行う。

1. 新規 subagent を dispatch し、現行 skill とシナリオを渡す。
2. fixed rubric で採点する。
3. 自己申告を読む。
   - 詰まった箇所
   - 裁量補完した箇所
   - description と body の食い違い
   - references のリンク切れ / 古さ
4. 必要に応じて tool_uses の偏りを見る。
5. **1 テーマだけ**選び、最小修正を入れる。
6. 次 iter では必ず新規 subagent で再実行する。

### 評価シグナル

- **primary**: rubric 充足率
- **qualitative**: subagent の自己申告
- **secondary**: 出力品質そのもの
- **secondary**: tool_uses の偏り
  - あるシナリオだけ他シナリオ比で 3〜5 倍以上なら、skill の自己完結性が低いサインとみなす。
  - 対処は「最小完成例の inline 追加」または「どの references をいつ読むか」の明示。

### 修正優先順位

1. description と body の乖離
2. subagent が裁量補完した箇所
3. 用語定義の欠落や曖昧さ
4. 手順順序の不明瞭さ
5. reference のリンク切れ・古さ

## 7. 停止条件

### 正常停止

以下を **連続 2 回** 満たしたら停止する。

- 新規不明瞭点ゼロ
- rubric 充足率の伸び幅が事前閾値未満 (例: +0.05)

### 上限停止

- 4 iteration で正常停止条件に届かなければ escalate する。
- その場合は minor patch ではなく、major refactor の可能性を検討する。

### Tier 目安

- 軽改修: 1〜2 iter
- 中改修: 3〜4 iter
- 重改修: 範囲外。別 track に回す

## 8. 停止判定後の必須確認

### hold-out 過適合チェック

停止判定の直後に、封緘していた hold-out シナリオ 1 本で再評価する。

- 閾値: hold-out の rubric 充足率が、直近 2 iter の inner loop 平均から **15 ポイント以上**落ちたら過適合。
- 過適合なら、rubric 設計まで遡って review する。
- 過適合でなければ Stage 2 に進む。

### Stage 2: regression confirm

過去成功ケース 3〜5 件を、**同じ rubric** で再実行する。

- 改修後の rubric 充足率が改修前比で劣化していないことを確認する。
- 劣化があれば rollback し、rubric 設計を含めて再 review する。

## 9. dispatch 不能時の扱い

dispatch 不能な環境では production mode は適用しない。

許される対応は以下のみ。

- lightweight-preflight のみ行う。
- `integrity tuning skipped: dispatch unavailable` と報告する。

**NG**:
- 自己再読で評価したことにする。
- 構造審査だけで merge 判定する。

## 10. subagent 起動契約

dispatch する subagent には、最低限以下を要求する。

- 自分を **白紙で読む実行者** として扱うこと
- 親 context を参照しないこと
- skill 本文と references のみを根拠に実行すること
- 次を必ず分けて返すこと
  - 成果物本体
  - 自己申告
    - 詰まった箇所
    - 裁量補完した箇所
    - description / body の食い違い
    - 辿れない / 古い references

完全なテンプレートは `references/templates.md` を参照。

## 11. アンチパターン

以下は禁止。

- 自己再読で評価する
- rubric を iter 中に更新する
- シナリオを修正に合わせて変える
- 1 iter で複数テーマを混ぜる
- 1 回の達成で停止する
- Iteration 0 を飛ばす
- hold-out を置かずに停止する
- 構造審査モードだけで merge 判定する
- 新規 skill 作成を兼ねる
- 複数 skill を同じ cycle で並行改修する

## 12. references

- `references/operating-modes.md`
  - lightweight-preflight と production の境界、許可される主張、merge 可否。
- `references/rubric-design.md`
  - rubric 粒度の決め方、meta rubric、シナリオ設計。
- `references/templates.md`
  - rubric、シナリオ、iteration log、subagent prompt のテンプレート。
- `references/example-log.md`
  - 最小実装例とログ例。

## 13. merge 判定の最終原則

- **実際に merge / accept の根拠に使えるのは production mode のみ**。
- lightweight-preflight は skill を軽く整えるための前処理であって、元の仕様を置き換えない。
