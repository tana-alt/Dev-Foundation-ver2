# Workflow Implementation Architecture

## Purpose

この文書は、7-agent workflow を実装する際のディレクトリ構造と、各 agent へのデータ注入方法を共有するための設計メモである。

`workflow-agent-handoff.md` と `specialist-agent-workflow-design.md` を source of truth とし、ここでは実装時に迷いやすい境界を具体化する。

## Target Directory Structure

```text
earnings-debate-agent/
  src/
    api.py
      - FastAPI entrypoint
      - POST /reviews
      - handler は ReviewWorkflow.run() を呼ぶだけ

    main.py
      - CLI thin client
      - API server 起動
      - POST /reviews を叩く実験用 client

    llm.py
      - OpenAI / Anthropic provider abstraction
      - agent はこの interface だけを使う

    preprocessor.py
      - financial API fetch
      - filing / presentation / transcript fetch
      - document sectioning
      - EPS surprise, revenue surprise, margins, CFO, FCF, CapEx, liquidity values の Python 計算

    workflow.py
      - ReviewWorkflow
      - fixed execution order
      - context routing
      - evidence aggregation
      - validation gates
      - MarkdownRenderer

    workflow_models.py
      - API contracts
      - RunSpec / ReviewRequest / ReviewResponse
      - FinancialSnapshot / DocumentSection / SourceRef / EvidenceItem
      - specialist findings
      - BullCase / BearCase / FinalVerdict

    workflow_agents.py
      - 7 runtime LLM agent wrappers
      - EarningsQualityAnalyst
      - CashFlowRiskAnalyst
      - ManagementIntentAnalyst
      - GuidanceAnalyst
      - BullAgent
      - BearAgent
      - JudgeAgent

    structured.py
      - JSON extraction
      - Pydantic parse helpers

    prompts/
      README.md
      financial_agents.md
      presentation_agents.md
      debate_judge_agents.md

  tests/
    test_preprocessor.py
    test_workflow_models.py
    test_workflow_agents.py
    test_workflow_api.py

  Plan/
    active/
      specialist-agent-workflow-design.md
      workflow-agent-handoff.md
      workflow-implementation-architecture.md

  archive/
    old_prototype/
      - 旧 CLI-first prototype
```

## Skill Directory Structure

この設計は skill としても配置できるようにする。

想定構造:

```text
.codex/skills/earnings-review-workflow/
  SKILL.md
  references/
    workflow-agent-handoff.md
    specialist-agent-workflow-design.md
    workflow-implementation-architecture.md
```

`SKILL.md` は短く保つ。

含める内容:

- この repo の workflow / agent / API / prompt / Pydantic 契約を変更する時に使うこと
- 7-agent 構成を守ること
- Data ingestion / calculation / Markdown rendering は Python に残すこと
- LLM agent には必要最小限の context だけを注入すること
- 詳細は `references/` の3文書を読むこと

## Hook Trigger Assumption

hook は以下のファイル変更時に、この skill を参照するよう促す。

```text
src/workflow.py
src/workflow_agents.py
src/workflow_models.py
src/preprocessor.py
src/prompts/*.md
Plan/active/*workflow*.md
Plan/active/*agent*.md
```

hook の目的は実装を止めることではなく、Plan と実装のズレを早期に気づかせること。

## Runtime Workflow

```text
POST /reviews
  ↓
ReviewRequest validation
  ↓
Data Ingestion / Normalization [Python]
  ↓
Financial Agents [parallel]
  - EarningsQualityAnalyst
  - CashFlowRiskAnalyst
  ↓
Presentation Agents [parallel]
  - ManagementIntentAnalyst
  - GuidanceAnalyst
  ↓
Evidence Aggregation [Python]
  ↓
Debate Agents [sequential]
  - BullAgent
  - BearAgent(with BullCaseSummary)
  ↓
JudgeAgent
  ↓
MarkdownRenderer [Python]
  ↓
ReviewResponse
```

## Core Data Objects

### RunSpec

Request identity and scope.

Fields:

