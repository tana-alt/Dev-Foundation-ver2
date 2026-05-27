# rubric-design

## 1. rubric 粒度の決め方

rubric は skill 設計の最大自由度なので、inner loop に入る前に固定する。

### 原則 1: description の抽象度に揃える

- description が「plan を出力する」とだけ言うなら、rubric も粗くする。
- description が「構造化 format で出力」と言うなら、形式整合も rubric に入れる。
- description を超える rubric は責務越え。
- description を下回る rubric は integrity を測り切れない。

### 原則 2: 下流依存性で境界を引く

- 別 agent / skill が読むなら、形式整合性は rubric 必須。
- human-facing 最終成果物なら、readability も rubric 必須。
- 後段で refine される中間出力なら、完成度は rubric から外してよい。

### 原則 3: 失敗ログから bottom-up で補う

- 過去の失敗ケースがあるなら列挙する。
- 各失敗について「どの rubric 項目があれば検知できたか」を逆引きする。
- 目安は **失敗ログ由来 7 割 + description 準拠 3 割**。
- 失敗ログがない場合は top-down のみで設計し、**観測データ不足**フラグを付ける。

## 2. rubric の形式要件

- 項目数は **3〜7**。
- 各項目は **0 / 0.5 / 1** で離散採点可能。
- 項目間で意味重複しない。
- 判定基準は閾値まで具体化する。

例:
- 悪い: 「想定フローが書かれている」
- 良い: 「処理ステップが 3 個以上あり、順序が明示され、各ステップに入出力が書かれている」

## 3. meta rubric

rubric 自体の妥当性は次の 4 項目で固定し、これ以上細分化しない。

1. 各項目は測定可能か
2. 項目間で重複していないか
3. description の範囲を越えていないか / 下回っていないか
4. 下流依存性で必要な性質をカバーしているか

## 4. シナリオ設計

### inner loop 用

- 2〜3 本
- 中央値ケース 1 本
- edge ケース 1〜2 本

### hold-out 用

- 別途 1 本確保
- inner loop 中は使わない
- 停止判定直後に初めて開く

### 禁止事項

- 修正に合わせてシナリオを変える
- hold-out を途中で覗く
- 難しすぎる / 簡単すぎるシナリオでシグナルを潰す

## 5. 閾値の扱い

以下は初期値であり、run ごとに事前固定してよい。

- 伸び幅閾値の例: +0.05
- hold-out 劣化閾値の例: -15 pt
- tool_uses 偏り閾値の例: 3〜5 倍
- iteration 上限: 4

重要なのは **loop 中に変更しないこと**であり、初期値そのものの絶対性ではない。

## 6. rubric テンプレートの使い方

具体的な記入用テンプレートは `templates.md` を使う。

最低限、以下を 1 セットとして保存する。

- rubric 本体
- meta rubric チェック
- inner loop シナリオ
- hold-out シナリオ
- 閾値設定

## 7. rubric を見直すタイミング

以下が起きたら、次回 cycle の前に outer review で rubric を見直す。

- 成功ケースで常に 1.0 ばかりになり、差が出ない
- 失敗ケースでも高得点になる
- skill description 自体が実質的に変わった

**inner loop 中には rubric を変えない。**
