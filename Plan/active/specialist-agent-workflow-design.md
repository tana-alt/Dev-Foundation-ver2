# Specialist Agent Workflow Design

## Purpose

AGENTS.md のフローを、インターン課題として説明しやすい専門エージェント設計へ落とし込む。

前回の4 agent案は実装コストを下げるには有効だが、context engineering / context isolation の観点では粗い。特にこの課題の中心は EPS と FCF の将来性を別々に読み、肯定根拠と反対根拠を構造化することなので、必要 context が異なる専門領域は独立エージェントにする。

## Design Principles

- 独立させる基準は agent 名ではなく、必要な context と判断軸が違うかどうか。
- EPS と FCF は良し悪しが逆方向に出ることがあるため、独立させる。
- Management intent と guidance は近いが、経営方針の解釈と来期数値目標の現実性評価は別なので独立させる。
- Bull と Bear は同じ `AnalysisBrief` を見ても目的が逆なので、反対根拠を強くするため独立させる。
- Data ingestion、財務計算、document sectioning、Markdown rendering は LLM agent にしない。
- すべての agent 出力は Pydantic で検証する。
- Judge に全文資料や全文討論ログを渡さず、圧縮済みの構造化出力だけを渡す。
- `good | neutral | bad` を正式な判定ラベルにする。
- 反対根拠が空のまま report 生成へ進めない。
- 投資助言、株価予測、売買推奨に踏み込まない。

## Recommended Phase 1 Workflow

```text
RunSpec
  - ticker
  - fiscal quarter
  - source URLs / local documents

        ↓

Non-LLM Data Workflow
  - financial API data fetch
  - filing / presentation / transcript fetch
  - PDF / HTML / text sectioning
  - EPS surprise, revenue surprise, margins, FCF, CapEx changes
  - output: FinancialSnapshot + DocumentSections

        ↓

Financial Specialist Agents
  - EPSQualityAnalyst
  - CashFlowFcfAnalyst

        ↓

Presentation Specialist Agents
  - ManagementIntentAnalyst
  - GuidanceAnalyst

        ↓

Evidence Aggregation
  - deterministic Python aggregation
  - output: AnalysisBrief

        ↓

Debate Agents
  - BullAgent
  - BearAgent

        ↓

Judge Agent
  - good / neutral / bad
  - confidence
  - positive evidence
  - negative evidence
  - EPS outlook
  - FCF outlook

        ↓

Markdown Renderer
  - deterministic Python template
```

Phase 1 では LLM agent を7つにする。

1. `EPSQualityAnalyst`
2. `CashFlowFcfAnalyst`
3. `ManagementIntentAnalyst`
4. `GuidanceAnalyst`
5. `BullAgent`
6. `BearAgent`
7. `JudgeAgent`

これは最小ではないが、AGENTS.md の専門エージェント構造と context isolation を課題として見せるには最もバランスがよい。

## Why Not One Financial Analyst?

`FinancialAnalyst` へ統合すると実装は楽になる。しかし、次の理由でこの課題では分けるべき。

| 統合 | 問題 |
| --- | --- |
| EPS + FCF | EPS は会計利益、FCF は現金創出力。EPS beat でも FCF 悪化は普通にあり得る |
| EPS + P&L + CFS + BS | context が広がり、agent が headline beat に引っ張られやすい |
| Management + Guidance | 経営方針と来期数値目標の現実性は別の判断 |
| Bull + Bear | 片方の立場に引っ張られ、反対根拠が薄くなりやすい |
| Judge + Report | 構造化判断と文章整形が混ざり、Pydantic 契約が崩れやすい |

統合してよいのは、必要 context が同じで、出力の責務が重ならない場合に限る。

## Agent Decisions

| AGENTS.md の要素 | 判断 | Phase 1での扱い |
| --- | --- | --- |
| Data Ingestion Layer | 残すが非LLM | Python処理。外部取得、sectioning、計算を担当 |
| EPS Analyst | 独立 | `EPSQualityAnalyst` |
| P&L Analyst | 後回し | Phase 1では EPS quality の補助 context。Phase 2で `ProfitabilityAnalyst` |
| CFS Analyst | 独立 | `CashFlowFcfAnalyst` |
| BS Analyst | 後回し | Phase 1では重大な負債・流動性リスクだけ扱う。Phase 2で独立 |
| Management eval Agent | 独立 | `ManagementIntentAnalyst` |
| Guidance Agent | 独立 | `GuidanceAnalyst` |
| Bull Agent | 独立 | `BullAgent` |
| Bear Agent | 独立 | `BearAgent` |
| Risk Agent | 後回し | Phase 1では各出力の `risk_factors` / `counter_evidence` に吸収 |
| Eval Agent | 削る | `JudgeAgent` と責務が重複 |
| Judge / Report Agent | 分離 | 判断は `JudgeAgent`、Markdown 整形は Python |
| Macro Agent | 削る | AGENTS.md の主目的から外れるため後回し |