```text
ticker
fiscal_quarter
filing_url
presentation_url
transcript_url
request_id
purpose = earnings_review_not_investment_advice
```

Injected into every agent.

### FinancialSnapshot

Python workflow が取得・計算済みの財務データ。

Fields:

```text
revenue_actual
revenue_consensus
revenue_surprise_pct
eps_actual
eps_consensus
eps_surprise_pct
gross_margin
operating_margin
operating_cash_flow
free_cash_flow
fcf_margin
capex
working_capital_change
cash
debt
liquidity_values
guidance_summary
source_refs
```

LLM agent はこれを読んで解釈するだけで、再計算しない。

### DocumentSection

Document ingestion / sectioning の出力。

Fields:

```text
section_id
section_type
source_type
source_ref
heading
text
page
```

`section_type` は context routing の主キーにする。

### SourceIndex

すべての `SourceRef` の集合。

用途:

- Evidence が存在する source を参照しているか検証する
- Judge が新しい根拠を作っていないか検証する
- Markdown report に source を追跡可能な形で残す

### EvidenceItem

全 agent 共通の根拠単位。

Fields:

```text
evidence_id
claim
source_ref
source_type
metric
period
quote_or_value
interpretation
polarity
confidence
```

Validation:

- `source_ref` 必須
- `source_ref` は `SourceIndex` に存在すること
- `polarity` は supporting / counter / mixed / neutral のいずれか
- 投資助言語彙を含めない

## Data Injection By Agent

### EarningsQualityAnalyst

Purpose:

EPS surprise、売上品質、利益率、営業レバレッジ、segment mix、一時要因を統合して評価する。

Injected context:

```text
RunSpec
FinancialSnapshot:
  - eps_actual
  - eps_consensus
  - eps_surprise_pct
  - revenue_actual
  - revenue_consensus
  - revenue_surprise_pct
  - gross_margin
  - operating_margin
  - operating_expense
  - tax_rate
  - share_count

DocumentSection where section_type in:
  - eps
  - revenue
  - margin
  - segment
  - operating_expense
  - tax
  - share_count
  - one_time_item

SourceIndex subset:
  - injected financial source refs
  - injected document source refs
```

Not injected:

- cash flow details
- liquidity / debt details
- Bull/Bear/Judge outputs
- raw full filing
- stock price / valuation

Output:

```text
EarningsQualityFinding
```

### CashFlowRiskAnalyst

Purpose:

CFO、FCF、CapEx、working capital、liquidity、debt、maturity を統合して、FCF outlook と financial risk を評価する。

Injected context:

```text
RunSpec
FinancialSnapshot:
  - operating_cash_flow
  - free_cash_flow
  - fcf_margin
  - capex
  - working_capital_change
  - cash
  - debt
  - liquidity_values

DocumentSection where section_type in:
  - cash_flow
  - capex
  - working_capital
  - liquidity
  - debt
  - maturity
  - capital_resources
  - risk

SourceIndex subset:
  - injected financial source refs
  - injected document source refs
```

Not injected:

- detailed EPS quality sections unless tied to cash conversion
- management narrative unrelated to cash/risk
- Bull/Bear/Judge outputs
- stock price / valuation

Output:

```text
CashFlowRiskFinding
```

### ManagementIntentAnalyst

Purpose:

経営陣の意図、投資判断、成長ドライバー、EPS/FCFへの時間軸別影響を評価する。

Injected context:

```text
RunSpec
FinancialSnapshot minimal:
  - revenue_surprise_pct
  - eps_surprise_pct
  - operating_margin
  - free_cash_flow
  - capex
  - guidance_summary

DocumentSection where section_type in:
  - management_commentary
  - strategy
  - mdna
  - risk when tied to management actions

SourceIndex subset:
  - injected document source refs
```

Not injected:

- full raw financial table
- detailed guidance vs consensus calculations
- Bull/Bear/Judge outputs
- stock price / valuation

Output:

```text
ManagementIntentFinding
```

### GuidanceAnalyst

Purpose:

