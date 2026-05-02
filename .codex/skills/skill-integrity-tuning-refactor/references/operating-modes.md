# operating-modes

この skill の運用モードは 2 つある。**本来の受入判定は production のみ**であり、lightweight-preflight はその前段に置く補助モードである。

## 1. モード一覧

| mode | 主用途 | 必須ステップ | 許可される出力 | 禁止される主張 | merge / accept 可否 |
|---|---|---|---|---|---|
| lightweight-preflight | 事前整理、静的整合、文言整理、構造審査 | Iteration 0、必要なら構造審査 | 乖離一覧、曖昧点一覧、修正提案、rubric/シナリオ案 | empirical に通った、停止条件を満たした、hold-out 済み、regression 済み | 不可 |
| production | 本番の integrity tuning | Iteration 0 → 0.5 → 1..N → hold-out → Stage 2 | 採点付き反復ログ、停止判定、過適合判定、regression 判定 | なし | 可 |

## 2. lightweight-preflight の位置づけ

lightweight-preflight は、元の skill にあった以下をまとめ直したものとみなす。

- Iteration 0 の静的整合チェック
- 構造審査モード

したがって、これは **別仕様** ではない。production を軽量化して置き換えるのではなく、production に入る前に静的欠陥を安く洗い出すための補助である。

## 3. lightweight-preflight を使う場面

以下で使ってよい。

- description と body の乖離が明らかにありそうなとき
- references の整理を先にやりたいとき
- rubric やシナリオの初案を作りたいとき
- dispatch は可能だが、まず静的な欠陥だけを安く見たいとき
- dispatch 不能で、empirical loop を後送するしかないとき

## 4. lightweight-preflight の成果物

最低限、以下を出す。

1. description / body / references の乖離一覧
2. 曖昧語・未定義語・順序不明箇所
3. references に逃がすべき詳細候補
4. rubric 初案または rubric 設計上の注意点
5. production 実行前に最低限直すべき箇所

## 5. lightweight-preflight の禁止事項

以下はしてはいけない。

- 「この skill は要件を満たしている」と判定する
- 連続 2 回達成などの停止条件を満たしたことにする
- hold-out や regression を省略したまま merge 推奨する
- 自己再読のみで preflight を完了したことにする

## 6. production の必須手順

production では以下を必ず行う。

1. Iteration 0 の静的整合チェック
2. rubric / inner loop シナリオ / hold-out の事前固定
3. 新規 subagent による empirical loop
4. 停止条件の連続 2 回達成確認
5. hold-out 過適合チェック
6. Stage 2 regression confirm

どれか 1 つでも飛ばした場合、その run は production 完了扱いにしない。

## 7. dispatch 不能時の扱い

dispatch 不能時に許される報告は次のいずれか。

- 「lightweight-preflight のみ実施した」
- 「integrity tuning skipped: dispatch unavailable」

**許されない報告**:
- 「production 相当の評価をした」
- 「empirical に validated した」

## 8. 推奨の使い分け

### パターン A: 草案の整理から始める
1. lightweight-preflight
2. 必要最小限の編集
3. production

### パターン B: dispatch 不能
1. lightweight-preflight
2. 明示的に skip 報告
3. 別 run / 別環境で production

### パターン C: 明らかな minor patch
1. Iteration 0 を短く行う
2. そのまま production

## 9. 最終原則

- lightweight-preflight は **前処理**。
- production は **本判定**。
- 両者を混同しない。
