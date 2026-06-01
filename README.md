# Earnings Debate Agent

米国株の四半期決算レビューで行う「財務数値の確認」「決算資料の読解」「Bull / Bear 両面の論点整理」「最終レポート化」を、LLM multi-agent workflow として自動化するシステムです。

提出リポジトリ: https://github.com/tana-alt/Dev-Foundation-ver2

> This project generates an earnings-analysis artifact. It does not provide stock-price forecasts, target prices, trading recommendations, or investment advice.

---

## 1. 概要

決算直後のレビューでは、EPS surprise や revenue growth だけでなく、FCF、CapEx、guidance、経営陣コメント、反対根拠まで短時間で整理する必要があります。

このリポジトリでは、その作業を次のような固定 workflow に分解します。

```text
ReviewRequest
  ├─ financial_metrics
  ├─ document_sections
  └─ filing_url optional

        ↓

Data Ingestion / Normalization
  - 財務指標を正規化
  - EPS / revenue surprise を計算
  - filing HTML を必要に応じて section 分割

        ↓

Financial Agents
  - EPSQualityAnalyst
  - ProfitabilityAnalyst
  - CashFlowFcfAnalyst
  - BalanceSheetRiskAnalyst

        ↓

Presentation Agents
  - ManagementIntentAnalyst
  - GuidanceAnalyst

        ↓

Evidence Aggregation
  - positive evidence
  - negative evidence
  - risk evidence
  - source traceability check

        ↓

Debate Agents
  - BullAgent
  - BearAgent

        ↓

JudgeAgent
  - good / neutral / bad
  - confidence
  - EPS outlook
  - FCF outlook

        ↓

MarkdownRenderer
  - final earnings review report
```

---

## 2. なぜこのタスクを自動化したのか

自分が企業決算を読むとき、手作業では次の問題が起きやすいです。

- EPS surprise や revenue growth のような目立つ数値だけで判断してしまう
- FCF や CapEx のような将来キャッシュフローに関わる論点を後回しにしやすい
- 決算説明資料、10-Q、経営陣コメント、guidance を読む順番が毎回ぶれる
- 良い材料だけ、または悪い材料だけを拾ってしまい、反対根拠の確認が弱くなる
- 最後に Markdown レポートへ整理するまでに時間がかかる

そのため、数値計算は Python 側で決定的に処理し、LLM には「解釈」「反証」「要約」「論点整理」を担当させる構成にしました。

このシステムの目的は、投資判断を自動化することではありません。目的は、決算情報を構造化し、毎回同じ観点で、根拠と反対根拠を含むレビュー資料を短時間で作ることです。

---

## 3. 自動化する業務

| 手作業の業務 | 自動化後 |
| --- | --- |
| EPS / revenue surprise を確認する | `FinancialMetrics` と preprocessor で正規化・計算 |
| 決算資料の該当箇所を探す | filing / document sections を semantic chunk として扱う |
| EPS、P&L、CFS、BSを別々に読む | Specialist agents が観点別に分析 |
| 経営陣コメントと guidance を読む | Presentation agents が文脈を分析 |
| Bull / Bear 両面を整理する | Debate agents が positive / negative evidence から主張を作成 |
| 最終判断を書く | JudgeAgent が good / neutral / bad と理由を出力 |
| レポートを整形する | MarkdownRenderer が決定的に整形 |

---

## 4. 設計思想

課題指定の参考文献を、次のように実装へ反映しています。

