# AGENTS.md

これは以下のインターンの課題を作成することを目的とする
・内容：あなた自身の業務をAIで自動化する仕組みを設計・実装してください。 ・提出物：GitHubリポジトリ（URLを共有してください） また、GitHubのREADMEに以下の項目もまとめてください。 ・なぜそのタスクを自動化しようと思ったのか（背景・動機） ・システム設計上の設計思想（以下の参考文献を前提としたもの） 【参考文献URL】 https://lstep.app/F1mQlQB https://lstep.app/R3cZy8u https://lstep.app/SwKfiMq https://lstep.app/e6YVtQS

## 目的

このリポジトリでは、米国株の四半期決算を対象に、multi agents による分析レポートを出力するシステムを構築する

目的は、株価予測や売買推奨ではなく、決算後に以下の問いへ短時間で答えられるようにすること。

- 今回の決算は市場予想と比べて良いのか、悪いのか
- EPS は将来的に増加しそうか
- FCF は将来的に増加する方向に進んでいるか
- その判断を支える根拠と、反対方向の根拠は何か

最終成果物は GitHub リポジトリとして提出し、README には背景・動機、設計思想、使い方、出力例をまとめる。

## 背景・動機

決算レビューでは、EPS サプライズや売上成長率だけを見ると判断を誤る可能性がある。

例えば、EPS が市場予想を上回っていても、一時的な税率低下やコスト削減によるものかもしれない。逆に、短期的な投資負担で FCF が悪化していても、その投資が将来の利益率改善につながる可能性もある。

そのため、本プロジェクトでは「良い決算 / 悪い決算」を単純に判定するのではなく、財務数値と決算説明資料を分離して分析し、EPS と FCF の将来性を中心に multi agents で討論させる。

## 参考文献と設計思想

参考文献:

- https://lstep.app/F1mQlQB
- https://lstep.app/R3cZy8u
- https://lstep.app/SwKfiMq
- https://lstep.app/e6YVtQS

本プロジェクトでは、参考文献の要点を以下のように設計へ反映する。

- エージェントごとの責務を分離し、影響範囲を小さくする
- 財務計算、データ取得、レポート整形を分離し、副作用を局所化する
- LLM には自由形式の文章を直接出させず、Pydantic による構造化出力を必須にする
- LLM は計算主体ではなく、解釈・反証・要約を担当する
- 最終判断には、肯定根拠だけでなく反対根拠も必ず含める

## やること

- 財務情報を API で取得する
  - 売上
  - EPS
  - 営業利益率
  - 営業キャッシュフロー
  - FCF
  - CapEx
  - ガイダンス
  - コンセンサス予想との差分
- 決算プレゼン、10-Q、10-K、決算説明資料を取り込む
- 財務情報を分析する agents team を作る
- 決算プレゼンや経営陣コメントを分析する agents team を作る
- それぞれの agents team の分析結果をもとに、Bull / Bear / Risk の観点で討論する
- Judge agent が最終的に good / neutral / bad を判定する
- 判定理由、反対根拠、EPS 見通し、FCF 見通しを簡潔な Markdown レポートとして出力する

## やらないこと

- 株価予測
- 目標株価の算出
- 売買推奨
- リアルタイム自動売買
- 複雑なポートフォリオ最適化
- LLM に財務指標を直接計算させること
- エージェント数を過度に増やすこと

本プロジェクトの評価対象は、投資判断そのものではなく、決算情報を構造化し、複数視点から読み解き、可読性の高い分析レポートに落とし込む設計である。

## エージェント構造

