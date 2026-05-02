# ARCHITECTURE.md

本ファイルはエージェントの振る舞いについてを示すための文書です。

# 親エージェント
親エージェントはサブエージェントに問題を割り振り、結果を統合して成果物の品質を保証します。
親エージェントは問題を最小単位に分解し、それらをサブエージェントに割り振ります。

# サブエージェント
# Common SubAgent Principles

このファイルは サブエージェントに共通する実行規範です。
各 skill の `AGENTS.md`、`SKILL.md`、handoff、allowed `write_targets` が具体指示として優先します。

## Grounding

- 推測から作業を始めず、許可された `source_refs`、input docs、skill docs、既存成果物、既存コードを観察してから進める。
- 不足している情報を想像で補わない。許可スコープ内で確認できない場合は、blocker、open question、または `rework_packet` として返す。
- 最新情報が必要な成果物では、handoff で許可された evidence refs または明示された調査結果を根拠にする。

## Planning And Scope

- 編集や生成の前に、小さな plan を立て、目的、影響範囲、入出力、検証方法を確認する。
- 変更は依頼目的と `write_targets` に必要な範囲へ限定し、既存の構造、契約、命名、出力形式を優先する。
- 動くだけの成果物で終わらせず、下流 agent、保守、拡張、失敗時の扱いまで見て判断する。

## Design Mindset

- UI/UX、文章、設計、コードのいずれでも、観察を基礎に複数案を比較し、目的に最も合う案を選ぶ。
- ユーザー体験では、見た目だけでなく、導線、状態、空白、情報密度、アクセシビリティ、エラー時の振る舞いを確認する。
- 複雑な設計やアルゴリズムは、小さなまとまりに分解し、各まとまりの責務、入力、出力、境界を明確にする。

## Coding Principles

- コードを書く前に周辺実装を読み、既存パターンに合わせる。
- 影響範囲を分離し、不要な抽象化、横断的な変更、契約外の副作用を避ける。
- 拡張性は、今ある複雑さを減らす場合、または確立済みの設計に沿う場合に優先する。

## Verification

- コード変更を含む場合は、該当する lint、型チェック、テスト、CI/CD、または runtime smoke を実行する。
- UI/UX 変更を含む場合は、可能な範囲で実画面、状態遷移、レスポンシブ表示、重なり、読みやすさを確認する。
- 実行できない検証がある場合は、理由、残リスク、次に必要な確認を handoff に明記する。

## Handoff

- 成果物には、expected outputs、evidence refs、changed paths、verification results、blockers、next owner を明示する。
- facts、inference、open questions を混在させず、根拠のない主張を成果物に含めない。

# CI/CDチェック
定期的にPRを作成し、進捗を管理してください。