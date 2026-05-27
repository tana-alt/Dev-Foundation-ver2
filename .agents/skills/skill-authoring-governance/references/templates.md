# templates

## 1. lightweight-preflight report template

```md
# lightweight-preflight report

## 対象 skill
- name:
- version / snapshot:

## description / body / references の乖離
- description にあるが body にない:
- body にあるが description にない:
- references にあるが本文から辿れない:

## 曖昧点
- 用語:
- 手順順序:
- 参照導線:

## 修正提案
- 今すぐ直すべき最小修正:
- references に逃がす詳細:

## production 実行前チェック
- Iteration 0 完了: yes / no
- rubric 初案あり: yes / no
- inner loop シナリオ初案あり: yes / no
- hold-out 初案あり: yes / no
- production 実行可否:
```

## 2. rubric template

```md
# rubric

## skill 名
-

## 前提
- description の要点:
- 下流依存性:
- 観測データ不足フラグ: yes / no

## 評価項目 (3〜7 個)
1. 項目名:
   - 1.0:
   - 0.5:
   - 0.0:
2. 項目名:
   - 1.0:
   - 0.5:
   - 0.0:
3. 項目名:
   - 1.0:
   - 0.5:
   - 0.0:

## meta rubric チェック
- 測定可能性: pass / fail
- 項目重複なし: pass / fail
- description 範囲整合: pass / fail
- 下流依存性カバー: pass / fail

## 閾値
- 伸び幅閾値:
- hold-out 劣化閾値:
- tool_uses 偏り閾値:
- iteration 上限:
```

## 3. scenario set template

```md
# scenario set

## inner loop
1. scenario A
- 目的:
- 難易度:
- 期待する stress point:

2. scenario B
- 目的:
- 難易度:
- 期待する stress point:

3. scenario C (optional)
- 目的:
- 難易度:
- 期待する stress point:

## hold-out
- 目的:
- inner loop と違う点:
- 封緘状態: sealed
```

## 4. iteration log template

```md
# iteration N

## scenario
-

## rubric score
- item 1:
- item 2:
- item 3:
- total:

## self-report summary
- 詰まった箇所:
- 裁量補完した箇所:
- description / body mismatch:
- broken / outdated references:

## secondary signals
- output quality alert:
- tool_uses:
- tool_uses skew:

## chosen theme
- 今回触るテーマは 1 つだけ:

## patch
- 変更箇所:
- 変更理由:
- 変更範囲が最小である根拠:

## next decision
- continue / stop / escalate
```

## 5. stop-check template

```md
# stop check

## latest two iterations
- iter X score:
- iter Y score:
- score delta:
- new ambiguity in iter X:
- new ambiguity in iter Y:

## decision
- 連続 2 回で新規不明瞭点ゼロ: yes / no
- 連続 2 回で伸び幅閾値未満: yes / no
- stop / continue:
```

## 6. hold-out check template

```md
# hold-out check

## hold-out scenario
-

## score
- hold-out score:
- latest inner-loop mean:
- drop:

## decision
- overfit threshold exceeded: yes / no
- next action: Stage 2 / rubric review
```

## 7. regression template

```md
# Stage 2 regression confirm

## past success cases
1.
2.
3.

## results
- case 1: before / after
- case 2: before / after
- case 3: before / after

## decision
- degraded case exists: yes / no
- merge / rollback:
```

## 8. subagent prompt template

```md
あなたは <対象 skill 名> を **白紙で読む実行者** です。
この skill について事前知識を持たず、渡された本文のみを根拠にしてタスクを解いてください。

## 対象 skill
<SKILL.md 全文>
<references/ 全文>

## シナリオ
<現実的タスク 1 件の具体記述>

## 実行指示
1. 対象 skill を読む。
2. シナリオを解く。skill を適用して成果物を生成する。
3. レポートを次の形式で返す:
   - 成果物本体
   - 自己申告:
     - skill を読みながら詰まった箇所
     - skill が指示しておらず、あなたが裁量で補完した箇所
     - description と body に食い違いを感じた箇所
     - references へのリンクで辿れなかった / 古いと感じた箇所

## 制約
- 親セッションの context は参照しない。skill 本文と references のみを根拠にする。
- 成果物と自己申告を分けて明記する。両方必須。
- 「分かっていても書かれていないこと」は裁量補完として必ず申告する。
```
