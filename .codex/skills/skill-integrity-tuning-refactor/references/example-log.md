# example-log

以下は最小構成でこの skill を回したときのログ例。

```md
[Iteration 0]
description: "API の rate limit を検出し、exponential backoff で retry する"
body の実装範囲: retry 処理はあるが exponential backoff なし (固定 sleep)
乖離: あり (backoff 手法)
→ body に exponential backoff の擬似コードを追加

[Iteration 0.5]
rubric (top-down 3 項目, 失敗ログなし):
1. rate limit header を読んで検出しているか
2. backoff が exponential か (固定待機なら 0)
3. retry 上限が設定されているか
inner シナリオ: "429 を 3 回連続で返す mock API に対してリクエストを送る"
hold-out: "429 と 503 が混在する mock API に対してリクエストを送る" (封緘)

[Iteration 1]
rubric: 2/3 (item 3 が 0: 上限が書かれていない)
tool_uses: 2
自己申告: "retry 上限が書かれておらず、自分で 5 回と決めた"
修正: body に "retry 上限は 5 回、超過で例外" を追記

[Iteration 2]
rubric: 3/3
tool_uses: 2
自己申告: 新規指摘なし
判定: 1 回目の全項目達成。停止条件は連続 2 回なので、もう 1 iter 必要。

[Iteration 3]
rubric: 3/3
tool_uses: 2
自己申告: 新規指摘なし
判定: 連続 2 回達成 → 停止。

[hold-out]
hold-out "429/503 混在" で再実行
rubric: 3/3
inner loop 平均比で劣化なし
→ 過適合なし、Stage 2 へ

[Stage 2]
過去成功ケース 3 件で再実行、全て 3/3 維持
→ merge
```

## 読み方

- Iteration 0 で description / body の構造乖離を先に潰している。
- Iteration 1..N では 1 iter 1 テーマで最小修正している。
- 停止判定と hold-out と regression を分離している。
- これが production の最小骨格である。
