---
name: app-plan-best-practice
description: アプリ作成の際のplanのベストプラクティス
---

# AI App Development Workflow　Planning

この文書は、AI を用いたアプリ開発のための **実行フロー** をまとめたもの。
短い rules ではなく、企画から運用までの流れと判断観点を扱う。
Plan作成のための参考書。

## Goal
AI を使って開発速度を上げつつ、品質・再現性・保守性を落とさないこと。

## End-To-End Flow

### 1. Goal Definition
最初に以下を定義する。
- ユーザーゴール
- ビジネスゴール
- 成功指標
- 制約条件

目標は SMART を意識し、曖昧な成功条件を避ける。

### 2. Requirement Framing
要件を次に分ける。
- **機能要件**: 何ができる必要があるか
- **非機能要件**: 速度、信頼性、拡張性、運用性、セキュリティ
- **AI 固有要件**: 推論精度、応答時間、モデル更新頻度、データ制約

特に AI アプリでは、推論 latency とデータ制約を早期に固定する。

### 3. Prototype First
本実装前に、薄いプロトタイプで次を検証する。
- ユーザーフローが成立するか
- AI 出力品質が最低ラインを超えるか
- UI 上の違和感や操作負荷が大きくないか
- 主要リスクが何か

プロトタイプ段階で不確実性を潰し、手戻りコストを抑える。

### 4. Data And Model Planning
AI 機能を含む場合は、先にデータとモデル方針を決める。
- 学習・参照データの出所
- データ品質
- 偏りや欠損への対応
- 個人情報や機密情報の扱い
- モデルの更新方法
- 評価指標

原則として **garbage in, garbage out** を前提にし、データ品質を軽視しない。

### 5. System Design
設計は少なくとも次を分ける。
- 外部設計: 画面、操作、API 契約、入力と出力
- 内部設計: 状態遷移、責務分離、保存、ジョブ、監視
- AI 設計: prompt, model, tools, guardrails, eval

AI 部分を魔法扱いせず、通常のコンポーネントと同じく境界を定義する。

### 6. Build With Reusable Base
毎回ゼロから作らず、汎用テンプレートを土台にする。
例:
- 認証
- 設定画面
- 通知
- ログ
- ダークモード
- API client
- エラーハンドリング
- 検証基盤

その上に AI で UI や補助コードを高速生成する。

### 7. AI Assisted Implementation
生成AIは以下に使う。
- UI の叩き台生成
- 定型コードの生成
- テストケース案の補助
- リファクタ案の比較
- ドキュメント下書き

ただし、人間または verifier が次を確認する。
- architecture 境界違反
- 無関係な差分
- 例外系の欠落
- state 管理の崩れ
- セキュリティ事故

### 8. Verification
最低限の確認項目:
- lint
- type check
- unit test
- integration test
- 主要フローの手動確認
- AI 出力の品質確認
- 異常系確認

AI 出力を含む場合は deterministic test だけでなく rubric / eval 的な確認も導入する。

### 9. Release
リリース前に次を確認する。
- rollback 手段
- 監視項目
- ログ粒度
- rate limit
- 権限管理
- データ保持方針
- 失敗時の代替フロー

### 10. Operations And MLOps
AI アプリはリリース後の運用が重要。
- モデル性能監視
- 概念ドリフト監視
- prompt / model 更新履歴管理
- 再学習または再評価のトリガー
- ユーザーフィードバック収集
- 事故時の停止条件

## Fast Workflow Recommendation
実務では次の順を推奨する。
1. Goal を固定
2. 非機能要件を固定
3. 薄い prototype を作る
4. reusable base を敷く
5. AI で UI / 定型コードを高速化
6. verifier で局所修正
7. eval を回す
8. 小さく出す
9. 観測して改善する

## Design Heuristics
- 大きく作り直す前に、小さく通す
- 先に interface / schema を決める
- AI に自由記述させる部分ほど guardrail を強くする
- 変更頻度の高い箇所は疎結合にする
- UI と domain logic を密結合にしない
- AI 出力をそのまま正解扱いしない