| 参考文献 | 設計への反映 |
| --- | --- |
| [Building Effective Agents](https://lstep.app/F1mQlQB) | 完全自律 agent ではなく、明示的な固定 workflow と specialist agents を組み合わせる |
| [Effective Context Engineering for AI Agents](https://lstep.app/R3cZy8u) | 全文を agent に渡さず、agent ごとに必要な context keys だけを渡す |
| [The Twelve-Factor App](https://lstep.app/SwKfiMq) | API key、model、log level、SEC user-agent を環境変数で管理する |
| [Shape Up](https://lstep.app/e6YVtQS) | MVP の範囲を「決算レビューの構造化とレポート生成」に限定し、株価予測や自動売買は No-Go とする |

### 4.1 Workflow-first

LLM が自由に手順を決める完全自律型ではなく、以下の順序をコードで固定しています。

```text
Data ingestion
→ Financial agents
→ Presentation agents
→ Evidence aggregation
→ Debate
→ Judge
→ Markdown rendering
```

これにより、失敗箇所の特定、テスト、再現性の確保がしやすくなります。

### 4.2 Context Engineering

Agent には必要な context だけを渡します。

例:

- `EPSQualityAnalyst` には EPS metrics と EPS sections を渡す
- `CashFlowFcfAnalyst` には cash flow / capex / risk sections を渡す
- `JudgeAgent` には validated AnalysisBrief、BullCase、BearCase だけを渡す

生の filing 全文や無関係な metrics は、原則として各 agent に渡しません。

### 4.3 Structured Output

LLM の出力は自由文として信用せず、Pydantic model で検証します。

- 未定義 field を拒否
- confidence の範囲を検証
- `good / neutral / bad` の label を enum で制限
- positive evidence / negative evidence を必須化
- source reference を必須化
- investment advice ではないことを contract に含める

### 4.4 Scope Control

この提出でやらないことを明確にしています。

- 株価予測
- 目標株価の算出
- 売買推奨
- 自動売買
- ポートフォリオ最適化
- LLM による財務指標の直接計算

---

## 5. 実装済み機能

- FastAPI endpoint: `POST /reviews`
- CLI:
  - `earnings-debate serve`
  - `earnings-debate run`
- LLM provider abstraction:
  - Anthropic
  - OpenAI
- Financial metrics normalization
- Filing HTML segmentation
- Specialist agents
- Bull / Bear debate agents
- Judge agent
- Markdown report renderer
- Pydantic contracts
- Source reference validation
- pytest による contract / agent / workflow / API tests

---

## 6. セットアップ

### 6.1 Install

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 6.2 Environment variables

```bash
cp .env.example .env
```

`.env` に少なくとも一つの LLM API key を設定します。

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...

# or
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

SEC filing を取得する場合は、SEC user-agent も設定します。

```bash
SEC_USER_AGENT="Your Name your.email@example.com"
```

---

## 7. テスト

API key なしで contract / workflow tests を実行できます。

```bash
pytest
```

テストでは fake LLM を使い、外部 API fetch に依存せず、以下を検証します。

- Pydantic contract が不正値を拒否すること
- LLM 出力が JSON として parse / validate されること
- agent ごとの context routing が守られること
- workflow が決まった順序で実行されること
- `/reviews` endpoint が workflow に委譲すること
- Markdown report が生成されること

---

## 8. 実行方法

### 8.1 API server

```bash
earnings-debate serve --host 127.0.0.1 --port 8000
```

### 8.2 CLIからレビューを実行

別ターミナルで実行します。

```bash
earnings-debate run \
  --api-url http://127.0.0.1:8000 \
  --input-json samples/request.example.json \
  --out outputs
```

ローカルの PDF / text file を読み込む場合は、`document_files` を含む request JSON を指定します。

```bash
LLM_PROVIDER=fake earnings-debate run \
  --api-url local \
  --input-json samples/request.document-files.example.json \
  --out outputs/document-files-example
```

成功すると、以下のファイルが生成されます。

```text
outputs/
  ├─ workflow_result.json
  └─ report.md
```

### 8.3 API request

```bash
curl -X POST http://127.0.0.1:8000/reviews \
  -H "Content-Type: application/json" \
  -d @samples/request.example.json
```

---

## 9. 入力例

`samples/request.example.json` は、外部 financial API や SEC fetch に依存せずに動作確認するための fixture input です。

主な入力は次の通りです。

```json
{
  "request_id": "sample-nvda-2025q3",
  "ticker": "NVDA",
  "fiscal_period": "2025Q3",
  "financial_metrics": {
    "eps": 0.81,
    "eps_consensus": 0.75,
    "eps_surprise_pct": 8.0,
    "revenue": 35000000000,
    "revenue_consensus": 33000000000,
    "revenue_surprise_pct": 6.06,
    "free_cash_flow": 12000000000,
    "capex": 3000000000
  },
  "document_sections": [
    {
      "section_id": "eps",
      "source_ref": {
        "source_id": "filing:eps",
        "source_type": "filing",
        "document_id": "10q-2025q3",
        "section_id": "eps",
        "title": "EPS section"
      },
      "heading": "EPS",
      "text": "Diluted EPS exceeded consensus..."
    }
  ]
}
```

### 9.1 ローカル資料ファイルの指定

`document_sections` を直接指定する代わりに、`document_files` でローカルの PDF / text file を指定できます。指定されたファイルは data ingestion layer で `DocumentSection` に展開され、既存の multi-agent workflow に渡されます。`document_sections` と `document_files` は併用できます。

```json
{
  "ticker": "NVDA",
  "fiscal_period": "2025Q3",
  "document_files": [
    {
      "path": "data/presentations/nvda-q3-2025.pdf",
      "source_type": "earnings_presentation",
      "document_id": "nvda-q3-2025-presentation",
      "title": "NVDA Q3 2025 earnings presentation"
    }
  ]
}
```

- 対応拡張子は `.pdf`, `.txt`, `.text`, `.md` です。
- PDF はページ単位で text extraction し、長いページは chunk に分割します。
- text file は UTF-8 として読み込み、長い本文は chunk に分割します。
- `source_ref` は `source_id`, `source_type`, `document_id`, `section_id`, `page`, `title` を workflow 内で安定生成します。
- PDF を repository に含めない場合は、`data/presentations/` などの local path を request JSON に書き、PDF 本体は `.gitignore` 管理または手元配置にしてください。
- 不正 path、存在しない file、未対応拡張子、抽出 text が空の PDF / text file は validation error として扱います。

---

## 10. 出力例

出力は Markdown report です。Report renderer contract は、検証済みの `ReportMatrix`
から次の固定順で section を出力します。これは投資助言ではなく、決算レビュー用の
構造化 artifact です。

```markdown
# Earnings Review: NVDA 2025Q3

## Judge Rationale

- Verdict: neutral
- Confidence: 0.66
- Summary: The quarter is constructive, with cash-flow caveats.
- Rationale: The Judge treats checked EPS evidence as supportive, but limits durability because FCF evidence is incomplete.
- EPS outlook: EPS outlook is constructive if margin support persists.
- EPS rationale: The EPS beat is supported by a checked financial source.
- FCF outlook: FCF outlook remains uncertain until the CapEx bridge is clearer.
- FCF rationale: CapEx pressure and missing bridge data limit confidence.

## Bull vs Bear Tension

### Bull Case

EPS quality improved on a verified beat.

### Bear Case

CapEx pressure can delay FCF conversion.

### Risk Case

Missing guidance limits forward confidence.

### Judge Tension

Bull evidence is stronger for the current quarter, while bear evidence limits durability.

## Evidence Matrix

| Claim ID | Fact | Interpretation | Implication | Time scope | Fact-check status | Judge treatment | Sources |
|---|---|---|---|---|---|---|---|
| claim:eps-quality | Adjusted EPS of $1.23 exceeded consensus by 8%. | The fact supports current-quarter EPS quality. | The report should avoid converting the fact into a durable forecast. | Current quarter 2025Q3 | supported | supporting | api:eps:2025Q3 / eps |

## Agent Contribution

| Agent | Stance | Contribution | Key evidence | Counter evidence | Confidence | Missing data |
|---|---|---|---|---|---:|---|
| EarningsQualityAnalyst | mixed | Uses validated evidence only. | ev:eps-beat | ev:capex-pressure | 0.74 | - |

## Uncertainty And Missing Data

| Topic | Materiality | Blocks verdict | Reason |
|---|---|---:|---|
| FCF bridge | medium | false | The source set does not explain conversion from operating cash flow to FCF. |

## Quality Gates

- ReportMatrix validation: passed
- Evidence items: 2
- Source references: registered and internally consistent
- No-advice framing: present in Disclaimer

## Source Appendix

| Source ID | Type | Locator | Title | Reported period | URL |
|---|---|---|---|---|---|
| `api:eps:2025Q3` | financial_api | eps | Financial API EPS | 2025Q3 | no URL |

## Disclaimer

This report is an earnings analysis artifact and is not investment advice.
```

---

## 11. Project structure

```text
.
├─ src/
│  ├─ api.py                # FastAPI entry point
│  ├─ main.py               # CLI wrapper
│  ├─ workflow.py           # Explicit workflow orchestration
│  ├─ report_renderer.py    # Deterministic report renderer contract
│  ├─ workflow_agents.py    # LLM agent wrappers
│  ├─ workflow_models.py    # Pydantic contracts
│  ├─ preprocessor.py       # Metrics normalization and filing segmentation
│  ├─ structured.py         # JSON parsing and model validation
│  └─ llm.py                # Provider abstraction
├─ tests/
│  ├─ test_workflow_api.py
│  ├─ test_workflow_agents.py
│  ├─ test_workflow_models.py
│  ├─ test_report_renderer.py
│  └─ test_preprocessor.py
├─ samples/
│  ├─ request.example.json
│  └─ request.document-files.example.json
├─ outputs/
│  └─ example/
│     └─ report.md
├─ .env.example
├─ pyproject.toml
└─ README.md
```

---

## 12. Limitations

現在の MVP では、評価しやすさと再現性を優先しています。

- `financial_metrics` と `document_sections` または `document_files` を明示的に渡す fixture 実行を推奨
- `filing_url` からの HTML fetch / segmentation は実装済みだが、実運用では filing 形式差分への追加対応が必要
- PDF extraction は text layer を持つ PDF が対象。scan image PDF の OCR は対象外
- `presentation_url` と `transcript_url` は入力 contract として保持しているが、自動取得処理は将来拡張
- `yfinance` による consensus fetch は schema 変更の影響を受けるため、MVPでは defensive に欠損を許容
- 投資助言、株価予測、売買推奨は意図的に対象外

---

## 13. Future work

- SEC filing parser の精度向上
- earnings presentation / transcript の自動取得
- source citation の line / page 単位での強化
- sample company を複数追加
- review history の比較機能
- CI 上での coverage report 追加

---

## 14. Submission checklist

- [ ] `README.md` がプロジェクト説明として読める
- [ ] 背景・動機が明記されている
- [ ] 参考文献と設計思想の対応が明記されている
- [ ] 実装済み機能と未実装機能が分かれている
- [ ] `samples/request.example.json` がある
- [ ] `outputs/example/report.md` がある
- [ ] `pytest` が通る
- [ ] GitHub Actions が通る
- [ ] 投資助言ではないことが明記されている

## Report Quality Controls

This project does not simply ask an LLM to write an earnings report. The report
quality layer enforces deterministic controls around the existing workflow:

1. Guidance acquisition gate
2. Claim-to-source Evidence Matrix
3. Numeric grounding check for material claims
4. Source timing classification
5. Missing-data confidence caps
6. Source inventory table
7. Interactive external-source appendix separated from the main report

Material claims do not need every possible KPI. They need the value, quote, or
missing-data caveat that supports that specific claim. External sources remain
outside `report.md` unless a human explicitly accepts and routes them.

### Applying the report-quality setup

Run each setup program separately from the repository root:

```bash
python setup/01_setup_report_quality_contracts.py
python setup/02_setup_source_timing.py
python setup/03_setup_guidance_gate.py
python setup/04_setup_evidence_matrix_renderer.py
python setup/05_setup_source_inventory.py
python setup/06_setup_missing_data_confidence.py
python setup/07_setup_numeric_grounding.py
python setup/08_setup_external_source_separation.py
python setup/09_setup_prompt_policies.py
python setup/10_setup_report_quality_tests.py
pytest tests/test_report_quality_full.py
```

For legacy tests only, these escape hatches are available:

```bash
EARNINGS_DEBATE_REQUIRE_GUIDANCE=0
EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING=0
```

Do not disable those gates for the internship/demo report run.

---

## 15. Development foundation

このリポジトリは提出物の実装に加えて、agent / human / CI が同じ前提で作業するための開発基盤を含みます。

- Agent entrypoint: `AGENTS.md`
- Active contracts and references: `docs/`
- Local environment restore: `scripts/setup-agent-environment.sh`
- Environment inspection: `make doctor`
- Full local gate: `make check-foundation`

クローン後に agent 環境を復元する場合は次を実行します。

```bash
sh scripts/setup-agent-environment.sh
```