## Pydantic Contracts

### Core Data Models

```python
RunSpec:
  ticker: str
  fiscal_quarter: str
  filing_url: str | None
  presentation_url: str | None
  transcript_url: str | None

FinancialSnapshot:
  ticker: str
  fiscal_quarter: str
  revenue_actual: float | None
  revenue_consensus: float | None
  revenue_surprise_pct: float | None
  eps_actual: float | None
  eps_consensus: float | None
  eps_surprise_pct: float | None
  eps_yoy_pct: float | None
  gross_margin: float | None
  operating_margin: float | None
  operating_margin_yoy_delta: float | None
  operating_cash_flow: float | None
  free_cash_flow: float | None
  fcf_margin: float | None
  capex: float | None
  working_capital_change: float | None
  cash: float | None
  debt: float | None
  guidance_summary: str | None

DocumentSection:
  source_type: financial_api | filing | presentation | transcript
  section_type: revenue | eps | margin | cash_flow | capex | balance_sheet | guidance | management_commentary | risk | other
  source_ref: str
  text: str
```

### Shared Evidence Model

```python
EvidenceItem:
  claim: str
  source_type: financial_api | filing | presentation | transcript
  source_ref: str
  metric: str | None
  value: float | str | None
  period: str | None
  interpretation: str
```

### Specialist Outputs

```python
EPSQualityFinding:
  agent_name: Literal["eps_quality"]
  eps_surprise_assessment: str
  quality_of_beat: positive | negative | mixed | neutral | unclear
  one_time_factors: list[EvidenceItem]
  sustainable_factors: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  eps_outlook: positive | negative | neutral | unclear
  confidence: float
  missing_data: list[str]

CashFlowFcfFinding:
  agent_name: Literal["cash_flow_fcf"]
  fcf_trend: positive | negative | mixed | neutral | unclear
  capex_pressure: str
  working_capital_effect: str
  cash_conversion_assessment: str
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  fcf_outlook: positive | negative | neutral | unclear
  confidence: float
  missing_data: list[str]

ManagementIntentFinding:
  agent_name: Literal["management_intent"]
  management_priorities: list[str]
  growth_drivers: list[EvidenceItem]
  investment_or_cost_actions: list[EvidenceItem]
  eps_implication: positive | negative | neutral | unclear
  fcf_implication: positive | negative | neutral | unclear
  time_horizon: short_term | medium_term | long_term | unclear
  counter_evidence: list[EvidenceItem]
  confidence: float
  missing_data: list[str]

GuidanceFinding:
  agent_name: Literal["guidance"]
  guidance_vs_consensus: positive | negative | mixed | neutral | unclear
  conservatism_level: conservative | balanced | aggressive | unclear
  assumption_quality: str
  revision_risk: str
  key_evidence: list[EvidenceItem]
  counter_evidence: list[EvidenceItem]
  eps_implication: positive | negative | neutral | unclear
  fcf_implication: positive | negative | neutral | unclear
  confidence: float
  missing_data: list[str]
```

### Debate and Judge Outputs

```python
AnalysisBrief:
  ticker: str
  fiscal_quarter: str
  eps_finding: EPSQualityFinding
  fcf_finding: CashFlowFcfFinding
  management_finding: ManagementIntentFinding
  guidance_finding: GuidanceFinding
  positive_evidence_pool: list[EvidenceItem]
  negative_evidence_pool: list[EvidenceItem]
  disputed_points: list[str]
  missing_data: list[str]

BullCase:
  thesis: str
  strongest_positive_evidence: list[EvidenceItem]
  eps_bull_argument: str
  fcf_bull_argument: str
  conditions_needed: list[str]
  weak_points: list[str]
  confidence: float

BearCase:
  thesis: str
  strongest_negative_evidence: list[EvidenceItem]
  eps_bear_argument: str
  fcf_bear_argument: str
  failure_modes: list[str]
  counter_to_bull_case: list[str]
  confidence: float

FinalVerdict:
  label: good | neutral | bad
  confidence: float
  summary: str
  positive_evidence: list[EvidenceItem]
  negative_evidence: list[EvidenceItem]
  eps_outlook: positive | negative | neutral | unclear
  eps_outlook_reason: str
  fcf_outlook: positive | negative | neutral | unclear
  fcf_outlook_reason: str
  non_advice_disclaimer: str
```

## Agent Responsibilities

### EPSQualityAnalyst

EPS surprise の大きさではなく、EPS beat / miss の質と持続性を見る。

Inputs:

- EPS actual / consensus / surprise
- EPS YoY
- margin and tax related values
- EPS / margin / one-off related sections

Outputs:

- EPS surprise assessment
- one-time factors
- sustainable factors
- EPS outlook
- counter evidence

### CashFlowFcfAnalyst

FCF が将来増加する方向にあるかを見る。EPS とは独立に判断する。

Inputs:

- operating cash flow
- free cash flow
- CapEx
- working capital changes
- cash flow / CapEx / balance sheet sections

Outputs:

- FCF trend
- CapEx pressure
- working capital effect
- cash conversion assessment
- FCF outlook
- counter evidence

### ManagementIntentAnalyst

経営陣が何を成長ドライバー、投資領域、コスト改善策として説明しているかを読む。

Inputs:

- presentation sections
- transcript / management commentary
- risk sections where relevant

Outputs:

- management priorities
- growth drivers
- investment or cost actions
- EPS / FCF implication by time horizon
- counter evidence

### GuidanceAnalyst

来期ガイダンスと市場期待の match / mismatch、前提の保守性や楽観性を見る。

Inputs:

- guidance summary
- consensus expectations
- guidance / outlook sections
- management commentary about assumptions

Outputs:

- guidance versus consensus
- conservatism level
- assumption quality
- revision risk
- EPS / FCF implication
- counter evidence

### BullAgent

Validated findings だけを使い、良い決算と判断できる最強ケースを作る。

Inputs:

- `AnalysisBrief`

Outputs:

- bull thesis
- strongest positive evidence
- EPS bull argument
- FCF bull argument
- conditions needed
- weak points

### BearAgent

Validated findings だけを使い、悪い決算または過大評価と判断できる最強ケースを作る。

Inputs:

- `AnalysisBrief`

Outputs:

- bear thesis
- strongest negative evidence
- EPS bear argument
- FCF bear argument
- failure modes
- counter to bull case

### JudgeAgent

Bull / Bear の主張と `AnalysisBrief` をもとに最終判定を出す。Markdown は生成しない。

Inputs:

- `FinancialSnapshot`
- `AnalysisBrief`
- `BullCase`
- `BearCase`

Outputs:

- `good | neutral | bad`
- confidence
- positive evidence
- negative evidence
- EPS outlook
- FCF outlook
- non-advice disclaimer

## Orchestrator Responsibilities

- Validate input ticker, quarter, and source configuration.
- Fetch and normalize data.
- Calculate financial metrics in Python.
- Split documents into typed sections.
- Route only relevant sections to each agent.
- Run independent specialist agents in parallel where possible.
- Validate every LLM response with Pydantic.
- Aggregate findings into `AnalysisBrief`.
- Reject outputs with empty `counter_evidence` where counter evidence is required.
- Run Bull and Bear independently from the same validated `AnalysisBrief`.
- Pass only compact evidence and debate outputs to Judge.
- Render final Markdown with a deterministic Python template.
- Log each stage as structured events.

## Phase Roadmap

### Phase 1: Context Isolation MVP

Implement the minimum useful specialist system while preserving context separation.

- `EPSQualityAnalyst`
- `CashFlowFcfAnalyst`
- `ManagementIntentAnalyst`
- `GuidanceAnalyst`
- `BullAgent`
- `BearAgent`
- `JudgeAgent`
- Python `MarkdownRenderer`

Prompt bases for these agents live under `src/prompts/`:

- `src/prompts/financial_agents.md`
- `src/prompts/presentation_agents.md`
- `src/prompts/debate_judge_agents.md`

### Phase 2: Financial Depth

Add agents when data coverage and schemas are stable.

- `ProfitabilityAnalyst`
- `BalanceSheetRiskAnalyst`
- `RiskReviewer`

### Phase 3: Reliability

Improve orchestration and validation.

- `EvidenceAggregator`
- `DebateModerator`
- validation retry
- missing data gate
- source_ref gate
- confidence calibration checks

## Existing Code Alignment

The current implementation has `BullAnalyst`, `BearAnalyst`, `QuantsAnalyst`, and `MacroAnalyst`. For the AGENTS.md target workflow, these should not be treated as the final specialist set.

Recommended migration:

- Replace `QuantsAnalyst` with `EPSQualityAnalyst` and `CashFlowFcfAnalyst`.
- Replace `MacroAnalyst` with `ManagementIntentAnalyst` and `GuidanceAnalyst`, or remove macro-specific claims until peer/macro data is explicitly available.
- Keep `BullAnalyst` and `BearAnalyst` as debate-stage agents, not round-one analysts over raw filing sections.
- Change verdict label from `GOOD | MIXED | BAD` to `good | neutral | bad`.
- Keep report rendering in Python, but update the template to match the AGENTS.md output image.