```text
Input
  - ticker
  - fiscal quarter
  - financial API data
  - earnings presentation / filing documents

        ↓

Data Ingestion Layer
  - 財務 API から数値データを取得
  - 決算資料を取得
  - PDF / HTML / text を分析可能な単位に分割

        ↓

Financial Agents Team
  - EPS Analyst: EPSの市場予想とのmatchを図り、mismatchの原因を調査する
  - P&L Analyst: P&Lに特筆すべき変化はないか、それに対するエビデンスを調査する
  - CFS Analyst: CFSに特筆すべき変化はないか、それに対するエビデンスを調査する
  - BS Analyst: BSの健全性と特筆点についてレポートをまとめる

        ↓

Presentation Agents Team
  - Management eval Agent: 決算プレゼンから経営判断に関わる方針を調査、経営陣の意図とそれによるEPS、FCFへの影響を時間軸ごとにまとめる
  - Guidance Agent: 来期ガイダンスと市場の期待のmatchを見る、ガイダンスの現実性と過大評価、過小評価の可能性を分析する

        ↓

Debate Agents
  - Bull Agent: レポートを元にBull側で主張
  - Bear Agent: レポートを元にBear側で主張
  - Eval Agent: 主張を元に結果を判定する

        ↓

Judge / Report Agent
  - good / neutral / bad を判定
  - 根拠を整理
  - 反対根拠を整理
  - Markdown レポートを生成
```

## 各エージェントの責務

### Financial Agents Team

財務情報を API から取得し、決算数値の変化を分析する。

- EPS が市場予想を上回ったか
- EPS の改善が一時要因か継続要因か
- トップラインの伸びと懸念や営業利益率に注目すべき変化はないか
- CapEx や運転資本が FCF に与える影響は何か
- 財務レバレッジや負債水準に問題はないか

### Presentation Agents Team

決算プレゼンや経営陣コメントをもとに、数値だけでは見えない文脈を分析する。

- 経営陣は何を成長ドライバーとして説明しているか
- 今回の決算が市場予想より良い、または悪い理由は何か
- ガイダンスの前提は保守的か、楽観的か
- リスク要因は決算資料内でどう説明されているか
- 将来FCFに対してどのようなインパクトがあるかを分析する

### Debate Agents

Financial Agents Team と Presentation Agents Team の分析結果をもとに討論する。

- Bull Agent: 良い決算と判断できる根拠を整理する
- Bear Agent: 悪い決算または過大評価と判断できる根拠を整理する
- Eval Agent: 根拠を元に評価を行う

### Judge / Report Agent

討論結果をもとに、最終レポートを出力する。

- good / neutral / bad のいずれかを判定する
- confidence を付与する
- 主な根拠を簡潔に示す
- 反対方向の根拠を必ず示す
- EPS の将来見通しを示す
- FCF の将来見通しを示す
- 可読性の高い Markdown に整形する

## 構造化出力

LLM の出力は Pydantic で検証する。

## レポート出力イメージ

```markdown
# Earnings Review: NVDA 2025 Q3

## Verdict

Good

Confidence: 0.78

## Summary

EPS は市場予想を上回り、粗利率と営業利益率も改善した。短期的な投資負担はあるが、経営陣の説明とガイダンスを見る限り、将来 FCF を増やす方向に進んでいる可能性が高い。

## Positive Evidence

- EPS surprise がプラス
- 営業利益率が前年同期比で改善
- 経営陣が FCF 改善につながる投資回収フェーズを説明
- ガイダンスが市場予想を上回る

## Negative Evidence

- CapEx 増加により短期 FCF は圧迫されている
- 売上成長の一部が特定顧客に依存している
- ガイダンス達成には下期需要の継続が必要

## EPS Outlook

利益率改善と売上成長が継続すれば、EPS は今後も増加する余地がある。

## FCF Outlook

短期的には投資負担があるが、CapEx のピークアウトと営業利益率改善により、FCF は中期的に改善する可能性がある。
```

## 実装上の注意

- データ取得と LLM 分析を分離する
- 財務指標の計算は通常の Python 関数で行う
- LLM には計算済みの構造化データを渡す
- エージェントの出力は必ず Pydantic で検証する
- レポート生成前に、反対根拠が空でないことを確認する
- good / bad の判定だけでなく、neutral を許容する
- 出力は投資助言ではなく、決算分析レポートとして扱う