guidance と consensus の差分、前提、達成可能性、revision risk を評価する。

Injected context:

```text
RunSpec
FinancialSnapshot:
  - guidance_summary
  - revenue_consensus
  - eps_consensus
  - precomputed guidance_vs_consensus deltas where available

DocumentSection where section_type in:
  - guidance
  - outlook
  - guidance_assumptions
  - risk when tied to guidance assumptions

Optional handoff:
  - compact ManagementIntentFinding.handoff_summary

SourceIndex subset:
  - injected document source refs
```

Not injected:

- Bull/Bear/Judge outputs
- full management narrative unrelated to guidance
- external analyst commentary not in provided data
- stock price / valuation

Output:

```text
GuidanceFinding
```

### BullAgent

Purpose:

validated `AnalysisBrief` だけを使って、good と評価できる最強ケースを作る。

Injected context:

```text
RunSpec
AnalysisBrief:
  - EarningsQualityFinding summary
  - CashFlowRiskFinding summary
  - ManagementIntentFinding summary
  - GuidanceFinding summary
  - positive_evidence_pool
  - negative_evidence_pool
  - disputed_points
  - missing_data
```

Not injected:

- raw documents
- unvalidated specialist output
- Bear/Judge outputs
- stock price / valuation

Output:

```text
BullCase
BullCaseSummary [Python-generated compact summary]
```

Required:

- `strongest_positive_evidence` non-empty
- `weak_points` non-empty
- `finding_coverage` includes all four specialist keys

### BearAgent

Purpose:

validated `AnalysisBrief` と `BullCaseSummary` を使って、bad / neutral と評価すべき最強ケースを作る。

Injected context:

```text
RunSpec
AnalysisBrief
BullCaseSummary:
  - thesis
  - strongest_positive_evidence ids
  - weak_points
  - conditions_needed
```

Not injected:

- raw documents
- unvalidated specialist output
- Judge output
- stock price / valuation

Output:

```text
BearCase
```

Required:

- `strongest_negative_evidence` non-empty
- `counter_to_bull_case` non-empty
- `finding_coverage` includes all four specialist keys

### JudgeAgent

Purpose:

validated inputs onlyから、good / neutral / bad を判定する。

Injected context:

```text
RunSpec
AnalysisBrief
BullCase
BearCase
FinancialSnapshot compact summary
```

Not injected:

- raw documents
- report draft
- unvalidated LLM output
- stock price / valuation

Output:

```text
FinalVerdict
```

Required:

- label: good | neutral | bad
- confidence: 0.0 <= confidence <= 1.0
- positive_evidence non-empty
- negative_evidence non-empty
- eps_outlook
- fcf_outlook
- non_advice_disclaimer

Judge should prefer `neutral` when:

- Bull and Bear evidence are close
- EPS outlook and FCF outlook point in opposite directions
- important missing data materially weakens confidence

## Validation Gates

### Before Specialist Agents

- `ReviewRequest` validates.
- `FinancialSnapshot` is normalized.
- Derived metrics are calculated by Python.
- Document sections have `section_type` and `source_ref`.

### Before Evidence Aggregation

- all specialist outputs parse into Pydantic models.
- `source_ref` exists in `SourceIndex`.
- `counter_evidence` is non-empty, or missing limitation is recorded and confidence is capped.
- banned investment-advice phrases are absent.

### Before Debate

- `AnalysisBrief` includes all four specialist findings.
- positive and negative evidence pools are both non-empty.
- disputed points and missing data are compact.

### Before Judge

- `BullCase.strongest_positive_evidence` non-empty.
- `BearCase.strongest_negative_evidence` non-empty.
- `BullCase.finding_coverage` covers all four specialist keys.
- `BearCase.finding_coverage` covers all four specialist keys.
- `BearCase.counter_to_bull_case` non-empty.

### Before MarkdownRenderer

- `FinalVerdict` validates.
- Judge evidence IDs exist in `AnalysisBrief`.
- report contains no investment advice.
- Markdown is generated deterministically from structured data.
