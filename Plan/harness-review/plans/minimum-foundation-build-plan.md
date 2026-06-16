# 最低限の土台 — 実装計画(self-attestation の終焉)

作成日: 2026-06-10
前提文書: `Plan/harness-review/harness-implementation-report.md`(診断)
このファイルの役割: 診断を「今すぐ着手できる実装ステップ」に落とす。

---

## 0. 設計判断 — 「evidence を作らせる」のではなく「ゲートが再実行する」

レポート P1 は「hook が JSON evidence を書き、agent は参照のみ」とする。
しかし agent が JSON を手で偽造する逃げが理論上残る。最小で最も堅牢な形は:

> **完了ゲートが自分で `make check-required` を再実行し、現在の diff hash に束縛して判定する。
> agent は verdict を一切生成しない。**

これで evidence の偽造は無意味になる(ゲートが入力を信用せず再計算するため)。
JSON evidence は「キャッシュ兼監査ログ」に降格し、信頼の根拠ではなくなる。
これが CI / SWE-agent 系の本物のゲートと同じモデル。

判定の所在が agent の外に出た瞬間に、現行の envelope/scorecard/audit 系
チェッカー(= 自己申告 YAML の文法検証)は役割を失う。撤去はこの土台とセット。

---

## 1. 構成要素(依存順)

### S1. 完了ゲート(門番)— 最優先・単独で self-attestation を殺す
- `.claude/settings.json`(または Codex の equivalent)に **Stop hook** を追加。
- `scripts/completion_gate.py`:
  1. task packet の Done criteria から要求 tier を読む(default: `check-required`)。
  2. `git diff` のハッシュ(`H_now`)を計算。
  3. 要求 tier を `subprocess` で実行。
  4. exit≠0 → **停止をブロック**し、失敗出力をそのまま feedback として返す。
  5. exit=0 → `artifact/<project>/evidence/<tier>-<H_now>.json` に
     `{command, exit_code, diff_hash, timestamp}` を記録して通す。
- **効果:** 「make check を呼ばずに完了と言う」逃げと「pass と書く」逃げが同時に消える。
  git hook(commit/push 時のみ発火)の死角 = 「完了宣言の瞬間」をここで塞ぐ。

### S2. 逃げパターンの機械スキャン(コード品質監査の最小核)
- `scripts/scan_escapes.py`:`git diff` の追加行のみを対象に
  `type: ignore` / `# noqa` / `pytest.skip` / `NotImplementedError` /
  空関数体 / `pass` だけの body / `TODO`スタブ を検出。
- S1 のゲートに合流(差分内で新規導入された逃げがあれば block)。
- 既存行は対象外(diff スコープ限定)。コスト小・効果大。

### S3. レビューの機械必須化(fresh context)
- `scripts/run_review.py`:変更ファイルを `git diff --name-only` で機械列挙 →
  one-hop(直接の caller/callee・共有 contract)を加えて reviewer subagent を
  **実装者の会話履歴を共有しない fresh context** で起動。
- 返り値は型付き verdict `{status, findings:[{id, severity}]}` →
  `artifact/<project>/reviews/review-<H_now>.json`。
- **blocking は Done criteria 違反 / invariant 違反のみ**(レポート P3 の効力分離)。
  それ以外は follow-up log。これを先に固定しないと reviewer が無限ゲート化する。
- S1 のゲートは「現在の diff hash に束縛された fresh review verdict の存在」を要求。
  レビュー後に編集 → hash 不一致 → 再レビュー強制(P1 の hash 束縛がここでも効く)。

### S4. テスト所有権の凍結
- task packet に `frozen_paths`(受入テスト等)を宣言。
- `hooks/pre-commit` に1本追加:実装フェーズの commit がそれらに触れたら block。
- 受入条件は spec 段階(`templates/detailed-spec.md`)で **実行可能な pytest** として確定。
  散文の受入条件は解釈で逃げられるため不可。

### S5. governance / heavy-contract の撤去
- S1〜S4 が動けば、以下は代替物(自己申告)として不要になる:
  - 6 governance skills + `check-skill-routes` の skill 選択オーバーヘッド
  - legacy checker 4種(`check-residual-risk-carryover` / `check-review-convergence`
    / `check-audit-provenance` / `check-operational-scorecard`)と対応 heavy template 群
- `archive/` へ退避。`AGENTS.md` の Skill Routes 節を
  「ハーネスがゲートを機械強制する。skill 選択は不要」に置換。
- **表面積が減りながら強度が上がる**のがこの撤去の狙い。

---

## 2. 実装順序

| 順 | 要素 | 単独で効くか | コスト |
|---|---|---|---|
| 1 | S1 完了ゲート(再実行 + hash 束縛) | ◎ self-attestation を即死 | 中 |
| 2 | S2 逃げスキャン | ◎ | 小 |
| 3 | S4 テスト凍結 | ◎ | 小 |
| 4 | S3 レビュー必須化 | subagent 基盤要 | 中 |
| 5 | S5 governance 撤去 | S1-S4 後 | 小 |

**最小の一歩 = S1 のみ。** ゲートが自分で再実行し diff hash に束縛する一点が動けば、
このハーネスは「作文の検証」から「事実の検証」へ質的に変わる。残りはその上に小さく足す。

---

## 3. この土台で到達する地点と、まだ届かない核

到達:**完了の宣言権が agent から hook へ移る。** レポートの完成形(6章)の骨格。

未到達(本格ハーネスの核として別途必要 — 詳細は別紙):
1. ハーネスが**ループを所有する**(document ではなく runtime になる)。S1 はその最初の 5%。
2. **eval** — ハーネス自身の hack 率を測る仕組み。これが無いと S1〜S5 の効果が反証不能。
3. **trajectory 捕捉** — 全 tool-call→observation の構造化ログ。2 と debug の前提。
4. **権限/副作用の機械強制**(sandbox/allowlist)。human-gate は今なお散文強制。
5. **context window 機構**(compaction/budget を runtime 化)。今は自己申告 YAML。
